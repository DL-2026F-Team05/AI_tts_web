"""OCR·영역 검출 공통 약속과 도우미 함수.  담당: 이도현

엔진을 새로 만들 때는 OCREngine 처럼 name 과 read() 만 맞추면 파이프라인에 바로 끼울 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Protocol, runtime_checkable

import numpy as np

from ..schema import Region, TextBox


@dataclass
class ReadContext:
    """엔진에 사진 외에 넘겨주는 정보. 진짜 엔진은 보통 쓰지 않는다."""

    sha1: str | None = None  # 원본 바이트 sha1
    name: str | None = None  # 파일 이름
    scale: float = 1.0  # 처리 이미지 크기 / 원본 크기


@runtime_checkable
class OCREngine(Protocol):
    name: str

    def read(self, rgb: np.ndarray, ctx: ReadContext | None = None) -> list[TextBox]:
        """RGB 이미지에서 글자 줄 목록을 돌려준다. poly 는 입력 이미지 픽셀 좌표."""
        ...


@runtime_checkable
class RegionDetector(Protocol):
    name: str

    def detect(self, rgb: np.ndarray) -> list[Region]:
        """제품명, 소비기한, 알레르기 표시란 같은 영역을 찾는다."""
        ...


def poly_bbox(poly) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in poly]
    ys = [float(p[1]) for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def box_height(box: TextBox) -> float:
    if not box.poly:
        return 0.0
    _, y1, _, y2 = poly_bbox(box.poly)
    return y2 - y1


def assign_regions(boxes: list[TextBox], regions: list[Region]) -> list[TextBox]:
    """글자 박스 중심이 들어가는 영역 이름을 붙인다. 이미 region 이 있으면 그대로 둔다."""
    if not regions:
        return boxes
    out = []
    for box in boxes:
        if box.region is not None or not box.poly:
            out.append(box)
            continue
        x1, y1, x2, y2 = poly_bbox(box.poly)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        inside = [r for r in regions if r.bbox[0] <= cx <= r.bbox[2] and r.bbox[1] <= cy <= r.bbox[3]]
        if inside:
            best = max(inside, key=lambda r: r.conf)
            box = box.model_copy(update={"region": best.name})
        out.append(box)
    return out


def reading_order(boxes: list[TextBox]) -> list[TextBox]:
    """위에서 아래, 같은 줄이면 왼쪽에서 오른쪽 순서로 정렬한다. 좌표가 없으면 원래 순서."""
    if not boxes or any(not b.poly for b in boxes):
        return list(boxes)
    items = []
    for b in boxes:
        x1, y1, x2, y2 = poly_bbox(b.poly)
        items.append(((y1 + y2) / 2, x1, max(1.0, y2 - y1), b))
    tol = 0.5 * median(h for _, _, h, _ in items)
    items.sort(key=lambda t: t[0])
    lines: list[list[tuple]] = []
    for it in items:
        if lines and abs(it[0] - lines[-1][0][0]) <= tol:
            lines[-1].append(it)
        else:
            lines.append([it])
    return [it[3] for line in lines for it in sorted(line, key=lambda t: t[1])]
