"""제품 단위로 학습·검증·테스트 나누기.

같은 제품을 각도·조명만 바꿔 찍은 사진이 학습과 테스트에 섞이면 점수가 부풀려진다(데이터 누수).
그래서 사진이 아니라 제품 ID 로 나눈다. 결과(data/splits/*.txt)는 커밋해서 모두 같은 분할을 쓴다.

    python -m tools.make_splits --root /content/drive/MyDrive/DL-Team05/data
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from pathlib import Path

from packreader.config import REPO_ROOT

from .dataset import load_products, scan_images


def split_products(product_ids: list[str], ratios=(0.6, 0.2, 0.2), seed: int = 42, groups: dict[str, str] | None = None):
    """groups 를 주면(제품ID → 분류) 분류마다 같은 비율로 나눈다."""
    rng = random.Random(seed)
    buckets: dict[str, list[str]] = {}
    for pid in sorted(set(product_ids)):
        buckets.setdefault((groups or {}).get(pid, ""), []).append(pid)
    out = {"train": [], "val": [], "test": []}
    for key in sorted(buckets):
        ids = buckets[key]
        rng.shuffle(ids)
        n = len(ids)
        n_test = max(1, round(n * ratios[2])) if n >= 3 else 0
        n_val = max(1, round(n * ratios[1])) if n >= 3 else 0
        out["test"] += ids[:n_test]
        out["val"] += ids[n_test : n_test + n_val]
        out["train"] += ids[n_test + n_val :]
    return {k: sorted(v) for k, v in out.items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description="제품 단위 분할")
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default=str(REPO_ROOT / "data" / "splits"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--by-category", action="store_true", help="products.csv 의 category 별로 같은 비율")
    args = ap.parse_args(argv)

    root = Path(args.root)
    images, _ = scan_images(root / "images")
    groups = None
    if args.by_category:
        groups = {pid: t.category for pid, t in load_products(root / "labels" / "products.csv").items()}
    splits = split_products([m.product_id for m in images], seed=args.seed, groups=groups)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    per_image = Counter()
    which = {pid: name for name, ids in splits.items() for pid in ids}
    for m in images:
        per_image[which[m.product_id]] += 1
    for name, ids in splits.items():
        (out / f"{name}.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
        print(f"{name}: 제품 {len(ids)}개, 사진 {per_image[name]}장")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
