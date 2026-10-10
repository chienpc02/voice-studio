# Voice Studio

Web app chạy trên máy: tạo giọng từ mẫu thu ngắn, đọc văn bản hoặc phụ đề SRT/VTT, xuất MP3/WAV.

## Chạy
- Cần Python 3.10 trở lên. Nên cài ffmpeg (để xuất MP3, dùng ghi âm từ micro, tăng tốc câu dài).
- Mac/Linux: `./run.sh`   Windows: bấm đúp `run.bat`
- Mở http://127.0.0.1:8000. Lần đầu chạy sẽ tải mô hình VieNeu-TTS nên cần chờ vài phút.

## Dùng
1. Thêm giọng: đặt tên, chọn file hoặc thu âm 10–30 giây, tick xác nhận quyền sử dụng, bấm Lưu giọng.
2. Tab "Đọc văn bản": nhập nội dung, chọn giọng, bấm Tạo âm thanh.
3. Tab "Đọc phụ đề SRT": chọn file, chọn ghép đúng mốc thời gian hoặc nối liền.

Giọng được lưu trong thư mục `voices/`. Thử giao diện không cần mô hình: `VOICE_ENGINE=dummy ./run.sh` (chỉ ra tiếng bíp).

## Token Hugging Face (tải mô hình nhanh hơn)
Sao chép `.env.example` thành `.env`, điền `HF_TOKEN=...` của bạn rồi chạy lại. File `.env` không bị đưa lên Git. Đừng dán token vào code hay gửi cho người khác.

## Đổi mô hình
Mở `engine.py`, thêm một lớp có `sample_rate` và `synthesize(text, ref_wav_path)`, rồi trả về trong `load_engine()`.

## Lưu ý
Chỉ tạo bản sao giọng của chính bạn hoặc của người đã đồng ý.
