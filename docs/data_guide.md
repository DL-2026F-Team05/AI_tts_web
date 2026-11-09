# 데이터 가이드

## 무엇을 찍나
집에 있는 식품 포장, 한 사람당 10개 정도. 제품마다 이 면들을 찍는다.

| 면 (`face`) | 무엇 | 필수 |
|---|---|---|
| `back` | 표시사항 면 (원재료, 알레르기, 소비기한) | 필수 |
| `front` | 앞면 (제품명) | 권장 |
| `date` | 날짜가 따로 찍힌 곳 (뚜껑, 바닥, 윗면 점 글씨) | 날짜가 따로 있으면 필수 |
| `etc` | 그 밖의 면 | 선택 |

`back`은 조건을 바꿔 여러 장 찍는다.

| 조건 (`condition`) | 찍는 법 |
|---|---|
| `normal` | 밝은 곳, 정면, 손 고정 |
| `lowlight` | 불 끈 방이나 그늘 |
| `glare` | 형광등·창문 빛이 비닐에 반사되게 |
| `blur` | 살짝 흔들리게 |
| `crumple` | 구긴 봉지 |
| `curve` | 병·캔처럼 휜 면 |
| `angle` | 비스듬히 (약 45도) |

목표: 제품마다 `back_normal` + 조건 2~3가지 + `front` 1장 (+ `date`) = 5~6장. 7명 × 10개면 400장 정도.

## 파일 이름

```
{제품ID}_{면}_{조건}_{번호}.jpg
P023_back_lowlight_01.jpg
```

- 제품ID는 사람마다 구간을 나눠서 겹치지 않게: 이도현 P001~P099, 배창현 P100~P199, 이서영 P200~P299, 박세준 P300~P399, 박주윤 P400~P499, 백연경 P500~P599, 김세희 P600~P699
- 규칙 검사: `python -m tools.dataset --root <데이터 폴더>`

## 촬영 팁
- 폰 기본 카메라, 기본 해상도. 아이폰은 설정 > 카메라 > 포맷 > **높은 호환성**(JPG)
- 손가락이 글자를 가리지 않게
- 영수증, 택배 송장, 얼굴처럼 개인정보가 보이는 건 찍지 않는다

## 정답표 `labels/products.csv`
양식: [data/templates/products_template.csv](../data/templates/products_template.csv) (UTF-8)

| 열 | 쓰는 법 |
|---|---|
| `product_id` | P023 |
| `product_name` | 포장에 적힌 제품명 |
| `category` | 과자, 음료, 유제품, 라면, 소스 등 |
| `expiry_date` | 2027-03-15 (모르면 비움) |
| `expiry_kind` | `use_by`(소비기한), `sell_by`(유통기한), `best_before`(품질유지기한) |
| `expiry_face` | 날짜가 있는 면: `back` 또는 `date` 등 |
| `allergens_contains` | 함유 성분, `;`로 구분. 표준 이름 19종만: 알류;우유;메밀;땅콩;대두;밀;잣;호두;게;새우;오징어;고등어;조개류;복숭아;토마토;닭고기;돼지고기;쇠고기;아황산류 |
| `allergens_may` | "같은 제조시설" 문구에 나온 성분 |
| `notes` | 특이사항 |

제품당 한 줄이라 빠르다. 이것만 있어도 소비기한·알레르기·위험 판단 평가가 된다.

## 글자 박스 라벨 `labels/boxes/{사진이름}.json` (테스트셋만)
CER, 검출 지표, 영역 혼동행렬에 필요하다. 시간이 많이 들어서 테스트셋만 한다.

```json
{
  "boxes": [
    {"text": "소비기한: 2027.03.15까지", "poly": [[80, 640], [470, 640], [470, 680], [80, 680]], "region": "expiry"}
  ]
}
```

- `region`은 `product_name`, `expiry`, `allergen`, `ingredients`, `nutrition`, `caution`, `other`
- 기성 OCR 결과를 먼저 넣어 두고 Label Studio에서 고치면 빠르다 (변환 스크립트는 이도현)
- 형식 예시: `data/samples/*.json`

## 드라이브 구조

```
DL-Team05/data/
  images/       P001_back_normal_01.jpg ...
  labels/
    products.csv
    boxes/      P001_back_normal_01.json ...
```

- 공유받은 폴더는 내 드라이브에 **바로가기 추가**를 해야 코랩에서 보인다
- 코랩 경로: `/content/drive/MyDrive/DL-Team05/data`

## 분할
같은 제품을 조건만 바꿔 찍은 사진이 학습과 테스트에 섞이면 점수가 부풀려진다. 그래서 제품 ID로 나눈다.

```
python -m tools.make_splits --root /content/drive/MyDrive/DL-Team05/data
```

나온 `data/splits/*.txt`는 커밋해서 모두 같은 분할을 쓴다. 분할은 한 번 정하면 바꾸지 않는다.
