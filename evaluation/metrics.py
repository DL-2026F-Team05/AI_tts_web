"""평가 지표. 정의는 docs/eval_protocol.md 에 있다.

한국어 CER 은 자모가 아니라 음절(NFC) 단위로 센다. 공백은 빼고 센다 (띄어쓰기 오류까지 세려면 remove_spaces=False).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence


def levenshtein(a: Sequence, b: Sequence) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def normalize_text(text: str, remove_spaces: bool = True) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = " ".join(text.split())
    return text.replace(" ", "") if remove_spaces else text


def cer(ref: str, hyp: str, remove_spaces: bool = True) -> float:
    r, h = normalize_text(ref, remove_spaces), normalize_text(hyp, remove_spaces)
    return levenshtein(r, h) / max(1, len(r))


def wer(ref: str, hyp: str) -> float:
    r, h = normalize_text(ref, False).split(), normalize_text(hyp, False).split()
    return levenshtein(r, h) / max(1, len(r))


def corpus_error(pairs, unit: str = "char") -> float:
    """여러 쌍을 합쳐서 계산 (짧은 문장이 평균을 흔들지 않게). unit: char | word"""
    edits = total = 0
    for ref, hyp in pairs:
        if unit == "char":
            r, h = normalize_text(ref), normalize_text(hyp)
        else:
            r, h = normalize_text(ref, False).split(), normalize_text(hyp, False).split()
        edits += levenshtein(r, h)
        total += len(r)
    return edits / max(1, total)


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def set_counts(true: set, pred: set) -> tuple[int, int, int]:
    return len(true & pred), len(pred - true), len(true - pred)


def macro_f1(per_class: dict[str, tuple[int, int, int]]) -> float:
    """정답이나 예측에 한 번이라도 나온 클래스만 평균 낸다."""
    scores = [prf(*c)[2] for c in per_class.values() if sum(c) > 0]
    return sum(scores) / len(scores) if scores else 0.0


def confusion_matrix(y_true: list[str], y_pred: list[str], labels: list[str]) -> list[list[int]]:
    idx = {lab: i for i, lab in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred):
        if t in idx and p in idx:
            m[idx[t]][idx[p]] += 1
    return m


def iou(a, b) -> float:
    """a, b: (x1, y1, x2, y2)"""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match_boxes(gt: list, pred: list, thr: float = 0.5) -> tuple[list[tuple[int, int]], int, int]:
    """IoU 큰 쌍부터 1:1 로 짝짓기. (짝 목록, 남은 예측 수 fp, 남은 정답 수 fn)"""
    pairs = sorted(
        ((iou(g, p), i, j) for i, g in enumerate(gt) for j, p in enumerate(pred)),
        reverse=True,
    )
    used_g, used_p, matched = set(), set(), []
    for v, i, j in pairs:
        if v < thr:
            break
        if i in used_g or j in used_p:
            continue
        used_g.add(i)
        used_p.add(j)
        matched.append((i, j))
    return matched, len(pred) - len(matched), len(gt) - len(matched)


def coverage_risk(records: list[tuple[float, bool]], thresholds=None) -> list[dict]:
    """(신뢰도, 맞았는지) 목록 → 기준값별 (답한 비율, 답한 것 중 틀린 비율).

    판단 보류 기준(Config.expiry_min_conf)을 정할 때 쓰는 그래프 데이터.
    """
    thresholds = thresholds or [round(i * 0.05, 2) for i in range(21)]
    n = len(records)
    out = []
    for t in thresholds:
        answered = [ok for c, ok in records if c >= t]
        cov = len(answered) / n if n else 0.0
        err = (len(answered) - sum(answered)) / len(answered) if answered else 0.0
        out.append({"threshold": t, "coverage": round(cov, 4), "error": round(err, 4)})
    return out
