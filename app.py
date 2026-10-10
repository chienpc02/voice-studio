"""Voice Studio: web app chạy trên máy, clone giọng từ mẫu ngắn và đọc văn bản / phụ đề."""
import json
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import env  # noqa: F401  (nạp .env, gồm HF_TOKEN, trước khi tải mô hình)
import audio as au
import srt as srtlib
from engine import load_engine

ROOT = Path(__file__).parent
VOICES = ROOT / "voices"
VOICES.mkdir(exist_ok=True)

app = FastAPI(title="Voice Studio")
_engine = None
_lock = threading.Lock()


def engine():
    global _engine
    with _lock:
        if _engine is None:
            _engine = load_engine()
        return _engine


def _meta(vid: str):
    p = VOICES / f"{vid}.json"
    if not re.fullmatch(r"[0-9a-f]{12}", vid) or not p.exists():
        raise HTTPException(404, "Không tìm thấy giọng này.")
    return json.loads(p.read_text("utf-8"))


def _synth(text: str, vid: str):
    _meta(vid)
    eng = engine()
    with _lock:
        a = eng.synthesize(text, str(VOICES / f"{vid}.wav"))
    return a, eng.sample_rate


@app.get("/api/status")
def status():
    return {"engine": os.environ.get("VOICE_ENGINE", "vieneu"), "ffmpeg": bool(au.FFMPEG),
            "hf_token": bool(os.environ.get("HF_TOKEN"))}


@app.get("/api/voices")
def list_voices():
    out = [json.loads(p.read_text("utf-8")) for p in VOICES.glob("*.json")]
    return sorted(out, key=lambda v: v["created"], reverse=True)


@app.post("/api/voices")
def create_voice(name: str = Form(...), consent: bool = Form(False), file: UploadFile = File(...)):
    if not consent:
        raise HTTPException(400, "Cần xác nhận bạn có quyền hoặc sự đồng ý của chủ giọng.")
    name = name.strip()[:60]
    if not name:
        raise HTTPException(400, "Hãy đặt tên cho giọng.")
    vid = uuid.uuid4().hex[:12]
    suffix = Path(file.filename or "").suffix or ".bin"
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / f"in{suffix}"
        src.write_bytes(file.file.read())
        try:
            au.to_wav_file(str(src), str(VOICES / f"{vid}.wav"))
        except Exception:
            raise HTTPException(400, "Không đọc được file âm thanh. Hãy thử WAV, hoặc cài ffmpeg để dùng MP3/ghi âm.")
    secs = au.duration(str(VOICES / f"{vid}.wav"))
    if secs < 3:
        (VOICES / f"{vid}.wav").unlink(missing_ok=True)
        raise HTTPException(400, "Mẫu quá ngắn. Hãy dùng đoạn thu từ 5 đến 30 giây.")
    meta = {"id": vid, "name": name, "seconds": round(secs, 1), "created": time.time()}
    (VOICES / f"{vid}.json").write_text(json.dumps(meta, ensure_ascii=False), "utf-8")
    return meta


@app.delete("/api/voices/{vid}")
def delete_voice(vid: str):
    _meta(vid)
    (VOICES / f"{vid}.wav").unlink(missing_ok=True)
    (VOICES / f"{vid}.json").unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/voices/{vid}/sample")
def sample(vid: str):
    _meta(vid)
    return FileResponse(VOICES / f"{vid}.wav", media_type="audio/wav")


def _reply(a, sr, fmt, name):
    data, mime, ext = au.encode(a, sr, fmt)
    return Response(data, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{name}.{ext}"'})


@app.post("/api/speak")
def speak(text: str = Form(...), voice_id: str = Form(...), fmt: str = Form("wav")):
    text = text.strip()
    if not text:
        raise HTTPException(400, "Chưa có nội dung để đọc.")
    a, sr = _synth(text, voice_id)
    return _reply(a, sr, fmt, "giong-doc")


@app.post("/api/parse")
def parse(text: str = Form(...)):
    cues = srtlib.parse(text)
    return {"count": len(cues), "cues": cues[:200]}


@app.post("/api/srt")
def srt_to_audio(text: str = Form(...), voice_id: str = Form(...), fmt: str = Form("wav"),
                 mode: str = Form("timed"), fit: bool = Form(True)):
    cues = srtlib.parse(text)
    if not cues:
        raise HTTPException(400, "Không đọc được câu thoại nào trong phụ đề.")
    _meta(voice_id)
    clips, sr = [], None
    for c in cues:
        a, sr = _synth(c["text"], voice_id)
        slot = (c["end"] - c["start"]) / 1000
        if mode == "timed" and fit and slot > 0.3 and len(a) / sr > slot:
            a = au.speed_up(a, sr, min(1.6, (len(a) / sr) / slot))
        clips.append(a)
    gap = int(0.3 * sr)
    placed, cursor = [], 0
    for c, a in zip(cues, clips):
        pos = int(c["start"] / 1000 * sr) if mode == "timed" else cursor
        pos = max(pos, cursor)           # không để hai câu chồng lên nhau
        placed.append((pos, a))
        cursor = pos + len(a) + (0 if mode == "timed" else gap)
    out = np.zeros(cursor, dtype=np.float32)
    for pos, a in placed:
        out[pos:pos + len(a)] = a
    return _reply(out, sr, fmt, "phu-de")


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
