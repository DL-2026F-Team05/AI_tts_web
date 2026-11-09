"""모듈끼리 주고받는 결과 형식.

모든 단계(전처리 → 영역 검출·OCR → 정보 추출 → 안내 문장 → TTS)가 AnalysisResult 하나를 채워 나간다.
필드를 바꾸면 docs/interface.md 를 같이 고치고 `python -m tools.export_schema` 로 docs/schema.json 을 다시 만든다.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"

RegionName = Literal["product_name", "expiry", "allergen", "ingredients", "nutrition", "caution", "other"]
ExpiryKind = Literal["use_by", "sell_by", "best_before", "unknown"]
ExpiryStatus = Literal["ok", "soon", "expired", "elsewhere", "unknown"]
RiskLevel = Literal["danger", "caution", "ok", "unknown"]
QualityIssue = Literal["blur", "dark", "glare", "small"]

REGION_NAMES: tuple[str, ...] = (
    "product_name", "expiry", "allergen", "ingredients", "nutrition", "caution", "other",
)

# 화면과 안내 문장에 쓰는 한국어 이름
REGION_LABEL = {
    "product_name": "제품명",
    "expiry": "소비기한",
    "allergen": "알레르기",
    "ingredients": "원재료",
    "nutrition": "영양정보",
    "caution": "주의사항",
    "other": "기타",
}
KIND_LABEL = {"use_by": "소비기한", "sell_by": "유통기한", "best_before": "품질유지기한", "unknown": "날짜"}
STATUS_LABEL = {"ok": "남음", "soon": "곧 지남", "expired": "지남", "elsewhere": "다른 면에 표기", "unknown": "판단 보류"}
RISK_LABEL = {"danger": "위험", "caution": "주의", "ok": "특이사항 없음", "unknown": "확인 필요"}


class Quality(BaseModel):
    """사진 품질. 담당: 배창현 (preprocess.quality)"""

    sharpness: float | None = Field(None, description="라플라시안 분산. 클수록 선명")
    brightness: float | None = Field(None, description="평균 밝기 0~255")
    glare_ratio: float | None = Field(None, description="하얗게 날아간 픽셀 비율 0~1")
    issues: list[QualityIssue] = Field(default_factory=list)
    retake: bool = Field(False, description="다시 찍기를 권할지")


class Region(BaseModel):
    """영역 검출 결과. 담당: 이도현 (ocr.detector)"""

    name: RegionName
    conf: float = Field(ge=0, le=1)
    bbox: tuple[float, float, float, float] = Field(description="x1, y1, x2, y2 (처리 이미지 픽셀)")


class TextBox(BaseModel):
    """OCR 한 줄. 담당: 이도현 (ocr). 정답 라벨(labels/boxes/*.json)도 같은 형식을 쓴다."""

    text: str
    conf: float = Field(1.0, ge=0, le=1)
    poly: list[tuple[float, float]] | None = Field(None, description="네 꼭짓점 [[x, y], ...] (처리 이미지 픽셀)")
    region: RegionName | None = None


class TextField(BaseModel):
    value: str | None = None
    conf: float = Field(0.0, ge=0, le=1)


class Expiry(BaseModel):
    """소비기한·유통기한. 담당: 이서영 (extract)"""

    raw: str | None = Field(None, description="근거가 된 원문")
    date: dt.date | None = None
    kind: ExpiryKind = "unknown"
    status: ExpiryStatus = "unknown"
    days_left: int | None = None
    conf: float = Field(0.0, ge=0, le=1)


class Allergens(BaseModel):
    """알레르기 정보. 성분 이름은 extract.allergens.ALLERGENS 의 표준 이름만 쓴다. 담당: 이서영"""

    contains: list[str] = Field(default_factory=list, description="함유")
    may_contain: list[str] = Field(default_factory=list, description="같은 제조시설 등 혼입 가능")
    user_hits: list[str] = Field(default_factory=list, description="사용자 등록 성분 중 contains 에 있는 것")
    user_may_hits: list[str] = Field(default_factory=list, description="사용자 등록 성분 중 may_contain 에 있는 것")
    raw: list[str] = Field(default_factory=list, description="근거 문장")
    conf: float = Field(0.0, ge=0, le=1)


class Fields(BaseModel):
    product_name: TextField = Field(default_factory=TextField)
    expiry: Expiry = Field(default_factory=Expiry)
    allergens: Allergens = Field(default_factory=Allergens)
    ingredients: TextField = Field(default_factory=TextField)
    nutrition: TextField = Field(default_factory=TextField)
    caution: TextField = Field(default_factory=TextField)


class Risk(BaseModel):
    """위험 판단. 담당: 이서영 (extract.risk)"""

    level: RiskLevel = "unknown"
    reasons: list[str] = Field(
        default_factory=list,
        description="allergen_contains, expired, allergen_may, expiry_soon, expiry_unknown, expiry_elsewhere",
    )


class SpeechItem(BaseModel):
    key: str
    text: str


class Speech(BaseModel):
    """안내 문장. 담당: 박세준 (speech.compose)"""

    summary: str = Field(description="바로 읽어 주는 문장")
    detail: str = Field("", description="'더 듣기'에서 읽는 문장")
    items: list[SpeechItem] = Field(default_factory=list, description="summary 를 이루는 문장, 읽는 순서대로")


class Audio(BaseModel):
    engine: str
    mime: str
    url: str | None = None
    seconds: float | None = None


class ImageInfo(BaseModel):
    name: str | None = None
    sha1: str | None = None
    width: int = Field(description="처리에 쓴 크기. 박스 좌표는 이 크기 기준")
    height: int
    orig_width: int
    orig_height: int


class StageError(BaseModel):
    stage: str
    message: str


class UserProfile(BaseModel):
    allergens: list[str] = Field(default_factory=list, description="사용자가 등록한 알레르기 성분")


class AnalysisResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    request_id: str
    created_at: dt.datetime
    today: dt.date = Field(description="소비기한 계산 기준 날짜 (한국 시간)")
    image: ImageInfo | None = None
    quality: Quality = Field(default_factory=Quality)
    preprocess_ops: list[str] = Field(default_factory=list)
    regions: list[Region] = Field(default_factory=list)
    boxes: list[TextBox] = Field(default_factory=list)
    fields: Fields = Field(default_factory=Fields)
    risk: Risk = Field(default_factory=Risk)
    speech: Speech | None = None
    audio: Audio | None = None
    engines: dict[str, str] = Field(default_factory=dict)
    timing_ms: dict[str, float] = Field(default_factory=dict)
    errors: list[StageError] = Field(default_factory=list)
