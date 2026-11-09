"""영역 검출기.  담당: 이도현

계획: 소비기한, 알레르기 표시란, 원재료, 제품명 영역을 먼저 찾고, 잘라서 OCR 에 넣는다.
- 작은 글씨가 크게 들어가서 인식이 좋아지고
- 항목별 F1·혼동행렬이 검출 클래스에서 바로 나오고
- Grad-CAM(EigenCAM)을 붙일 모델이 생긴다.

학습할 때 클래스 이름은 schema.REGION_NAMES 와 같게 맞춘다.
"""

from __future__ import annotations

import numpy as np

from ..schema import REGION_NAMES, Region


class NullDetector:
    """영역 검출 없이 사진 전체를 읽을 때."""

    name = "none"

    def detect(self, rgb: np.ndarray) -> list[Region]:
        return []


class YoloRegionDetector:
    """Ultralytics YOLO 로 학습한 영역 검출기. pip install ultralytics"""

    name = "yolo"

    def __init__(self, weights: str, conf: float = 0.25):
        self.weights = weights
        self.conf = conf
        self._model = None

    def load(self):
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.weights)
        return self._model

    warmup = load

    def detect(self, rgb: np.ndarray) -> list[Region]:
        model = self.load()
        res = model.predict(source=np.ascontiguousarray(rgb[:, :, ::-1]), conf=self.conf, verbose=False)[0]
        out: list[Region] = []
        for xyxy, cls, conf in zip(res.boxes.xyxy.tolist(), res.boxes.cls.tolist(), res.boxes.conf.tolist()):
            label = res.names[int(cls)]
            out.append(
                Region(
                    name=label if label in REGION_NAMES else "other",
                    conf=float(conf),
                    bbox=tuple(float(v) for v in xyxy),
                )
            )
        return out
