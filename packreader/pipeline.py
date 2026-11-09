"""전체 연결: 사진 → 품질 체크·전처리 → 영역 검출·OCR → 정보 추출·위험 판단 → 안내 문장 → TTS.  담당: 박세준

각 단계가 실패해도 멈추지 않고 errors 에 적은 뒤 다음 단계로 넘어간다.
시연 중에 한 모듈이 터져도 사용자는 "다시 찍어 주세요" 같은 안내는 듣게 하려는 것.

    from packreader.pipeline import Pipeline
    result = Pipeline().analyze("data/samples/S001.jpg")
    print(result.speech.summary)
"""

from __future__ import annotations

import datetime as dt
import logging
import time
import uuid
from contextlib import contextmanager

from .config import KST, Config, kst_today
from .extract import assess_risk, extract_fields
from .io import load_image
from .ocr import ReadContext, get_detector, get_ocr_engine, run_ocr
from .preprocess import assess_quality, dot_kernels, enhance, join_dots
from .schema import AnalysisResult, Audio, ImageInfo, Speech, SpeechItem, StageError, TextBox, UserProfile
from .speech import compose
from .speech.tts import TTSManager

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, cfg: Config | None = None, *, ocr=None, detector=None, tts: TTSManager | None = None):
        self.cfg = cfg or Config.from_env()
        self.ocr = ocr if ocr is not None else get_ocr_engine(self.cfg)
        self.detector = detector if detector is not None else get_detector(self.cfg)
        self.tts = tts if tts is not None else TTSManager.from_names(
            self.cfg.tts_engines, self.cfg.audio_dir, self.cfg.tts_voice
        )

    # ------------------------------------------------------------------ 공개 함수
    def analyze(
        self,
        image,
        *,
        profile: UserProfile | None = None,
        today: dt.date | None = None,
        name: str | None = None,
        with_audio: bool = True,
        speed: float = 1.0,
    ) -> AnalysisResult:
        """image: bytes | 파일 경로 | numpy RGB 배열 | PIL.Image"""
        res = self._new_result(today)
        t_all = time.perf_counter()

        loaded = None
        with self._stage(res, "load"):
            loaded = load_image(image, self.cfg.max_side, name=name)
            w, h = loaded.size
            res.image = ImageInfo(
                name=loaded.name, sha1=loaded.sha1, width=w, height=h,
                orig_width=loaded.orig_size[0], orig_height=loaded.orig_size[1],
            )
        if loaded is None:
            res.speech = Speech(
                summary="사진을 열지 못했어요. 다시 찍어 주세요.",
                items=[SpeechItem(key="load_error", text="사진을 열지 못했어요. 다시 찍어 주세요.")],
            )
            return self._finish(res, t_all, with_audio, speed)

        rgb = loaded.rgb
        with self._stage(res, "preprocess"):
            res.quality = assess_quality(rgb, self.cfg)
            rgb, res.preprocess_ops = enhance(rgb, res.quality, self.cfg)

        ctx = ReadContext(sha1=loaded.sha1, name=loaded.name, scale=loaded.scale)
        with self._stage(res, "ocr"):
            res.regions, res.boxes = run_ocr(self.ocr, self.detector, rgb, ctx)

        # 사진은 멀쩡한데 글자를 하나도 못 읽었으면 점 글씨(뚜껑·바닥 날짜)일 수 있다 → 점을 이어 붙여 한 번 더
        ocr_failed = any(e.stage == "ocr" for e in res.errors)  # 엔진이 고장 난 거면 다시 해 봐야 소용없다
        if not ocr_failed and not res.quality.retake and not self._readable(res.boxes):
            with self._stage(res, "ocr_retry"):
                for k in dot_kernels(rgb):
                    regions, boxes = run_ocr(self.ocr, self.detector, join_dots(rgb, k), ctx)
                    if self._readable(boxes):
                        res.regions, res.boxes = regions, boxes
                        res.preprocess_ops.append(f"join_dots{k}")
                        break

        self._understand(res, profile)
        return self._finish(res, t_all, with_audio, speed)

    def analyze_text(
        self,
        text: str,
        *,
        profile: UserProfile | None = None,
        today: dt.date | None = None,
        with_audio: bool = True,
        speed: float = 1.0,
    ) -> AnalysisResult:
        """OCR 을 건너뛰고 글자만으로 추출·안내를 돌린다. 줄바꿈 = OCR 한 줄."""
        res = self._new_result(today)
        t_all = time.perf_counter()
        res.engines["ocr"] = "text"
        res.boxes = [TextBox(text=line.strip(), conf=1.0) for line in text.splitlines() if line.strip()]
        self._understand(res, profile)
        return self._finish(res, t_all, with_audio, speed)

    def warmup(self) -> None:
        for part in (self.ocr, self.detector):
            if hasattr(part, "warmup"):
                try:
                    part.warmup()
                except Exception as exc:  # pragma: no cover - 모델 다운로드 실패 등
                    log.warning("%s 미리 올리기 실패: %s", getattr(part, "name", part), exc)
        self.tts.warmup()

    # ------------------------------------------------------------------ 내부
    def _new_result(self, today: dt.date | None) -> AnalysisResult:
        return AnalysisResult(
            request_id=uuid.uuid4().hex[:12],
            created_at=dt.datetime.now(KST),
            today=today or kst_today(),
            engines={"ocr": getattr(self.ocr, "name", "?"), "detector": getattr(self.detector, "name", "?")},
        )

    @contextmanager
    def _stage(self, res: AnalysisResult, stage: str):
        t0 = time.perf_counter()
        try:
            yield
        except Exception as exc:
            log.exception("단계 %s 실패", stage)
            res.errors.append(StageError(stage=stage, message=f"{type(exc).__name__}: {exc}"))
        finally:
            res.timing_ms[stage] = round((time.perf_counter() - t0) * 1000, 1)

    def _readable(self, boxes: list[TextBox]) -> bool:
        return any(b.conf >= self.cfg.min_box_conf and len(b.text.strip()) >= 2 for b in boxes)

    def _understand(self, res: AnalysisResult, profile: UserProfile | None) -> None:
        with self._stage(res, "extract"):
            res.fields = extract_fields(res.boxes, profile, res.today, self.cfg)
            res.risk = assess_risk(res.fields)
        with self._stage(res, "compose"):
            # 점 글씨처럼 엉뚱하게 읽힌 박스(신뢰도 아주 낮음, 한 글자짜리)는 빼고 센다
            readable = sum(b.conf >= self.cfg.min_box_conf and len(b.text.strip()) >= 2 for b in res.boxes)
            res.speech = compose(res.fields, res.risk, res.quality, profile, res.today, readable, self.cfg)
        if res.speech is None:
            msg = "분석 중에 문제가 생겼어요. 다시 찍어 주세요."
            res.speech = Speech(summary=msg, items=[SpeechItem(key="error", text=msg)])

    def _finish(self, res: AnalysisResult, t_all: float, with_audio: bool, speed: float) -> AnalysisResult:
        if with_audio and res.speech:
            with self._stage(res, "tts"):
                clip = self.tts.synthesize(res.speech.summary, speed=speed)
                if clip is not None:
                    url = self.cfg.audio_url_prefix + self.tts.last_path.name if self.tts.last_path else None
                    res.audio = Audio(engine=clip.engine, mime=clip.mime, url=url, seconds=clip.seconds)
        res.engines["tts"] = res.audio.engine if res.audio else "browser"
        res.timing_ms["total"] = round((time.perf_counter() - t_all) * 1000, 1)
        return res
