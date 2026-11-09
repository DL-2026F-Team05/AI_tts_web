"""TTS 에 넣기 전에 숫자·단위·날짜를 한글 읽기로 바꾼다.

엔진마다 숫자를 읽는 방식이 달라서(특히 MMS 는 숫자를 거의 못 읽는다) 미리 풀어 쓰면 결과가 고르게 나온다.
  2027년 3월 15일 → 이천이십칠년 삼월 십오일
  6월 → 유월, 10월 → 시월
  900mL → 구백 밀리리터, 12.5% → 십이 점 오 퍼센트, 0~10℃ → 영에서 십 도
화면에 보이는 글자는 그대로 두고, 엔진에 넣는 글자만 바꾼다.
"""

from __future__ import annotations

import re

_DIGITS = "영일이삼사오육칠팔구"
_BIG_UNITS = ("", "만", "억", "조", "경")
_UNITS = {
    "kcal": "킬로칼로리",
    "mg": "밀리그램",
    "kg": "킬로그램",
    "g": "그램",
    "mL": "밀리리터",
    "ml": "밀리리터",
    "L": "리터",
    "cm": "센티미터",
    "mm": "밀리미터",
    "%": "퍼센트",
    "℃": "도",
    "°C": "도",
}

_NUM = r"\d[\d,]*(?:\.\d+)?"
_DATE_RE = re.compile(r"(?<!\d)(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})(?!\d)")
_YEAR_RE = re.compile(r"(\d{4})\s*년")
_MONTH_RE = re.compile(r"(?<![\d.])(\d{1,2})\s*월")
_DAY_RE = re.compile(r"(?<![\d.])(\d{1,2})\s*일")
_RANGE_RE = re.compile(r"(\d)\s*~\s*(\d)")
_UNIT_RE = re.compile(rf"({_NUM})\s*(kcal|mg|kg|mL|ml|cm|mm|g|L|%|℃|°C)(?![A-Za-z])")
_NUMBER_RE = re.compile(_NUM)


def _group(g: int) -> str:
    """1~9999"""
    out = ""
    for unit, div in (("천", 1000), ("백", 100), ("십", 10), ("", 1)):
        d = g // div % 10
        if d == 0:
            continue
        out += (unit if d == 1 and unit else _DIGITS[d] + unit)
    return out


def sino(n: int) -> str:
    """한자어 수 읽기. 2026 → 이천이십육, 10000 → 만, 110000 → 십일만"""
    if n == 0:
        return "영"
    if n < 0:
        return "마이너스 " + sino(-n)
    parts = []
    idx = 0
    while n > 0:
        g = n % 10000
        if g:
            words = "" if (idx == 1 and g == 1) else _group(g)  # '일만'이 아니라 '만'
            parts.append(words + _BIG_UNITS[idx])
        n //= 10000
        idx += 1
    return "".join(reversed(parts))


def read_number(token: str) -> str:
    """'1,000' → 천, '12.5' → 십이 점 오"""
    token = token.replace(",", "")
    if "." in token:
        whole, frac = token.split(".", 1)
        return f"{sino(int(whole or 0))} 점 {''.join(_DIGITS[int(c)] for c in frac)}"
    return sino(int(token))


def month_word(m: int) -> str:
    return {6: "유월", 10: "시월"}.get(m, sino(m) + "월")


def _date_sub(m: re.Match) -> str:
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return m.group(0)
    return f"{sino(y)}년 {month_word(mo)} {sino(d)}일"


def normalize_for_tts(text: str) -> str:
    text = text.replace("ㆍ", ", ").replace("·", ", ")
    text = _DATE_RE.sub(_date_sub, text)
    text = _YEAR_RE.sub(lambda m: sino(int(m.group(1))) + "년", text)
    text = _MONTH_RE.sub(lambda m: month_word(int(m.group(1))) if 1 <= int(m.group(1)) <= 12 else m.group(0), text)
    text = _DAY_RE.sub(lambda m: sino(int(m.group(1))) + "일", text)
    text = _RANGE_RE.sub(r"\1에서 \2", text)
    text = _UNIT_RE.sub(lambda m: f"{read_number(m.group(1))} {_UNITS[m.group(2)]}", text)
    text = _NUMBER_RE.sub(lambda m: read_number(m.group(0)), text)
    return re.sub(r"\s{2,}", " ", text).strip()
