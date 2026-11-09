"""이미지 읽기. 폰 사진의 EXIF 회전을 바로잡고, 너무 크면 줄인다.

폰으로 찍은 사진은 픽셀은 옆으로 누워 있고 EXIF 에 '돌려서 보라'는 값만 들어 있는 경우가 많다.
이걸 안 바로잡으면 OCR 이 옆으로 누운 글자를 읽게 된다.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

try:  # 아이폰 HEIC 사진 (pip install pillow-heif 했을 때만)
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover - 선택 기능
    pass


@dataclass
class LoadedImage:
    rgb: np.ndarray  # (H, W, 3) uint8, RGB
    sha1: str | None  # 원본 바이트의 sha1 (가짜 OCR 이 샘플을 알아보는 데 쓴다)
    name: str | None
    orig_size: tuple[int, int]  # (W, H) 회전 보정 후, 축소 전
    scale: float  # 처리 크기 / 원본 크기

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.rgb.shape[:2]
        return w, h


def load_image(source, max_side: int = 2000, name: str | None = None) -> LoadedImage:
    """source: bytes | 파일 경로 | numpy RGB 배열 | PIL.Image"""
    raw: bytes | None = None
    if isinstance(source, np.ndarray):
        pil = Image.fromarray(np.ascontiguousarray(source).astype(np.uint8))
    elif isinstance(source, (bytes, bytearray, memoryview)):
        raw = bytes(source)
        pil = Image.open(io.BytesIO(raw))
    elif isinstance(source, (str, Path)):
        path = Path(source)
        raw = path.read_bytes()
        name = name or path.name
        pil = Image.open(io.BytesIO(raw))
    elif isinstance(source, Image.Image):
        pil = source
    else:
        raise TypeError(f"이미지로 읽을 수 없는 형식: {type(source).__name__}")

    pil = ImageOps.exif_transpose(pil) or pil
    pil = pil.convert("RGB")
    ow, oh = pil.size
    scale = 1.0
    if max_side and max(ow, oh) > max_side:
        scale = max_side / max(ow, oh)
        pil = pil.resize((max(1, round(ow * scale)), max(1, round(oh * scale))), Image.Resampling.LANCZOS)
    rgb = np.array(pil)  # 복사본 (쓰기 가능)
    sha1 = hashlib.sha1(raw).hexdigest() if raw is not None else None
    return LoadedImage(rgb=rgb, sha1=sha1, name=name, orig_size=(ow, oh), scale=scale)
