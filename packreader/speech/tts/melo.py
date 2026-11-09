"""MeloTTS 한국어 (로컬 모델, MIT 라이선스, CPU 실시간 추론 지원).

설치가 까다로워서 notebooks/01_tts_compare.ipynb 의 설치 셀을 쓴다.
첫 실행 때 Hugging Face 에서 모델(myshell-ai/MeloTTS-Korean)을 내려받는다.
"""

from __future__ import annotations

import importlib.util

from .base import AudioClip, float_to_wav


class MeloEngine:
    name = "melo"

    def __init__(self, device: str | None = None, speaker: str = "KR"):
        self.device = device
        self.speaker = speaker
        self._model = None
        self._spk = None

    def available(self) -> bool:
        return importlib.util.find_spec("melo") is not None

    def load(self):
        if self._model is None:
            from melo.api import TTS

            device = self.device
            if device is None:
                try:
                    import torch

                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except Exception:
                    device = "cpu"
            self._model = TTS(language="KR", device=device)
            self._spk = self._model.hps.data.spk2id[self.speaker]
        return self._model

    warmup = load

    def synthesize(self, text: str, speed: float = 1.0) -> AudioClip:
        model = self.load()
        audio = model.tts_to_file(text, self._spk, None, speed=speed)  # output_path=None 이면 배열을 돌려준다
        sr = int(model.hps.data.sampling_rate)
        return AudioClip(float_to_wav(audio, sr), "audio/wav", self.name, sr, round(len(audio) / sr, 3))
