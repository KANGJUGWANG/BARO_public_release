# BARO 모델링 최종 정리: 항공권 구매 의사결정 보조 모델

## 1. 개요

BARO 모델링의 목적은 항공권 가격 자체를 맞히는 것이 아니라, 사용자가 특정 시점에 항공권을 **지금 구매할지(BUY)** 또는 **기다릴지(WAIT)** 판단하는 데 필요한 보조 신호를 제공하는 것이다.

이 문서는 leakage 수정 이후의 clean medium 실험, seed-validation, 최신 누적 CSV 기반 final cumulative evaluation까지 정리한 모델링 최종 요약이다. 기존 `medium_tabular_v3` 계열 결과는 `cv_pct` leakage가 확인된 leaky reference이므로 clean 후보 선정 근거로 사용하지 않는다.

## 2. 문제 정의

사용자 관점의 문제는 “현재 항공권을 바로 구매해야 하는가, 아니면 기다렸을 때 의미 있는 가격 절감 가능성이 있는가”이다.

따라서 모델링도 단순히 다음 가격을 예측하는 방식이 아니라, 다음 두 단계를 연결하는 구조로 설계했다.

1. 현재 관측 시점에서 앞으로 절감 가능성이 얼마나 있는지 예측한다.
2. 그 절감 가능성이 해당 항공권 trajectory의 변동성 기준을 넘는지 판단해 BUY/WAIT 의사결정을 보조한다.

현재 label 해석은 다음과 같다.

| label | 의사결정 | 의미 |
|---:|---|---|
| 0 | BUY | 의미 있는 절감 가능성이 기준 이하 |
| 1 | WAIT | 의미 있는 절감 가능성이 기준 초과 |

## 3. 데이터 구조

row 하나는 하나의 `traj_id` trajectory 안에서 특정 `observed_at` 또는 `scan_seq` 시점에 관측된 항공권 가격과 파생 feature를 의미한다.

- `traj_id`: 동일 항공권 가격 흐름을 묶는 trajectory 식별자
- `observed_at`: 실제 가격 관측 시각
- `scan_seq`: 동일 trajectory/DPD 내 관측 순서
- `dpd`: departure day까지 남은 일수

시간이 흐르면 일반적으로 `observed_at`은 증가하고, 출발일에 가까워지므로 `dpd`는 감소한다. 편도와 왕복은 별도 데이터로 분리했고, 왕복 데이터에는 귀국편 정보를 반영하는 `ret_flight_enc`가 추가된다.

### 데이터 규모

| dataset | rows | columns | traj_id count |
|---|---:|---:|---:|
| data/team oneway | 585,456 | 28 | 9,406 |
| data/team roundtrip | 2,120,910 | 29 | 35,043 |
| final-test oneway | 585,456 | 28 | 9,406 |
| final-test roundtrip | 2,120,910 | 29 | 35,043 |

final-test는 별도 신규 holdout 평가가 아니라 **최신 누적 CSV 기반 final cumulative evaluation**으로 해석한다.

### Final evaluation 대상 row

| mode | input rows | censored rows | final evaluation rows |
|---|---:|---:|---:|
| oneway | 585,456 | 9,406 | 576,050 |
| roundtrip | 2,120,910 | 35,043 | 2,085,867 |

`future_obs_count == 0` row는 아직 이후 관측이 없어 label 평가가 불완전할 수 있는 censored row로 보고 기본 평가에서 제외했다.

## 4. 라벨 정의

### `saving_pct`

`saving_pct`는 현재 가격 대비 이후 관측 구간에서 확인되는 최저가를 기준으로, 지금 사지 않고 기다렸을 때 절감 가능했던 비율이다. Stage1의 target으로만 사용하고 feature로는 사용하지 않는다.

### `cv_pct`

`cv_pct`는 동일 trajectory 전체 가격의 표준편차/평균 기반 변동계수이다. 이 값은 label 생성 기준으로는 유지하지만, 전체 trajectory를 참조하므로 모델 feature로 사용하면 현재 관측 시점 이후 가격 정보를 포함할 수 있다.

