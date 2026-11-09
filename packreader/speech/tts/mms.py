"""Meta MMS-TTS 한국어 (facebook/mms-tts-kor, VITS, CC-BY-NC 4.0).

transformers 만 있으면 돼서 설치가 쉽다. 비교 실험용.
이 모델은 로마자로 바꾼 글자로 학습돼서 uroman 패키지가 필요할 수 있다 (pip install uroman).
"""

from __future__ import annotations

import importlib.util

from .base import AudioClip, float_to_wav


class MMSEngine:
    name = "mms"
    model_id = "facebook/mms-tts-kor"

    def __init__(self, device: str | None = None):
        self.device = device
        self._model = None
        self._tok = None
        self._uroman = None

    def available(self) -> bool:
        return importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None

    def load(self):
        if self._model is None:
            import torch
            from transformers import AutoTokenizer, VitsModel

            self.device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
            self._tok = AutoTokenizer.from_pretrained(self.model_id)
            self._model = VitsModel.from_pretrained(self.model_id).to(self.device).eval()
            if getattr(self._tok, "is_uroman", False):
                import uroman

                self._uroman = uroman.Uroman()
        return self._model

    warmup = load

    def synthesize(self, text: str, speed: float = 1.0) -> AudioClip:
        import torch

        model = self.load()
        if self._uroman is not None:
            text = self._uroman.romanize_string(text)
        inputs = self._tok(text, return_tensors="pt").to(self.device)
        model.speaking_rate = speed
        with torch.no_grad():
            wav = model(**inputs).waveform[0].cpu().numpy()
        sr = int(model.config.sampling_rate)
        return AudioClip(float_to_wav(wav, sr), "audio/wav", self.name, sr, round(len(wav) / sr, 3))
