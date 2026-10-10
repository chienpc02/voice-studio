#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
echo "Mở http://127.0.0.1:8000 (lần đầu sẽ tải mô hình, chờ vài phút)"
uvicorn app:app --host 127.0.0.1 --port 8000
