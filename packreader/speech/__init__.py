"""안내 문장과 TTS.  담당: 박세준

- compose: 위험한 정보부터 읽는 안내 문장
- normalize: 숫자·단위·날짜를 한글 읽기로 (TTS 직전)
- josa: 조사 붙이기
- tts: 엔진 여러 개를 순서대로 시도하고, 다 안 되면 브라우저 음성으로 넘긴다
"""

from .compose import compose, compose_detail, expiry_sentence, retake_sentence
from .josa import join_names, josa
from .normalize import normalize_for_tts, sino

__all__ = [
    "compose", "compose_detail", "expiry_sentence", "retake_sentence",
    "josa", "join_names", "normalize_for_tts", "sino",
]
