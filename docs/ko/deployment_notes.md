# Deployment Notes

공개 레포는 재현 가능한 소스와 문서를 제공하기 위한 버전입니다. 실제 배포에는 private 환경변수, DB, 모델 artifact가 필요합니다.

## Frontend

Vercel 또는 정적 호스팅에 배포할 수 있습니다. API URL은 환경변수로 설정합니다.

```env
VITE_API_BASE_URL=<BACKEND_API_URL>
```

## Backend

FastAPI 서버 실행에는 private `.env`와 DB 접근 정보가 필요합니다. 공개 레포에는 실제 설정값이 포함되지 않습니다.

## Android / APK

Capacitor Android 프로젝트를 통해 APK 빌드가 가능합니다. release keystore와 key password는 공개하지 않습니다.

## Not Included

- production DB
- model pkl artifacts
- server IP/internal paths
- release signing keys
- phase-level internal logs
