"""OCR 줄에서 제품명, 소비기한, 알레르기, 원재료, 영양정보, 주의사항 뽑기.  담당: 이서영

기준선 규칙
- 제품명: '제품명:' 칸 → 제품명 영역 박스 → 가장 큰 글씨(박스 높이 × 신뢰도)
- 알레르기 함유: '함유' 또는 '알레르기/유발물질'이 있는 줄
- 혼입 가능: "이 제품은 ○○, ○○를 사용한 제품과 같은 제조시설..." 표준 문구 (줄이 나뉘어도 처리)
- 원재료: '원재료명:' 줄 (쉼표로 끝나면 다음 줄까지 이어 붙임)

날짜와 '제품명:' 칸은 박스 단위로, 나머지는 같은 줄 박스를 이어 붙인 줄 단위로 본다.
실제 EasyOCR 결과(tests/fixtures/easyocr_samples.json)로 확인한 OCR 실수도 일부 견딘다.
"""

from __future__ import annotations

import datetime as dt
import re

from ..config import Config, kst_today
from ..ocr.base import box_height, group_lines
from ..schema import Allergens, Fields, TextBox, TextField, UserProfile
from .allergens import find_allergens
from .dates import find_dates, find_elsewhere, pick_expiry
from .risk import build_expiry, match_profile

_PRODUCT_KEY = re.compile(r"제품\s*명\s*[:：]\s*(.+)")
_NAME_STOP = re.compile(
    r"소비|유통|기한|원재료|알레르기|유발|함유|보관|영양|제조|kcal|나트륨|식품\s*유형|내용량|주의|섭취|반품|교환|고객|상담|www|http|\d{4}"
)
_HANGUL2 = re.compile(r"[가-힣].*[가-힣]")
# 조사(을/를)는 OCR 이 자주 틀리게 읽어서('새우틀', '호두름') 목록 쪽에 붙은 채로 두고 canonical() 이 떼어 낸다
_FACILITY = re.compile(
    r"이\s*제품은\s*(?P<items>[^.]{1,60}?)\s*사용(?:한|하는)\s*제품과\s*같은\s*(?:제조\s*)?시설", re.S
)
_FACILITY_WORDS = re.compile(r"제조\s*시설|같은\s*시설|혼입")
_CONTAINS_WORDS = re.compile(r"알레\S?기|알러지|유발\s*물질")  # OCR 오타 '알레로기' 포함
_INGREDIENTS = re.compile(r"원재료\s*명?\s*(?:및\s*함량)?\s*[:：]\s*(.+)")
_NUTRITION = re.compile(r"kcal|나트륨|탄수화물|단백질|지방|영양\s*정보|영양\s*성분")
_CAUTION = re.compile(r"보관|주의")


def _box_lines(boxes: list[TextBox]) -> list[tuple[str, float, str | None]]:
    """박스 하나 = 한 줄 (날짜, '제품명:' 칸처럼 박스 단위가 정확한 것에 쓴다)."""
    return [(b.text.strip(), b.conf, b.region) for b in boxes if b.text.strip()]


def _visual_lines(boxes: list[TextBox]) -> list[tuple[str, float, str | None]]:
    """같은 줄에 있는 박스를 이어 붙인 한 줄 (문장이 박스 여러 개로 쪼개진 경우를 위해).

    신뢰도는 가장 낮은 박스 값을 쓴다 ('틀릴 수 있어요' 안내를 보수적으로 하려고).
    """
    out = []
    for group in group_lines([b for b in boxes if b.text.strip()]):
        regions = [b.region for b in group if b.region]
        out.append((
            " ".join(b.text.strip() for b in group),
            min(b.conf for b in group),
            max(set(regions), key=regions.count) if regions else None,
        ))
    return out


