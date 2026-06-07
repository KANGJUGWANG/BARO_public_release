# Phase 13 Model Improvement Plan

## 1. 격상 배경

기존 Phase 12B 계열 작업은 처음에는 release 이후 모델 점검으로 시작했지만, 실제 내용은 최종 발표 전 모델 개선을 위한 검증과 의사결정 근거 수집에 해당한다.

따라서 기존 Phase 12B 모델 분석/검증 작업을 Phase 13으로 격상한다.

Phase 12는 발표용 release, APK, 배포, 도메인, 앱 마감 단계로 유지한다.

Phase 13은 최종 모델 개선 준비, 추천 기준 재정립, DB 기반 사후 검증, threshold/label/DPD 분석 단계로 정의한다.

## 2. Phase 역할 분리

| Phase | 역할 |
|---|---|
| Phase 12 | 발표용 release, APK signing, launcher/splash, Vercel 도메인, Google Drive 배포 |
| Phase 13 | 최종 모델 개선 준비, 추천 논리/라벨/평가 기준 검증, retrospective validation |
| Phase 14 | 최종 모델 재학습 및 artifact 교체 |
| Phase 15 | 최종 frontend 출력 정리 및 최종 발표 release |

## 3. 기존 12B -> 신규 13 매핑

| 기존 명칭 | 신규 명칭 | 내용 |
|---|---|---|
| Phase 12B-1 | Phase 13-1 | 모델 runtime/artifact contract 정리 |
| Phase 12B-1-1 | Phase 13-1-1 | model-info / health contract 표시 정합성 정리 |
| Phase 12B-2 | Phase 13-2 | 추천 논리 / 라벨 / 평가 기준 기존 설계 audit |
| Phase 12B-3 | Phase 13-3 | 학습 이후 DB 기반 retrospective validation |
| Phase 12B-3-2 | Phase 13-3-2 | realistic outcome / DPD threshold / label candidate 확장 분석 |

## 4. 완료된 Phase 13 작업 요약

### Phase 13-1 Runtime / Artifact Contract

- 편도 운영 contract: RF + XGB
- 왕복 운영 contract: XGB + XGB
- 왕복은 더 이상 RF/XGB 후보로 취급하지 않음
- `pred_saving`, `wait_probability`, `threshold`, `decision`, `confidence` 의미 정리
- `confidence`는 accuracy가 아니라 decision-side probability intensity임을 명시

문서:

- `docs/phase_13_1_model_runtime_artifact_contract.md`

### Phase 13-1-1 Model Info / Health Contract

- `/health/model`과 `/recommend/model-info`가 편도/왕복 상태를 혼동 없이 표시하도록 contract 정리
- active threshold source는 root threshold json임을 문서화
- artifact 파일은 수정하지 않음

문서:

- `docs/phase_13_1_1_model_info_health_contract.md`

### Phase 13-2 추천 논리 / 라벨 / 평가 기준 Audit

- 현재 추천 구조를 복원
  - Stage1: feature -> `pred_saving`
  - Stage2: feature + `pred_saving` -> `wait_probability`
  - decision: `WAIT if wait_probability > threshold else BUY`
- 기존 라벨 철학 `saving_pct > cv_pct` 확인
- `cv_pct`는 feature에서 제거되어 leakage feature 문제로 보지 않음
- 다만 사용자 체감 손익 기준과의 정합성 검증이 필요하다고 판단

결론:

- 바로 재학습보다 추천 기준/평가 기준 재정의가 먼저 필요하다.

### Phase 13-3 DB Retrospective Validation

기존 output 경로는 재현성을 위해 legacy path를 유지한다.

- legacy server output: `/tmp/baro_phase12b3/`
- legacy local output: `outputs/phase_12b_3/`
- legacy script: `backend/tools/phase_12b_3_retrospective_validation.py`

핵심 결과:

- BUY 비율이 높음
- WAIT은 적지만 oracle 기준 성공률은 높음
- BUY 이후 의미 있는 가격 하락이 존재
- top-k 저가 후보에서도 BUY regret이 존재
- 편도는 `wait_probability`가 매우 낮게 눌리는 경향
- 왕복은 route/DPD별 차이가 큼

주의:

- 이 스크립트 파일명은 기존 Phase 12B 명칭으로 생성되었지만, 현재 Phase 13-3 산출물로 분류한다.
- 파일명과 output 경로는 재현성 유지를 위해 변경하지 않는다.

### Phase 13-3-2 Realistic Outcome Extended Analysis

기존 output 경로는 재현성을 위해 legacy path를 유지한다.

- legacy server output: `/tmp/baro_phase12b3_2/`
- legacy local output: `outputs/phase_12b_3_2/`
- legacy script: `backend/tools/phase_12b_3_2_extended_retrospective_analysis.py`

확장 분석 내용:

- oracle `future_min_price` 기준만 보지 않고 next-N, time-limited, sustained drop 기준을 추가
- 금액 기준, 비율 기준, 금액+비율 혼합 기준 비교
- top-k realistic outcome 계산
- DPD bucket별 threshold 후보 산출
- label candidate 비교

핵심 결과:

- oracle 기준에서는 WAIT success가 높아 보이지만, next6/72h/sustained 기준에서는 성공률이 크게 낮아진다.
- `future_min_price` 단독 평가는 모델 개선 근거로 부족하다.
- BUY regret은 현실성 기준에서도 남아 있다.
- DPD dynamic threshold는 강한 후보지만 holdout 검증 전 운영 반영은 금지한다.
- 기존 `saving_pct > cv_pct` 라벨은 feature leakage 문제는 아니지만, 사용자 체감형 라벨 후보와 차이가 크다.

