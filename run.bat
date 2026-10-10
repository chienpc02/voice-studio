@echo off
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt
echo Mo http://127.0.0.1:8000 (lan dau se tai mo hinh, cho vai phut)
uvicorn app:app --host 127.0.0.1 --port 8000