def pick_product_name(boxes: list[TextBox], lines) -> TextField:
    for text, conf, _ in lines:
        m = _PRODUCT_KEY.search(text)
        if m:
            value = re.split(r"\s*[|/]\s*|\s{2,}|식품\s*유형", m.group(1))[0].strip()
            if value:
                return TextField(value=value, conf=conf)
    tagged = [b for b in boxes if b.region == "product_name" and b.text.strip()]
    if tagged:
        best = max(tagged, key=lambda b: b.conf)
        return TextField(value=best.text.strip(), conf=best.conf)
    cands = [
        b for b in boxes
        if _HANGUL2.search(b.text) and not _NAME_STOP.search(b.text) and len(b.text.strip()) <= 30
    ]
    if not cands:
        return TextField()
    best = max(cands, key=lambda b: box_height(b) * b.conf)
    return TextField(value=best.text.strip(), conf=best.conf)


def parse_allergens(lines) -> Allergens:
    contains: list[str] = []
    may: list[str] = []
    raw: list[str] = []
    confs: list[float] = []

    # 1) 혼입 가능 표준 문구 (줄바꿈이 있어도 되게 이어 붙여서 찾는다)
    joined = "\n".join(t for t, _, _ in lines)
    for m in _FACILITY.finditer(joined):
        items = find_allergens(m.group("items"))
        may += [a for a in items if a not in may]
        raw.append(" ".join(m.group(0).split()))
    if may:
        confs += [c for t, c, _ in lines if _FACILITY_WORDS.search(t)] or [1.0]

    # 2) 함유 표시 줄
    for text, conf, _ in lines:
        if _FACILITY_WORDS.search(text):
            continue
        segment = None
        if "함유" in text:
            segment = text[: text.rfind("함유")]
        elif _CONTAINS_WORDS.search(text) and (":" in text or "：" in text):
            segment = text
        if segment is None:
            continue
        segment = re.split(r"[:：]", segment)[-1]
        found = find_allergens(segment)
        if found:
            contains += [a for a in found if a not in contains]
            raw.append(text)
            confs.append(conf)

    may = [a for a in may if a not in contains]  # 함유가 우선
    return Allergens(contains=contains, may_contain=may, raw=raw, conf=min(confs) if confs else 0.0)


def _first_match(lines, rx, continue_on_comma: bool = False) -> TextField:
    for i, (text, conf, _) in enumerate(lines):
        m = rx.search(text)
        if not m:
            continue
        value, confs = m.group(1).strip(), [conf]
        # 줄이 쉼표로 끝나면 다음 줄로 이어진 것으로 본다 (원재료 목록이 두 줄에 걸친 경우)
        j = i + 1
        while continue_on_comma and value.endswith(",") and j < len(lines):
            value += " " + lines[j][0]
            confs.append(lines[j][1])
            j += 1
        return TextField(value=value, conf=min(confs))
    return TextField()


def _join_matching(lines, rx, exclude=None) -> TextField:
    picked = [(t, c) for t, c, _ in lines if rx.search(t) and not (exclude and exclude.search(t))]
    if not picked:
        return TextField()
    return TextField(value=" ".join(t for t, _ in picked), conf=min(c for _, c in picked))


def extract_fields(
    boxes: list[TextBox],
    profile: UserProfile | None = None,
    today: dt.date | None = None,
    cfg: Config | None = None,
) -> Fields:
    cfg = cfg or Config()
    today = today or kst_today()
    box_lines = _box_lines(boxes)
    lines = _visual_lines(boxes)
    pairs = [(t, c) for t, c, _ in box_lines]

    expiry = build_expiry(pick_expiry(find_dates(pairs)), find_elsewhere(pairs), today, cfg)
    allergens = match_profile(parse_allergens(lines), profile)
    return Fields(
        product_name=pick_product_name(boxes, box_lines),
        expiry=expiry,
        allergens=allergens,
        ingredients=_first_match(lines, _INGREDIENTS, continue_on_comma=True),
        nutrition=_join_matching(lines, _NUTRITION),
        caution=_join_matching(lines, _CAUTION, exclude=_FACILITY_WORDS),
    )
