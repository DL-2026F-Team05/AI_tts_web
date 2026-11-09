"""gTTS (구글 번역 음성, 인터넷 필요). pip install gTTS"""

from __future__ import annotations

import importlib.util
import io

from .base import AudioClip


class GTTSEngine:
    name = "gtts"

    def available(self) -> bool:
        return importlib.util.find_spec("gtts") is not None

    def synthesize(self, text: str, speed: float = 1.0) -> AudioClip:
        from gtts import gTTS

        buf = io.BytesIO()
        gTTS(text=text, lang="ko", slow=speed < 0.85).write_to_fp(buf)
        return AudioClip(buf.getvalue(), "audio/mpeg", self.name)
