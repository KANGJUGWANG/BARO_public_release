# 핵심 근거 문서 세트

이 문서는 공개/제출 문서에 반드시 반영할 근거 문서를 4개 묶음으로 정리한다.

## A. 프로젝트 진행 근거

| 문서 경로 | 역할 | 공개 문서 반영 내용 | 비공개 제외 내용 | 대표 수치/결론 |
| --- | --- | --- | --- | --- |
| docs/v0.2.1/project_anchor.md | 초기 문제와 범위 | 항공권 가격 변동 문제와 대상 노선 정의 | 초기 내부 메모 | 초기 기획 근거 |
| docs/v0.4.3/anchor.md | 수집 운영 시작 | 반복 관측과 운영 시작 흐름 | 운영 세부 환경 | 2026-04-16 운영 시작 기록 |
| docs/v0.4.3/schema.md | DB 저장 구조 | observation 중심 저장 구조 | DB 원문/민감 설정 | search/offer 관측 구조 |
| docs/eda/eda_report.md | EDA 근거 | 가격 변동성과 데이터 품질 | raw data | 가격 변동성 존재 |
| docs/v1.0.0/anchor.md | Phase 9 마감 | 웹/APK/왕복/분석 기능 완성 흐름 | 내부 TODO | 기능 마감 기준 |

## B. 모델 의사결정 근거

| 문서 경로 | 역할 | 공개 문서 반영 내용 | 비공개 제외 내용 | 대표 수치/결론 |
| --- | --- | --- | --- | --- |
| docs/modeling/label_design.md | 초기 라벨 | BUY=0, WAIT=1, 미래 절약 가능성 | raw data | 변동성 기반 라벨 |
| docs/modeling/final_modeling_summary_clean_v1.md | 초기 모델 구조 | Stage1/Stage2 구조 | artifact 경로 | pred_saving + WAIT probability |
| docs/phase_13_4_label_metric_threshold_decision.md | 문제 재정의 | BUY ratio보다 BUY regret이 핵심 | 내부 분석 경로 | 72h, 20,000원, 3% 후보 |
| docs/phase_13_5_retraining_experiment_design.md | 실험 설계 | threshold/calibration/holdout 분리 | 내부 output | Exp-C 실험 설계 |
| docs/phase_14_8_stage1_alignment_holdout_validation.md | Exp-C 검증 | Exp-C가 Exp-A 대비 우세 | 내부 output 경로 | BUY regret 15.94%, WAIT success 41.52% |
| docs/phase_16b_3b_full_retrain_final_refit.md | full retrain | final rows와 Stage1/Stage2 refit | private workspace 경로 | 편도 989,669 rows, 왕복 3,573,072 rows |
| docs/phase_16b_3c_baseline_threshold_review.md | threshold review | 편도 0.80, 왕복 0.65 근거 | 내부 output 경로 | 왕복 0.65가 BUY regret 감소 |
| docs/phase_16d_live_model_switch.md | 운영 반영 | live model_version과 threshold 확인 | 운영 경로/명령 | 최종 모델 live 적용 |

## C. 재현성 근거

| 문서 경로 | 역할 | 공개 문서 반영 내용 | 비공개 제외 내용 | 대표 수치/결론 |
| --- | --- | --- | --- | --- |
| backend/tools/phase_16b_2_full_dataset_materialization.py | dataset materialization | feature/label 생성 코드 위치 | private data path | private data 필요 |
| backend/tools/phase_16b_3b_full_retrain_final_refit.py | final retrain | Stage1/Stage2 학습 코드 위치 | artifact output path | full retrain script |
| backend/tools/phase_16b_3c_baseline_threshold_review.py | threshold sweep | threshold review 코드 위치 | 내부 output | threshold sensitivity |
| backend/tools/phase_16c_final_runtime_smoke.py | runtime smoke | model load/predict smoke 코드 | live env path | deployment 전 검증 |
| backend/ml_inference/model_runtime.py | runtime adapter | artifact load와 predict contract | model binary | serving runtime |
| backend/recommend/service.py | service layer | prediction/history/model-info logic | secret 없음 | API service contract |

## D. 공개/제출 정리 근거

| 문서 경로 | 역할 | 공개 문서 반영 내용 | 비공개 제외 내용 | 대표 수치/결론 |
| --- | --- | --- | --- | --- |
| docs/repo_cleanup_inventory.md | cleanup inventory | 공개/비공개 분류 기준 | raw hit 값 | 공개 전 기준 |
| docs/repo_cleanup_phase1_summary.md | 1차 정리 | 복사/제외 정책 | 상세 민감 후보 | public repo baseline |
| docs/repo_cleanup_phase3_secret_final_summary.md | secret scan | residual scan 통과 여부 | raw secret 후보 | 공개 안전성 검증 |
| docs/repo_cleanup_phase3_large_forbidden_final_summary.md | large/forbidden scan | pkl/data/build 산출물 제외 | 대용량 원본 | 금지 파일 제거 확인 |
| docs/repo_cleanup_phase3_build_final_check.md | build check | frontend/backend 검증 결과 | 내부 로그 상세 | 공개 repo build 가능성 |
