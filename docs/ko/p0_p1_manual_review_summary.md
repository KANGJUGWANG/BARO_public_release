# P0/P1 수동 보정 요약

## 목적

Phase 3.5-B의 `full_docs_inventory.csv`는 파일명과 키워드 기반 자동 분류였기 때문에 일부 모델/라벨 문서가 frontend, apk, deployment 계열로 잘못 분류됐다. Phase 3.5-C에서는 P0/P1 후보 122개를 공개/제출 문서 작성 관점에서 보정했다.

## 보정 결과

| 항목 | 값 |
| --- | ---: |
| 보정 대상 P0/P1 후보 | 122 |
| corrected inventory 파일 | `docs/ko/full_docs_inventory_corrected.csv` |

## 보정 원칙

- 모델/라벨/threshold/Exp-C/retrain 문서는 `modeling_label_evaluation` 또는 `model_training_retraining`으로 보정한다.
- 왕복 후보/feature/history/prediction 문서는 `roundtrip_support`로 보정한다.
- 검색 결과, 카드, 상세, 모델 안내, UI 문구 문서는 `frontend_ui_ux`로 보정한다.
- Android, Capacitor, APK, launcher, splash, signing 문서는 `apk_mobile`로 보정한다.
- repo cleanup 문서는 핵심 프로젝트 진행 근거가 아니라 공개/제출 정리 근거로 분리한다.
- 민감 경로 또는 secret 위험이 있는 문서는 공개 문서 직접 인용 대상에서 제외하거나 redaction 필요로 표시한다.

## evidence_type 분리

- `problem_definition`: 문제 정의와 프로젝트 접근 근거
- `data_collection`: 수집 설계와 반복 관측 근거
- `db_schema_storage`: DB 저장 구조와 observation 설계
- `eda`: 데이터 품질과 가격 변동성 분석
- `model_design`: Stage1/Stage2 구조
- `label_design`: BUY/WAIT 라벨 설계
- `evaluation`: Exp-C, threshold, regret/success 평가
- `retraining`: final freeze, full retrain, runtime smoke, live switch
- `backend_serving`: FastAPI, candidates, history, analyze-job, route-analysis
- `roundtrip_support`: 왕복 후보/분석/상세/가격 추이
- `frontend_ui`: 화면 구성과 추천 표현 정리
- `apk_mobile`: APK/native shell/icon/splash/signing
- `public_release`: 공개 repo 정리와 민감정보 제외 근거

## 남은 한계

보정은 파일명, 기존 inventory, 주요 phase 흐름을 기반으로 한 수동 규칙 보정이다. 최종 제출 문서에 인용할 때는 각 문서의 해당 section을 한 번 더 열어 세부 수치를 확인하는 것이 안전하다.
