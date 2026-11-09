"""가짜 OCR. data/samples 의 정답 JSON 을 그대로 돌려준다.

모델 없이도 사진 → 음성 한 바퀴를 돌려 보려고 만든 것. 합성 샘플이 아닌 사진에서는 글자가 안 나온다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from ..schema import TextBox
from .base import ReadContext


class DummyOCR:
    name = "dummy"
    supports_crops = False

    def __init__(self, samples_dir: str | Path):
        self._by_sha1: dict[str, list[TextBox]] = {}
        self._by_stem: dict[str, list[TextBox]] = {}
        for meta_path in sorted(Path(samples_dir).glob("*.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            boxes = [TextBox.model_validate(b) for b in meta.get("boxes", [])]
            image_path = meta_path.with_name(meta.get("image", meta_path.stem + ".jpg"))
            if image_path.exists():
                self._by_sha1[hashlib.sha1(image_path.read_bytes()).hexdigest()] = boxes
            self._by_stem[image_path.stem] = boxes

    def read(self, rgb: np.ndarray, ctx: ReadContext | None = None) -> list[TextBox]:
        ctx = ctx or ReadContext()
        boxes = self._by_sha1.get(ctx.sha1 or "")
        if boxes is None and ctx.name:
            boxes = self._by_stem.get(Path(ctx.name).stem)
        if not boxes:
            return []
        s = ctx.scale
        return [
            b.model_copy(update={"poly": [(x * s, y * s) for x, y in b.poly] if b.poly else None})
            for b in boxes
        ]
