"""핵심 정보 추출, 날짜 해석, 알레르겐 매칭, 위험 판단.  담당: 이서영

지금 들어 있는 것은 기준선이다. 할 일은 tests/test_extract_spec.py 의 xfail 항목부터:
- 두 자리 연도(26.11.20), OCR 오타(O↔0, l↔1), 점 글씨 날짜, '제조일로부터 n개월'
- 원재료 괄호 속 알레르기 성분(밀가루(밀), 탈지분유(우유))
- 표준 문구가 아닌 혼입 문구('혼입될 수 있습니다' 등)
- 항목별 F1, 위험 놓침률, 보류율 측정 (evaluation/run_eval.py)
"""

from .allergens import ALLERGENS, canonical, canonicalize_list, find_allergens
from .fields import extract_fields
from .risk import assess_risk

__all__ = ["ALLERGENS", "canonical", "canonicalize_list", "find_allergens", "extract_fields", "assess_risk"]
