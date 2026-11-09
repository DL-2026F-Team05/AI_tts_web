"""안내 문장 순서와 문구. 문구를 바꾸면 이 테스트도 같이 고친다."""

import datetime as dt

from packreader.schema import Allergens, Expiry, Fields, Quality, TextField, UserProfile
from packreader.speech.compose import compose, date_words, expiry_sentence, retake_sentence

TODAY = dt.date(2026, 11, 10)


def make_fields(status="ok", date=dt.date(2026, 11, 22), kind="use_by", contains=(), may=(), hits=(), may_hits=(), name="바삭 고소칩", conf=0.95):
    days = (date - TODAY).days if date else None
    return Fields(
        product_name=TextField(value=name, conf=0.97) if name else TextField(),
        expiry=Expiry(raw="x", date=date, kind=kind, status=status, days_left=days if status != "unknown" else None, conf=conf),
        allergens=Allergens(contains=list(contains), may_contain=list(may), user_hits=list(hits), user_may_hits=list(may_hits), conf=0.95),
    )


def keys(speech):
    return [i.key for i in speech.items]


def test_ok_without_profile():
    f = make_fields(contains=["밀", "우유"])
    s = compose(f, today=TODAY)
    assert keys(s) == ["expiry", "product", "allergen_info"]
    assert s.summary == "소비기한은 11월 22일까지예요. 12일 남았어요. 제품은 바삭 고소칩이에요. 알레르기 표시는 밀, 우유예요."


def test_user_allergen_comes_first_with_warning():
    f = make_fields(contains=["밀", "우유"], may=["땅콩"], hits=["우유"], may_hits=["땅콩"])
    s = compose(f, profile=UserProfile(allergens=["우유", "땅콩"]), today=TODAY)
    assert keys(s) == ["allergen_user", "allergen_may", "expiry", "product"]
    assert s.items[0].text == "주의하세요. 우유가 들어 있어요."
    assert s.items[1].text == "땅콩이 섞였을 수 있어요."  # '같은 시설' 설명은 더 듣기로


def test_expired_is_danger_and_first_without_hits():
    f = make_fields(status="expired", date=dt.date(2026, 10, 30))
    s = compose(f, today=TODAY)
    assert keys(s)[0] == "expiry"
    assert s.items[0].text == "주의하세요. 소비기한이 지났어요. 10월 30일까지였어요."


def test_warning_word_only_once():
    f = make_fields(status="expired", date=dt.date(2026, 10, 30), contains=["우유"], hits=["우유"])
    s = compose(f, profile=UserProfile(allergens=["우유"]), today=TODAY)
    assert s.summary.count("주의하세요") == 1
    assert keys(s)[:2] == ["allergen_user", "expiry"]


def test_profile_without_hits_says_not_found():
    f = make_fields(contains=["밀"])
    s = compose(f, profile=UserProfile(allergens=["땅콩"]), today=TODAY)
    assert "등록한 알레르기 성분은 찾지 못했어요." in s.summary
    assert "allergen_info" not in keys(s)


def test_soon_and_today():
    f = make_fields(status="soon", date=dt.date(2026, 11, 12))
    assert compose(f, today=TODAY).items[0].text == "소비기한이 2일 남았어요. 11월 12일까지예요."
    f = make_fields(status="soon", date=TODAY)
    assert compose(f, today=TODAY).items[0].text == "소비기한이 오늘까지예요."


def test_sell_by_label():
    f = make_fields(kind="sell_by", date=dt.date(2026, 11, 25))
    assert compose(f, today=TODAY).items[0].text.startswith("유통기한은 11월 25일까지예요.")


def test_date_words_relative_year():
    assert date_words(dt.date(2026, 3, 15), TODAY) == "3월 15일"
    assert date_words(dt.date(2027, 3, 15), TODAY) == "내년 3월 15일"
    assert date_words(dt.date(2025, 12, 30), TODAY) == "작년 12월 30일"
    assert date_words(dt.date(2028, 3, 15), TODAY) == "2028년 3월 15일"


