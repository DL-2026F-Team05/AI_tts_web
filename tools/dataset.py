"""촬영 데이터 규칙 (파일 이름, 정답표) 읽기와 검사.

파일 이름: {제품ID}_{면}_{조건}_{번호}.jpg   예) P023_back_lowlight_01.jpg
  제품ID  P001 ~ P9999
  면      front(앞면) | back(표시사항) | date(날짜가 따로 찍힌 곳) | etc
  조건    normal | lowlight | glare | blur | crumple | curve | angle
  번호    01 ~ 99

검사:  python -m tools.dataset --root /content/drive/MyDrive/DL-Team05/data
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

FACES = ("front", "back", "date", "etc")
CONDITIONS = ("normal", "lowlight", "glare", "blur", "crumple", "curve", "angle")
IMAGE_EXTS = (".jpg", ".jpeg", ".png")
FILENAME_RE = re.compile(
    rf"^(?P<pid>P\d{{3,4}})_(?P<face>{'|'.join(FACES)})_(?P<cond>{'|'.join(CONDITIONS)})_(?P<idx>\d{{2}})$"
)
PRODUCT_COLUMNS = (
    "product_id", "product_name", "category", "expiry_date", "expiry_kind", "expiry_face",
    "allergens_contains", "allergens_may", "notes",
)


@dataclass
class ImageMeta:
    path: Path
    product_id: str
    face: str
    condition: str
    index: int


@dataclass
class ProductTruth:
    product_id: str
    product_name: str = ""
    category: str = ""
    expiry_date: dt.date | None = None
    expiry_kind: str = "use_by"
    expiry_face: str = "back"
    allergens_contains: list[str] = field(default_factory=list)
    allergens_may: list[str] = field(default_factory=list)
    notes: str = ""


def parse_name(path: str | Path) -> ImageMeta | None:
    p = Path(path)
    if p.suffix.lower() not in IMAGE_EXTS:
        return None
    m = FILENAME_RE.match(p.stem)
    if not m:
        return None
    return ImageMeta(p, m["pid"], m["face"], m["cond"], int(m["idx"]))


def scan_images(images_dir: str | Path) -> tuple[list[ImageMeta], list[Path]]:
    """(규칙에 맞는 사진, 이름이 틀린 파일)"""
    good, bad = [], []
    for p in sorted(Path(images_dir).rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        meta = parse_name(p)
        (good.append(meta) if meta else bad.append(p))
    return good, bad


def _split_list(value: str) -> list[str]:
    return [v.strip() for v in re.split(r"[;,]", value or "") if v.strip()]


def load_products(csv_path: str | Path) -> dict[str, ProductTruth]:
    out: dict[str, ProductTruth] = {}
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = (row.get("product_id") or "").strip()
            if not pid:
                continue
            date_text = (row.get("expiry_date") or "").strip()
            out[pid] = ProductTruth(
                product_id=pid,
                product_name=(row.get("product_name") or "").strip(),
                category=(row.get("category") or "").strip(),
                expiry_date=dt.date.fromisoformat(date_text) if date_text else None,
                expiry_kind=(row.get("expiry_kind") or "use_by").strip() or "use_by",
                expiry_face=(row.get("expiry_face") or "back").strip() or "back",
                allergens_contains=_split_list(row.get("allergens_contains", "")),
                allergens_may=_split_list(row.get("allergens_may", "")),
                notes=(row.get("notes") or "").strip(),
            )
    return out


def check(root: str | Path) -> dict:
    root = Path(root)
    images, bad = scan_images(root / "images")
    products_csv = root / "labels" / "products.csv"
    products = load_products(products_csv) if products_csv.exists() else {}
    pids = {m.product_id for m in images}
    report = {
        "images": len(images),
        "bad_names": [str(p.relative_to(root)) for p in bad],
        "products_with_images": len(pids),
        "products_in_csv": len(products),
        "missing_in_csv": sorted(pids - set(products)),
        "no_images": sorted(set(products) - pids),
        "by_condition": dict(Counter(m.condition for m in images)),
        "by_face": dict(Counter(m.face for m in images)),
        "missing_date_face": sorted(
            pid for pid, t in products.items()
            if t.expiry_face == "date" and not any(m.product_id == pid and m.face == "date" for m in images)
        ),
    }
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="촬영 데이터 규칙 검사")
    ap.add_argument("--root", required=True, help="images/ 와 labels/ 가 있는 데이터 폴더")
    args = ap.parse_args(argv)
    r = check(args.root)
    print(f"사진 {r['images']}장, 제품 {r['products_with_images']}개 (정답표 {r['products_in_csv']}개)")
    print("조건별:", r["by_condition"])
    print("면별:", r["by_face"])
    for key, label in (
        ("bad_names", "이름 규칙이 틀린 파일"),
        ("missing_in_csv", "정답표에 없는 제품"),
        ("no_images", "사진이 없는 제품"),
        ("missing_date_face", "날짜가 다른 곳에 있는데 date 사진이 없는 제품"),
    ):
        if r[key]:
            print(f"\n[{label}] {len(r[key])}개")
            for x in r[key][:30]:
                print("  ", x)
    if not any(r[k] for k in ("bad_names", "missing_in_csv")):
        print("\n규칙 문제 없음")


if __name__ == "__main__":
    main()
