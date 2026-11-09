"""소비기한 상태, 사용자 알레르기 맞추기, 위험 판단.  담당: 이서영

판단 보류 원칙: 신뢰도가 낮으면 '괜찮다'고 말하지 않고 status=unknown 으로 둔다.
가장 위험한 실패는 날짜를 잘못 읽고 "아직 괜찮아요"라고 말하는 것이다.
"""

from __future__ import annotations

import datetime as dt

from ..config import Config
from ..schema import Allergens, Expiry, Fields, Risk, UserProfile
from .allergens import canonicalize_list
from .dates import DateCandidate, kind_of

_KINDS = ("use_by", "sell_by", "best_before")
_DANGER = ("allergen_contains", "expired")
_CAUTION = ("allergen_may", "expiry_soon")


def build_expiry(
    cand: DateCandidate | None,
    elsewhere: tuple[str, float] | None,
    today: dt.date,
    cfg: Config,
) -> Expiry:
    if cand is None:
        if elsewhere:
            raw, conf = elsewhere
            kind = kind_of(raw)
            return Expiry(raw=raw, kind=kind if kind in _KINDS else "use_by", status="elsewhere", conf=conf)
        return Expiry()
    kind = cand.kind if cand.kind in _KINDS else "unknown"
    if cand.conf < cfg.expiry_min_conf:
        # 날짜는 남겨 두되(평가·디버깅용) 판단은 보류
        return Expiry(raw=cand.raw, date=cand.date, kind=kind, status="unknown", conf=cand.conf)
    days = (cand.date - today).days
    status = "expired" if days < 0 else ("soon" if days <= cfg.soon_days else "ok")
    return Expiry(raw=cand.raw, date=cand.date, kind=kind, status=status, days_left=days, conf=cand.conf)


def match_profile(alg: Allergens, profile: UserProfile | None) -> Allergens:
    mine = set(canonicalize_list(profile.allergens)) if profile else set()
    return alg.model_copy(
        update={
            "user_hits": [a for a in alg.contains if a in mine],
            "user_may_hits": [a for a in alg.may_contain if a in mine],
        }
    )


def assess_risk(fields: Fields) -> Risk:
    exp, alg = fields.expiry, fields.allergens
    reasons: list[str] = []
    if alg.user_hits:
        reasons.append("allergen_contains")
    if exp.status == "expired":
        reasons.append("expired")
    if alg.user_may_hits:
        reasons.append("allergen_may")
    if exp.status == "soon":
        reasons.append("expiry_soon")
    if exp.status == "unknown":
        reasons.append("expiry_unknown")
    if exp.status == "elsewhere":
        reasons.append("expiry_elsewhere")

    if any(r in _DANGER for r in reasons):
        level = "danger"
    elif any(r in _CAUTION for r in reasons):
        level = "caution"
    elif exp.status in ("unknown", "elsewhere"):
        level = "unknown"
    else:
        level = "ok"
    return Risk(level=level, reasons=reasons)