def test_far_date_skips_days_left():
    f = make_fields(date=dt.date(2027, 3, 15))
    assert compose(f, today=TODAY).items[0].text == "소비기한은 내년 3월 15일까지예요."
    f = make_fields(date=dt.date(2026, 12, 10))  # 30일 남음 → 말함
    assert compose(f, today=TODAY).items[0].text == "소비기한은 12월 10일까지예요. 30일 남았어요."


def test_hedged_product_name():
    f = make_fields()
    f.product_name = TextField(value="바싹 고소집", conf=0.41)
    s = compose(f, today=TODAY)
    assert s.items[-1].text == "제품은 바싹 고소집으로 보여요."
    f.product_name = TextField(value="든든 두유", conf=0.41)
    assert compose(f, today=TODAY).items[-1].text == "제품은 든든 두유로 보여요."
    f.product_name = TextField(value="바색 고소집", conf=0.13)
    assert "product" not in keys(compose(f, today=TODAY))


def test_hedged_name_alone_is_not_enough():
    f = Fields(product_name=TextField(value="바싹 고소집", conf=0.41))
    assert keys(compose(f, today=TODAY, n_boxes=3)) == ["product", "no_info"]


def test_elsewhere_and_unknown():
    e = Expiry(status="elsewhere", kind="use_by", raw="소비기한: 별도표기일까지")
    assert expiry_sentence(e, TODAY).startswith("소비기한은 다른 곳에 따로 찍혀 있어요.")
    e = Expiry(status="unknown", raw="20?7.0?.1?")
    assert expiry_sentence(e, TODAY).startswith("소비기한을 정확히 읽지 못했어요.")
    assert expiry_sentence(Expiry(), TODAY).startswith("소비기한은 찾지 못했어요.")


def test_date_with_unknown_kind_is_hedged():
    e = Expiry(status="ok", kind="unknown", date=dt.date(2026, 12, 24), days_left=44, conf=0.83)
    assert expiry_sentence(e, TODAY) == "표시된 날짜는 12월 24일이에요."
    e = Expiry(status="ok", kind="unknown", date=dt.date(2026, 11, 24), days_left=14, conf=0.83)
    assert expiry_sentence(e, TODAY) == "표시된 날짜는 11월 24일이에요. 14일 남았어요."


def test_retake_when_nothing_reliable():
    f = Fields(product_name=TextField(value="바삭 고 칩", conf=0.41))
    s = compose(f, quality=Quality(issues=["blur", "dark"], retake=True), today=TODAY, n_boxes=2)
    assert keys(s) == ["retake"]
    assert s.summary == "사진 상태가 좋지 않아요. 밝은 곳에서 휴대폰을 멈춘 채로 다시 찍어 주세요."


def test_no_text_and_no_info():
    assert keys(compose(Fields(), today=TODAY, n_boxes=0)) == ["no_text"]
    assert keys(compose(Fields(), today=TODAY, n_boxes=5)) == ["no_info"]


def test_retake_sentence_single():
    assert retake_sentence(["glare"]).startswith("빛이 반사돼서")
    assert retake_sentence(["blur"]) == "사진이 흔들렸어요. 휴대폰을 멈춘 채로 다시 찍어 주세요."


def test_detail_contents_and_low_conf_note():
    f = make_fields(contains=["밀"], may=["땅콩"], conf=0.62)
    f.ingredients = TextField(value="원재료명: 밀가루(밀), 설탕", conf=0.9)
    f.nutrition = TextField(value="영양정보: 100kcal", conf=0.9)
    d = compose(f, today=TODAY).detail
    assert "알레르기 표시: 밀." in d
    assert "같은 시설에서 쓰는 성분: 땅콩." in d
    assert "원재료: 밀가루(밀), 설탕." in d
    assert "영양정보: 100kcal." in d
    assert "틀린 내용이 있을 수 있어요" in d


def test_long_ingredients_are_clipped():
    f = make_fields()
    f.ingredients = TextField(value=", ".join(["재료"] * 100), conf=0.9)
    d = compose(f, today=TODAY).detail
    assert d.count("재료") < 60
    assert "등." in d
