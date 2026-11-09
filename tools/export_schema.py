"""결과 형식 문서 만들기: docs/schema.json (JSON Schema), docs/example_result.json (S001 결과 예시)

    python -m tools.export_schema
schema.py 를 바꾸면 이걸 다시 돌려서 같이 커밋한다. (tests/test_schema.py 가 어긋나면 알려 준다)
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from packreader.config import REPO_ROOT, Config
from packreader.pipeline import Pipeline
from packreader.schema import AnalysisResult, UserProfile
from packreader.speech.tts import TTSManager

EXAMPLE_TODAY = dt.date(2026, 11, 10)


def schema_text() -> str:
    return json.dumps(AnalysisResult.model_json_schema(), ensure_ascii=False, indent=2) + "\n"


def example_text() -> str:
    pipe = Pipeline(Config(ocr_engine="dummy"), tts=TTSManager([]))
    res = pipe.analyze(
        REPO_ROOT / "data" / "samples" / "S001.jpg",
        profile=UserProfile(allergens=["우유", "땅콩"]),
        today=EXAMPLE_TODAY,
        with_audio=False,
    )
    data = res.model_dump(mode="json")
    data["request_id"] = "example0001"
    data["created_at"] = "2026-11-10T09:00:00+09:00"
    data["timing_ms"] = {k: 0.0 for k in data["timing_ms"]}
    data["boxes"] = data["boxes"][:4]  # 예시라서 앞부분만
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main():
    docs = Path(REPO_ROOT / "docs")
    (docs / "schema.json").write_text(schema_text(), encoding="utf-8")
    (docs / "example_result.json").write_text(example_text(), encoding="utf-8")
    print("docs/schema.json, docs/example_result.json 갱신")


if __name__ == "__main__":
    main()
