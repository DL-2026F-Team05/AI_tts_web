"""결과 형식과 문서(docs/schema.json, docs/example_result.json)가 어긋나지 않는지.

pydantic·OpenCV 버전에 따라 글자 단위로는 조금 달라질 수 있어서, 필드 이름과 안내 문장만 비교한다.
"""

import json

from packreader.config import REPO_ROOT
from packreader.schema import AnalysisResult, Expiry
from tools.export_schema import example_text, schema_text

from conftest import SAMPLES, TODAY


def _fields(schema: dict) -> dict:
    out = {"$root": sorted(schema.get("properties", {}))}
    for name, d in schema.get("$defs", {}).items():
        out[name] = sorted(d.get("properties", {}))
    return out


def test_schema_doc_is_up_to_date():
    doc = json.loads((REPO_ROOT / "docs" / "schema.json").read_text(encoding="utf-8"))
    assert _fields(doc) == _fields(json.loads(schema_text())), "schema.py 를 바꿨으면 python -m tools.export_schema 실행"


def test_example_doc_is_up_to_date():
    doc = json.loads((REPO_ROOT / "docs" / "example_result.json").read_text(encoding="utf-8"))
    now = json.loads(example_text())
    for d in (doc, now):
        d.pop("quality")  # 라이브러리 버전에 따라 소수점이 조금 달라질 수 있음
        d["image"].pop("sha1")  # 샘플 사진을 다시 저장하면 바뀜 (픽셀은 같아도)
    assert doc == now, "python -m tools.export_schema 실행"


def test_roundtrip(pipe):
    r = pipe.analyze(SAMPLES / "S001.jpg", today=TODAY, with_audio=False)
    again = AnalysisResult.model_validate_json(r.model_dump_json())
    assert again == r


def test_defaults_are_not_shared():
    a, b = Expiry(), Expiry()
    assert a is not b
    r1 = AnalysisResult(request_id="a", created_at="2026-11-10T00:00:00+09:00", today="2026-11-10")
    r2 = AnalysisResult(request_id="b", created_at="2026-11-10T00:00:00+09:00", today="2026-11-10")
    r1.preprocess_ops.append("x")
    assert r2.preprocess_ops == []
