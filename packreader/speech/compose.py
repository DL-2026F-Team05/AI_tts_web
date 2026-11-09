"""안내 문장 만들기.  담당: 박세준

바로 읽는 문장(summary) 순서
  1. 사진을 다시 찍어야 할 때는 그 안내만
  2. 내 알레르기 성분 함유 (위험)
  3. 소비기한 지남 (위험)
  4. 내 알레르기 성분 혼입 가능 (주의)
  5. 소비기한 (30일 이하일 때만 남은 날, 다른 면 표기, 못 읽음)
  6. 등록한 알레르기 성분을 못 찾았다는 안내 (등록했을 때만)
  7. 제품명 (신뢰도가 낮으면 '~로 보여요')
  8. 알레르기 표시 전체 (알레르기를 등록하지 않았을 때만)
요약은 짧게 둔다. S001 기준 edge-tts 18초 → 13.3초로 줄였다 (docs/ocr_findings.md).
'더 듣기'(detail)에는 알레르기 전체, 원재료, 영양정보, 보관 방법, 정확도 안내를 넣는다.

화면에 보여 줄 글자를 만든다. 숫자를 한글 읽기로 바꾸는 건 TTS 직전에 normalize 가 한다.
"""

from __future__ import annotations

import datetime as dt
import re

from ..config import Config, kst_today
from ..schema import KIND_LABEL, Expiry, Fields, Quality, Risk, Speech, SpeechItem, UserProfile
from .josa import join_names, josa

_RETAKE_SINGLE = {
    "dark": "사진이 너무 어두워요. 밝은 곳에서 다시 찍어 주세요.",
    "blur": "사진이 흔들렸어요. 휴대폰을 멈춘 채로 다시 찍어 주세요.",
    "glare": "빛이 반사돼서 글자가 잘 안 보여요. 각도를 조금 바꿔서 다시 찍어 주세요.",
}
_RETAKE_TIP = {"dark": "밝은 곳에서", "glare": "빛이 비치지 않게 각도를 바꿔서", "blur": "휴대폰을 멈춘 채로"}


SAY_DAYS_MAX = 30  # 남은 날이 이보다 많으면 날짜만 말한다 ('126일 남았어요'는 듣기에 군더더기)


def date_words(d: dt.date, today: dt.date) -> str:
    """올해 '11월 20일', 내년 '내년 3월 15일', 작년 '작년 12월 30일', 그 밖에는 '2028년 3월 15일'"""
    md = f"{d.month}월 {d.day}일"
    gap = d.year - today.year
    if gap == 0:
        return md
    if gap == 1:
        return "내년 " + md
    if gap == -1:
        return "작년 " + md
    return f"{d.year}년 {md}"


def retake_sentence(issues: list[str]) -> str:
    probs = [i for i in ("dark", "glare", "blur") if i in issues]
    if not probs:
        return "글자가 잘 보이게 다시 찍어 주세요."
    if len(probs) == 1:
        return _RETAKE_SINGLE[probs[0]]
    return "사진 상태가 좋지 않아요. " + " ".join(_RETAKE_TIP[p] for p in probs) + " 다시 찍어 주세요."


def expiry_sentence(exp: Expiry, today: dt.date) -> str:
    label = KIND_LABEL.get(exp.kind, "날짜")
    if exp.status == "elsewhere":
        return f"{josa(KIND_LABEL.get(exp.kind) if exp.kind != 'unknown' else '소비기한', '은/는')} 다른 곳에 따로 찍혀 있어요. 뚜껑이나 바닥의 날짜를 찍어 주세요."
    if exp.status == "unknown" or exp.date is None:
        if exp.raw:
            return "소비기한을 정확히 읽지 못했어요. 날짜 부분을 가까이에서 다시 찍어 주세요."
        return "소비기한은 찾지 못했어요. 날짜가 있는 면도 찍어 주세요."

    when = date_words(exp.date, today)
    days = exp.days_left if exp.days_left is not None else (exp.date - today).days
    left = f" {days}일 남았어요." if days <= SAY_DAYS_MAX else ""
    if exp.kind == "unknown":
        if days < 0:
            return f"표시된 날짜는 {when}이에요. 이 날짜가 소비기한이라면 이미 지났어요."
        if days == 0:
            return "표시된 날짜는 오늘이에요."
        return f"표시된 날짜는 {when}이에요.{left}"
    if exp.status == "expired":
        return f"{josa(label, '이/가')} 지났어요. {when}까지였어요."
    if days == 0:
        return f"{josa(label, '이/가')} 오늘까지예요."
    if exp.status == "soon":
        return f"{josa(label, '이/가')} {days}일 남았어요. {when}까지예요."
    return f"{josa(label, '은/는')} {when}까지예요.{left}"


_LABEL_PREFIX = re.compile(r"^\s*[가-힣 ]{2,8}\s*[:：]\s*")


