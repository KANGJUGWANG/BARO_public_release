# 프로젝트 여정 추출 요약

## 작성 파일

- docs/ko/project_journey_source_index.md
- docs/ko/project_decision_journey.md
- docs/ko/project_metric_evidence_table.csv
- docs/ko/project_metric_evidence_summary.md
- docs/ko/public_private_boundary.md
- docs/ko/project_process_summary_draft.md
- docs/ko/reproducibility_scope_draft.md
- docs/ko/missing_evidence_todo.md
- docs/ko/project_journey_extraction_validation.md
- docs/ko/project_journey_extraction_summary.md

## 요약 결론

BARO의 의사결정 흐름은 다음으로 정리된다.

1. 단순 항공권 검색이 아니라 구매 시점 판단 보조 문제로 정의했다.
2. 사용자 행동으로 연결되도록 BUY/WAIT 표현을 채택했다.
3. 가격 이력과 현재 가격의 복합 패턴 때문에 머신러닝 접근을 선택했다.
4. 초기 라벨은 미래 절약 가능성과 변동성 기준을 사용했다.
5. 운영 관찰 후 핵심 문제를 BUY 비율이 아니라 BUY regret으로 재정의했다.
6. 사용자 체감 기준으로 72시간, 20,000원, 3% 조건을 도입했다.
7. Exp-C 기준이 보완 검증에서 더 나은 서비스 지표를 보였다.
8. 최종 full retrain 후 편도와 왕복 모델 및 threshold를 분리해 live 적용했다.
9. UI는 신뢰도 표현을 제거하고 가격 하락 기대 강도로 정리했다.
10. 공개 repo는 구조와 근거를 제공하되, 모델 바이너리와 원천 데이터는 제외한다.

## 산출물 판정

B+에서 A- 사이로 본다. 공개 가능한 프로젝트 스토리와 핵심 근거 수치는 정리됐지만, 외부 논문/시장 근거와 사용자 조사 근거는 별도 보강 여지가 있다.