### `label`

최종 label은 다음 기준으로 정의했다.

```text
label = saving_pct > cv_pct
```

즉, 향후 절감 가능성이 해당 trajectory의 변동성 기준을 넘으면 WAIT, 그렇지 않으면 BUY로 본다.

### Final-test label filter

final cumulative evaluation에서는 다음 정책을 적용했다.

- `saving_pct`, `cv_pct`, `label` 중 하나라도 null이면 평가에서 제외
- `future_obs_count >= 1` row만 기본 metric 계산에 사용
- `future_obs_count == 0` row는 censored row로 분류하고 평가 제외
- `future_obs_count`는 feature가 아니라 평가 필터/meta로만 사용

## 5. 피처 엔지니어링

Stage1과 Stage2는 모두 tabular 모델을 사용하지만, 가격 흐름을 볼 수 있도록 현재 시점까지의 누적 통계와 가격 변화 feature를 포함했다. 따라서 LSTM 같은 명시적 sequence 모델을 쓰지 않더라도, 모델은 현재 관측 시점까지의 가격 흐름 요약을 입력으로 받는다.

### Stage1 feature 요약

| feature group | features |
|---|---|
| current_price | `price_krw` |
| time_position | `dpd`, `dpd_ratio`, `scan_hour`, `scan_seq` |
| cumulative_price_stat | `cum_min`, `cum_max`, `cum_mean`, `cum_std`, `cum_count`, `price_pct_from_cum_min`, `price_pct_from_cum_max`, `price_pct_from_cum_mean` |
| price_change | `price_chg_1`, `price_chg_3`, `price_chg_6` |
| categorical_encoding | `route_enc`, `airline_enc`, `flight_enc`, `ret_flight_enc` for roundtrip |

### Stage2 feature 요약

| feature group | features |
|---|---|
| stage1_prediction | `pred_saving` |
| time_position | `dpd`, `dpd_ratio`, `scan_hour` |
| cumulative_price_stat | `price_pct_from_cum_min`, `price_pct_from_cum_mean` |
| price_change | `price_chg_1`, `price_chg_3`, `price_chg_6` |
| categorical_encoding | `route_enc`, `airline_enc`, `flight_enc`, `ret_flight_enc` for roundtrip |

### 금지 feature

다음 컬럼은 clean pipeline에서 feature로 사용하지 않는다.

- `cv_pct`
- `saving_pct`
- `label`
- `pred_margin`
- `pred_margin_*`
- `future_obs_count`

누적 통계 feature와 가격 변화 feature는 expanding 또는 과거 변화 기반으로 현재 관측 시점까지의 정보만 사용한다.

## 6. Stage1/Stage2 모델 구조

BARO 모델링은 two-stage 구조이다.

| stage | task | target | output |
|---|---|---|---|
| Stage1 | regression | `saving_pct` | `pred_saving` |
| Stage2 | classification | `label` | WAIT probability |

Stage1은 현재 관측 시점에서 앞으로의 절감 가능성인 `saving_pct`를 예측한다. Stage2는 Stage1 output인 `pred_saving`과 현재 관측 feature를 함께 사용해 BUY/WAIT를 분류한다.

Stage2 train에는 Stage1의 out-of-fold prediction을 사용해 train leakage를 줄였다. validation/test에는 train에서 학습한 Stage1 모델의 prediction을 사용한다.

Stage2 threshold는 validation set에서 `best_service_score` 기준으로 선택한다. test set에서는 validation에서 선택된 threshold를 그대로 적용하고, test 기준 threshold 재선택은 하지 않는다.

`best_stage1` 방식과 `selected_stage1_preds` 방식을 비교했지만, `selected_stage1_preds`는 명확한 validation 개선을 보이지 않아 운영 단순성 측면에서 기본 최종 후보에서 제외했다.

## 7. Leakage 발견과 clean pipeline 수정

