"""사진 품질 판정.  담당: 배창현

기준값(Config.blur_threshold 등)은 합성 샘플로 정한 임시값이다. 실제 촬영 데이터로 다시 정한다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..config import Config
from ..schema import Quality

_MEASURE_SIDE = 1000  # 사진 크기에 따라 선명도 값이 달라지지 않게, 긴 변을 이 크기로 줄여서 잰다
_RETAKE_ISSUES = ("blur", "dark", "glare")


def assess_quality(rgb: np.ndarray, cfg: Config | None = None) -> Quality:
    cfg = cfg or Config()
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    s = _MEASURE_SIDE / max(h, w)
    small = cv2.resize(gray, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else gray

    sharpness = float(cv2.Laplacian(small, cv2.CV_64F).var())
    brightness = float(gray.mean())
    glare_ratio = float((gray >= 253).mean())  # TODO(배창현): 흰 종이와 반사광을 구분하는 방법으로 바꾸기

    issues: list[str] = []
    if sharpness < cfg.blur_threshold:
        issues.append("blur")
    if brightness < cfg.dark_threshold:
        issues.append("dark")
    if glare_ratio > cfg.glare_threshold:
        issues.append("glare")
    if min(h, w) < cfg.min_side:
        issues.append("small")

    return Quality(
        sharpness=round(sharpness, 2),
        brightness=round(brightness, 2),
        glare_ratio=round(glare_ratio, 4),
        issues=issues,
        retake=any(i in _RETAKE_ISSUES for i in issues),
    )
