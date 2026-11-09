import pytest

from packreader.speech.josa import join_names, josa


@pytest.mark.parametrize(
    "word, pair, out",
    [
        ("우유", "이/가", "우유가"),
        ("밀", "이/가", "밀이"),
        ("땅콩", "이/가", "땅콩이"),
        ("대두", "이/가", "대두가"),
        ("아황산류", "이/가", "아황산류가"),
        ("새우", "을/를", "새우를"),
        ("땅콩", "을/를", "땅콩을"),
        ("소비기한", "은/는", "소비기한은"),
        ("바삭 고소칩", "이에요/예요", "바삭 고소칩이에요"),
        ("든든 두유", "이에요/예요", "든든 두유예요"),
        ("서울", "으로/로", "서울로"),
        ("집", "으로/로", "집으로"),
        ("학교", "으로/로", "학교로"),
        ("3", "이/가", "3이"),
        ("2", "이/가", "2가"),
    ],
)
def test_josa(word, pair, out):
    assert josa(word, pair) == out


def test_join_names_uses_last_word():
    assert join_names(["밀", "대두", "우유"], "이/가") == "밀, 대두, 우유가"
    assert join_names(["우유", "밀"], "이/가") == "우유, 밀이"
    assert join_names(["우유"]) == "우유"
