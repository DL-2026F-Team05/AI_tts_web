"""PaddleOCR 기준선 래퍼 (한국어 PP-OCRv5).  담당: 이도현

설치(CPU): pip install paddlepaddle paddleocr
코랩 GPU 로 쓰려면 paddlepaddle-gpu 를 설치한다 (docs/colab_guide.md 참고).
PaddleOCR 3.x 와 2.x 결과 형식이 달라서 둘 다 처리한다.
"""

from __future__ import annotations

import numpy as np

from ..schema import TextBox
from .base import ReadContext


class PaddleOCREngine:
    name = "paddle"
    supports_crops = True

    def __init__(self, lang: str = "korean"):
        self.lang = lang
        self._ocr = None
        self._v3 = True

    def load(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR

            try:  # 3.x
                self._ocr = PaddleOCR(
                    lang=self.lang,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
                self._v3 = True
            except (TypeError, ValueError):  # 2.x
                self._ocr = PaddleOCR(lang=self.lang, use_angle_cls=False, show_log=False)
                self._v3 = False
        return self._ocr

    warmup = load

    def read(self, rgb: np.ndarray, ctx: ReadContext | None = None) -> list[TextBox]:
        ocr = self.load()
        bgr = np.ascontiguousarray(rgb[:, :, ::-1])
        out: list[TextBox] = []
        if self._v3:
            for res in ocr.predict(bgr):
                data = res if isinstance(res, dict) else getattr(res, "json", {}).get("res", {})
                texts = list(data.get("rec_texts") or [])
                scores = list(data.get("rec_scores") or [])
                polys = data.get("rec_polys")
                if polys is None:
                    polys = data.get("dt_polys") or []
                for text, score, poly in zip(texts, scores, polys):
                    pts = np.asarray(poly, dtype=float).reshape(-1, 2)
                    if str(text).strip():
                        out.append(TextBox(text=str(text).strip(), conf=float(score), poly=[(x, y) for x, y in pts.tolist()]))
        else:
            result = ocr.ocr(bgr, cls=False)
            for line in (result[0] if result else None) or []:
                poly, (text, score) = line
                if str(text).strip():
                    out.append(TextBox(text=str(text).strip(), conf=float(score), poly=[(float(x), float(y)) for x, y in poly]))
        return out
