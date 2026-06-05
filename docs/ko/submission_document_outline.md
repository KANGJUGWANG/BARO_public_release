# 제출용 진행 문서 목차 제안

## 목적

교수 제출용 또는 발표 보조 문서에 들어갈 목차를 확정한다. 각 목차는 근거 문서, 코드 경로, 대표 수치와 연결된다.

## 권장 목차

| 번호 | 목차 | 포함 내용 | 근거 문서 | 코드 경로 | 대표 수치 |
| ---: | --- | --- | --- | --- | --- |
| 1 | 프로젝트 개요 | BARO 서비스 목적, BUY/WAIT 구매 시점 추천 | v1.0.0 anchor, project_timeline_v2 | frontend/src/App.jsx | - |
| 2 | 문제 정의와 주제 접근 | 단순 검색이 아닌 구매 타이밍 문제 | v0.x anchor, project_decision_journey_v2 | frontend/src/web/pages/HomePage.jsx | - |
| 3 | 데이터 수집 및 저장 구조 | 반복 관측, search/offer observation | schema 문서, data pipeline 문서 | backend/crawler, src/loaders | 2026-04-16 시작 |
| 4 | EDA 및 초기 모델링 | 가격 변동성, 초기 label 설계 | docs/eda/eda_report.md, label_design.md | experiments/eda, experiments/modeling | 변동성/라벨 근거 |
| 5 | 모델 개선 과정 | BUY regret 문제, Exp-C 기준 | Phase 13~14 문서 | backend/tools/phase_14_* | BUY regret 15.94%, WAIT success 41.52% |
| 6 | Stage1/Stage2 모델 구조 | pred_saving, wait_probability, threshold | final_modeling_summary, runtime contract | backend/ml_inference/model_runtime.py | threshold 기반 decision |
| 7 | 최종 학습 데이터 조건 | freeze 기간, trainable rows | Phase 16A~16B 문서 | backend/tools/phase_16b_* | 4,562,741 rows |
| 8 | 평가 기준과 결과 | threshold review, final model result | Phase 16B-3C | backend/tools/phase_16b_3c_* | 편도 0.80, 왕복 0.65 |
| 9 | backend API와 serving 구조 | candidates, prediction, history, route-analysis | API contract 문서 | backend/recommend, backend/flights | - |
| 10 | frontend UI/UX | 카드, 상세, 모델 안내, 가격 하락 기대 강도 | Phase 11, Phase 16E | frontend/src/web | - |
| 11 | 배포 및 시연 | Vercel, APK, Android resources | Phase 12, deploy docs | frontend/android, deploy | build pass |
| 12 | 재현성 안내 | 공개 repo로 가능한 것과 불가능한 것 | reproducibility_scope_v2 | docs, backend, frontend | Level 0~4 |
| 13 | 공개/비공개 경계 | 모델/DB/secret 제외 이유 | public_private_boundary, cleanup docs | .gitignore, examples | scan hit 0 |
| 14 | 한계와 향후 개선 | pipeline 정리, sample data, public skeleton | pipeline_restructure_plan | future pipelines | - |

## 제출 문서 작성 원칙

- 실제 운영 주소와 개인 경로를 쓰지 않는다.
- 모델 바이너리와 원천 DB는 포함하지 않는다.
- 수치는 근거 문서가 있는 것만 사용한다.
- 재현 범위는 공개 repo 기준과 private asset 필요 기준을 분리한다.
- UI 문구는 “가격 보장”이 아니라 “구매 보조”로 설명한다.