### Phase 13-4 Label / Metric / Threshold Decision

- 기존 `saving_pct > cv_pct` 라벨은 baseline으로 보존한다.
- `20K AND 3%`는 최종 라벨이 아니라 primary evaluation metric 후보로 둔다.
- `72h`, `next6`, `sustained`는 realistic evaluation 후보로 둔다.
- DPD dynamic threshold와 Platt scaling은 Phase 14 실험 후보로만 둔다.
- 신규 라벨은 Phase 14 ablation 후보로만 비교한다.

문서:

- `docs/phase_13_4_label_metric_threshold_decision.md`

## 5. 핵심 도출 사실

1. 현재 모델은 BUY 비율이 높다.
2. BUY 비율 자체보다 BUY regret이 더 중요한 문제다.
3. WAIT은 적지만 oracle 기준 성공률은 높다.
4. realistic 기준에서는 WAIT success가 낮아진다.
5. `future_min_price` 단독 평가는 지나치게 oracle-like하다.
6. DPD dynamic threshold는 후보지만 holdout 검증이 필요하다.
7. `cv_pct` 라벨은 feature leakage 문제로 단정하지 않는다.
8. 다만 기존 라벨 철학이 사용자 체감 손익과 맞는지는 재검토해야 한다.
9. 최종 재학습 전 라벨/평가 기준 후보를 먼저 고정해야 한다.

## 6. 다음 예정 작업

### Phase 13-4 Label / Evaluation Criteria Selection

완료. 기준 문서:

- `docs/phase_13_4_label_metric_threshold_decision.md`

### Phase 13-5 Retraining Experiment Design

- Phase 13-4 기준을 바탕으로 재학습 데이터 cutoff 확정
- train/valid/test split 정책 확정
- baseline / label 후보 / threshold 후보 실험표 작성
- 편도/왕복 각각 실험 설계

### Phase 14 Final Retraining

- 최종 모델 재학습
- artifact contract 준수
- threshold 및 metadata 정리
- server smoke

### Phase 15 Final Release

- 최종 추천 표현/UI 반영
- APK / web 최종 smoke
- 발표 release 정리

## 7. 주의사항

- Phase 13 작업에서는 아직 모델 pkl/json artifact를 수정하지 않았다.
- threshold artifact도 수정하지 않았다.
- DB write는 수행하지 않았다.
- Phase 13-3 / 13-3-2는 read-only DB 분석이다.
- 분석 결과는 sample 기반 1차 근거이며, holdout 검증 없이 운영 threshold를 바꾸면 안 된다.
- legacy path에 남은 `phase_12b` 명칭은 재현성 보존을 위한 기존 산출물 경로다.
- Phase 13-4는 기준 정리 단계이며 모델/threshold/artifact를 수정하지 않았다.

## 8. 판정

판정: A-

## 9. Phase 13-5 업데이트

Phase 13-5는 완료되었다.

문서:

- `docs/phase_13_5_retraining_experiment_design.md`

핵심 정리:

- 기존 `cv_pct` label은 baseline으로 유지한다.
- `20K AND 3%`는 최종 label이 아니라 primary evaluation metric 후보로 둔다.
- threshold recalibration, probability calibration, DPD dynamic threshold를 Phase 14 최소 실험 세트로 정의했다.
- 신규 label은 Phase 14 ablation 후보로만 비교한다.
- threshold/calibration은 calibration set에서 선택하고, holdout은 최종 1회 비교에만 사용한다.
- Phase 14의 다음 순서는 latest data export, label ratio 재확인, baseline reproduction, threshold/calibration 실험이다.

## 10. Phase 14-0 업데이트

Phase 14-0은 최신 DB / label ratio / split readiness 준비 audit으로 시작했다.

문서:

- `docs/phase_14_0_data_label_split_readiness.md`

핵심 정리:

- 실서버 `search_observation` success rows는 134,400건이며 최신 observed_at은 `2026-06-01 16:00:00`이다.
- 기존 feature export는 `2026-05-14 00:00:00`까지라 최신 DB보다 약 18일 뒤처져 있다.
- 최신 7일 smoke 기준 `cv_pct` label은 BUY-dominant가 아니므로, 운영 BUY 다수 출력은 threshold/calibration 문제 가능성이 계속 강하다.
- 21일 split readiness dry-run은 timeout되어 Phase 14-1 전 export/audit 최적화가 필요하다.

## 11. Phase 14-0-1 업데이트

Phase 14-0-1은 split readiness helper 최적화 단계다.

문서:

- `docs/phase_14_0_1_split_readiness_optimization.md`

핵심 정리:

- summary-only SQL aggregation helper를 추가했다.
- 21일/28일 route-level readiness 산출에 성공했다.
- 28일 window가 train/calibration/holdout 구성에 더 적합하다.
- all-routes both one-shot은 여전히 timeout되므로 Phase 14-1은 trip + route chunk 실행을 권장한다.

근거:

- Phase 12 release 영역과 Phase 13 모델 개선 영역을 분리했다.
- 기존 12B 계열 작업의 Phase 13 매핑을 정리했다.
- 완료된 runtime/artifact, model-info/health, 추천 논리 audit, retrospective validation, extended analysis 결과를 연결했다.
- Phase 13-4에서 기존 cv_pct 라벨 보존, realistic evaluation 후보, threshold/calibration 실험 후보를 정리했다.
- 아직 Phase 14 holdout/retraining이 남아 있으므로 A가 아니라 A-로 둔다.
