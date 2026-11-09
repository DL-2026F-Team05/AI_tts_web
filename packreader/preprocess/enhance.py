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
