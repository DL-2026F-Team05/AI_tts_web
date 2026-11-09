"""조사 붙이기. '우유가', '밀이', '땅콩을', '고소칩이에요', '우유예요'"""

from __future__ import annotations

_RIEUL = 8  # 받침 ㄹ 의 종성 번호
# 숫자를 한자어로 읽었을 때 마지막 소리의 받침 (0 영, 1 일, 3 삼, 6 육, 7 칠, 8 팔 → 받침 있음)
_DIGIT_JONG = {"0": 21, "1": 8, "2": 0, "3": 16, "4": 0, "5": 0, "6": 1, "7": 8, "8": 8, "9": 0}


def final_consonant(word: str) -> int:
    """마지막 글자의 종성 번호. 0 이면 받침 없음. 괄호·문장부호는 건너뛴다."""
    for ch in reversed(word.strip()):
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28
        if ch.isdigit():
            return _DIGIT_JONG[ch]
        if ch.isalpha():
            return 0  # 영문은 받침 없음으로 친다
    return 0


def josa(word: str, pair: str) -> str:
    """pair 는 '받침 있을 때/없을 때' 순서: '이/가', '은/는', '을/를', '과/와', '이에요/예요', '으로/로'"""
    with_jong, without = pair.split("/")
    jong = final_consonant(word)
    if pair == "으로/로":
        return word + ("로" if jong in (0, _RIEUL) else "으로")
    return word + (with_jong if jong else without)


def join_names(names: list[str], pair: str | None = None) -> str:
    """['밀', '대두', '우유'] → '밀, 대두, 우유' (+ 마지막 말에 맞는 조사)"""
    text = ", ".join(names)
    return josa(text, pair) if pair else text
