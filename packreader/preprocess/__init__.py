"""품질 체크와 전처리.  담당: 배창현

지금 들어 있는 것은 기준선이다.
- quality.assess_quality: 선명도(라플라시안 분산), 밝기, 반사광 비율로 다시 찍기 여부 판정
- enhance.enhance: 어두울 때 CLAHE 로 대비 올리기
- enhance.join_dots: 점 글씨 날짜의 점 이어 붙이기 (첫 OCR 이 아무것도 못 읽었을 때 파이프라인이 다시 시도)

할 일 (배창현)
- 실제 촬영 데이터로 Config 의 기준값(blur_threshold 등) 다시 정하기
- 반사광 제거, 기울기·원근 보정, 구김/곡면 보정 등 보정 방법 추가
- 촬영 조건별로 보정 전후 CER 비교표 만들기 (evaluation/run_eval.py 결과 활용)
"""

from .enhance import dot_kernels, enhance, join_dots
from .quality import assess_quality

__all__ = ["assess_quality", "enhance", "join_dots", "dot_kernels"]
