"""실제 EasyOCR 출력으로 만든 회귀 테스트.

tests/fixtures/easyocr_samples.json 은 2026-11-09 코랩에서 EasyOCR 이 합성 샘플을 읽은 결과 그대로다.
가짜 OCR(정답)로는 안 보이던 문제(혼입 경고 누락, 제품명 누락, 점 글씨 못 읽음)가 여기서 드러났다.
"""

import json

import numpy as np
import pytest

from packreader.config import REPO_ROOT, Config
from packreader.ocr import clean_ocr_text, group_lines
from packreader.pipeline import Pipeline
from packreader.schema import TextBox, UserProfile
from packreader.speech.tts import TTSManager

from conftest import SAMPLES, TODAY

FIXTURE = json.loads((REPO_ROOT / "tests" / "fixtures" / "easyocr_samples.json").read_text(encoding="utf-8"))["samples"]


class FixtureOCR:
    """샘플 이름으로 저장된 EasyOCR 결과를 돌려준다. 점을 이어 붙인(흑백) 이미지면 그 결과를 돌려준다."""

    name = "easyocr-fixture"
    supports_crops = False

    def read(self, rgb, ctx=None):
        sid = (ctx.name or "").split(".")[0] if ctx else ""
        binary = len(np.unique(rgb)) <= 2
        key = f"{sid}_join_dots13" if binary and f"{sid}_join_dots13" in FIXTURE else sid
        if binary and key == sid:
            return []
        return [TextBox.model_validate(b) for b in FIXTURE.get(key, [])]


@pytest.fixture
def real(cfg):
    return Pipeline(cfg, ocr=FixtureOCR(), tts=TTSManager([]))


def run(real, sid, allergens=("우유", "땅콩")):
    return real.analyze(SAMPLES / f"{sid}.jpg", name=f"{sid}.jpg", today=TODAY,
                        profile=UserProfile(allergens=list(allergens)), with_audio=False)


def test_s001_facility_warning_survives_ocr_typo(real):
    r = run(real, "S001")
    a = r.fields.allergens
    assert a.contains == ["밀", "대두", "우유"]
    assert a.may_contain == ["땅콩", "새우"]  # '새우틀' 로 읽혀도 잡혀야 한다
    assert str(r.fields.expiry.date) == "2027-03-15"
    assert r.speech.summary == (
        "주의하세요. 우유가 들어 있어요. 땅콩이 섞였을 수 있어요. "
        "소비기한은 내년 3월 15일까지예요. 제품은 바싹 고소집으로 보여요."
    )


def test_s002_expired_and_nutrition_line_merged(real):
    r = run(real, "S002")
    assert r.risk.level == "danger"
    assert r.fields.allergens.contains == ["우유", "알류", "대두"]
    assert r.fields.product_name.value == "부드러운 우유 푸딩"
    # 박스 4개로 쪼개진 영양정보 줄이 한 줄로 합쳐지고, '7Omg' 는 '70mg' 로 고쳐진다
    assert r.fields.nutrition.value == "영양정보: 총 내용량 120g, 165kcal 나트룹 70mg"


def test_s003_elsewhere_and_hedged_name(real):
    r = run(real, "S003")
    assert r.fields.expiry.status == "elsewhere"
    assert r.fields.allergens.may_contain == ["땅콩", "호두"]
    assert r.speech.items[-1].text == "제품은 듣튼 두유로 보여요."


def test_s004_blurry_asks_retake(real):
    r = run(real, "S004")
    assert [i.key for i in r.speech.items] == ["retake"]


def test_s005_dot_matrix_read_after_joining_dots(real):
    r = run(real, "S005")
    assert any(op.startswith("join_dots") for op in r.preprocess_ops)
    assert "ocr_retry" in r.timing_ms
    assert str(r.fields.expiry.date) == "2026-12-24"
    assert r.speech.items[0].text == "표시된 날짜는 12월 24일이에요."


def test_s006_sell_by(real):
    r = run(real, "S006", allergens=())
    assert r.fields.expiry.kind == "sell_by"
    assert r.fields.product_name.value == "신선 우유"
    assert r.speech.summary.startswith("유통기한은 11월 25일까지예요. 15일 남았어요. 제품은 신선 우유예요.")


@pytest.mark.parametrize(
    "raw, fixed",
    [
        ("6Og", "60g"), ("19OmL", "190mL"), ("9oOmL", "900mL"), ("32Okcal", "320kcal"),
        ("냉장보관(O~109C)", "냉장보관(0~109C)"), ("2O26.1l.2O", "2026.11.20"),
        ("SO2", "SO2"), ("No.3", "No.3"), ("보관방법", "보관방법"),
    ],
)
def test_clean_ocr_text(raw, fixed):
    assert clean_ocr_text(raw) == fixed


def test_group_lines_merges_split_boxes():
    boxes = [TextBox.model_validate(b) for b in FIXTURE["S002"]]
    lines = [" ".join(b.text for b in g) for g in group_lines(boxes)]
    assert "영양정보: 총 내용량 120g, 165kcal 나트룹 7Omg" in lines
    assert lines[0] == "부드러운 우유 푸딩"
