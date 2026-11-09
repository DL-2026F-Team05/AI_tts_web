"""데이터 규칙, 제품 단위 분할, 평가 실행 (합성 샘플로 만든 작은 데이터셋)."""

import json
import shutil

from evaluation.run_eval import main as run_eval
from tools.dataset import check, load_products, parse_name
from tools.make_splits import split_products

from conftest import SAMPLES


def test_parse_name():
    m = parse_name("P023_back_lowlight_01.jpg")
    assert (m.product_id, m.face, m.condition, m.index) == ("P023", "back", "lowlight", 1)
    assert parse_name("P023_back_lowlight_1.jpg") is None
    assert parse_name("IMG_1234.jpg") is None
    assert parse_name("P023_side_normal_01.jpg") is None
    assert parse_name("P023_back_normal_01.txt") is None


def test_split_is_by_product_and_stable():
    ids = [f"P{i:03d}" for i in range(1, 21)]
    a = split_products(ids, seed=1)
    b = split_products(ids, seed=1)
    assert a == b
    all_ids = a["train"] + a["val"] + a["test"]
    assert sorted(all_ids) == ids  # 빠짐도 겹침도 없음
    assert len(a["test"]) == 4 and len(a["val"]) == 4


def make_dataset(root):
    (root / "images").mkdir(parents=True)
    (root / "labels" / "boxes").mkdir(parents=True)
    pairs = {
        "P001_back_normal_01": "S001",
        "P002_back_normal_01": "S002",
        "P003_back_normal_01": "S003",
        "P003_date_normal_01": "S005",
        "P001_back_blur_01": "S004",
    }
    for new, sid in pairs.items():
        shutil.copy(SAMPLES / f"{sid}.jpg", root / "images" / f"{new}.jpg")
        meta = json.loads((SAMPLES / f"{sid}.json").read_text(encoding="utf-8"))
        if sid == "S004":  # 흐린 사진의 정답은 원본(S001)과 같은 글자
            meta = json.loads((SAMPLES / "S001.json").read_text(encoding="utf-8"))
        (root / "labels" / "boxes" / f"{new}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (root / "labels" / "products.csv").write_text(
        "product_id,product_name,category,expiry_date,expiry_kind,expiry_face,allergens_contains,allergens_may,notes\n"
        "P001,바삭 고소칩,과자,2027-03-15,use_by,back,밀;대두;우유,땅콩;새우,\n"
        "P002,부드러운 우유 푸딩,디저트,2026-10-30,use_by,back,우유;알류;대두,,\n"
        "P003,든든 두유,음료,2026-12-24,use_by,date,대두,땅콩;호두,\n",
        encoding="utf-8",
    )


def test_dataset_check(tmp_path):
    make_dataset(tmp_path)
    (tmp_path / "images" / "IMG_0001.jpg").write_bytes(b"x")
    r = check(tmp_path)
    assert r["images"] == 5 and r["products_in_csv"] == 3
    assert r["bad_names"] == ["images/IMG_0001.jpg"]
    assert r["missing_in_csv"] == [] and r["missing_date_face"] == []
    assert load_products(tmp_path / "labels" / "products.csv")["P001"].allergens_may == ["땅콩", "새우"]


def test_run_eval_end_to_end(tmp_path):
    root = tmp_path / "data"
    make_dataset(root)
    splits = tmp_path / "splits"
    splits.mkdir()
    (splits / "test.txt").write_text("P001\nP002\nP003\n", encoding="utf-8")
    out = tmp_path / "out"
    rep = run_eval(["--root", str(root), "--split-dir", str(splits), "--ocr", "dummy", "--today", "2026-11-10", "--out", str(out)])

    assert rep["n_images"] == 5
    assert (out / "per_image.csv").exists() and (out / "summary.md").exists()
    # 가짜 OCR 은 정답을 돌려주니 깨끗한 사진의 CER 은 0, 흐린 사진(S004)만 틀린다
    assert rep["by_condition"]["normal"]["cer"] == 0
    assert rep["by_condition"]["blur"]["cer"] > 0.5
    # 날짜가 보이는 사진: P001 back(정상), P001 blur(보류), P002 back(지남), P003 date(종류 모름)
    e = rep["expiry"]
    assert e["n"] == 4
    assert e["missed_expired_rate"] == 0
    assert e["abstain_rate"] == 0.25
    # P003 back 은 날짜가 다른 면이라 '다른 곳에 표기'로 답해야 맞다
    assert rep["expiry_not_visible"]["hallucination_rate"] == 0
    assert rep["allergen_contains"]["micro"]["recall"] < 1  # 흐린 사진에서 놓침
    json.loads((out / "report.json").read_text(encoding="utf-8"))
