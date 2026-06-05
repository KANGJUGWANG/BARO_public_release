# BARO Public Docs Phase 3.5-B 요약

## 작성 파일

- docs/ko/full_docs_inventory.csv
- docs/ko/full_docs_inventory_summary.md
- docs/ko/full_docs_category_map.md
- docs/ko/project_timeline_v2.md
- docs/ko/project_decision_journey_v2.md
- docs/ko/project_metric_evidence_table_v2.csv
- docs/ko/project_metric_evidence_summary_v2.md
- docs/ko/reproducibility_scope_v2.md
- docs/ko/pipeline_restructure_plan.md
- docs/ko/full_docs_extraction_encoding_check.md
- docs/ko/full_docs_extraction_validation.md
- docs/ko/full_docs_extraction_summary.md

## 전체 docs 확인 범위

원본 private repo의 `docs/` 아래 파일 210개를 inventory로 생성했다. 원본 repo는 read-only로만 사용했고, 삭제/이동/수정/git 작업은 하지 않았다.

## 카테고리별 분류 결과

| category | count |
| --- | ---: |
| frontend_ui_ux | 54 |
| apk_mobile | 52 |
| deployment_infra | 28 |
| misc_review_required | 24 |
| public_release_cleanup | 19 |
| roundtrip_support | 13 |
| backend_api_serving | 10 |
| modeling_label_evaluation | 3 |
| presentation | 3 |
| handoff_summary | 2 |
| eda_analysis | 1 |
| planning_problem_definition | 1 |

## P0/P1 핵심 근거

- P0 핵심 근거 후보: 45개
- P1 보조 근거 후보: 77개

핵심 근거는 Phase 13~16 모델 개선/재학습/live switch 문서, Phase 7~11 왕복/backend/frontend 문서, Phase 12 APK/release 문서, repo cleanup 문서를 중심으로 정리했다.

## 프로젝트 서사 v2 요약

BARO는 항공권 검색 결과를 단순히 나열하는 서비스가 아니라, 반복 관측 가격 이력과 머신러닝 모델을 사용해 “지금 구매할지, 기다릴지”를 보조하는 서비스로 발전했다. 프로젝트 흐름은 기획, 수집, DB, EDA, 모델, backend serving, frontend UI, APK, 최종 재학습, live switch, 공개 repo 정리로 이어진다.

## 새로 확인한 수치

- 원본 docs 파일 수: 210개
- 수치 근거 후보 문서: 139개
- 경로/민감정보 위험 후보 문서: 60개
- 최종 학습 가능 row: 4,562,741건
- 편도 학습 row: 989,669건
- 왕복 학습 row: 3,573,072건
- 최종 편도 threshold: 0.80
- 최종 왕복 threshold: 0.65

## 재현 범위 v2 요약

공개 repo만으로는 코드와 문서 구조, frontend/backend skeleton, API contract, 모델 구조 설명까지 확인할 수 있다. 동일한 최종 예측값, full retrain, live inference는 private DB/model artifact가 있어야 가능하다.

## pipeline 재구성 필요 목록

- crawler
- dataset materialization
- feature/label generation
- Stage1/Stage2 training
- model packaging
- smoke validation

이번 Phase에서는 실제 파일 이동 없이 계획만 작성했다.

## 인코딩 검증

한글 깨짐, replacement character, 반복 물음표 패턴 없음. pass.

## secret/private scan

Phase 3.5-B 산출물 대상 금지 키워드 scan hit 없음. pass.

## 다음 단계 제안

1. `full_docs_inventory.csv`에서 P0/P1 문서를 사람이 한 번 더 검토한다.
2. 자동 분류가 어긋난 문서를 수동 보정한다.
3. public README와 docs/en 문서에 v2 서사를 반영한다.
4. pipeline 공개화는 실제 파일 이동 전에 별도 Phase로 진행한다.
5. 공개용 architecture diagram과 sample smoke guide를 추가한다.

## 판정

B+.

전수 inventory와 v2 문서 작성은 완료됐다. 다만 자동 카테고리 분류는 보수적 1차 분류이므로, 최종 공개 전 P0/P1 문서의 수동 재분류를 한 번 더 수행하면 A로 올릴 수 있다.
