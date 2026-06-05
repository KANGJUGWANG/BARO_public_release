# 시스템 아키텍처

BARO는 프론트엔드, 백엔드 API, 관측 DB, ML inference runtime으로 구성됩니다.

```text
React/Vite Frontend
  -> FastAPI Backend
      -> Candidate / History / Route Analysis API
      -> ML Inference Runtime
      -> MySQL Observation DB
      -> Refresh / Crawler Jobs
```

## Frontend

- React + Vite 기반 SPA
- 항공권 검색, 검색 결과 카드, 상세 페이지, 모델 안내, 노선 분석 화면 제공
- Capacitor 기반 Android WebView/APK 빌드 구조 포함

## Backend

- FastAPI 기반 API 서버
- 후보 조회, 추천 분석, 가격 추이, 모델 상태, 노선 분석 endpoint 제공
- 실제 운영 환경에서는 private DB와 model artifact가 필요합니다.

## DB

- MySQL 기반 관측 데이터 저장소
- 공개 레포에는 DB dump나 접속 정보가 포함되지 않습니다.

## ML Inference

- Stage1 / Stage2 artifact 기반 추론 구조
- 공개 레포에는 모델 pkl artifact가 포함되지 않습니다.

## Public Placeholder Policy

공개 문서와 예제에서는 실제 서버 URL 대신 `<BACKEND_API_URL>`을 사용합니다.
