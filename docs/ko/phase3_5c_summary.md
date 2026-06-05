# BARO Public Docs Phase 3.5-C 요약

## 작성 파일

- docs/ko/full_docs_inventory_corrected.csv
- docs/ko/p0_p1_manual_review_summary.md
- docs/ko/core_evidence_document_set.md
- docs/ko/pipeline_code_map.csv
- docs/ko/pipeline_code_map_summary.md
- docs/ko/pipeline_oriented_repo_structure_proposal.md
- docs/ko/submission_document_outline.md
- docs/ko/phase3_5_artifact_consolidation_plan.md
- docs/ko/phase3_5c_validation.md
- docs/ko/phase3_5c_summary.md

## P0/P1 수동 보정 결과

`full_docs_inventory.csv`의 P0/P1 후보 122개를 검토해 `full_docs_inventory_corrected.csv`를 작성했다. 자동 분류에서 어긋난 모델/라벨/threshold/retrain 문서는 모델 계열로, repo cleanup 문서는 공개 정리 근거로 분리했다.

## 핵심 근거 문서 세트

근거 문서는 네 묶음으로 정리했다.

1. 프로젝트 진행 근거
2. 모델 의사결정 근거
3. 재현성 근거
4. 공개/제출 정리 근거

## pipeline code map 요약

실제 코드 위치를 pipeline stage별로 매핑했다.

- crawler/parser/collector
- DB loader/storage
- feature builder
- label/training/retraining
- threshold/package/live switch
- runtime adapter
- FastAPI serving
- frontend UI
- APK/Capacitor
- systemd/deploy template

## 공개 repo 구조 제안

다음 구조를 후속 정리 후보로 제안했다.

```text
pipelines/
  crawler/
  dataset/
  features/
  training/
  packaging/
  smoke/
configs/examples/
data/sample/
models/
outputs/
backend/
frontend/
docs/
```

이번 Phase에서는 실제 파일 이동을 하지 않았다.

## 제출 문서 목차

제출 문서는 프로젝트 개요, 문제 정의, 데이터 수집, EDA, 모델 개선, Stage1/Stage2, 최종 학습, 평가 결과, backend, frontend, 배포, 재현성, 공개/비공개 경계, 한계와 향후 개선 순서로 제안했다.

## 검증 결과

- 한글 깨짐 없음
- 민감 키워드 scan 통과
- private repo 수정 없음
- git add/commit/push 없음
- pkl/data 추가 없음

## 남은 확인 사항

- corrected inventory의 일부 `review` 항목은 사람이 최종 판단해야 한다.
- pipeline code map의 `document_only` 항목은 공개 skeleton을 만들지 여부를 결정해야 한다.
- public README와 docs/en에 v2 문서를 반영할지 결정해야 한다.

## 판정

A-.

P0/P1 보정, 핵심 근거 문서 세트, pipeline code map, 공개 구조 제안, 제출 문서 목차를 작성했다. 실제 구조 재배치는 아직 하지 않았으므로 A가 아니라 A-로 둔다.
