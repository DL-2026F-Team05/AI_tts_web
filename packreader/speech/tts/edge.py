"""edge-tts (마이크로소프트 온라인 음성, 인터넷 필요). pip install edge-tts

목소리 예: ko-KR-SunHiNeural(여성), ko-KR-InJoonNeural(남성)
"""

from __future__ import annotations

import importlib.util

from .base import AudioClip, run_coro


class EdgeEngine:
    name = "edge"

    def __init__(self, voice: str = "ko-KR-SunHiNeural"):
        self.voice = voice

    def available(self) -> bool:
        return importlib.util.find_spec("edge_tts") is not None

    def synthesize(self, text: str, speed: float = 1.0) -> AudioClip:
        import edge_tts

        rate = f"{round((speed - 1.0) * 100):+d}%"

        async def _run() -> bytes:
            comm = edge_tts.Communicate(text, self.voice, rate=rate)
            buf = bytearray()
            async for chunk in comm.stream():
                if chunk.get("type") == "audio":
                    buf.extend(chunk["data"])
            return bytes(buf)

        data = run_coro(_run())
        if not data:
            raise RuntimeError("edge-tts 가 음성을 돌려주지 않았다")
        return AudioClip(data, "audio/mpeg", self.name)
