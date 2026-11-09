import pytest

from packreader.speech.normalize import month_word, normalize_for_tts, read_number, sino


@pytest.mark.parametrize(
    "n, words",
    [
        (0, "영"), (1, "일"), (10, "십"), (11, "십일"), (20, "이십"), (100, "백"), (101, "백일"),
        (125, "백이십오"), (1000, "천"), (2026, "이천이십육"), (10000, "만"), (15000, "만오천"),
        (110000, "십일만"), (100000000, "일억"),
    ],
)
def test_sino(n, words):
    assert sino(n) == words


def test_month_irregular():
    assert month_word(6) == "유월"
    assert month_word(10) == "시월"
    assert month_word(3) == "삼월"
    assert month_word(12) == "십이월"


def test_read_number_decimal_and_comma():
    assert read_number("12.5") == "십이 점 오"
    assert read_number("1,000") == "천"


@pytest.mark.parametrize(
    "text, spoken",
    [
        ("소비기한은 2027년 3월 15일까지예요. 125일 남았어요.", "소비기한은 이천이십칠년 삼월 십오일까지예요. 백이십오일 남았어요."),
        ("유통기한은 11월 25일까지예요.", "유통기한은 십일월 이십오일까지예요."),
        ("6월 10일", "유월 십일"),
        ("2026.10.30", "이천이십육년 시월 삼십일"),
        ("우유 900mL", "우유 구백 밀리리터"),
        ("320kcal, 나트륨 180mg", "삼백이십 킬로칼로리, 나트륨 백팔십 밀리그램"),
        ("냉장보관(0~10℃)", "냉장보관(영에서 십 도)"),
        ("원유 100%", "원유 백 퍼센트"),
    ],
)
def test_normalize_for_tts(text, spoken):
    assert normalize_for_tts(text) == spoken


def test_text_without_numbers_is_unchanged():
    text = "주의하세요. 우유가 들어 있어요."
    assert normalize_for_tts(text) == text
