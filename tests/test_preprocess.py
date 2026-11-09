import cv2
import numpy as np

from packreader.config import Config
from packreader.io import load_image
from packreader.preprocess import assess_quality, enhance

from conftest import SAMPLES


def sample(name="S001"):
    return load_image(SAMPLES / f"{name}.jpg").rgb


def test_clean_sample_has_no_issues():
    q = assess_quality(sample("S001"), Config())
    assert q.issues == [] and not q.retake


def test_blurred_dark_sample_needs_retake():
    q = assess_quality(sample("S004"), Config())
    assert "blur" in q.issues and "dark" in q.issues and q.retake


def test_blur_detection_on_synthetic_blur():
    img = sample("S001")
    blurred = cv2.GaussianBlur(img, (0, 0), 8)
    assert "blur" in assess_quality(blurred, Config()).issues


def test_glare_detection():
    img = sample("S001").copy()
    h, w = img.shape[:2]
    img[: h // 2, : w // 2 + 100] = 255  # 큰 반사광
    assert "glare" in assess_quality(img, Config()).issues


def test_enhance_keeps_size_and_brightens_dark():
    img = sample("S004")
    q = assess_quality(img, Config())
    out, ops = enhance(img, q, Config())
    assert out.shape == img.shape
    assert ops == ["clahe"]
    assert out.mean() > img.mean()


def test_load_image_resizes_and_hashes(tmp_path):
    big = np.zeros((3000, 1500, 3), dtype=np.uint8)
    path = tmp_path / "big.png"
    cv2.imwrite(str(path), big)
    li = load_image(path, max_side=2000)
    assert li.size == (1000, 2000)
    assert li.orig_size == (1500, 3000)
    assert abs(li.scale - 2000 / 3000) < 1e-9
    assert li.sha1 and li.name == "big.png"


def test_load_image_applies_exif_rotation(tmp_path):
    from PIL import Image

    img = Image.new("RGB", (400, 200), "white")
    exif = img.getexif()
    exif[0x0112] = 6  # 90도 돌려서 보라는 표시 (폰 세로 사진)
    path = tmp_path / "rot.jpg"
    img.save(path, exif=exif)
    li = load_image(path)
    assert li.size == (200, 400)
