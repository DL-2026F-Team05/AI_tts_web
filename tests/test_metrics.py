import pytest

from evaluation.metrics import (
    cer, confusion_matrix, corpus_error, coverage_risk, iou, levenshtein, macro_f1, match_boxes, prf, wer,
)


def test_levenshtein():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3
    assert levenshtein(["a", "b"], ["a", "b"]) == 0


def test_cer_korean_syllables_ignore_spaces():
    assert cer("소비기한 2026.11.20", "소비기한2026.11.20") == 0
    assert cer("우유", "우유") == 0
    assert cer("우유", "우뮤") == pytest.approx(0.5)


def test_wer():
    assert wer("밀 대두 우유", "밀 대두 우유") == 0
    assert wer("밀 대두 우유", "밀 우유") == pytest.approx(1 / 3)


def test_corpus_error_weights_by_length():
    pairs = [("가나다라마바사아자차", "가나다라마바사아자차"), ("가", "나")]
    assert corpus_error(pairs) == pytest.approx(1 / 11)


def test_prf_and_macro():
    assert prf(8, 2, 2) == pytest.approx((0.8, 0.8, 0.8))
    assert prf(0, 0, 0) == (0.0, 0.0, 0.0)
    assert macro_f1({"a": (1, 0, 0), "b": (0, 1, 1), "c": (0, 0, 0)}) == pytest.approx(0.5)


def test_confusion_matrix():
    m = confusion_matrix(["x", "x", "y"], ["x", "y", "y"], ["x", "y"])
    assert m == [[1, 1], [0, 1]]


def test_iou_and_matching():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0
    matched, fp, fn = match_boxes([(0, 0, 10, 10), (50, 50, 60, 60)], [(1, 1, 10, 10), (100, 100, 110, 110)])
    assert matched == [(0, 0)] and fp == 1 and fn == 1


def test_coverage_risk():
    rows = coverage_risk([(0.9, True), (0.8, True), (0.4, False), (0.2, False)], thresholds=[0.0, 0.5, 0.95])
    assert rows[0] == {"threshold": 0.0, "coverage": 1.0, "error": 0.5}
    assert rows[1] == {"threshold": 0.5, "coverage": 0.5, "error": 0.0}
    assert rows[2]["coverage"] == 0.0
