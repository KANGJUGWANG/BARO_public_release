# BARO

BARO는 항공권 가격 관측 데이터와 머신러닝 모델을 기반으로 항공권 구매 시점을 `BUY` 또는 `WAIT`으로 안내하는 캡스톤 디자인 프로젝트입니다.

이 공개 레포는 발표/제출용 소스와 문서를 정리한 버전입니다. 실제 운영 DB, 학습 데이터, 모델 pkl artifact, 운영 서버 주소, secret 값은 보안과 용량 문제로 포함하지 않습니다.

## 주요 기능

- 편도/왕복 항공권 후보 조회
- DB 관측 결과와 실시간 갱신 결과 표시
- BUY / WAIT 추천 결과 표시
- 가격 하락 기대 강도 게이지
- 편도/왕복 상세 페이지와 가격 추이
- 노선 분석 화면
- 모바일 WebView / Android APK 빌드 구조

## 시스템 구성

```text
Frontend (React/Vite)
  -> Backend API (FastAPI)
      -> MySQL observation DB
      -> ML inference runtime
      -> crawler/refresh jobs
```

자세한 구조는 [docs/ko/architecture.md](docs/ko/architecture.md)를 참고하세요.

## 모델 구조 요약

BARO 추천 모델은 2-stage 구조입니다.

- Stage 1: 향후 가격 절감 가능성 예측
- Stage 2: BUY / WAIT 판단

서비스 UI에서는 가격 하락 기대 강도를 표시하며, 최종 모델 기준 표시 threshold는 다음과 같습니다.

- 편도: 80%
- 왕복: 65%

모델 세부 설명은 [docs/ko/model_overview.md](docs/ko/model_overview.md)를 참고하세요.

## 데이터 개요

최종 발표 기준 데이터 요약:

- 수집 기간: 2026-04-16 08:00 ~ 2026-06-04 00:00
- 관측 시점: 147개
- 서비스 DB 관측 수: 141,120건
- 학습 가능 항공권 row: 4,562,741건

실제 학습 데이터와 모델 artifact는 공개 레포에 포함하지 않습니다. 자세한 내용은 [docs/ko/data_and_training_summary.md](docs/ko/data_and_training_summary.md)를 참고하세요.

## 기술 스택

- Frontend: React, Vite, CSS Modules, Capacitor
- Backend: FastAPI, Python
- DB: MySQL
- ML: scikit-learn / XGBoost 계열 artifact 기반 inference
- Android: Capacitor Android

## 로컬 실행

### Frontend

```bash
cd frontend
npm install
npm run build
```

개발 서버가 필요하면:

```bash
npm run dev
```

### Backend syntax check

공개 레포에는 실제 DB와 모델 artifact가 포함되지 않으므로 운영 inference 실행은 별도 private 환경이 필요합니다.

```bash
python -m py_compile backend/main.py
```

## 환경변수

실제 값은 공개하지 않습니다. `.env.example` 또는 각 환경의 example 파일을 기준으로 로컬에서 직접 설정해야 합니다.

공개 레포에는 환경변수 이름, HTTP 인증 헤더 이름, 예시 placeholder만 포함됩니다. 실제 운영 값, 운영 서버 주소, 개인 로컬 경로, private model artifact는 포함하지 않는 것을 기준으로 관리합니다.

대표 항목:

```env
VITE_API_BASE_URL=<BACKEND_API_URL>
DB_HOST=<DB_HOST>
DB_USER=<DB_USER>
DB_PASS_PLACEHOLDER=<DB_PASS>
AUTH_PROVIDER_KEY=<AUTH_PROVIDER_KEY>
AUTH_REDIRECT_URI=<AUTH_REDIRECT_URI>
APP_SIGNING_KEY=<APP_SIGNING_KEY>
```

## API 요약

주요 endpoint는 [docs/ko/api_contract.md](docs/ko/api_contract.md)에 정리되어 있습니다.

- `GET /health`
- `GET /health/model`
- `GET /recommend/model-info`
- `POST /recommend/predict-one`
- `POST /recommend/analyze-job`
- `POST /recommend/oneway-candidates`
- `POST /recommend/roundtrip-candidates`
- `POST /recommend/history`


## 재현성 및 파이프라인

- [파이프라인 개요](pipelines/README.md)
- [데이터 샘플 안내](data/README.md)
- [모델 artifact 안내](models/README.md)
- [출력물 정책](outputs/README.md)
- [재현 가능 범위](docs/ko/reproducibility_scope_v2.md)
- [Pipeline code map](docs/ko/pipeline_code_map_summary.md)

## 공개 레포 제한사항

이 레포에는 다음 항목을 포함하지 않습니다.

- 실제 `.env` 파일
- release keystore / jks / key note
- 운영 서버 IP 또는 내부 경로
- 실제 DB dump / parquet / 대용량 csv
- 모델 pkl artifact
- phase별 내부 작업 로그 원문

내부 phase 로그는 공개 문서에서 요약 형태로만 제공합니다.

## 문서

한국어 문서:

- [Architecture](docs/ko/architecture.md)
- [Model Overview](docs/ko/model_overview.md)
- [API Contract](docs/ko/api_contract.md)
- [Data and Training Summary](docs/ko/data_and_training_summary.md)
- [Frontend Guide](docs/ko/frontend_guide.md)
- [Deployment Notes](docs/ko/deployment_notes.md)

English docs:

- [README.en.md](README.en.md)
- [docs/en/architecture.md](docs/en/architecture.md)
- [docs/en/model_overview.md](docs/en/model_overview.md)

## 과제 안내

본 프로젝트는 캡스톤 디자인 발표/제출 목적의 교육용 프로젝트입니다. 항공권 가격과 추천 결과는 보조 정보이며 실제 가격 또는 구매 결과를 보장하지 않습니다.
