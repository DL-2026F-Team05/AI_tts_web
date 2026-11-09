"""날짜 찾기와 소비기한 고르기.  담당: 이서영

지금 들어 있는 것은 기준선이다. 처리하는 형식:
  2026.11.20 / 2026-11-20 / 2026/11/20 / 2026년 11월 20일 (사이 공백 허용)
  앞에 붙은 말로 종류 구분: 소비기한, 유통기한, 품질유지기한, 제조일자(소비기한 후보에서 뺌)
  '별도표기일까지' 같은 문구 찾기

아직 못 하는 것은 tests/test_extract_spec.py 의 xfail 항목에 적어 두었다.
(두 자리 연도, O/0 같은 OCR 오타, '제조일로부터 12개월' 같은 상대 표기 등)
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(20\d{2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"),
)
_KIND_PATTERNS = (
    ("use_by", re.compile(r"소비\s*기한")),
    ("sell_by", re.compile(r"유통\s*기한")),
    ("best_before", re.compile(r"품질\s*유지\s*기한")),
    ("manufactured", re.compile(r"제조\s*일|포장\s*일|생산\s*일")),
)
_ELSEWHERE = re.compile(r"별도\s*(?:표기|표시)")
_KIND_PRIORITY = {"use_by": 0, "sell_by": 1, "best_before": 2, "unknown": 3}


@dataclass
class DateCandidate:
    date: dt.date
    raw: str
    kind: str  # use_by | sell_by | best_before | manufactured | unknown
    line: int
    conf: float


def kind_of(text: str) -> str | None:
    """글자 안에서 가장 마지막에 나온 날짜 종류 키워드."""
    best, best_pos = None, -1
    for kind, rx in _KIND_PATTERNS:
        for m in rx.finditer(text):
            if m.start() > best_pos:
                best, best_pos = kind, m.start()
    return best


def _has_date(text: str) -> bool:
    return any(rx.search(text) for rx in _DATE_PATTERNS)


def find_dates(lines: list[tuple[str, float]]) -> list[DateCandidate]:
    """lines: [(글자, 신뢰도), ...] 읽는 순서대로."""
    out: list[DateCandidate] = []
    for i, (text, conf) in enumerate(lines):
        for rx in _DATE_PATTERNS:
            for m in rx.finditer(text):
                y, mo, d = (int(g) for g in m.groups())
                try:
                    day = dt.date(y, mo, d)
                except ValueError:
                    continue
                kind = kind_of(text[: m.start()])
                if kind is None and i > 0:
                    prev = lines[i - 1][0]
                    # '소비기한' 칸과 날짜 칸이 따로 읽힌 경우: 바로 앞 짧은 줄의 키워드를 쓴다
                    if len(prev) <= 15 and not _has_date(prev):
                        kind = kind_of(prev)
                out.append(DateCandidate(day, m.group(0).strip(), kind or "unknown", i, float(conf)))
    return out


def pick_expiry(cands: list[DateCandidate]) -> DateCandidate | None:
    """소비기한 > 유통기한 > 품질유지기한 > 종류 모름 순서. 같은 종류면 신뢰도 높은 것."""
    pool = [c for c in cands if c.kind != "manufactured"]
    if not pool:
        return None
    return min(pool, key=lambda c: (_KIND_PRIORITY.get(c.kind, 9), -c.conf))


def find_elsewhere(lines: list[tuple[str, float]]) -> tuple[str, float] | None:
    """'소비기한: 별도표기일까지' 같은 줄을 찾는다. (원문, 신뢰도)"""
    for text, conf in lines:
        if _ELSEWHERE.search(text):
            return text.strip(), float(conf)
    return None
