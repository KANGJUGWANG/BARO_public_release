# BARO 프로젝트 의사결정 근거 인덱스

이 문서는 공개 문서화에 사용할 수 있는 내부 기록의 상대 경로와 근거 유형만 정리한다. 원본 기록에 포함된 운영 경로, 서버 주소, 개인 경로, 비공개 설정값은 공개 문서로 옮기지 않는다.

| source | 근거 유형 | 공개 문서 반영 방식 | 요약 |
| --- | --- | --- | --- |
| docs/modeling/label_design.md | 초기 라벨 설계 | 개념 요약 | BUY=0, WAIT=1 구조와 미래 절약률 기반 라벨 철학을 설명한다. |
| docs/modeling/final_modeling_summary_clean_v1.md | 초기 2단계 모델 구조 | 개념 요약 | Stage1은 예상 절약 가능성, Stage2는 WAIT 확률을 산출하는 구조로 정리되어 있다. |
| docs/phase_13_1_model_runtime_artifact_contract.md | 운영 추론 계약 | 계약 요약 | 편도와 왕복의 모델 계열, threshold, decision rule 분리 필요성을 정리했다. |
| docs/phase_13_4_label_metric_threshold_decision.md | 라벨/평가 기준 재정립 | 의사결정 요약 | 핵심 문제를 BUY 비율 자체가 아니라 BUY regret으로 정의했고, 72h 및 체감 절약 기준을 후보로 정리했다. |
| docs/phase_13_5_retraining_experiment_design.md | 실험 설계 | 의사결정 요약 | threshold, calibration, holdout, trip별 기준을 분리해서 검증하는 방향을 세웠다. |
| docs/phase_14_8_stage1_alignment_holdout_validation.md | Exp-C 보완 검증 | 수치 근거 | Exp-C가 Exp-A 대비 BUY regret과 WAIT success에서 우세했으나 Stage1 정렬은 약하다는 근거를 제공한다. |
| docs/phase_14_9b_fresh_stage1_holdout_validation.md | fresh Stage1 보완 검증 | 수치 근거 | compact pred_saving coverage 병목을 보완하고 Exp-C 후보성을 재확인했다. |
| docs/phase_15b_expc_staging_package.md | staging package | 과정 요약 | Exp-C 기준 Stage2 staging artifact를 만들되 바로 운영 반영하지 않은 절차를 보여준다. |
| docs/phase_16a_final_data_freeze_retraining_plan.md | 최종 학습 범위 고정 | 범위 요약 | 최종 재학습 데이터 기간과 Exp-C 라벨 유지 결정을 정리한다. |
| docs/phase_16b_2_full_dataset_materialization.md | 최종 데이터 materialization | 수치 근거 | 학습 가능 row와 Exp-C 라벨 생성 가능성을 기록한다. |
| docs/phase_16b_3b_full_retrain_final_refit.md | 최종 full retrain | 수치 근거 | 편도/왕복 final rows, split, Stage1/Stage2 학습 결과를 기록한다. |
| docs/phase_16b_3c_baseline_threshold_review.md | threshold review | 수치 근거 | 편도 0.80, 왕복 0.65 기준의 운영 판단 근거를 제공한다. |
| docs/phase_16d_live_model_switch.md | live switch | 운영 반영 근거 | 최종 모델 버전과 threshold가 live backend에서 확인된 과정을 기록한다. |
| docs/phase_16e_frontend_model_info_polish.md | UI 표현 정리 | UI 근거 | 신뢰도 표현을 가격 하락 기대 강도로 바꾼 이유와 최종 모델 정보를 정리한다. |
| docs/phase_16e_2_price_drop_gauge_threshold_marker.md | UI threshold marker | UI 근거 | 편도 80%, 왕복 65% 기준선을 UI에 표시하는 정책을 정리한다. |

## 사용 원칙

- 공개 문서에는 상대 문서명과 요약 수치만 사용한다.
- 운영 주소, 개인 로컬 경로, 서버 내부 경로, 비공개 설정 파일명, 인증값은 옮기지 않는다.
- 모델 바이너리와 학습 원천 데이터는 공개 대상이 아니라 산출물 설명 대상으로만 언급한다.
