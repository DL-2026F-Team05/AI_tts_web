"""알레르기 유발물질 사전과 이름 맞추기.  담당: 이서영

표시 대상 19종 출처: 질병관리청 국가건강정보포털 '알레르기 없이 맛있게! 식품알레르기 관리하기'
(식품의약품안전처 지정 품목으로 소개).

SYNONYMS 는 출발점일 뿐이다. 식약처 「식품등의 표시기준」 원문과 실제 포장 문구를 보고 이서영이 보강한다.
"""

from __future__ import annotations

import re

ALLERGENS: tuple[str, ...] = (
    "알류", "우유", "메밀", "땅콩", "대두", "밀", "잣", "호두", "게", "새우",
    "오징어", "고등어", "조개류", "복숭아", "토마토", "닭고기", "돼지고기", "쇠고기", "아황산류",
)

# 표준 이름 → 포장에서 쓰이는 다른 이름
SYNONYMS: dict[str, tuple[str, ...]] = {name: (name,) for name in ALLERGENS}
SYNONYMS.update(
    {
        "알류": ("알류", "난류", "계란", "달걀"),
        "쇠고기": ("쇠고기", "소고기"),
        "조개류": ("조개류", "조개", "굴", "전복", "홍합"),  # TODO(이서영): 표시기준 원문으로 확인
        "아황산류": ("아황산류", "아황산"),
    }
)

_LOOKUP = {syn: canon for canon, syns in SYNONYMS.items() for syn in syns}
_SPLIT = re.compile(r"[\s,·ㆍ/()\[\]{}:;|+]+")
# 이름 뒤에 붙는 말. 떼고 나서 사전에 있는 이름이 될 때만 뗀다 (함부로 자르지 않으려고)
_SUFFIXES = ("함유", "포함", "등", "을", "를", "와", "과", "이", "가", "은", "는", "도", "및")


def canonical(token: str) -> str | None:
    """'계란' → '알류', '새우를' → '새우', '밀가루' → None"""
    t = token.strip(" .\"'")
    if t in _LOOKUP:
        return _LOOKUP[t]
    for suf in _SUFFIXES:
        if t.endswith(suf) and t[: -len(suf)] in _LOOKUP:
            return _LOOKUP[t[: -len(suf)]]
    return None


def find_allergens(segment: str) -> list[str]:
    """쉼표·괄호 등으로 나뉜 목록에서 표준 이름을 순서대로, 중복 없이 뽑는다.

    한 글자 이름(밀, 게, 잣)은 토큰이 정확히 같을 때만 잡힌다. '밀폐', '하게' 같은 오탐을 막으려고.
    """
    out: list[str] = []
    for tok in _SPLIT.split(segment):
        name = canonical(tok)
        if name and name not in out:
            out.append(name)
    return out


def canonicalize_list(names) -> list[str]:
    """사용자 프로필처럼 이름 목록을 표준 이름으로 바꾼다. 모르는 이름은 버린다."""
    out: list[str] = []
    for n in names or []:
        c = canonical(str(n))
        if c and c not in out:
            out.append(c)
    return out
