import datetime as dt

import numpy as np
import pytest

from packreader.config import REPO_ROOT, Config
from packreader.pipeline import Pipeline
from packreader.speech.tts import TTSManager
from packreader.speech.tts.base import AudioClip, float_to_wav

TODAY = dt.date(2026, 11, 10)  # 테스트 기준 날짜 (샘플 날짜와 맞춰 둠)
SAMPLES = REPO_ROOT / "data" / "samples"


class FakeEngine:
    """테스트용 TTS 엔진. 실제 모델 없이 짧은 무음 WAV 를 돌려준다."""

    def __init__(self, name="fake", ok=True, avail=True):
        self.name, self.ok, self.avail = name, ok, avail
        self.calls: list[str] = []

    def available(self):
        return self.avail

    def synthesize(self, text, speed=1.0):
        if not self.ok:
            raise RuntimeError("일부러 실패")
        self.calls.append(text)
        return AudioClip(float_to_wav(np.zeros(800), 8000), "audio/wav", self.name, 8000, 0.1)


@pytest.fixture
def cfg(tmp_path):
    return Config(
        ocr_engine="dummy", tts_engines=(), audio_dir=tmp_path / "audio", log_dir=tmp_path / "logs", warmup=False
    )


@pytest.fixture
def pipe(cfg):
    return Pipeline(cfg, tts=TTSManager([], cfg.audio_dir))
