"""TTS 엔진 공통 약속과 도우미."""

from __future__ import annotations

import asyncio
import concurrent.futures
import io
import wave
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass
class AudioClip:
    data: bytes
    mime: str  # audio/wav | audio/mpeg
    engine: str
    sample_rate: int | None = None
    seconds: float | None = None

    @property
    def ext(self) -> str:
        return "mp3" if self.mime == "audio/mpeg" else "wav"


@runtime_checkable
class TTSEngine(Protocol):
    name: str

    def available(self) -> bool:
        """패키지가 설치돼 있는지만 빠르게 본다. 모델은 synthesize/load 때 올린다."""
        ...

    def synthesize(self, text: str, speed: float = 1.0) -> AudioClip: ...


def float_to_wav(samples, sample_rate: int) -> bytes:
    """-1~1 float 배열 → 16bit 모노 WAV 바이트"""
    arr = np.asarray(samples, dtype=np.float32).reshape(-1)
    pcm = (np.clip(arr, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sample_rate))
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def run_coro(coro):
    """동기 코드에서 async 함수를 돌린다. 이미 이벤트 루프가 도는 곳(주피터, 코랩)에서도 된다."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()