기존 v3 계열에서 `cv_pct`가 feature로 포함된 문제가 확인됐다. `cv_pct`는 trajectory 전체 가격의 std/mean 기반이므로, 현재 관측 시점 이후 가격 정보를 포함할 수 있다. 따라서 feature로 사용하면 future leakage가 된다.

clean pipeline에서는 다음을 수정했다.

- `cv_pct`는 label/meta로만 유지하고 feature에서 제거
- `saving_pct`는 Stage1 target으로만 사용
- `label`은 Stage2 target으로만 사용
- `pred_margin` 및 `pred_margin_*` 계열은 `cv_pct` 파생이므로 제거
- leaky Stage1 artifact 재사용 차단
- `rule_pred_saving_gt_cv` baseline 비활성화
- `rule_pred_saving_val_threshold` baseline 추가

clean medium은 위 leakage feature를 제거한 뒤 Stage1부터 다시 학습한 결과이다.

## 8. 모델 후보 탐색 과정

모델 후보 탐색은 다음 단계로 진행했다.

| 단계 | 역할 |
|---|---|
| smoke/small | pipeline 실행 가능성, feature/label 누락, artifact 저장 구조 확인 |
| medium | 여러 후보군을 validation 기준으로 압축 |
| clean medium | leakage 제거 후 후보 재탐색 |
| selected_stage1_preds 비교 | 여러 Stage1 prediction을 Stage2에 넣는 방식의 추가 효과 확인 |
| seed-validation | best params를 고정하고 seed만 바꿔 안정성 확인 |
| final cumulative evaluation | 최신 누적 CSV 기반 최종 후보 평가 및 임시 서비스 모델 저장 |

medium 단계는 최종 확정이 아니라 seed-validation 후보를 압축하기 위한 단계로 사용했다.

## 9. Clean medium 결과

clean medium 결과에서 Stage1은 oneway와 roundtrip 모두 `random_forest`가 가장 강한 후보로 확인됐다.

### Stage1 clean medium top candidates

| mode | top model | val MAE | test MAE reference |
|---|---|---:|---:|
| oneway | random_forest | 3.9037 | 3.7927 |
| roundtrip | random_forest | 2.4413 | 2.3613 |

### Stage2 clean medium top candidates

| mode | top model | val service_score | test service_score reference | threshold |
|---|---|---:|---:|---:|
| oneway | lightgbm | 0.8850 | 0.8806 | 0.34 |
| roundtrip | xgboost | 0.9078 | 0.9086 | 0.41 |

oneway Stage2에서는 `lightgbm`이 clean medium 기준 1위였고, `xgboost`가 근접 후보였다. 이후 seed-validation에서는 `xgboost`가 우선 후보로 정리됐다.

`selected_stage1_preds`는 best_stage1 대비 명확한 개선을 보이지 않아 최종 기본 경로에서 제외했다.

## 10. Seed-validation 결과

seed-validation은 medium에서 선택한 best params를 고정하고 seed만 바꿔 후보 안정성을 확인하는 단계이다. test metric은 후보 선정 기준이 아니라 참고값으로만 보았다.

### Stage1 seed-validation

| mode | selected model | mean validation metric | decision |
|---|---|---:|---|
| oneway | random_forest | val MAE 3.8392 | selected |
| roundtrip | random_forest | val MAE 2.3662 | selected |

### Stage2 seed-validation

| mode | candidate | mean val service_score | std | decision |
|---|---|---:|---:|---|
| oneway | xgboost | 0.8751 | 0.0068 | selected |
| oneway | lightgbm | 0.8730 | 0.0074 | close reference |
| roundtrip | random_forest | 0.9033 | 0.0021 | tie-band reference |
| roundtrip | xgboost | 0.9020 | 0.0023 | selected for service |

roundtrip Stage2는 `random_forest`가 mean service_score에서 근소 우세였지만 `xgboost`와 동률권으로 보았다. 단건/소량 서비스 요청에서는 `xgboost`가 더 빠르므로 최종 임시 서비스 후보는 `xgboost`로 선택했다.

