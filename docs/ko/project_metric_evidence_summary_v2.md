# BARO 근거 수치 요약 v2

## docs 전수 인덱싱 수치

| 항목 | 값 |
| --- | ---: |
| 원본 docs 파일 수 | 210 |
| 수치 근거 후보 문서 | 139 |
| 경로/민감정보 위험 후보 문서 | 60 |
| P0 핵심 근거 후보 | 45 |
| P1 보조 근거 후보 | 77 |

## 데이터/학습 범위

| 항목 | 값 |
| --- | ---: |
| 수집 기간 | 2026-04-16 08:00 ~ 2026-06-04 00:00 |
| 관측 시점 | 147개 |
| 서비스 DB 관측 수 | 141,120건 |
| 학습 가능 항공권 row | 4,562,741건 |
| 편도 학습 row | 989,669건 |
| 왕복 학습 row | 3,573,072건 |

## Exp-C 기준 선택 근거

| 지표 | Exp-A | Exp-C | 해석 |
| --- | ---: | ---: | --- |
| BUY regret | 20.79% | 15.94% | BUY 추천 후 의미 있는 하락을 놓치는 비율 감소 |
| WAIT success | 31.37% | 41.52% | WAIT 추천 후 의미 있는 하락 발생 비율 증가 |

Stage1 정렬은 약했다.

| 지표 | 값 |
| --- | ---: |
| pred_saving vs 72h max drop Pearson | 0.2693 |
| pred_saving vs Exp-C label Pearson | 0.2093 |
| compact matched rows | 11,939 |
| oneway route holdout issue | 244 rows |

따라서 Exp-C를 바로 운영 확정하지 않고 fresh Stage1 검증, staging package, final full retrain을 거쳤다.

## 최종 운영 모델 요약

| trip | model_version | threshold |
| --- | --- | ---: |
| 편도 | finaltest_expc_full_final_v1_thr065_oneway | 0.80 |
| 왕복 | finaltest_expc_full_final_v1_thr065_roundtrip | 0.65 |

## threshold review 요약

| trip | threshold | BUY regret | WAIT success |
| --- | ---: | ---: | ---: |
| 편도 | 0.80 | 8.56% | 83.06% |
| 왕복 | 0.65 | 18.93% | 75.24% |

## 공개 repo 검증 요약

Phase 3 공개 repo 정리 단계에서 build/compile/secret/large file scan이 수행됐다. 이 수치는 public release 상태를 설명하기 위한 보조 근거이며, 원본 private repo의 전체 품질 보증을 의미하지는 않는다.
