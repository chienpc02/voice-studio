"""Chuyển đổi, ghép và xuất âm thanh."""
import io
import shutil
import subprocess
import numpy as np
import soundfile as sf

FFMPEG = shutil.which("ffmpeg")


def to_wav_file(src_path: str, dst_path: str):
    """Đưa mọi định dạng (wav, mp3, webm từ micro...) về wav mono."""
    if FFMPEG:
        subprocess.run([FFMPEG, "-y", "-i", src_path, "-ac", "1", dst_path],
                       check=True, capture_output=True)
        return
    data, sr = sf.read(src_path, dtype="float32", always_2d=True)
    sf.write(dst_path, data.mean(axis=1), sr)


def duration(path: str) -> float:
    info = sf.info(path)
    return info.frames / info.samplerate


def _stretch_numpy(x: np.ndarray, factor: float, frame: int = 1024) -> np.ndarray:
    """Tăng tốc không đổi cao độ khi không có ffmpeg (overlap-add có dò khớp pha)."""
    hop_out = frame // 2
    hop_in = int(hop_out * factor)
    win = np.hanning(frame).astype(np.float32)
    n_frames = max(1, (len(x) - frame) // hop_in + 1)
    out = np.zeros(n_frames * hop_out + frame, dtype=np.float32)
    norm = np.zeros_like(out)
    search = hop_out // 2
    prev_tail = None
    for k in range(n_frames):
        start = k * hop_in
        if prev_tail is not None and start + search + frame <= len(x):
            lo = max(0, start - search)
            seg = x[lo:start + search + frame]
            c = np.correlate(seg, prev_tail, mode="valid")
            if len(c):
                start = lo + int(np.argmax(c))
        chunk = x[start:start + frame]
        if len(chunk) < frame:
            chunk = np.pad(chunk, (0, frame - len(chunk)))
        pos = k * hop_out
        out[pos:pos + frame] += chunk * win
        norm[pos:pos + frame] += win
        nxt = x[start + hop_out:start + hop_out + frame]
        prev_tail = np.pad(nxt, (0, frame - len(nxt))) if len(nxt) < frame else nxt
    norm[norm < 1e-3] = 1.0
    return (out / norm)[:int(len(x) / factor)]


def speed_up(audio: np.ndarray, sr: int, factor: float) -> np.ndarray:
    """Tăng tốc mà không đổi cao độ. Dùng ffmpeg nếu có, không thì tự xử lý bằng numpy."""
    if factor <= 1.02:
        return audio
    if not FFMPEG:
        return _stretch_numpy(np.asarray(audio, dtype=np.float32), factor)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    # atempo chỉ nhận tối đa 2,0 mỗi lần nên hệ số lớn hơn thì nối nhiều bước
    steps, f = [], factor
    while f > 2.0:
        steps.append("atempo=2.0")
        f /= 2.0
    steps.append(f"atempo={f:.3f}")
    p = subprocess.run(
        [FFMPEG, "-i", "pipe:0", "-filter:a", ",".join(steps), "-f", "wav", "pipe:1"],
        input=buf.getvalue(), capture_output=True)
    if p.returncode != 0:
        return _stretch_numpy(np.asarray(audio, dtype=np.float32), factor)
    out, _ = sf.read(io.BytesIO(p.stdout), dtype="float32")
    return out.reshape(-1)


def encode(audio: np.ndarray, sr: int, fmt: str):
    """Trả về (bytes, mime, đuôi file)."""
    buf = io.BytesIO()
    sf.write(buf, np.clip(audio, -1, 1), sr, format="WAV", subtype="PCM_16")
    wav = buf.getvalue()
    if fmt == "mp3" and FFMPEG:
        p = subprocess.run(
            [FFMPEG, "-i", "pipe:0", "-codec:a", "libmp3lame", "-q:a", "2", "-f", "mp3", "pipe:1"],
            input=wav, capture_output=True)
        if p.returncode == 0:
            return p.stdout, "audio/mpeg", "mp3"
    return wav, "audio/wav", "wav"
