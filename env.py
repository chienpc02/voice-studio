"""Nạp biến môi trường từ file .env (nếu có) trước khi dùng Hugging Face.

File .env nằm cạnh app.py, KHÔNG được đưa lên Git. Ví dụ nội dung:
    HF_TOKEN=hf_xxxxxxxxxxxxxxxx
Biến đã đặt sẵn trong hệ thống có ưu tiên hơn file .env.
"""
import os
from pathlib import Path


def load_env(path: Path | None = None) -> None:
    p = path or Path(__file__).parent / ".env"
    if not p.is_file():
        return
    for line in p.read_text("utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


load_env()