## 11. Final cumulative evaluation

final-test는 최신 누적 CSV 기반 final cumulative evaluation이다. 기본 평가는 `future_obs_count >= 1` 기준으로 수행했다.

### Stage1 final cumulative evaluation

| mode | model | val MAE | val R2 | test MAE reference | test R2 reference |
|---|---|---:|---:|---:|---:|
| oneway | random_forest | 4.9213 | 0.6375 | 4.9396 | 0.6435 |
| roundtrip | random_forest | 2.9914 | 0.8180 | 2.9722 | 0.8127 |

### Stage2 final cumulative evaluation

| mode | model | val service | test service reference | test AUC reference | test F1 macro reference | threshold |
|---|---|---:|---:|---:|---:|---:|
| oneway | xgboost | 0.8567 | 0.8508 | 0.9177 | 0.8174 | 0.55 |
| roundtrip | xgboost | 0.9010 | 0.9012 | 0.9557 | 0.8767 | 0.35 |

`service_score`는 코드상 heuristic metric이다. 현재 pipeline에서는 F1 macro, AUC, BUY/WAIT recall balance를 함께 반영하는 비교 지표로 사용했으며, 별도 business weight 최적화 결과로 표현하지 않는다.

### future_obs_count sensitivity

| mode | future_obs_min | rows | test service | test AUC | test F1 macro |
|---|---:|---:|---:|---:|---:|
| oneway | 1 | 115,587 | 0.8508 | 0.9177 | 0.8174 |
| oneway | 2 | 113,720 | 0.8495 | 0.9166 | 0.8167 |
| oneway | 3 | 111,859 | 0.8484 | 0.9159 | 0.8161 |
| roundtrip | 1 | 419,168 | 0.9012 | 0.9557 | 0.8767 |
| roundtrip | 2 | 412,210 | 0.9007 | 0.9550 | 0.8760 |
| roundtrip | 3 | 405,303 | 0.9005 | 0.9546 | 0.8755 |

`future_obs_count >= 2`, `>= 3`에서도 score가 크게 무너지지 않아, censored row 제외 정책에 대해 결과가 비교적 안정적이었다.

## 12. 최종 모델 구성

최종 임시 서비스 후보는 다음과 같다.

| mode | Stage1 | Stage2 | stage1_source |
|---|---|---|---|
| oneway | random_forest | xgboost | best_stage1 |
| roundtrip | xgboost | xgboost | service runtime contract |

`selected_stage1_preds`는 validation 개선이 명확하지 않았고 운영 복잡도를 증가시키므로 제외했다.

roundtrip은 초기 후보 평가에서 Stage1 `random_forest`가 강한 후보였지만, 운영 runtime은 `roundtrip_stage1_xgboost.pkl` + `roundtrip_stage2_xgboost.pkl`을 로드하는 XGB/XGB contract로 정리했다. 따라서 재학습 산출물과 model-info 표시는 왕복을 RF/XGB 후보가 아니라 XGB/XGB 운영 모델로 취급한다.

roundtrip Stage2에서 `xgboost`를 선택한 이유는 다음과 같다.

- seed-validation 성능은 `random_forest`와 동률권
- 단건/소량 추론 속도에서 `xgboost`가 우세
- 실제 서비스 요청은 대량 batch보다 단건/소량 중심일 가능성이 높음

최종 발표 직전에는 최신 누적 데이터로 final model을 다시 재생성할 예정이다.

## 13. 추론 속도 및 서비스 적용 고려

roundtrip Stage2 기준 속도 비교는 다음과 같다.

| rows | random_forest_ms | xgboost_ms | interpretation |
|---:|---:|---:|---|
| 1 | 62.3 | 2.57 | xgboost faster for single request |
| 100 | 81.4 | 5.77 | xgboost faster for small batch |
| 1,000 | 100.8 | 8.22 | xgboost faster |
| 10,000 | 160.1 | 48.6 | xgboost faster |
| 100,000 | 361.9 | 446.2 | random_forest slightly faster for large batch |
| 200,000 | 729.4 | 820.6 | random_forest slightly faster for large batch |

