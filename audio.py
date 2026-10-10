"""Chuyển đổi, ghép và xuất âm thanh."""
import io
import shutil
import subprocess
import sys
from pathlib import Path
import numpy as np
import soundfile as sf

def _find_ffmpeg():
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    for name in ("ffmpeg.exe", "ffmpeg"):
        p = base / name
        if p.is_file():
            return str(p)
    return shutil.which("ffmpeg")


FFMPEG = _find_ffmpeg()


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


def speed_up(audio: np.ndarray, sr: int, factor: float) -> np.ndarray:
    """Tăng tốc mà không đổi cao độ (cần ffmpeg). Không có ffmpeg thì giữ nguyên."""
    if not FFMPEG or factor <= 1.02:
        return audio
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    p = subprocess.run(
        [FFMPEG, "-i", "pipe:0", "-filter:a", f"atempo={factor:.3f}", "-f", "wav", "pipe:1"],
        input=buf.getvalue(), capture_output=True)
    if p.returncode != 0:
        return audio
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
