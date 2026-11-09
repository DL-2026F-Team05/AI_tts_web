"""EasyOCR 기준선 래퍼.  담당: 이도현

설치: pip install easyocr   (코랩에는 torch 가 이미 있다)
첫 실행 때 한국어 모델을 내려받는다.
"""

from __future__ import annotations

import numpy as np

from ..schema import TextBox
from .base import ReadContext


class EasyOCREngine:
    name = "easyocr"
    supports_crops = True

    def __init__(self, langs=("ko", "en"), gpu: bool | None = None):
        self.langs = list(langs)
        self.gpu = gpu
        self._reader = None

    def load(self):
        if self._reader is None:
            import easyocr

            gpu = self.gpu
            if gpu is None:
                try:
                    import torch

                    gpu = torch.cuda.is_available()
                except Exception:
                    gpu = False
            self._reader = easyocr.Reader(self.langs, gpu=gpu)
        return self._reader

    warmup = load

    def read(self, rgb: np.ndarray, ctx: ReadContext | None = None) -> list[TextBox]:
        reader = self.load()
        bgr = np.ascontiguousarray(rgb[:, :, ::-1])  # EasyOCR 은 배열을 BGR 로 본다
        out: list[TextBox] = []
        for poly, text, conf in reader.readtext(bgr):
            text = str(text).strip()
            if not text:
                continue
            out.append(
                TextBox(
                    text=text,
                    conf=float(min(1.0, max(0.0, conf))),
                    poly=[(float(x), float(y)) for x, y in poly],
                )
            )
        return out