def _clip(text: str, limit: int) -> str:
    """앞의 '영양정보:' 같은 칸 이름을 떼고, 길면 쉼표에서 잘라 '등'을 붙인다."""
    text = _LABEL_PREFIX.sub("", " ".join(text.split()))
    if len(text) <= limit:
        return text.rstrip(" .,") + "."
    cut = text[:limit]
    if "," in cut:
        cut = cut[: cut.rfind(",")]
    return cut.rstrip(" .,") + " 등."


def compose_detail(fields: Fields, quality: Quality, cfg: Config) -> str:
    alg = fields.allergens
    parts: list[str] = []
    if alg.contains:
        parts.append(f"알레르기 표시: {', '.join(alg.contains)}.")
    if alg.may_contain:
        parts.append(f"같은 시설에서 쓰는 성분: {', '.join(alg.may_contain)}.")
    if not alg.contains and not alg.may_contain:
        parts.append("알레르기 표시는 찾지 못했어요.")
    if fields.ingredients.value:
        parts.append("원재료: " + _clip(fields.ingredients.value, 150))
    if fields.nutrition.value:
        parts.append("영양정보: " + _clip(fields.nutrition.value, 100))
    if fields.caution.value:
        parts.append("보관과 주의사항: " + _clip(fields.caution.value, 100))

    used = []
    if fields.expiry.status not in ("unknown", "elsewhere"):
        used.append(fields.expiry.conf)
    if alg.contains or alg.may_contain:
        used.append(alg.conf)
    if fields.product_name.value and fields.product_name.conf >= cfg.product_min_conf:
        used.append(fields.product_name.conf)
    if any(c < cfg.low_conf_note for c in used):
        parts.append("글자가 일부 흐려서 틀린 내용이 있을 수 있어요.")
    if quality.retake:
        parts.append("사진을 다시 찍으면 더 정확하게 읽을 수 있어요.")
    return " ".join(parts)


def compose(
    fields: Fields,
    risk: Risk | None = None,
    quality: Quality | None = None,
    profile: UserProfile | None = None,
    today: dt.date | None = None,
    n_boxes: int | None = None,
    cfg: Config | None = None,
) -> Speech:
    cfg = cfg or Config()
    today = today or kst_today()
    quality = quality or Quality()
    exp, alg, name = fields.expiry, fields.allergens, fields.product_name
    has_profile = bool(profile and profile.allergens)
    name_ok = bool(name.value) and name.conf >= cfg.product_min_conf
    name_sure = name_ok and name.conf >= cfg.product_sure_conf
    # '~로 보여요' 수준의 제품명만 건졌으면 쓸 만한 정보를 찾은 걸로 치지 않는다 (흐린 사진은 다시 찍기가 먼저)
    found_any = exp.status != "unknown" or bool(alg.contains or alg.may_contain) or name_sure

    items: list[SpeechItem] = []

    def add(key: str, text: str) -> None:
        items.append(SpeechItem(key=key, text=text))

    def product_sentence() -> str:
        if name_sure:
            return f"제품은 {josa(name.value, '이에요/예요')}."
        return f"제품은 {josa(name.value, '으로/로')} 보여요."  # 글자가 흐려 틀렸을 수 있으면 단정하지 않는다

    if not found_any:
        if quality.retake:
            add("retake", retake_sentence(quality.issues))
        elif n_boxes == 0:
            add("no_text", "글자를 읽지 못했어요. 글자가 화면에 가득 차게 가까이에서 다시 찍어 주세요.")
        else:
            if name_ok:
                add("product", product_sentence())
            add("no_info", "소비기한과 알레르기 정보를 찾지 못했어요. 포장 뒷면의 표시사항을 찍어 주세요.")
        return Speech(summary=" ".join(i.text for i in items), detail=compose_detail(fields, quality, cfg), items=items)

    warned = False

    def warn(text: str) -> str:
        nonlocal warned
        if warned:
            return text
        warned = True
        return "주의하세요. " + text

    if alg.user_hits:
        add("allergen_user", warn(f"{join_names(alg.user_hits, '이/가')} 들어 있어요."))
    if exp.status == "expired":
        add("expiry", warn(expiry_sentence(exp, today)))
    if alg.user_may_hits:
        # '같은 시설에서 만든다'는 설명은 '더 듣기'로 보낸다 (요약은 짧게)
        add("allergen_may", f"{join_names(alg.user_may_hits, '이/가')} 섞였을 수 있어요.")
    if exp.status != "expired":
        add("expiry", expiry_sentence(exp, today))
    if has_profile and not alg.user_hits and not alg.user_may_hits:
        if alg.contains or alg.may_contain:
            add("allergen_none", "등록한 알레르기 성분은 찾지 못했어요.")
        else:
            add("allergen_none", "알레르기 표시를 찾지 못했어요.")
    if name_ok:
        add("product", product_sentence())
    if not has_profile and alg.contains:
        add("allergen_info", f"알레르기 표시는 {join_names(alg.contains, '이에요/예요')}.")

    return Speech(summary=" ".join(i.text for i in items), detail=compose_detail(fields, quality, cfg), items=items)
