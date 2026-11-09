"""웹 데모 서버.  담당: 박세준

실행 (저장소 루트에서):
    uvicorn app.main:app --host 0.0.0.0 --port 8000
엔진 바꾸기: PACK_OCR=easyocr, PACK_TTS=melo,edge,gtts 같은 환경 변수 (packreader/config.py)

API
  GET  /api/health        엔진 상태, 알레르기 목록
  GET  /api/samples       합성 샘플 목록
  POST /api/analyze       사진(또는 sample_id) → 결과 JSON (+ 요약 음성 주소)
  POST /api/analyze-text  OCR 없이 글자로 → 결과 JSON
  POST /api/tts           글자 → 음성 주소 ('더 듣기')
  GET  /api/audio/{name}  만들어 둔 음성 파일
  POST /api/events        사용자 테스트 기록 (첫 음성까지 시간 등) → logs/events.jsonl
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from packreader.config import KST, Config
from packreader.extract.allergens import ALLERGENS
from packreader.pipeline import Pipeline
from packreader.schema import SCHEMA_VERSION, UserProfile

log = logging.getLogger("app")
STATIC_DIR = Path(__file__).parent / "static"
_AUDIO_NAME = re.compile(r"^[0-9a-f]{8,40}\.(wav|mp3)$")
_SAMPLE_ID = re.compile(r"^S\d{3}$")


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    allergens: list[str] = Field(default_factory=list)
    today: dt.date | None = None
    audio: bool = True
    speed: float = Field(1.0, ge=0.5, le=2.0)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    speed: float = Field(1.0, ge=0.5, le=2.0)


class EventRequest(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    data: dict = Field(default_factory=dict)


def _parse_today(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, "today 는 YYYY-MM-DD 형식이어야 한다")


def _parse_allergens(value: str) -> list[str]:
    try:
        data = json.loads(value or "[]")
    except json.JSONDecodeError:
        raise HTTPException(400, "allergens 는 JSON 배열이어야 한다")
    if not isinstance(data, list):
        raise HTTPException(400, "allergens 는 JSON 배열이어야 한다")
    return [str(x) for x in data][:30]


def create_app(pipeline: Pipeline | None = None, cfg: Config | None = None) -> FastAPI:
    cfg = cfg or (pipeline.cfg if pipeline else Config.from_env())
    state: dict = {"pipeline": pipeline}
    lock = threading.Lock()  # 시연용 서버라 모델을 한 번에 하나씩만 돌린다

    def get_pipeline() -> Pipeline:
        if state["pipeline"] is None:
            state["pipeline"] = Pipeline(cfg)
        return state["pipeline"]

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        pipe = get_pipeline()
        if cfg.warmup:
            threading.Thread(target=pipe.warmup, daemon=True).start()
        yield

    app = FastAPI(title="패키지 읽어주기 데모", version=SCHEMA_VERSION, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    if cfg.samples_dir.exists():
        app.mount("/samples", StaticFiles(directory=cfg.samples_dir), name="samples")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health():
        pipe = get_pipeline()
        return {
            "status": "ok",
            "schema_version": SCHEMA_VERSION,
            "ocr": getattr(pipe.ocr, "name", "?"),
            "detector": getattr(pipe.detector, "name", "?"),
            "tts": {"configured": pipe.tts.configured(), "available": pipe.tts.available(), "errors": pipe.tts.last_errors},
            "allergens": list(ALLERGENS),
        }

    @app.get("/api/samples")
    def samples():
        out = []
        for meta_path in sorted(cfg.samples_dir.glob("S*.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            out.append({"id": meta_path.stem, "title": meta.get("title", meta_path.stem), "url": f"/samples/{meta.get('image', meta_path.stem + '.jpg')}"})
        return out

    @app.post("/api/analyze")
    def analyze(
        image: UploadFile | None = File(None),
        sample_id: str | None = Form(None),
        allergens: str = Form("[]"),
        today: str | None = Form(None),
        audio: bool = Form(True),
        speed: float = Form(1.0),
    ):
        if image is not None:
            limit = cfg.max_upload_mb * 1024 * 1024
            data = image.file.read(limit + 1)
            if len(data) > limit:
                raise HTTPException(413, f"사진은 {cfg.max_upload_mb}MB 까지 올릴 수 있다")
            if not data:
                raise HTTPException(400, "빈 파일")
            name = image.filename
        elif sample_id:
            if not _SAMPLE_ID.match(sample_id):
                raise HTTPException(400, "sample_id 형식이 틀렸다")
            path = cfg.samples_dir / f"{sample_id}.jpg"
            if not path.exists():
                raise HTTPException(404, "없는 샘플")
            data, name = path.read_bytes(), path.name
        else:
            raise HTTPException(400, "image 또는 sample_id 가 필요하다")

        profile = UserProfile(allergens=_parse_allergens(allergens))
        with lock:
            result = get_pipeline().analyze(
                data, profile=profile, today=_parse_today(today), name=name,
                with_audio=audio, speed=min(2.0, max(0.5, speed)),
            )
        return result.model_dump(mode="json")

    @app.post("/api/analyze-text")
    def analyze_text(req: TextRequest):
        with lock:
            result = get_pipeline().analyze_text(
                req.text, profile=UserProfile(allergens=req.allergens), today=req.today,
                with_audio=req.audio, speed=req.speed,
            )
        return result.model_dump(mode="json")

    @app.post("/api/tts")
    def tts(req: TTSRequest):
        pipe = get_pipeline()
        with lock:
            clip = pipe.tts.synthesize(req.text, speed=req.speed)
            path = pipe.tts.last_path
        if clip is None or path is None:
            return {"audio": None}
        return {"audio": {"engine": clip.engine, "mime": clip.mime, "url": cfg.audio_url_prefix + path.name, "seconds": clip.seconds}}

    @app.get("/api/audio/{name}")
    def audio_file(name: str):
        if not _AUDIO_NAME.match(name):
            raise HTTPException(404)
        path = cfg.audio_dir / name
        if not path.exists():
            raise HTTPException(404)
        return FileResponse(path, media_type="audio/mpeg" if name.endswith(".mp3") else "audio/wav")

    @app.post("/api/events")
    def events(req: EventRequest):
        if len(json.dumps(req.data, ensure_ascii=False)) > 2000:
            raise HTTPException(413, "기록이 너무 크다")
        cfg.log_dir.mkdir(parents=True, exist_ok=True)
        line = {**req.data, "time": dt.datetime.now(KST).isoformat(timespec="seconds"), "type": req.type}
        with (cfg.log_dir / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return {"ok": True}

    return app


app = create_app()
