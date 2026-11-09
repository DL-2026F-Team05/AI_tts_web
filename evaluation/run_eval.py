"""분할 하나(기본 test)를 파이프라인으로 돌려 지표를 계산한다. 정의는 docs/eval_protocol.md

    python -m evaluation.run_eval --root /content/drive/MyDrive/DL-Team05/data --ocr easyocr --out outputs/eval_easyocr

데이터 폴더 구조
    images/P001_back_normal_01.jpg ...
    labels/products.csv            제품 단위 정답 (tools/dataset.py 참고)
    labels/boxes/<사진이름>.json     글자 박스 정답 (있을 때만 CER·검출 지표 계산)
분할 파일은 저장소의 data/splits/<split>.txt (제품 ID 목록)

결과: per_image.csv, report.json, summary.md
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

from packreader.config import REPO_ROOT, Config
from packreader.extract.allergens import ALLERGENS
from packreader.ocr.base import poly_bbox, reading_order
from packreader.pipeline import Pipeline
from packreader.schema import REGION_NAMES, TextBox
from packreader.speech.tts import TTSManager
from tools.dataset import ImageMeta, ProductTruth, load_products, scan_images

from .metrics import cer, confusion_matrix, corpus_error, coverage_risk, macro_f1, match_boxes, prf, set_counts


def load_box_labels(path: Path) -> list[TextBox] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    boxes = data["boxes"] if isinstance(data, dict) else data
    return [TextBox.model_validate(b) for b in boxes]


def expected_status(truth: ProductTruth, today: dt.date, soon_days: int) -> str | None:
    if truth.expiry_date is None:
        return None
    days = (truth.expiry_date - today).days
    return "expired" if days < 0 else ("soon" if days <= soon_days else "ok")


def evaluate_image(meta: ImageMeta, res, truth: ProductTruth, gt_boxes: list[TextBox] | None, today, cfg) -> dict:
    rec: dict = {
        "image": meta.path.name, "product_id": meta.product_id, "face": meta.face, "condition": meta.condition,
        "total_ms": res.timing_ms.get("total", 0.0), "ocr_ms": res.timing_ms.get("ocr", 0.0),
        "n_boxes": len(res.boxes), "errors": "; ".join(e.stage for e in res.errors),
    }
    pred_text = " ".join(b.text for b in res.boxes)

    # 1) OCR (박스 정답이 있을 때만)
    if gt_boxes is not None:
        gt_text = " ".join(b.text for b in reading_order(gt_boxes))
        rec["gt_text"], rec["pred_text"] = gt_text, pred_text
        rec["cer"] = round(cer(gt_text, pred_text), 4)
        gt_bb = [poly_bbox(b.poly) for b in gt_boxes if b.poly]
        pr_bb = [poly_bbox(b.poly) for b in res.boxes if b.poly]
        matched, fp, fn = match_boxes(gt_bb, pr_bb)
        rec["det_tp"], rec["det_fp"], rec["det_fn"] = len(matched), fp, fn
        gt_with_poly = [b for b in gt_boxes if b.poly]
        pr_with_poly = [b for b in res.boxes if b.poly]
        rec["region_pairs"] = [
            (gt_with_poly[i].region or "other", pr_with_poly[j].region or "none") for i, j in matched
        ]

    # 2) 소비기한: 이 사진에 날짜가 보이는가 (박스 정답 우선, 없으면 면으로 판단)
    #    '별도표기일까지'처럼 숫자가 없는 소비기한 칸은 날짜가 안 보이는 것으로 친다
    if gt_boxes is not None:
        date_visible = truth.expiry_date is not None and any(
            b.region == "expiry" and re.search(r"\d", b.text) for b in gt_boxes
        )
    else:
        date_visible = meta.face == truth.expiry_face and truth.expiry_date is not None
    exp = res.fields.expiry
    rec["date_visible"] = date_visible
    rec["pred_date"] = exp.date.isoformat() if exp.date else ""
    rec["pred_status"] = exp.status
    rec["pred_conf"] = round(exp.conf, 4)
    if date_visible:
        gt_status = expected_status(truth, today, cfg.soon_days)
        rec["gt_date"] = truth.expiry_date.isoformat()
        rec["gt_status"] = gt_status
        rec["date_correct"] = exp.date == truth.expiry_date
        rec["abstained"] = exp.status in ("unknown", "elsewhere")
        rec["missed_expired"] = gt_status == "expired" and exp.status in ("ok", "soon")
        rec["wrong_date_spoken"] = (not rec["abstained"]) and exp.date != truth.expiry_date
    else:
        rec["hallucinated_date"] = exp.status in ("ok", "soon", "expired")

    # 3) 알레르기 (표시사항 면이거나 박스 정답에 알레르기 영역이 있을 때)
    if gt_boxes is not None:
        allergen_visible = any(b.region == "allergen" for b in gt_boxes)
    else:
        allergen_visible = meta.face == "back"
    rec["allergen_visible"] = allergen_visible
    if allergen_visible:
        rec["gt_contains"] = ";".join(truth.allergens_contains)
        rec["pred_contains"] = ";".join(res.fields.allergens.contains)
        rec["gt_may"] = ";".join(truth.allergens_may)
        rec["pred_may"] = ";".join(res.fields.allergens.may_contain)

    # 4) 제품명
    if truth.product_name and meta.face in ("front", "back"):
        rec["name_cer"] = round(cer(truth.product_name, res.fields.product_name.value or ""), 4)
    return rec


def summarize(records: list[dict]) -> dict:
    rep: dict = {"n_images": len(records)}

    ocr = [r for r in records if "cer" in r]
    if ocr:
        rep["ocr"] = {
            "n": len(ocr),
            "cer": round(corpus_error([(r["gt_text"], r["pred_text"]) for r in ocr], "char"), 4),
            "wer": round(corpus_error([(r["gt_text"], r["pred_text"]) for r in ocr], "word"), 4),
        }
        tp, fp, fn = (sum(r[k] for r in ocr) for k in ("det_tp", "det_fp", "det_fn"))
        p, rr, f = prf(tp, fp, fn)
        rep["detection"] = {"precision": round(p, 4), "recall": round(rr, 4), "f1": round(f, 4)}
        pairs = [pair for r in ocr for pair in r.get("region_pairs", [])]
        if pairs:
            labels = list(REGION_NAMES) + ["none"]
            rep["region_confusion"] = {
                "labels": labels,
                "matrix": confusion_matrix([a for a, _ in pairs], [b for _, b in pairs], labels),
            }

    vis = [r for r in records if r.get("date_visible")]
    if vis:
        expired = [r for r in vis if r["gt_status"] == "expired"]
        rep["expiry"] = {
            "n": len(vis),
            "date_accuracy": round(sum(r["date_correct"] for r in vis) / len(vis), 4),
            "abstain_rate": round(sum(r["abstained"] for r in vis) / len(vis), 4),
            "wrong_date_spoken_rate": round(sum(r["wrong_date_spoken"] for r in vis) / len(vis), 4),
            "missed_expired_rate": round(sum(r["missed_expired"] for r in expired) / len(expired), 4) if expired else None,
            "coverage_risk": coverage_risk([(r["pred_conf"], r["date_correct"]) for r in vis]),
        }
    hidden = [r for r in records if "hallucinated_date" in r]
    if hidden:
        rep["expiry_not_visible"] = {
            "n": len(hidden),
            "hallucination_rate": round(sum(r["hallucinated_date"] for r in hidden) / len(hidden), 4),
        }

    alg = [r for r in records if r.get("allergen_visible")]
    if alg:
        per = {a: [0, 0, 0] for a in ALLERGENS}
        for r in alg:
            t = set(filter(None, r["gt_contains"].split(";")))
            p = set(filter(None, r["pred_contains"].split(";")))
            for a in ALLERGENS:
                tp, fp, fn = set_counts({a} & t, {a} & p)
                per[a][0] += tp
                per[a][1] += fp
                per[a][2] += fn
        tp, fp, fn = (sum(v[i] for v in per.values()) for i in range(3))
        p, rr, f = prf(tp, fp, fn)
        rep["allergen_contains"] = {
            "n": len(alg),
            "micro": {"precision": round(p, 4), "recall": round(rr, 4), "f1": round(f, 4)},
            "macro_f1": round(macro_f1({k: tuple(v) for k, v in per.items()}), 4),
            "miss_rate": round(fn / (tp + fn), 4) if tp + fn else None,
            "per_item": {k: dict(zip(("tp", "fp", "fn"), v)) for k, v in per.items() if sum(v)},
        }

    names = [r["name_cer"] for r in records if "name_cer" in r]
    if names:
        rep["product_name_cer_mean"] = round(statistics.mean(names), 4)

    by_cond: dict[str, dict] = defaultdict(dict)
    for cond in sorted({r["condition"] for r in records}):
        rs = [r for r in records if r["condition"] == cond]
        row = {"n": len(rs)}
        o = [r for r in rs if "cer" in r]
        if o:
            row["cer"] = round(corpus_error([(r["gt_text"], r["pred_text"]) for r in o]), 4)
        v = [r for r in rs if r.get("date_visible")]
        if v:
            row["date_accuracy"] = round(sum(r["date_correct"] for r in v) / len(v), 4)
            row["abstain_rate"] = round(sum(r["abstained"] for r in v) / len(v), 4)
        by_cond[cond] = row
    rep["by_condition"] = dict(by_cond)
    rep["timing_ms"] = {
        "total_median": round(statistics.median(r["total_ms"] for r in records), 1) if records else None,
        "ocr_median": round(statistics.median(r["ocr_ms"] for r in records), 1) if records else None,
    }
    return rep


def summary_markdown(rep: dict, title: str) -> str:
    lines = [f"# 평가 결과: {title}", "", f"사진 {rep['n_images']}장", ""]
    if "ocr" in rep:
        lines += ["## OCR", "", "| CER | WER | 검출 P | 검출 R | 검출 F1 |", "|---|---|---|---|---|",
                  f"| {rep['ocr']['cer']} | {rep['ocr']['wer']} | {rep['detection']['precision']} | {rep['detection']['recall']} | {rep['detection']['f1']} |", ""]
    if "expiry" in rep:
        e = rep["expiry"]
        lines += ["## 소비기한 (날짜가 보이는 사진)", "", "| 날짜 정확도 | 보류율 | 틀린 날짜를 말한 비율 | 지난 제품을 놓친 비율 |", "|---|---|---|---|",
                  f"| {e['date_accuracy']} | {e['abstain_rate']} | {e['wrong_date_spoken_rate']} | {e['missed_expired_rate']} |", ""]
    if "expiry_not_visible" in rep:
        lines += [f"날짜가 안 보이는 사진에서 날짜를 지어낸 비율: {rep['expiry_not_visible']['hallucination_rate']}", ""]
    if "allergen_contains" in rep:
        a = rep["allergen_contains"]
        lines += ["## 알레르기 함유", "", "| micro P | micro R | micro F1 | macro F1 | 놓친 비율 |", "|---|---|---|---|---|",
                  f"| {a['micro']['precision']} | {a['micro']['recall']} | {a['micro']['f1']} | {a['macro_f1']} | {a['miss_rate']} |", ""]
    if rep.get("by_condition"):
        lines += ["## 촬영 조건별", "", "| 조건 | 사진 수 | CER | 날짜 정확도 | 보류율 |", "|---|---|---|---|---|"]
        for cond, row in rep["by_condition"].items():
            lines.append(f"| {cond} | {row['n']} | {row.get('cer', '-')} | {row.get('date_accuracy', '-')} | {row.get('abstain_rate', '-')} |")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description="파이프라인 평가")
    ap.add_argument("--root", required=True, help="images/, labels/ 가 있는 데이터 폴더")
    ap.add_argument("--split", default="test")
    ap.add_argument("--split-dir", default=str(REPO_ROOT / "data" / "splits"))
    ap.add_argument("--ocr", default=None, help="dummy | easyocr | paddle (기본: PACK_OCR 또는 dummy)")
    ap.add_argument("--today", default=None, help="소비기한 기준 날짜 YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--limit", type=int, default=0, help="앞에서 n장만 (빠른 확인용)")
    ap.add_argument("--out", default="outputs/eval")
    args = ap.parse_args(argv)

    root = Path(args.root)
    overrides = {"ocr_engine": args.ocr} if args.ocr else {}
    cfg = Config.from_env(**overrides)
    pipe = Pipeline(cfg, tts=TTSManager([]))
    today = dt.date.fromisoformat(args.today) if args.today else None

    split_file = Path(args.split_dir) / f"{args.split}.txt"
    keep = set(split_file.read_text(encoding="utf-8").split()) if split_file.exists() else None
    if keep is None:
        print(f"[알림] {split_file} 이 없어서 전체 사진으로 평가한다")
    products = load_products(root / "labels" / "products.csv")
    images, _ = scan_images(root / "images")
    images = [m for m in images if (keep is None or m.product_id in keep) and m.product_id in products]
    if args.limit:
        images = images[: args.limit]

    records = []
    for i, meta in enumerate(images, 1):
        res = pipe.analyze(meta.path, today=today, with_audio=False)
        gt = load_box_labels(root / "labels" / "boxes" / f"{meta.path.stem}.json")
        records.append(evaluate_image(meta, res, products[meta.product_id], gt, res.today, cfg))
        if i % 20 == 0:
            print(f"{i}/{len(images)}")

    rep = summarize(records)
    rep["settings"] = {
        "ocr": pipe.ocr.name,
        "detector": pipe.detector.name,
        "split": args.split,
        "today": today.isoformat() if today else "실행한 날 (한국 시간)",
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for r in records for k in r if k != "region_pairs"})
    with (out / "per_image.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in records:
            w.writerow({k: v for k, v in r.items() if k != "region_pairs"})
    (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "summary.md").write_text(summary_markdown(rep, f"{pipe.ocr.name} / {args.split}"), encoding="utf-8")
    print(f"사진 {len(records)}장 평가 → {out}")
    return rep


if __name__ == "__main__":
    main()
