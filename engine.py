"""Động cơ tạo giọng. Mặc định dùng VieNeu-TTS (tiếng Việt, clone từ mẫu ngắn).

Muốn đổi sang mô hình khác, viết thêm một lớp có hai phần:
  - thuộc tính sample_rate
  - hàm synthesize(text, ref_wav_path) -> numpy float32 mono
rồi trả về nó trong load_engine().
"""
import os
import numpy as np


class VieneuEngine:
    name = "VieNeu-TTS"

    def __init__(self):
        from vieneu import Vieneu  # import muộn để tải mô hình lần đầu có thông báo rõ
        self.model = Vieneu()
        self.sample_rate = int(getattr(self.model, "sample_rate", 48000))

    def synthesize(self, text: str, ref_wav_path: str) -> np.ndarray:
        audio = self.model.infer(text, ref_audio=ref_wav_path, denoise=True)
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        return audio


class DummyEngine:
    """Chỉ để thử giao diện và luồng xử lý: tạo tiếng bíp, không phải giọng thật."""
    name = "Thử nghiệm (tiếng bíp)"
    sample_rate = 24000

    def synthesize(self, text: str, ref_wav_path: str) -> np.ndarray:
        dur = max(0.4, len(text) / 14)
        t = np.linspace(0, dur, int(dur * self.sample_rate), endpoint=False)
        env = np.minimum(1, np.minimum(t, dur - t) * 20)
        return (0.25 * np.sin(2 * np.pi * 440 * t) * env).astype(np.float32)


def load_engine():
    if os.environ.get("VOICE_ENGINE", "").lower() == "dummy":
        return DummyEngine()
    return VieneuEngine()
