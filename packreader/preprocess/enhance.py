"""OCR 전에 사진 보정.  담당: 배창현

규칙: 이미지 크기를 바꾸지 않는다. (박스 좌표가 처리 이미지 기준이라서)
크기를 바꾸는 보정을 넣으려면 박스 좌표를 되돌리는 코드도 같이 넣는다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..config import Config
from ..schema import Quality


def enhance(rgb: np.ndarray, quality: Quality | None = None, cfg: Config | None = None) -> tuple[np.ndarray, list[str]]:
    """보정한 이미지와 적용한 보정 이름 목록을 돌려준다."""
    ops: list[str] = []
    out = rgb
    if quality is not None and "dark" in quality.issues:
        lab = cv2.cvtColor(out, cv2.COLOR_RGB2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        l_ch = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(l_ch)
        out = cv2.cvtColor(cv2.merge((l_ch, a_ch, b_ch)), cv2.COLOR_LAB2RGB)
        ops.append("clahe")
    # TODO(배창현): 반사광(glare) 완화, 기울기 보정, 흐림 보정 등
    return out, ops


def dot_kernels(rgb: np.ndarray) -> list[int]:
    """점 글씨를 이어 붙일 커널 크기 후보 (홀수). 사진 크기에 비례.

    합성 샘플 S005(1200x900)에서 커널 13 이 통했다. 5, 9 는 점이 덜 이어져 못 읽었다.
    """
    base = max(7, round(min(rgb.shape[:2]) / 70)) | 1
    return [base, (round(base * 1.5)) | 1]


def join_dots(rgb: np.ndarray, kernel: int) -> np.ndarray:
    """뚜껑·바닥에 점으로 찍힌 날짜(도트 프린트)의 점을 이어 붙인 흑백 이미지.

    1) 오츠 이진화로 글자와 바탕을 나누고 (글자 쪽이 면적이 작다고 본다)
    2) 모폴로지 닫힘(close)으로 점 사이 틈을 메운 뒤
    3) 흰 바탕 검은 글씨로 돌려준다. 크기는 그대로.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if bw.mean() > 127:  # 밝은 글씨가 어두운 바탕에 찍힌 경우
        bw = 255 - bw
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel))
    closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, k)
    return cv2.cvtColor(255 - closed, cv2.COLOR_GRAY2RGB)
