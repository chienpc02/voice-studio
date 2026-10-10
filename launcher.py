"""Điểm vào khi đóng gói thành .exe: chạy server và mở trình duyệt."""
import multiprocessing
import threading
import webbrowser

import uvicorn

from app import app

URL = "http://127.0.0.1:8000"


def main():
    multiprocessing.freeze_support()
    threading.Timer(2.5, lambda: webbrowser.open(URL)).start()
    print(f"Voice Studio đang chạy tại {URL}. Đóng cửa sổ này để tắt.")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
