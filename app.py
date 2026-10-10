"""Voice Studio: web app chạy trên máy, clone giọng từ mẫu ngắn và đọc văn bản / phụ đề."""
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import env  # noqa: F401  (nạp .env, gồm HF_TOKEN, trước khi tải mô hình)
import audio as au
import srt as srtlib
from engine import load_engine

FROZEN = getattr(sys, "frozen", False)
ROOT = Path(sys.executable).parent if FROZEN else Path(__file__).parent   # nơi chứa voices/, .env, ffmpeg.exe
BUNDLE = Path(getattr(sys, "_MEIPASS", ROOT))                              # nơi chứa static/ khi đã đóng gói
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


_CACHE: "OrderedDict" = OrderedDict()   # (voice_id, text) -> (audio, sample_rate)
_CACHE_MAX = 400
_cache_lock = threading.Lock()


def _synth(text: str, vid: str):
    """Đọc một câu. Kết quả được nhớ lại: nghe thử câu nào thì khi tạo toàn bộ dùng lại câu đó."""
    _meta(vid)
    key = (vid, text)
    with _cache_lock:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    eng = engine()
    with _lock:
        a = eng.synthesize(text, str(VOICES / f"{vid}.wav"))
    with _cache_lock:
        _CACHE[key] = (a, eng.sample_rate)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
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
def parse(text: str = Form(...), merge: bool = Form(True)):
    raw = srtlib.parse(text)
    cues = srtlib.merge(raw) if merge else raw
    return {"raw_count": len(raw), "count": len(cues), "cues": cues,
            "duration_ms": max((c["end"] for c in cues), default=0)}


class Cancelled(Exception):
    pass


def _build_srt(cues, voice_id, mode, fit, on_progress=None, is_cancelled=None):
    """Đọc từng câu rồi ghép thành một bản âm thanh. Trả về (audio, sample_rate)."""
    clips, sr = [], None
    for i, c in enumerate(cues):
        if is_cancelled and is_cancelled():
            raise Cancelled()
        a, sr = _synth(c["text"], c.get("voice_id") or voice_id)
        slot = (c["end"] - c["start"]) / 1000
        if mode == "timed" and fit and slot > 0.3 and len(a) / sr > slot:
            a = au.speed_up(a, sr, min(1.6, (len(a) / sr) / slot))
        clips.append(a)
        if on_progress:
            on_progress(i + 1, len(cues))
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
    return out, sr


@app.post("/api/srt")
def srt_to_audio(text: str = Form(...), voice_id: str = Form(...), fmt: str = Form("wav"),
                 mode: str = Form("timed"), fit: bool = Form(True)):
    cues = srtlib.parse(text)
    if not cues:
        raise HTTPException(400, "Không đọc được câu thoại nào trong phụ đề.")
    _meta(voice_id)
    out, sr = _build_srt(cues, voice_id, mode, fit)
    return _reply(out, sr, fmt, "phu-de")


# ---- Công việc chạy nền: để giao diện hiện tiến độ, thời gian còn lại và có thể hủy ----
JOBS: dict = {}


def _prune_jobs():
    now = time.time()
    for k in [k for k, j in JOBS.items() if now - j["created"] > 3600]:
        JOBS.pop(k, None)


def _run_job(jid, cues, voice_id, fmt, mode, fit):
    job = JOBS[jid]

    def progress(done, total):
        job["done"] = done
        job["marks"].append(time.time())

    try:
        out, sr = _build_srt(cues, voice_id, mode, fit, progress, lambda: job["cancel"])
        job["result"] = au.encode(out, sr, fmt)
        job["state"] = "done"
    except Cancelled:
        job["state"] = "cancelled"
    except Exception as e:  # báo lỗi cho giao diện thay vì làm sập luồng
        job["state"] = "error"
        job["error"] = str(e) or e.__class__.__name__


@app.post("/api/srt/start")
def srt_start(voice_id: str = Form(...), fmt: str = Form("wav"), mode: str = Form("timed"),
              fit: bool = Form(True), text: str = Form(""), cues: str = Form("")):
    if cues:      # danh sách câu đã gộp/chỉnh sửa từ giao diện, mỗi câu có thể có giọng riêng
        try:
            items = json.loads(cues)
            cues = [{"start": int(c["start"]), "end": int(c["end"]), "text": str(c["text"]).strip(),
                     "voice_id": str(c.get("voice_id") or "")} for c in items][:5000]
        except (ValueError, KeyError, TypeError):
            raise HTTPException(400, "Danh sách câu không hợp lệ.")
        cues = [c for c in cues if c["text"]]
        for c in cues:
            if c["voice_id"]:
                _meta(c["voice_id"])
    else:
        cues = srtlib.parse(text)
    if not cues:
        raise HTTPException(400, "Không đọc được câu thoại nào trong phụ đề.")
    _meta(voice_id)
    _prune_jobs()
    jid = uuid.uuid4().hex[:12]
    JOBS[jid] = {"state": "running", "done": 0, "total": len(cues), "created": time.time(),
                 "marks": [], "cancel": False, "result": None, "error": ""}
    threading.Thread(target=_run_job, args=(jid, cues, voice_id, fmt, mode, fit), daemon=True).start()
    return {"job_id": jid, "total": len(cues)}


def _job(jid):
    if jid not in JOBS:
        raise HTTPException(404, "Không tìm thấy công việc này.")
    return JOBS[jid]


@app.get("/api/jobs/{jid}")
def job_status(jid: str):
    j = _job(jid)
    return {"state": j["state"], "done": j["done"], "total": j["total"],
            "elapsed": round(time.time() - j["created"], 1), "error": j["error"],
            "marks": [round(m - j["created"], 2) for m in j["marks"][-30:]]}


@app.get("/api/jobs/{jid}/result")
def job_result(jid: str):
    j = _job(jid)
    if j["state"] != "done":
        raise HTTPException(409, "Âm thanh chưa tạo xong.")
    data, mime, ext = j["result"]
    JOBS.pop(jid, None)
    return Response(data, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="phu-de.{ext}"'})


@app.delete("/api/jobs/{jid}")
def job_cancel(jid: str):
    if jid in JOBS:
        JOBS[jid]["cancel"] = True       # luồng sẽ dừng sau câu đang đọc
    return {"ok": True}


app.mount("/", StaticFiles(directory=BUNDLE / "static", html=True), name="static")
