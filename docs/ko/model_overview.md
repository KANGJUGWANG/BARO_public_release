# 모델 개요

BARO 추천 모델은 항공권 구매 시점을 BUY 또는 WAIT으로 판단하기 위한 2-stage 구조를 사용합니다.

## Stage 1

Stage 1은 향후 가격 절감 가능성을 예측합니다. 이 값은 Stage 2가 BUY/WAIT 판단을 내릴 때 보조 feature로 사용됩니다.

## Stage 2

Stage 2는 가격 하락 가능성 및 관측 feature를 기반으로 BUY/WAIT 판단을 수행합니다.

## 표시 정책

프론트엔드에서는 `가격 하락 기대 강도` 게이지를 표시합니다.

- 편도 표시 기준: 80%
- 왕복 표시 기준: 65%

이 값은 UI 해석을 돕기 위한 기준선이며 실제 모델 artifact와 threshold 파일은 공개 레포에 포함하지 않습니다.

## Artifact Exclusion

모델 pkl, threshold json, 학습 중간 산출물은 공개 레포에서 제외합니다. 운영 inference는 private artifact가 배치된 환경에서만 완전하게 동작합니다.
