# BARO 프로젝트 전체 타임라인 v2

이 문서는 원본 `docs/` 전체 인덱싱을 바탕으로, 모델 개선뿐 아니라 기획, 데이터 수집, DB, backend, frontend, APK, 공개 repo 정리까지 포함한 전체 프로젝트 진행 흐름을 공개 가능한 수준으로 정리한다.

| 단계 | 기간 또는 phase | 문제/목표 | 수행한 작업 | 사용한 코드/문서 근거 | 산출 결과 | 다음 단계로 이어진 이유 | 공개 가능 여부 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 초기 기획 | 항공권 검색보다 구매 시점 판단이 어렵다는 문제 정의 | 항공권 가격 변동과 사용자 의사결정 문제를 MVP 주제로 정리 | v0.x anchor/checklist, v1.0.0 anchor | BUY/WAIT 추천 서비스 방향 확정 | 단순 검색이 아니라 가격 이력 기반 판단이 필요 | 가능 |
| 2 | 수집 운영 준비 | 추천을 위해 반복 관측 데이터가 필요 | 대상 노선, 항공사, 날짜 범위, 수집 주기 검토 | v0.4~v0.5 수집/checklist/schema 문서 | 2026-04-16부터 운영 관측 시작 | 가격 흐름을 저장할 DB 구조 필요 | 민감 설정 제외 후 가능 |
| 3 | DB 저장 구조 | 관측 결과를 검색 조건과 항공권 후보 단위로 저장해야 함 | search observation, offer observation 중심 구조 정리 | schema 계열 문서, observation 관련 phase 문서 | 가격 history와 후보 조회 기반 마련 | 후보 조회 API와 추천 추론으로 연결 | 가능 |
| 4 | EDA | 가격 변동성과 데이터 품질 확인 | 관측 가격 분포, 변동성, route/airline 패턴 분석 | docs/eda/eda_report.md | 단순 최저가보다 시간 흐름이 중요하다는 근거 확보 | label/model 설계로 연결 | 요약만 가능 |
| 5 | 초기 모델링 | 미래 가격 하락 가능성을 정량화해야 함 | BUY/WAIT 라벨, Stage1/Stage2 구조 설계 | docs/modeling/label_design.md, docs/modeling/final_modeling_summary_clean_v1.md | Stage1 예상 절약, Stage2 WAIT 확률 구조 확정 | backend serving contract 필요 | 가능 |
| 6 | 편도 추천 serving | 검색 결과에서 추천을 표시해야 함 | predict-one, history, search 결과 top-k 분석 연결 | Phase 4~6, v1.0.0 문서 | 편도 추천/상세/가격 추이 구현 | 왕복 후보와 모델 확장 필요 | 가능 |
| 7 | 왕복 확장 | 왕복은 출국편+귀국편 조합이라 편도 구조만으로 부족 | roundtrip candidates, feature builder, predict-one, analyze-job 확장 | Phase 7~11 왕복 문서 | 왕복 목록/상세/가격 추이/추천 분석 연결 | UI와 navigation 정리 필요 | 가능 |
| 8 | frontend MVP | 사용자가 검색, 분석, 상세를 모바일 화면에서 사용할 수 있어야 함 | Home, SearchResult, CardDetail, ModelInfo, BottomBar, sticky/scroll hotfix | Phase 8~11 UI 문서 | 웹과 APK에서 주요 기능 동작 | APK/native polish와 배포 준비 필요 | 가능 |
| 9 | 노선 분석 | 개별 카드 외에도 노선별 가격 흐름을 보여줄 필요 | route-analysis snapshot/API/frontend 구현 | Phase 9~10 문서 | 하단 분석 탭과 route-analysis 화면 연결 | UI 설명과 모델 정보 최신화 필요 | 가능 |
| 10 | APK/mobile | 앱 형태로 시연/배포 가능해야 함 | Capacitor build, icon/splash, signed release APK 설정 | Phase 12A 문서 | APK build와 release signing 준비 | 공개 repo와 제출 문서 정리 필요 | signing secret 제외 후 가능 |
| 11 | 모델 문제 재정의 | BUY 추천 과다와 confidence 오해 문제 확인 | confidence 의미 audit, BUY regret 중심 문제 정의 | Phase 12B, Phase 13 문서 | 핵심 문제를 BUY ratio가 아닌 BUY regret으로 재정의 | 라벨/threshold 실험 필요 | 가능 |
| 12 | Exp-C 기준 도입 | 사용자 체감형 평가 기준 필요 | 72h, 20,000원, 3% 기준으로 Exp-C 평가/실험 설계 | Phase 13~14 문서 | Exp-C가 주요 후보로 유지 | Stage1 coverage와 retrain 검증 필요 | 가능 |
| 13 | 최종 재학습 | 최신 데이터로 Stage1/Stage2를 다시 학습해야 함 | final freeze dataset, full retrain, threshold review | Phase 16A~16C 문서 | 편도/왕복 full retrain 후보 생성 | live switch 전 runtime smoke 필요 | 요약 수치만 가능 |
| 14 | live model switch | 최종 모델을 운영 backend에 반영 | model-info, predict-one, health smoke 확인 후 live switch | Phase 16D 문서 | 최종 model_version과 threshold 운영 확인 | frontend 표현 정리 필요 | 내부 경로 제외 후 가능 |
| 15 | UI 표현 개선 | 신뢰도 표현이 실제 정확도로 오해될 수 있음 | 가격 하락 기대 강도, WAIT 기준 marker, ModelInfo polish | Phase 16E 문서 | 사용자에게 더 정확한 추천 표현 제공 | 공개 repo 문서화 필요 | 가능 |
| 16 | 공개 repo 정리 | 제출/공개 전 민감 파일과 산출물 분리 필요 | cleanup inventory, README, public docs, secret/large file scan | repo cleanup Phase 0~3 문서 | public release repo 구성 | 전체 프로젝트 서사 보강 필요 | 가능 |

## 요약

BARO는 “항공권을 어디서 찾을까”가 아니라 “지금 살까, 기다릴까”를 다룬 프로젝트다. 이를 위해 반복 관측 DB를 만들고, 가격 이력 기반 feature를 구성하고, BUY/WAIT 추천 모델을 만들었으며, 최종적으로 편도/왕복 분리 모델과 모바일 UI, APK, 공개 repo 정리까지 이어졌다.
