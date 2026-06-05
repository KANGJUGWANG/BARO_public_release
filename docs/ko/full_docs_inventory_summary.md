# BARO docs 전수 인덱싱 요약

## 범위

원본 private repo의 `docs/` 아래 파일을 전수 스캔했다. 원본 repo는 읽기 전용으로만 사용했고, 산출물은 public repo의 `docs/ko`에 작성했다.

## 전체 결과

| 항목 | 값 |
| --- | ---: |
| 전체 docs 파일 수 | 210 |
| 수치 근거 후보 문서 | 139 |
| 경로/민감정보 위험 후보 문서 | 60 |
| P0 핵심 근거 후보 | 45 |
| P1 보조 근거 후보 | 77 |
| P2 배경 문서 후보 | 4 |
| P3 내부 로그 후보 | 84 |

## 카테고리별 자동 분류 결과

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

## 해석 주의

이 분류는 파일명과 문서 앞부분 키워드 기반의 자동 1차 분류다. 일부 문서는 여러 성격을 동시에 갖기 때문에 실제 공개 문서에 반영할 때는 category만 보지 않고 source 문서의 맥락을 함께 검토해야 한다.

예를 들어 roundtrip, frontend, apk, deployment 키워드가 섞인 phase 문서는 실제로는 모델/API/UI/검증이 함께 포함될 수 있다. 따라서 이 inventory는 “전체 누락 방지용 지도”이고, 최종 서사는 P0/P1 핵심 문서 중심으로 수동 정리했다.
