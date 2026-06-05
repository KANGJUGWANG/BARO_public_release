# API Contract 요약

공개 문서에서는 실제 운영 URL 대신 `<BACKEND_API_URL>`을 사용합니다.

## Health

```http
GET <BACKEND_API_URL>/health
GET <BACKEND_API_URL>/health/model
```

## Model Info

```http
GET <BACKEND_API_URL>/recommend/model-info
```

모델 운영 상태, 편도/왕복 모델 표시 정보, threshold 표시 정책을 반환합니다.

## Prediction

```http
POST <BACKEND_API_URL>/recommend/predict-one
POST <BACKEND_API_URL>/recommend/analyze-job
GET  <BACKEND_API_URL>/recommend/jobs/{job_id}
```

## Candidates

```http
POST <BACKEND_API_URL>/recommend/oneway-candidates
POST <BACKEND_API_URL>/recommend/roundtrip-candidates
```

## History

```http
POST <BACKEND_API_URL>/recommend/history
```

가격 추이 표시를 위한 관측 이력 API입니다.

## Route Analysis

```http
GET <BACKEND_API_URL>/recommend/route-analysis
```

노선별 요약 분석 정보를 반환합니다.
