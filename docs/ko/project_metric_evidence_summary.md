# BARO 주요 근거 수치 요약

## 데이터 범위

최종 full retrain 기준 공개 가능한 데이터 요약은 다음과 같다.

| 항목 | 값 |
| --- | ---: |
| 수집 기간 | 2026-04-16 08:00 ~ 2026-06-04 00:00 |
| 관측 시점 | 147개 |
| 서비스 DB 관측 수 | 141,120건 |
| 학습 가능 항공권 row | 4,562,741건 |
| 편도 학습 row | 989,669건 |
| 왕복 학습 row | 3,573,072건 |

## Exp-C 선택 근거

Phase 14-8 기준 Exp-C는 Exp-A 대비 다음과 같이 개선됐다.

| 지표 | Exp-A | Exp-C | 해석 |
| --- | ---: | ---: | --- |
| BUY regret | 20.79% | 15.94% | BUY 추천 후 의미 있는 하락을 놓치는 비율 감소 |
| WAIT success | 31.37% | 41.52% | WAIT 추천 후 의미 있는 하락이 발생한 비율 증가 |

동시에 Stage1 정렬은 강하지 않았다.

| 정렬 지표 | 값 | 해석 |
| --- | ---: | --- |
| pred_saving vs 72h max drop Pearson | 0.2693 | Stage1과 72h 결과의 선형 정렬은 약함 |
| pred_saving vs Exp-C label Pearson | 0.2093 | Exp-C label과의 직접 정렬도 약함 |

이 때문에 Phase 15 직행 대신 fresh Stage1 보완 검증과 최종 full retrain을 거쳤다.

## 최종 운영 기준

| trip | model_version | threshold |
| --- | --- | ---: |
| 편도 | finaltest_expc_full_final_v1_thr065_oneway | 0.80 |
| 왕복 | finaltest_expc_full_final_v1_thr065_roundtrip | 0.65 |

Phase 16B-3C threshold review에서 공개 가능한 요약값은 다음과 같다.

| trip | threshold | BUY regret | WAIT success |
| --- | ---: | ---: | ---: |
| 편도 | 0.80 | 8.56% | 83.06% |
| 왕복 | 0.65 | 18.93% | 75.24% |

위 값은 공개 설명용 요약이며, 원천 데이터와 모델 바이너리는 공개 저장소에 포함하지 않는다.
