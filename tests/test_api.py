import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from packreader.pipeline import Pipeline
from packreader.speech.tts import TTSManager

from conftest import SAMPLES, FakeEngine


@pytest.fixture
def client(cfg):
    pipe = Pipeline(cfg, tts=TTSManager([FakeEngine("fake")], cfg.audio_dir))
    with TestClient(create_app(pipe)) as c:
        yield c


def test_index_and_static(client):
    r = client.get("/")
    assert r.status_code == 200 and "패키지 읽어주기" in r.text
    assert client.get("/static/app.js").status_code == 200


def test_health(client):
    data = client.get("/api/health").json()
    assert data["ocr"] == "dummy"
    assert data["tts"]["available"] == ["fake"]
    assert "우유" in data["allergens"] and len(data["allergens"]) == 19


def test_samples_listed(client):
    data = client.get("/api/samples").json()
    assert [s["id"] for s in data] == ["S001", "S002", "S003", "S004", "S005", "S006"]
    assert client.get(data[0]["url"]).status_code == 200


def test_analyze_upload_with_profile_and_audio(client):
    with open(SAMPLES / "S001.jpg", "rb") as f:
        r = client.post(
            "/api/analyze",
            files={"image": ("S001.jpg", f, "image/jpeg")},
            data={"allergens": json.dumps(["우유"]), "today": "2026-11-10"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["risk"]["level"] == "danger"
    assert data["speech"]["summary"].startswith("주의하세요. 우유가 들어 있어요.")
    audio = client.get(data["audio"]["url"])
    assert audio.status_code == 200 and audio.headers["content-type"].startswith("audio/")


def test_analyze_sample_id(client):
    r = client.post("/api/analyze", data={"sample_id": "S003", "today": "2026-11-10", "audio": "false"})
    assert r.status_code == 200
    assert r.json()["fields"]["expiry"]["status"] == "elsewhere"
    assert r.json()["audio"] is None


def test_analyze_bad_requests(client):
    assert client.post("/api/analyze", data={}).status_code == 400
    assert client.post("/api/analyze", data={"sample_id": "../x"}).status_code == 400
    assert client.post("/api/analyze", data={"sample_id": "S999"}).status_code == 404
    assert client.post("/api/analyze", data={"sample_id": "S001", "today": "11/10"}).status_code == 400
    assert client.post("/api/analyze", data={"sample_id": "S001", "allergens": "우유"}).status_code == 400


def test_broken_upload_still_answers(client):
    r = client.post("/api/analyze", files={"image": ("x.jpg", b"garbage", "image/jpeg")})
    assert r.status_code == 200
    assert "사진을 열지 못했어요" in r.json()["speech"]["summary"]


def test_analyze_text_and_tts(client):
    r = client.post("/api/analyze-text", json={"text": "소비기한: 2026.11.11까지", "today": "2026-11-10"})
    assert r.status_code == 200
    assert r.json()["fields"]["expiry"]["status"] == "soon"
    t = client.post("/api/tts", json={"text": "더 들려 드릴게요"}).json()
    assert t["audio"]["engine"] == "fake"


def test_audio_path_traversal_blocked(client):
    assert client.get("/api/audio/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/api/audio/abc.txt").status_code == 404


def test_events_logged(client, cfg):
    assert client.post("/api/events", json={"type": "first_audio", "data": {"ms": 1234}}).json() == {"ok": True}
    lines = (cfg.log_dir / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[-1])["ms"] == 1234
