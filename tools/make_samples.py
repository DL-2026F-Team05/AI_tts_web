"""데모·테스트용 합성 포장 사진과 정답 JSON 만들기.

    python -m tools.make_samples            # data/samples 에 S001~S006 생성
    python -m tools.make_samples --font C:/Windows/Fonts/malgun.ttf

제품명은 모두 지어낸 것이다. 정답 JSON 의 boxes 는 DummyOCR 출력이자 박스 라벨 형식 예시다.
날짜를 바꾸고 싶으면 SAMPLES 의 날짜만 고치고 다시 실행하면 된다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from packreader.config import REPO_ROOT

FONT_CANDIDATES = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1),
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0),
    ("C:/Windows/Fonts/malgun.ttf", 0),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
]
BOLD_CANDIDATES = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1),
    ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", 0),
    ("C:/Windows/Fonts/malgunbd.ttf", 0),
]

W, H = 1200, 900


def _font(size: int, bold: bool = False, override: str | None = None):
    if override:
        return ImageFont.truetype(override, size)
    for path, idx in (BOLD_CANDIDATES if bold else []) + FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=idx)
    raise SystemExit("한글 글꼴을 못 찾았다. --font 로 경로를 넘겨 줘 (예: C:/Windows/Fonts/malgun.ttf)")


class Canvas:
    def __init__(self, bg, font_override=None):
        self.img = Image.new("RGB", (W, H), bg)
        self.draw = ImageDraw.Draw(self.img)
        self.boxes: list[dict] = []
        self.font_override = font_override

    def text(self, xy, text, size, region=None, bold=False, fill=(30, 30, 30), conf=0.97, anchor="la"):
        font = _font(size, bold, self.font_override)
        self.draw.text(xy, text, font=font, fill=fill, anchor=anchor)
        x1, y1, x2, y2 = self.draw.textbbox(xy, text, font=font, anchor=anchor)
        pad = 4
        poly = [[x1 - pad, y1 - pad], [x2 + pad, y1 - pad], [x2 + pad, y2 + pad], [x1 - pad, y2 + pad]]
        self.boxes.append({"text": text, "conf": conf, "poly": poly, "region": region})
        return y2

    def panel(self, box, fill=(244, 244, 240), outline=(120, 120, 120)):
        self.draw.rounded_rectangle(box, radius=14, fill=fill, outline=outline, width=3)


def label_height(ingredients, allergen_line, facility_lines, **_) -> int:
    """back_label 이 그릴 내용의 아래 끝 y (패널 크기를 내용에 맞추려고)."""
    return 265 + 48 + 40 * len(ingredients) + 10 + (66 if allergen_line else 0) + 40 * len(facility_lines) + 10 + 56 + 44 + 40


def back_label(c: Canvas, name, sub, ingredients, allergen_line, facility_lines, expiry_line, storage, nutrition):
    c.text((W // 2, 70), name, 76, region="product_name", bold=True, anchor="ma")
    c.text((W // 2, 170), sub, 34, region="other", anchor="ma", fill=(80, 80, 80))
    bottom = label_height(ingredients, allergen_line, facility_lines) + 30
    c.panel((50, 240, W - 50, bottom))
    y = 265
    c.text((80, y), f"제품명: {name} | {sub}", 26, region="product_name")
    y += 48
    for line in ingredients:
        c.text((80, y), line, 26, region="ingredients")
        y += 40
    y += 10
    if allergen_line:
        c.draw.rectangle((70, y - 8, W - 70, y + 44), outline=(200, 60, 40), width=3)
        c.text((86, y), allergen_line, 28, region="allergen", bold=True, fill=(150, 30, 20))
        y += 66
    for line in facility_lines:
        c.text((80, y), line, 26, region="allergen")
        y += 40
    y += 10
    c.text((80, y), expiry_line, 30, region="expiry", bold=True)
    y += 56
    c.text((80, y), storage, 26, region="caution")
    y += 44
    c.text((80, y), nutrition, 26, region="nutrition")


SAMPLES = [
    {
        "id": "S001",
        "title": "과자 뒷면",
        "bg": (240, 226, 200),
        "label": dict(
            name="바삭 고소칩",
            sub="감자칩 60g",
            ingredients=["원재료명: 감자(국산), 식물성유지(대두유), 밀가루(밀),", "탈지분유(우유), 정제소금, 설탕"],
            allergen_line="알레르기 유발물질: 밀, 대두, 우유 함유",
            facility_lines=["이 제품은 땅콩, 새우를 사용한 제품과", "같은 제조시설에서 제조하고 있습니다."],
            expiry_line="소비기한: 2027.03.15까지",
            storage="보관방법: 직사광선을 피해 서늘한 곳에 보관하세요.",
            nutrition="영양정보: 총 내용량 60g, 320kcal, 나트륨 180mg",
        ),
    },
    {
        "id": "S002",
        "title": "푸딩 뒷면 (소비기한 지남)",
        "bg": (232, 236, 245),
        "label": dict(
            name="부드러운 우유 푸딩",
            sub="디저트 120g",
            ingredients=["원재료명: 우유(국산), 설탕, 계란, 바닐라향, 젤라틴"],
            allergen_line="알레르기 유발물질: 우유, 알류(계란), 대두 함유",
            facility_lines=[],
            expiry_line="소비기한: 2026.10.30까지",
            storage="보관방법: 냉장보관(0~10℃)",
            nutrition="영양정보: 총 내용량 120g, 165kcal, 나트륨 70mg",
        ),
    },
    {
        "id": "S003",
        "title": "두유 뒷면 (날짜는 다른 곳에)",
        "bg": (236, 242, 228),
        "label": dict(
            name="든든 두유",
            sub="두유 190mL",
            ingredients=["원재료명: 정제수, 대두(국산), 설탕, 정제소금"],
            allergen_line="대두 함유",
            facility_lines=["이 제품은 땅콩, 호두를 사용한 제품과", "같은 제조시설에서 제조하고 있습니다."],
            expiry_line="소비기한: 별도표기일까지",
            storage="보관방법: 직사광선을 피하고 실온 보관",
            nutrition="영양정보: 총 내용량 190mL, 120kcal, 나트륨 95mg",
        ),
    },
    {
        "id": "S006",
        "title": "우유 팩 (유통기한 표기)",
        "bg": (228, 238, 246),
        "label": dict(
            name="신선 우유",
            sub="우유 900mL",
            ingredients=["원재료명: 원유 100%(국산)"],
            allergen_line="우유 함유",
            facility_lines=[],
            expiry_line="유통기한: 2026.11.25까지",
            storage="보관방법: 냉장보관(0~10℃)",
            nutrition="영양정보: 200mL당 130kcal, 나트륨 100mg",
        ),
    },
]


def make_back(spec, font=None):
    c = Canvas(spec["bg"], font)
    back_label(c, **spec["label"])
    bottom = label_height(**spec["label"]) + 30
    c.img = c.img.crop((0, 0, W, min(H, bottom + 40)))  # 아래 빈 공간 자르기 (좌표는 그대로)
    return c


def make_blurred(base: Canvas):
    """S004: S001 을 흔들리고 어둡게. OCR 이 제대로 못 읽은 상황을 흉내 낸다."""
    img = base.img.filter(ImageFilter.GaussianBlur(6))
    img = ImageEnhance.Brightness(img).enhance(0.18)
    boxes = []
    for b in base.boxes:
        if b["region"] == "product_name" and b["text"].startswith("바삭"):
            boxes.append({**b, "text": "바삭 고 칩", "conf": 0.41})
        elif b["region"] == "expiry":
            boxes.append({**b, "text": "소비기한: 20?7.0?.1?까지", "conf": 0.22})
    return img, boxes


def make_dot_date(font=None):
    """S005: 뚜껑·바닥에 점 글씨로 따로 찍힌 날짜."""
    c = Canvas((205, 205, 200), font)
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)
    f = _font(150, True, font)
    lines = [("2026.12.24", 300), ("L2 0314", 520)]
    boxes = []
    for text, y in lines:
        d.text((W // 2, y), text, font=f, fill=255, anchor="mm")
        x1, y1, x2, y2 = d.textbbox((W // 2, y), text, font=f, anchor="mm")
        boxes.append(
            {"text": text, "conf": 0.83 if "." in text else 0.7,
             "poly": [[x1 - 6, y1 - 6], [x2 + 6, y1 - 6], [x2 + 6, y2 + 6], [x1 - 6, y2 + 6]],
             "region": "expiry" if "." in text else "other"}
        )
    dots = Image.new("L", (W, H), 0)
    dd = ImageDraw.Draw(dots)
    step, r = 14, 5
    for yy in range(0, H, step):
        for xx in range(0, W, step):
            dd.ellipse((xx - r, yy - r, xx + r, yy + r), fill=255)
    mask = Image.fromarray(np.minimum(np.array(layer), np.array(dots)))
    c.img.paste((40, 40, 45), (0, 0), mask)
    return c.img, boxes


def save(out_dir: Path, sid: str, title: str, img: Image.Image, boxes: list[dict]):
    img.save(out_dir / f"{sid}.jpg", quality=90)
    meta = {
        "image": f"{sid}.jpg",
        "title": title,
        "note": "합성 샘플. boxes 는 DummyOCR 출력이자 박스 라벨 형식 예시 (좌표는 이미지 픽셀)",
        "boxes": boxes,
    }
    (out_dir / f"{sid}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO_ROOT / "data" / "samples"))
    ap.add_argument("--font", default=None, help="한글 글꼴 파일 경로")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    built = {}
    for spec in SAMPLES:
        c = make_back(spec, args.font)
        built[spec["id"]] = c
        save(out, spec["id"], spec["title"], c.img, c.boxes)
    img, boxes = make_blurred(built["S001"])
    save(out, "S004", "과자 뒷면 (흔들리고 어두움)", img, boxes)
    img, boxes = make_dot_date(args.font)
    save(out, "S005", "바닥에 찍힌 날짜 (점 글씨)", img, boxes)
    print(f"샘플 {len(SAMPLES) + 2}개를 {out} 에 만들었다")


if __name__ == "__main__":
    main()
