# BARO docs 카테고리 맵

## 목적

이 문서는 원본 `docs/` 전체를 공개 문서 작성 관점에서 카테고리별로 정리한다. 자동 분류 결과를 기반으로 하되, 공개 서사에 반영할 때 필요한 핵심 문서와 제외해야 할 내용을 함께 기록한다.

## planning_problem_definition

- 문서 수: 1
- 핵심 후보: `docs/v1.0.0/anchor.md`, 초기 anchor 계열 문서
- 공개 반영: 항공권 구매 시점 추천이라는 문제 정의, MVP 범위, Phase 마감 상태
- 제외: 내부 일정, 개인 작업 메모, 검증되지 않은 TODO
- 근거 부족: 사용자 조사나 외부 시장 근거는 별도 보강 필요

## crawler_data_collection

- 문서 수: 자동 분류에서는 적게 잡혔으나 v0.x, schema, checklist 문서에 분산되어 있음
- 핵심 후보: v0.4~v0.5 계열 수집 운영 문서, crawler/checklist 문서
- 공개 반영: 반복 관측이 필요한 이유, 가격 이력 DB가 필요한 이유
- 제외: 실제 운영 endpoint, 내부 서버 경로, 민감 설정
- 근거 부족: public repo에 공개 가능한 sample 수집 config 정리가 필요

## db_schema_storage

- 핵심 후보: schema 계열 문서, observation 관련 phase 문서
- 공개 반영: search observation과 flight offer observation 중심의 저장 구조 설명
- 제외: 실제 DB 접속 정보, 운영 테이블 dump, 내부 migration 로그
- 근거 부족: public 문서용 ERD 또는 간단 schema diagram 필요

## eda_analysis

- 핵심 후보: `docs/eda/eda_report.md`
- 공개 반영: 가격 변동성이 존재하고, 단순 최저가 목록만으로는 구매 시점 판단이 어렵다는 배경
- 제외: 원천 데이터 row 또는 민감 경로가 포함된 raw output
- 근거 부족: 발표용 핵심 chart만 별도 정리 가능

## modeling_label_evaluation

- 핵심 후보: `docs/modeling/label_design.md`, `docs/modeling/final_modeling_summary_clean_v1.md`, Phase 13~14 문서
- 공개 반영: BUY/WAIT 라벨, Stage1/Stage2 구조, Exp-C 평가 기준
- 제외: 모델 바이너리, 내부 artifact 경로, raw evaluation output
- 근거 부족: 외부 논문/기존 연구 인용은 선택 보강

## model_training_retraining

- 핵심 후보: Phase 15~16 retrain, threshold, runtime smoke, live switch 문서
- 공개 반영: final freeze, full retrain, threshold review, live 적용 과정
- 제외: 내부 학습 workspace 경로, 모델 파일 원본, 학습 raw data
- 근거 부족: 공개용 training pipeline skeleton 정리 필요

## backend_api_serving

- 핵심 후보: API contract, recommend/history, analyze-job, model-info 관련 문서
- 공개 반영: candidates, prediction, history, route-analysis, model-info의 역할
- 제외: 운영 도메인, 내부 IP, 비공개 환경값
- 근거 부족: public API contract 문서와 실제 README 간 용어 통일 필요

## roundtrip_support

- 핵심 후보: Phase 7~11 왕복 후보, 왕복 예측, 왕복 history, roundtrip analyze-job 문서
- 공개 반영: 편도와 왕복을 분리한 이유, 왕복 조합 난도, 왕복 전용 모델/threshold
- 제외: 운영 smoke의 실제 요청 주소와 내부 output 경로
- 근거 부족: 왕복 data flow diagram 있으면 좋음

## frontend_ui_ux

- 핵심 후보: Phase 11, Phase 16E UI polish 문서
- 공개 반영: 신뢰도 제거, 가격 하락 기대 강도, 카드/상세/분석 화면 개선
- 제외: 내부 캡처 파일 경로, 임시 디자인 메모
- 근거 부족: 최신 화면 스크린샷을 public-safe asset으로 정리 필요

## deployment_infra

- 핵심 후보: Phase 12 signed release, Vercel, live switch 문서
- 공개 반영: 웹 배포, APK release build, backend live model switch의 개념
- 제외: 운영 서버 주소, 계정명, private key, signing secret
- 근거 부족: public deployment guide는 mock/local 중심으로 작성 필요

## apk_mobile

- 핵심 후보: Android icon/splash, APK build, native shell 관련 문서
- 공개 반영: APK build 가능성, launcher/splash 분리, 모바일 화면 검증
- 제외: release keystore, signing 설정값
- 근거 부족: release APK 공유 절차는 별도 문서화 필요

## qa_smoke_validation

- 핵심 후보: 각 Phase의 smoke/runtime/build validation 문서
- 공개 반영: build, runtime smoke, route-analysis, predict-one, model-info 검증 절차
- 제외: 실제 운영 요청 주소, raw response에 민감값이 있는 경우
- 근거 부족: public-safe smoke checklist 통합 필요

## public_release_cleanup

- 핵심 후보: repo cleanup Phase 0~3 문서
- 공개 반영: 공개 repo에서 제외한 파일과 기준, 공개/비공개 경계
- 제외: secret scan raw hit 원문
- 근거 부족: 최종 push 전 checklist 문서 필요
