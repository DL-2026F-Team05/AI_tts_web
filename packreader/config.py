"""설정. 기본값은 코드에, 바꿀 때는 환경 변수(PACK_*)로 바꾼다.

예) 코랩에서 EasyOCR 로 돌리기:  os.environ["PACK_OCR"] = "easyocr"
"""

from __future__ import annotations

import datetime as dt
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KST = dt.timezone(dt.timedelta(hours=9))


def kst_today() -> dt.date:
    """한국 날짜. 코랩 서버는 UTC 라서 date.today() 를 쓰면 아침 9시 전에는 하루 전 날짜가 나온다."""
    return dt.datetime.now(KST).date()


def _split(value: str) -> tuple[str, ...]:
    return tuple(v.strip().lower() for v in value.split(",") if v.strip())


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # 단계별 엔진
    ocr_engine: str = "dummy"  # dummy | easyocr | paddle
    ocr_langs: tuple[str, ...] = ("ko", "en")
    detector: str = "none"  # none | yolo
    detector_weights: str | None = None
    detector_conf: float = 0.25
    tts_engines: tuple[str, ...] = ("melo", "edge", "gtts")  # 앞에서부터 되는 것을 쓴다. none 이면 브라우저 음성
    tts_voice: str = "ko-KR-SunHiNeural"  # edge-tts 목소리

    # 경로
    samples_dir: Path = REPO_ROOT / "data" / "samples"
    audio_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "packreader_audio")
    log_dir: Path = REPO_ROOT / "logs"
    audio_url_prefix: str = "/api/audio/"

    # 이미지
    max_side: int = 2000  # 긴 변이 이보다 크면 줄인다
    max_upload_mb: int = 15

    # 품질 판정 기준 (배창현이 실제 데이터로 다시 정한다)
    blur_threshold: float = 60.0
    dark_threshold: float = 50.0
    glare_threshold: float = 0.25
    min_side: int = 400

    # 정보 추출·판단 기준 (이서영)
    soon_days: int = 3  # 남은 날이 이 값 이하면 '곧 지남'
    expiry_min_conf: float = 0.6  # 이보다 낮으면 소비기한 판단을 보류한다
    product_min_conf: float = 0.3  # 이보다 낮으면 제품명을 말하지 않는다 (EasyOCR 한국어 신뢰도는 0.3~0.9로 낮게 나옴)
    product_sure_conf: float = 0.6  # 이보다 낮으면 '제품은 ~로 보여요'라고 말한다
    min_box_conf: float = 0.2  # 이보다 낮은 박스만 있으면 '글자를 읽지 못했어요'로 본다
    low_conf_note: float = 0.75  # 이보다 낮은 정보가 있으면 '틀릴 수 있어요' 안내

    warmup: bool = True  # 서버 시작 때 모델을 미리 올린다

    @classmethod
    def from_env(cls, **overrides) -> "Config":
        env = os.environ
        kw: dict = {}
        if env.get("PACK_OCR"):
            kw["ocr_engine"] = env["PACK_OCR"].strip().lower()
        if env.get("PACK_OCR_LANGS"):
            kw["ocr_langs"] = _split(env["PACK_OCR_LANGS"])
        if env.get("PACK_DETECTOR"):
            kw["detector"] = env["PACK_DETECTOR"].strip().lower()
        if env.get("PACK_DETECTOR_WEIGHTS"):
            kw["detector_weights"] = env["PACK_DETECTOR_WEIGHTS"].strip()
        if env.get("PACK_TTS"):
            kw["tts_engines"] = _split(env["PACK_TTS"])
        if env.get("PACK_TTS_VOICE"):
            kw["tts_voice"] = env["PACK_TTS_VOICE"].strip()
        if env.get("PACK_SAMPLES_DIR"):
            kw["samples_dir"] = Path(env["PACK_SAMPLES_DIR"])
        if env.get("PACK_AUDIO_DIR"):
            kw["audio_dir"] = Path(env["PACK_AUDIO_DIR"])
        if env.get("PACK_SOON_DAYS"):
            kw["soon_days"] = int(env["PACK_SOON_DAYS"])
        if env.get("PACK_EXPIRY_MIN_CONF"):
            kw["expiry_min_conf"] = float(env["PACK_EXPIRY_MIN_CONF"])
        if env.get("PACK_WARMUP"):
            kw["warmup"] = _bool(env["PACK_WARMUP"])
        kw.update(overrides)
        return cls(**kw)
