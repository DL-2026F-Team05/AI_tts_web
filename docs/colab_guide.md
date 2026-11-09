# 코랩에서 개발하기

## 처음 한 번
1. README의 Open in Colab 배지로 `notebooks/00_setup_and_demo.ipynb`를 연다
2. 런타임 > 런타임 유형 변경 > **T4 GPU** (OCR·TTS 모델 돌릴 때)
3. 위에서부터 셀 실행: 레포 받기 → 설치 → 테스트 → 샘플 돌리기 → 웹 데모

코랩은 세션이 끝나면 `/content`가 지워진다. 매번 노트북 첫 셀(레포 받기·설치)부터 다시 돌린다. 데이터와 결과는 드라이브에 둔다.

## 자주 쓰는 셀

```python
# 레포 받기 / 최신으로
import os
REPO = "/content/AI_tts_web"
if not os.path.exists(REPO):
    !git clone -q https://github.com/DL-2026F-Team05/AI_tts_web.git {REPO}
else:
    !git -C {REPO} pull -q
%cd {REPO}
!pip install -q -r requirements.txt -r requirements-dev.txt
```

```python
# 드라이브 (촬영 데이터)
from google.colab import drive
drive.mount("/content/drive")
DATA = "/content/drive/MyDrive/DL-Team05/data"
```

```python
# 엔진 바꾸기
import os
os.environ["PACK_OCR"] = "easyocr"      # dummy | easyocr | paddle
os.environ["PACK_TTS"] = "melo,edge,gtts"
```

## 엔진 설치

| 엔진 | 설치 |
|---|---|
| EasyOCR | `!pip install -q easyocr` |
| PaddleOCR (CPU) | `!pip install -q paddlepaddle paddleocr` |
| PaddleOCR (GPU) | paddlepaddle-gpu는 [공식 설치 안내](https://www.paddlepaddle.org.cn/en/install/quick)에서 코랩 CUDA 버전에 맞는 명령을 쓴다 |
| YOLO 영역 검출 | `!pip install -q ultralytics` |
| edge-tts, gTTS, MMS | `!pip install -q -r requirements-tts.txt` |
| MeloTTS | `notebooks/01_tts_compare.ipynb`의 설치 셀 |

설치 후 "런타임을 다시 시작하라"는 안내가 뜨면 다시 시작하고 레포 받기 셀부터 다시 돌린다.

## 웹 데모 띄우기
노트북 00의 마지막 부분. 두 가지 주소가 나온다.
- **코랩 프록시 주소**: 내 브라우저에서만 열린다. PC로 확인할 때
- **cloudflared 주소** (`https://xxxx.trycloudflare.com`): 폰에서도 열린다. HTTPS라 폰 카메라도 된다. 시연용

## 코드 고치고 올리기
코랩에서 바로 푸시하려면 깃허브 토큰이 필요하다.
1. GitHub > Settings > Developer settings > Fine-grained tokens > 이 레포만 Contents: Read and write
2. 코랩 왼쪽 열쇠 아이콘(Secrets)에 이름 `GH_TOKEN`으로 저장 (노트북 접근 허용)
3. 아래 셀. 토큰은 출력하지도, 노트북에 적지도 않는다.

```python
from google.colab import userdata
token = userdata.get("GH_TOKEN")
!git config user.name "내 이름"
!git config user.email "내 깃허브 이메일"
!git checkout -b ocr/easyocr-baseline        # 내 브랜치
!git add -A && git commit -m "EasyOCR 기준선 결과"
!git push https://{token}@github.com/DL-2026F-Team05/AI_tts_web.git HEAD
```

그다음 GitHub에서 PR을 연다. 코드 편집이 많으면 VS Code에서 고치고 코랩은 실행만 하는 쪽이 편하다.

## 자주 나는 문제
- `ModuleNotFoundError: packreader`: `%cd /content/AI_tts_web`를 안 했다
- 설치 후 import 오류: 런타임 다시 시작 후 첫 셀부터
- 드라이브 폴더가 안 보임: 공유 폴더에 "바로가기 추가"를 안 했다
- 소비기한 날짜가 하루 틀림: `date.today()` 대신 `packreader.config.kst_today()` 사용
