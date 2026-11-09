"""사진 → 안내 문장 전체 흐름 (가짜 OCR + 합성 샘플)."""

from packreader.config import Config
from packreader.pipeline import Pipeline
from packreader.schema import TextBox, UserProfile
from packreader.speech.tts import TTSManager

from conftest import SAMPLES, TODAY, FakeEngine


def test_s001_full_flow(pipe):
    r = pipe.analyze(SAMPLES / "S001.jpg", today=TODAY, with_audio=False)
    assert r.errors == []
    assert r.engines["ocr"] == "dummy"
    assert r.fields.product_name.value == "바삭 고소칩"
    assert str(r.fields.expiry.date) == "2027-03-15"
    assert r.fields.allergens.contains == ["밀", "대두", "우유"]
    assert r.fields.allergens.may_contain == ["땅콩", "새우"]
    assert r.speech.summary.startswith("소비기한은 2027년 3월 15일까지예요.")
    assert {"load", "preprocess", "ocr", "extract", "compose", "total"} <= set(r.timing_ms)


def test_s001_with_profile_is_danger(pipe):
    r = pipe.analyze(SAMPLES / "S001.jpg", today=TODAY, profile=UserProfile(allergens=["우유", "땅콩"]), with_audio=False)
    assert r.risk.level == "danger"
    assert r.speech.items[0].key == "allergen_user"


def test_each_sample_behaviour(pipe):
    expect = {
        "S002": ("danger", "expiry"),
        "S003": ("unknown", "expiry"),
        "S004": ("unknown", "retake"),
        "S005": ("ok", "expiry"),
        "S006": ("ok", "expiry"),
    }
    for sid, (level, first) in expect.items():
        r = pipe.analyze(SAMPLES / f"{sid}.jpg", today=TODAY, with_audio=False)
        assert r.risk.level == level, sid
        assert r.speech.items[0].key == first, sid
    assert "유통기한" in pipe.analyze(SAMPLES / "S006.jpg", today=TODAY, with_audio=False).speech.summary


def test_bytes_input_matches_sample(pipe):
    data = (SAMPLES / "S002.jpg").read_bytes()
    r = pipe.analyze(data, today=TODAY, with_audio=False)
    assert r.fields.expiry.status == "expired"


def test_unknown_photo_gives_no_text_message(pipe):
    import numpy as np

    # 선명하고 밝지만 글자가 없는 사진 (체크무늬)
    yy, xx = np.mgrid[0:600, 0:800]
    board = (((yy // 20) + (xx // 20)) % 2 * 200 + 30).astype(np.uint8)
    r = pipe.analyze(np.dstack([board] * 3), today=TODAY, with_audio=False)
    assert r.quality.issues == []
    assert r.boxes == []
    assert r.speech.items[0].key == "no_text"


def test_flat_gray_photo_asks_retake(pipe):
    import numpy as np

    r = pipe.analyze(np.full((600, 800, 3), 128, dtype=np.uint8), today=TODAY, with_audio=False)
    assert r.speech.items[0].key == "retake"


def test_broken_image_does_not_crash(pipe):
    r = pipe.analyze(b"not an image", today=TODAY, with_audio=False)
    assert r.errors and r.errors[0].stage == "load"
    assert "사진을 열지 못했어요" in r.speech.summary


def test_ocr_failure_is_recorded(cfg):
    class BrokenOCR:
        name = "broken"

        def read(self, rgb, ctx=None):
            raise RuntimeError("모델 없음")

    p = Pipeline(cfg, ocr=BrokenOCR(), tts=TTSManager([]))
    r = p.analyze(SAMPLES / "S001.jpg", today=TODAY, with_audio=False)
    assert [e.stage for e in r.errors] == ["ocr"]
    assert r.speech is not None and r.speech.summary


def test_analyze_text(pipe):
    r = pipe.analyze_text("알레르기 유발물질: 땅콩 함유\n소비기한: 2026.11.11까지", today=TODAY,
                          profile=UserProfile(allergens=["땅콩"]), with_audio=False)
    assert r.engines["ocr"] == "text"
    assert r.risk.level == "danger"
    assert r.speech.summary.startswith("주의하세요. 땅콩이 들어 있어요.")


def test_audio_attached_when_engine_works(cfg):
    p = Pipeline(cfg, tts=TTSManager([FakeEngine("fake")], cfg.audio_dir))
    r = p.analyze(SAMPLES / "S001.jpg", today=TODAY)
    assert r.audio is not None and r.audio.engine == "fake"
    assert r.audio.url.startswith("/api/audio/")
    assert r.engines["tts"] == "fake"


def test_no_engine_means_browser(pipe):
    r = pipe.analyze(SAMPLES / "S001.jpg", today=TODAY)
    assert r.audio is None and r.engines["tts"] == "browser"


def test_regions_from_detector_are_assigned(cfg):
    from packreader.schema import Region

    class FakeDetector:
        name = "fake"

        def detect(self, rgb):
            return [Region(name="expiry", conf=0.9, bbox=(0, 0, 2000, 2000))]

    class PlainOCR:
        name = "plain"

        def read(self, rgb, ctx=None):
            return [TextBox(text="소비기한 2026.11.20까지", conf=0.9, poly=[(10, 10), (200, 10), (200, 40), (10, 40)])]

    p = Pipeline(cfg, ocr=PlainOCR(), detector=FakeDetector(), tts=TTSManager([]))
    r = p.analyze(SAMPLES / "S001.jpg", today=TODAY, with_audio=False)
    assert r.boxes[0].region == "expiry"
    assert r.regions[0].name == "expiry"
