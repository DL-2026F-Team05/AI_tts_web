"""TTS 엔진 고르기와 캐시.  담당: 박세준

설정한 순서대로(기본: melo → edge → gtts) 쓸 수 있는 엔진을 찾고, 실패하면 다음 엔진으로 넘어간다.
전부 안 되면 None 을 돌려주고, 웹 화면이 브라우저 내장 음성(speechSynthesis)으로 읽는다.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

from ..normalize import normalize_for_tts
from .base import AudioClip, TTSEngine, float_to_wav, run_coro
from .edge import EdgeEngine
from .gtts_engine import GTTSEngine
from .melo import MeloEngine
from .mms import MMSEngine

log = logging.getLogger(__name__)

ENGINES = {"melo": MeloEngine, "mms": MMSEngine, "edge": EdgeEngine, "gtts": GTTSEngine}

__all__ = ["AudioClip", "TTSEngine", "TTSManager", "ENGINES", "float_to_wav", "run_coro"]


class TTSManager:
    COOLDOWN_SEC = 300  # 실패한 엔진은 5분 동안 건너뛴다 (인터넷이 끊겼을 때 매번 기다리지 않게)

    def __init__(self, engines: list[TTSEngine], cache_dir: str | Path | None = None, normalize: bool = True):
        self.engines = list(engines)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.normalize = normalize
        self.last_errors: dict[str, str] = {}
        self.last_path: Path | None = None
        self._skip_until: dict[str, float] = {}

    @classmethod
    def from_names(cls, names, cache_dir=None, voice: str = "ko-KR-SunHiNeural") -> "TTSManager":
        engines: list[TTSEngine] = []
        for n in names:
            if n in ("", "none", "browser"):
                continue
            if n not in ENGINES:
                log.warning("알 수 없는 TTS 엔진 %r 은 건너뜀 (가능: %s)", n, ", ".join(ENGINES))
                continue
            engines.append(EdgeEngine(voice) if n == "edge" else ENGINES[n]())
        return cls(engines, cache_dir)

    def configured(self) -> list[str]:
        return [e.name for e in self.engines]

    def available(self) -> list[str]:
        out = []
        for e in self.engines:
            try:
                if e.available():
                    out.append(e.name)
            except Exception:
                pass
        return out

    def warmup(self) -> None:
        for e in self.engines:
            try:
                if e.available() and hasattr(e, "load"):
                    e.load()
                    return  # 첫 번째로 되는 엔진만 미리 올린다
            except Exception as exc:  # pragma: no cover - 모델 다운로드 실패 등
                self.last_errors[e.name] = f"{type(exc).__name__}: {exc}"

    def _cache_path(self, engine: str, speed: float, text: str, ext: str) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha1(f"{engine}|{speed:.2f}|{text}".encode("utf-8")).hexdigest()[:20]
        return self.cache_dir / f"{key}.{ext}"

    def synthesize(self, text: str, speed: float = 1.0) -> AudioClip | None:
        """첫 번째로 성공한 엔진의 음성. 다 실패하면 None (브라우저 음성으로 넘김)."""
        self.last_path = None
        text = text.strip()
        if not text:
            return None
        spoken = normalize_for_tts(text) if self.normalize else text
        for e in self.engines:
            try:
                if not e.available():
                    continue
            except Exception:
                continue
            for ext, mime in (("wav", "audio/wav"), ("mp3", "audio/mpeg")):
                cached = self._cache_path(e.name, speed, spoken, ext)
                if cached and cached.exists():
                    self.last_path = cached
                    return AudioClip(cached.read_bytes(), mime, e.name)
            if time.monotonic() < self._skip_until.get(e.name, 0.0):
                continue
            try:
                clip = e.synthesize(spoken, speed=speed)
            except Exception as exc:
                self.last_errors[e.name] = f"{type(exc).__name__}: {exc}"
                self._skip_until[e.name] = time.monotonic() + self.COOLDOWN_SEC
                log.warning("TTS 엔진 %s 실패, 다음 엔진으로: %s", e.name, exc)
                continue
            self._skip_until.pop(e.name, None)
            path = self._cache_path(e.name, speed, spoken, clip.ext)
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(clip.data)
                self.last_path = path
            return clip
        return None
