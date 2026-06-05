# Phase 3.5 산출물 통합 계획

## 기존 산출물 상태

| 파일 | 현재 역할 | 향후 처리 |
| --- | --- | --- |
| project_decision_journey.md | 모델 중심 초안 | v2로 대체 가능 |
| project_decision_journey_v2.md | 전체 의사결정 문서 | 최종 후보 |
| project_metric_evidence_table.csv | 모델 중심 수치표 | v2로 대체 가능 |
| project_metric_evidence_table_v2.csv | 전수 inventory 반영 수치표 | 최종 후보 |
| project_metric_evidence_summary.md | 모델 중심 요약 | v2로 대체 가능 |
| project_metric_evidence_summary_v2.md | 전체 수치 요약 | 최종 후보 |
| reproducibility_scope_draft.md | 초안 | v2로 대체 가능 |
| reproducibility_scope_v2.md | 재현 범위 확장판 | 최종 후보 |
| pipeline_restructure_plan.md | 초기 계획 | pipeline_code_map 반영 후 보조 문서로 유지 |
| pipeline_code_map.csv | 실제 코드 위치 매핑 | 다음 구조 정리의 기준 |

## 통합 방향

1. 공개 README에는 v2 문서만 링크한다.
2. 초안 문서는 삭제하지 않고 `draft` 또는 `legacy draft`로 표시할지 결정한다.
3. 최종 제출 문서에는 `project_timeline_v2`, `project_decision_journey_v2`, `project_metric_evidence_summary_v2`, `reproducibility_scope_v2`를 우선 사용한다.
4. pipeline 정리 작업을 시작하면 `pipeline_code_map.csv`와 `pipeline_oriented_repo_structure_proposal.md`를 기준으로 한다.

## 삭제/이동 여부

이번 Phase에서는 삭제와 이동을 하지 않는다. 실제 정리는 별도 Phase에서 사용자 승인 후 진행한다.

## 남은 결정

- 초안 문서를 public repo에 계속 둘지 여부
- docs/en에도 v2 내용을 번역 반영할지 여부
- README에 v2 문서 링크를 바로 반영할지 여부
- pipeline 디렉토리 구조를 실제로 만들지 여부