대량 batch에서는 `random_forest`가 약간 빠른 구간이 있었지만, 실제 서비스는 사용자의 단건 또는 소량 요청이 중심일 가능성이 높다. 이 기준에서는 `xgboost`가 더 적합하다.

## 14. 모델 artifact 저장 정책

Stage1 `random_forest`는 service refit 후 `.pkl` 크기가 매우 커질 수 있다. 실행 중 `OSError: [Errno 28] No space left on device`가 발생했기 때문에, 대용량 `.pkl` 저장 위치를 외장 SSD로 분리했다.

정책은 다음과 같다.

- `.pkl` 모델 파일은 GitHub 업로드 제외
- C 드라이브 repo에는 평가 CSV, 문서, threshold json, feature/label metadata만 유지
- 대용량 `.pkl`은 별도 artifact 저장소에서 관리
- 현재 저장 위치: `E:\BARO_final_model_artifacts\finaltest_clean_v1`

모델 artifact 목록은 다음과 같다.

- `oneway_stage1_random_forest.pkl`
- `oneway_stage2_xgboost.pkl`
- `roundtrip_stage1_xgboost.pkl`
- `roundtrip_stage2_xgboost.pkl`
- `oneway_threshold.json`
- `roundtrip_threshold.json`
- `feature_columns.json`
- `enc_mappings.json`
- `label_policy.json`
- `final_model_metadata.json`
- `roundtrip_final_model_metadata.json` (왕복 model_version 분리 시 권장)

서비스 적용 시에는 편도 RF Stage1 모델의 RAM 사용량, 로딩 시간, 외장 경로 의존성, 백업 정책을 별도로 확인해야 한다. 왕복은 XGB/XGB contract를 기준으로 관리한다.

## 15. 한계와 향후 작업

- `cv_pct` label 기준은 유지했지만, 향후 과거 기반 기준선도 검토할 수 있다.
- 최신 누적 데이터에는 이후 관측이 없는 censored row가 존재한다.
- `future_obs_count >= 2`, `>= 3` 민감도 분석은 참고 분석이다.
- `service_score`는 heuristic metric이며, business weight 최적화 결과가 아니다.
- final cumulative evaluation은 최신 누적 CSV 기반 평가이며, 완전히 독립적인 신규 holdout 평가는 아니다.
- 최종 발표 직전 최신 데이터로 final model을 다시 재생성할 필요가 있다.
- 서비스 API 연동 후 실제 latency를 다시 측정해야 한다.

## 16. 부록

### 주요 산출물 경로

| 목적 | 경로 |
|---|---|
| source pack | `outputs/modeling_docs_source_pack_v1/` |
| leakage fix 근거 | `outputs/leakage_fix_clean_v1/` |
| clean medium snapshot | `colab_medium_clean_v1/outputs/presentation_snapshot_clean_medium_v1/` |
| seed-validation 결과 | `seedval_clean_v1/outputs/seed_validation_clean_v1/` |
| final cumulative evaluation 결과 | `finaltest_clean_v1/outputs/final_test_clean_v1/` |
| final model `.pkl` artifact | `E:\BARO_final_model_artifacts\finaltest_clean_v1` |

### 누락 파일

source pack 생성 시 다음 optional 파일이 없었다.

- `finaltest_clean_v1/outputs/final_test_clean_v1/final_test_label_distribution.csv`

label 분포는 `final_test_data_summary.md`와 `final_test_label_filter_audit.csv` 기준으로 대체했다.

### GitHub 업로드 제외 대상

다음 파일/폴더는 GitHub 업로드 대상이 아니다.

- `.pkl` 모델 파일
- 원본 또는 feature CSV
- `data/team/`
- `finaltest_clean_v1/data/final_test/`
- `outputs/optimization_medium/`
- OOF prediction artifact
- Optuna DB
- `.env` 및 인증정보
