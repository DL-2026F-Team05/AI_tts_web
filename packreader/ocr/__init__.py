"""영역 검출과 OCR.  담당: 이도현

지금 들어 있는 것
- DummyOCR: 합성 샘플의 정답을 돌려주는 가짜 엔진 (기본값)
- EasyOCREngine, PaddleOCREngine: 기성 OCR 기준선 래퍼
- NullDetector, YoloRegionDetector: 영역 검출 (YOLO 는 가중치 학습 후 사용)

할 일 (이도현)
- 기성 OCR 2종 기준 성능 (CER/WER) 측정
- 영역 검출기 학습 (클래스 = schema.REGION_NAMES)
- 인식기 파인튜닝 후 같은 인터페이스로 엔진 추가
- Grad-CAM(EigenCAM)으로 검출기가 소비기한·성분표에 주목하는지 확인
"""

from __future__ import annotations

import numpy as np

from ..config import Config
from ..schema import Region, TextBox
from .base import (
    OCREngine, ReadContext, RegionDetector, assign_regions, clean_boxes, clean_ocr_text, group_lines, poly_bbox,
    reading_order,
)
from .detector import NullDetector, YoloRegionDetector
from .dummy import DummyOCR

__all__ = [
    "OCREngine", "RegionDetector", "ReadContext", "DummyOCR", "NullDetector", "YoloRegionDetector",
    "get_ocr_engine", "get_detector", "run_ocr", "assign_regions", "reading_order", "group_lines", "poly_bbox",
    "clean_ocr_text", "clean_boxes",
]


def get_ocr_engine(cfg: Config) -> OCREngine:
    name = cfg.ocr_engine
    if name == "dummy":
        return DummyOCR(cfg.samples_dir)
    if name == "easyocr":
        from .easyocr_engine import EasyOCREngine

        return EasyOCREngine(cfg.ocr_langs)
    if name == "paddle":
        from .paddle_engine import PaddleOCREngine

        return PaddleOCREngine()
    raise ValueError(f"알 수 없는 OCR 엔진: {name!r} (dummy, easyocr, paddle 중 하나)")


def get_detector(cfg: Config) -> RegionDetector:
    if cfg.detector in ("", "none"):
        return NullDetector()
    if cfg.detector == "yolo":
        if not cfg.detector_weights:
            raise ValueError("PACK_DETECTOR=yolo 이면 PACK_DETECTOR_WEIGHTS 에 가중치 경로가 필요하다")
        return YoloRegionDetector(cfg.detector_weights, cfg.detector_conf)
    raise ValueError(f"알 수 없는 영역 검출기: {cfg.detector!r} (none, yolo 중 하나)")


def run_ocr(
    engine: OCREngine, detector: RegionDetector, rgb: np.ndarray, ctx: ReadContext | None = None, pad: int = 8
) -> tuple[list[Region], list[TextBox]]:
    """영역을 찾았고 엔진이 잘라 읽기를 지원하면 영역별로 잘라서 읽고, 아니면 전체를 읽는다."""
    regions = detector.detect(rgb)
    if regions and getattr(engine, "supports_crops", False):
        h, w = rgb.shape[:2]
        boxes: list[TextBox] = []
        for r in regions:
            x1, y1 = max(0, int(r.bbox[0]) - pad), max(0, int(r.bbox[1]) - pad)
            x2, y2 = min(w, int(r.bbox[2]) + pad), min(h, int(r.bbox[3]) + pad)
            if x2 - x1 < 4 or y2 - y1 < 4:
                continue
            for b in engine.read(rgb[y1:y2, x1:x2], None):
                poly = [(x + x1, y + y1) for x, y in b.poly] if b.poly else None
                boxes.append(b.model_copy(update={"poly": poly, "region": r.name}))
        # TODO(이도현): 영역 밖 글자도 필요하면 전체 이미지를 한 번 더 읽고 합치기
    else:
        boxes = assign_regions(engine.read(rgb, ctx), regions)
    return regions, reading_order(clean_boxes(boxes))
