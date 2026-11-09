# 모듈끼리의 약속

모든 단계가 `AnalysisResult` 하나(`packreader/schema.py`)를 채워서 넘긴다. 전체 JSON 스키마는 [schema.json](schema.json), 실제 결과 예시는 [example_result.json](example_result.json).

## 단계별 함수

| 단계 | 담당 | 함수 | 입력 | 출력 |
|---|---|---|---|---|
| 읽기 | 공통 | `io.load_image(source, max_side)` | 바이트·경로·배열 | `LoadedImage` (RGB 배열, EXIF 회전 보정) |
| 품질 | 배창현 | `preprocess.assess_quality(rgb, cfg)` | RGB | `Quality` |
| 보정 | 배창현 | `preprocess.enhance(rgb, quality, cfg)` | RGB | (RGB, 적용한 보정 이름들). **크기는 바꾸지 않는다** |
| 영역 검출 | 이도현 | `RegionDetector.detect(rgb)` | RGB | `list[Region]` |
| OCR | 이도현 | `OCREngine.read(rgb, ctx)` | RGB | `list[TextBox]` (좌표는 입력 이미지 픽셀) |
| 추출 | 이서영 | `extract.extract_fields(boxes, profile, today, cfg)` | 글자 박스 | `Fields` |
| 위험 판단 | 이서영 | `extract.assess_risk(fields)` | `Fields` | `Risk` |
| 안내 문장 | 박세준 | `speech.compose(fields, risk, quality, profile, today, n_boxes, cfg)` | | `Speech` |
| TTS | 박세준 | `TTSManager.synthesize(text, speed)` | 문장 | `AudioClip` 또는 `None`(브라우저 음성) |

새 엔진은 같은 모양의 클래스를 만들면 된다. OCR 엔진 예:

```python
class MyOCR:
    name = "my_ocr"
    supports_crops = True  # 영역별로 잘라 읽어도 되면 True

    def read(self, rgb, ctx=None) -> list[TextBox]:
        ...
        return [TextBox(text="소비기한 2027.03.15까지", conf=0.93, poly=[(x1, y1), (x2, y1), (x2, y2), (x1, y2)])]
```

`packreader/ocr/__init__.py`의 `get_ocr_engine`에 이름을 추가하면 `PACK_OCR=my_ocr`로 쓸 수 있다.

## 주요 필드

| 필드 | 뜻 |
|---|---|
| `quality.issues` | `blur`, `dark`, `glare`, `small` 중 해당하는 것 |
| `quality.retake` | 다시 찍기를 권할지 |
| `regions[].name` | `product_name`, `expiry`, `allergen`, `ingredients`, `nutrition`, `caution`, `other` (검출기 학습 클래스 이름과 같게) |
| `boxes[]` | OCR 한 줄: `text`, `conf`(0~1), `poly`(네 꼭짓점), `region` |
| `fields.expiry.kind` | `use_by`(소비기한), `sell_by`(유통기한), `best_before`(품질유지기한), `unknown` |
| `fields.expiry.status` | `ok`, `soon`(기준 3일 이하), `expired`, `elsewhere`(다른 면에 표기), `unknown`(판단 보류) |
| `fields.allergens.contains` / `may_contain` | 함유 / 같은 제조시설 등 혼입 가능. 이름은 표준 19종(`extract.allergens.ALLERGENS`) |
| `fields.allergens.user_hits` / `user_may_hits` | 사용자가 등록한 성분과 겹친 것 |
| `risk.level` | `danger`, `caution`, `ok`, `unknown` |
| `risk.reasons` | `allergen_contains`, `expired`, `allergen_may`, `expiry_soon`, `expiry_unknown`, `expiry_elsewhere` |
| `speech.summary` / `detail` | 바로 읽는 문장 / '더 듣기' 문장 |
| `speech.items[].key` | `retake`, `no_text`, `no_info`, `allergen_user`, `expiry`, `allergen_may`, `allergen_none`, `product`, `allergen_info` |
| `engines` | 단계별로 실제 쓴 엔진 (`tts`가 `browser`면 서버 음성 없이 브라우저가 읽음) |
| `timing_ms` | 단계별 처리 시간 |
| `errors` | 실패한 단계와 이유. 실패해도 다음 단계는 계속한다 |

## 바꾸는 규칙
- 필드를 더하는 건 괜찮다. 이름을 바꾸거나 지우면 다른 모듈이 깨지니 먼저 알린다.
- 바꾼 뒤 `python -m tools.export_schema`로 schema.json, example_result.json을 다시 만든다.
- 소비기한 계산 기준 날짜는 한국 시간(`config.kst_today()`). 코랩 서버 시간(UTC)을 그대로 쓰면 아침 9시 전에 하루 틀린다.
