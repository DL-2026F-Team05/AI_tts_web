# 같이 작업하는 규칙

## 브랜치
- `main`에는 직접 올리지 않는다. 자기 브랜치에서 작업하고 PR을 올린다.
- 브랜치 이름: `역할/내용` 예) `ocr/easyocr-baseline`, `extract/two-digit-year`, `preprocess/glare`
- PR은 박세준이 한 바퀴(사진 → 음성) 돌려 보고 머지한다.

## PR 올리기 전에
1. `python -m pytest -q`가 통과하는지 확인 (코랩: `!python -m pytest -q`)
2. 결과 형식(`packreader/schema.py`)을 바꿨다면 `python -m tools.export_schema`를 실행하고, `docs/interface.md`도 고친다
3. 내 모듈의 xfail 테스트를 통과시켰다면 xfail 표시를 지운다

## 올리지 않는 것
- 촬영 사진, 라벨 원본, 모델 가중치: 팀 드라이브에 둔다 (`.gitignore`에 막혀 있음)
- API 키, 깃허브 토큰: 코랩 비밀(Secrets)에만 둔다

## 내 모듈을 바꿀 때
- 함수 이름과 입출력(인터페이스)은 그대로 두고 안쪽만 바꾸면 다른 사람 코드에 영향이 없다
- 인터페이스를 바꿔야 하면 PR에 적고 박세준에게 먼저 알린다
- 새 OCR·TTS 엔진은 같은 모양의 클래스를 만들고 `get_ocr_engine` / `ENGINES`에 이름만 추가한다

## 커밋 메시지
한국어로 무엇을 했는지 한 줄. 예) `날짜 파서: 두 자리 연도 처리`
