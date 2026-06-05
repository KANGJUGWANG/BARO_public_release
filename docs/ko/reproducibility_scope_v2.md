# BARO 재현 가능 범위 v2

## Level 0: 코드/문서 구조 확인

공개 repo만으로 가능한 범위다.

- frontend/backend 디렉토리 구조 확인
- API contract 문서 확인
- 모델 구조와 라벨/평가 기준 이해
- public README와 docs 기반 프로젝트 흐름 파악

## Level 1: 공개 sample 또는 mock 기반 smoke

공개 가능한 예시 설정과 sample data가 추가되면 가능한 범위다.

- frontend build
- backend import/compile
- mock response 기반 화면 확인
- API schema 수준 smoke

현재 공개 repo에는 실제 운영 데이터와 모델 바이너리가 없으므로 동일 예측값 재현은 불가능하다.

## Level 2: private DB/data가 있는 경우 full retrain 가능

비공개 관측 DB 또는 materialized dataset이 있어야 가능한 범위다.

- crawler output 기반 DB 복원
- feature/label materialization
- Stage1/Stage2 학습 데이터 재생성
- Exp-C label 재계산
- train/calibration/holdout 평가

이 단계는 공개 repo 단독 범위를 넘는다.

## Level 3: private model artifact가 있는 경우 live inference 가능

비공개 모델 artifact가 있어야 가능한 범위다.

- runtime model load
- predict-one 결과 재현
- analyze-job batch prediction
- model-info/health의 실제 artifact 상태 확인

모델 바이너리는 공개 repo에 포함하지 않는다.

## Level 4: 운영 서버/DB까지 포함한 완전 재현

운영 서버, 운영 DB, 외부 API 설정, 배포 설정까지 모두 필요하다. 이 범위는 공개 대상이 아니다.

## crawler pipeline 재현 조건

- 외부 항공권 검색 source 접근 권한
- 요청 제한과 timeout 정책
- 수집 대상 노선/날짜/항공사 config
- DB 저장 schema
- 실패/부분 성공 처리 정책

## DB schema/storage 재현 조건

- search observation 저장 구조
- offer observation 저장 구조
- route/date/trip key 정책
- history 조회와 candidates 조회 기준

## feature/label pipeline 재현 조건

- 가격 이력 window
- DPD 계산
- 누적 min/max/mean/std feature
- route/airline/flight encoding
- Exp-C 72h/20,000원/3% label 계산

## Stage1/Stage2 training 재현 조건

- Stage1 target과 feature order
- Stage2 input에 pred_saving 포함
- trip별 모델 계열
- threshold calibration 기준
- purged temporal split 정책

## model packaging 재현 조건

- trip별 Stage1/Stage2 파일명
- threshold metadata
- model-info contract
- runtime smoke 통과

## backend/frontend 재현 조건

- backend는 공개 config placeholder를 실제 환경값으로 채워야 함
- frontend는 공개 API base URL 또는 local backend를 바라보도록 설정해야 함
- APK/release build는 signing secret 없이 debug 수준까지만 공개 재현 가능

## 제출용 zip과 공개 GitHub 차이

제출용 zip은 평가자에게 필요한 정적 산출물을 포함할 수 있지만, 공개 GitHub는 민감 자산을 배제한다. 두 산출물 모두 모델 바이너리와 원천 DB를 포함하지 않는 것을 기본 정책으로 둔다.

## Phase 3.5-D public structure update

Phase 3.5-D added public-safe pipeline directories and sample/config placeholders.

Public structure now includes:

- `pipelines/`: pipeline stage documentation
- `configs/`: placeholder example configs
- `data/sample/`: synthetic schema examples
- `models/`: model artifact policy placeholder
- `outputs/`: generated output policy placeholder

Public sample smoke is limited to schema understanding and build/import checks. Full materialization, training, packaging, and production-like inference still require private datasets and model artifacts.

## Suggested public execution order

1. Read `pipelines/README.md`.
2. Review placeholder configs under `configs/`.
3. Inspect synthetic samples under `data/sample/`.
4. Build the frontend.
5. Run backend syntax/import checks.
6. Use private datasets/artifacts only in a private environment for full retraining or inference.
