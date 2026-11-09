import asyncio
import wave
import io

import numpy as np

from packreader.speech.tts import TTSManager
from packreader.speech.tts.base import float_to_wav, run_coro

from conftest import FakeEngine


def test_first_available_engine_is_used(tmp_path):
    missing = FakeEngine("missing", avail=False)
    broken = FakeEngine("broken", ok=False)
    good = FakeEngine("good")
    m = TTSManager([missing, broken, good], tmp_path)
    clip = m.synthesize("소비기한은 3월 15일까지예요.")
    assert clip.engine == "good"
    assert "broken" in m.last_errors
    assert m.last_path is not None and m.last_path.exists()
    # 숫자는 한글 읽기로 바꿔서 엔진에 넣는다
    assert good.calls == ["소비기한은 삼월 십오일까지예요."]


def test_failed_engine_is_skipped_for_a_while(tmp_path):
    broken = FakeEngine("broken", ok=False)
    good = FakeEngine("good")
    m = TTSManager([broken, good], tmp_path)
    m.synthesize("첫 번째")
    broken.ok = True  # 다시 살아나도 쿨다운 동안은 건너뛴다
    assert m.synthesize("두 번째").engine == "good"
    assert broken.calls == []


def test_cache_hit_skips_synthesis(tmp_path):
    good = FakeEngine("good")
    m = TTSManager([good], tmp_path)
    m.synthesize("안녕하세요")
    m.synthesize("안녕하세요")
    assert len(good.calls) == 1


def test_no_engine_returns_none(tmp_path):
    m = TTSManager([], tmp_path)
    assert m.synthesize("안녕하세요") is None
    assert TTSManager.from_names(["none"]).engines == []


def test_unknown_engine_name_is_skipped():
    m = TTSManager.from_names(["melo", "nope", "gtts"])
    assert m.configured() == ["melo", "gtts"]


def test_float_to_wav_header():
    data = float_to_wav(np.linspace(-1, 1, 1600), 16000)
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 1600


def test_run_coro_inside_running_loop():
    async def inner():
        await asyncio.sleep(0)
        return 42

    async def outer():
        return run_coro(inner())  # 주피터처럼 루프가 이미 도는 상황

    assert run_coro(inner()) == 42
    assert asyncio.run(outer()) == 42
