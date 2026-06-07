# Phase 11D-1: ModelInfo 모델 정보 자동 최신화

## 1. 문제 배경

Phase 11D에서 ModelInfoPage UI 정리는 완료되었지만, 모델 정보는 단일 `model_version` 중심으로 표시되고 있었다.

기존 `/recommend/model-info`는 기본 모델 디렉터리의 `final_model_metadata.json`을 읽어 `finaltest_clean_v1` 계열 버전만 대표 모델처럼 반환했다. 반면 실제 운영 prediction 경로는 편도와 왕복이 분리되어 있다.

## 2. 왕복 모델 적용 확인 근거

이전 운영 확인에서 왕복 `predict-one` 응답은 다음 값을 반환했다.

- `prediction_status=ok`
- `model_version=finaltest_roundtrip_xgb_xgb_v1`
- `threshold=0.33999999999999997`
- `feature_status=ok`

따라서 왕복 모델 미적용 문제가 아니라, ModelInfo 표시 계약이 과거 편도 중심 구조로 남아 있던 문제다.

## 3. 개선된 response contract

`ModelInfoResponse`에 `models` 필드를 추가했다. 기존 `model_version`은 하위 호환을 위해 유지한다.

```json
{
  "status": "ok",
  "model_version": "finaltest_clean_v1",
  "models": {
    "oneway": {
      "status": "active",
      "display_name": "편도 추천 모델",
      "model_version": "finaltest_clean_v1",
      "artifact_status": "ok",
      "threshold": 0.55
    },
    "roundtrip": {
      "status": "active",
      "display_name": "왕복 추천 모델",
      "model_version": "finaltest_roundtrip_xgb_xgb_v1",
      "artifact_status": "ok",
      "threshold": 0.34
    }
  }
}
```

프론트 일반 안내 화면에서는 threshold를 강조하지 않고, 편도/왕복 추천 모델의 운영 상태와 버전만 보조 정보로 표시한다.

## 4. Backend 수정 내용

- `backend/recommend/schema.py`
  - `ModelInfoResponse.models` 추가
- `backend/recommend/service.py`
  - 기존 단일 `model_version` 유지
  - `models.oneway` 구성
  - `models.roundtrip` 구성
  - 왕복 정보는 실제 roundtrip artifact loader인 `load_roundtrip_artifacts()`와 `_roundtrip_model_version()` 결과를 사용
  - `models.oneway.stage1/stage2`와 `models.roundtrip.stage1/stage2`를 분리해 각 모델 파일 상태를 제공
  - 편도는 `oneway_stage1_random_forest.pkl`, `oneway_stage2_xgboost.pkl` 기준
  - 왕복은 `roundtrip_stage1_xgboost.pkl`, `roundtrip_stage2_xgboost.pkl` 기준
  - 모델 파일 경로, feature 전체 목록, hyperparameter, DB table명은 노출하지 않음

## 5. Frontend 수정 내용

- `frontend/src/web/pages/ModelInfoPage.jsx`
  - `models.oneway`, `models.roundtrip`을 우선 표시
  - 기존 `model_version`만 오는 경우에도 fallback 표시
  - “현재 모델: finaltest_clean_v1” 단일 표시를 편도/왕복 모델 상태 카드로 교체
  - “모델 파일 상태” 섹션도 편도/왕복을 분리해 표시
  - 편도 Stage 파일 크기와 왕복 model_version이 한 블록에 섞여 보이지 않도록 수정
- `frontend/src/web/pages/ModelInfoPage.module.css`
  - 모델 상태 카드/운영 중 badge 스타일 추가
  - 모델 파일 상태 분리 표시용 스타일 추가

추천 결과 표현, 신뢰도 문구, BUY/WAIT 설명 문구는 수정하지 않았다.

## 6. 노출하지 않는 내부 정보

- 모델 파일 경로
- feature column 전체 목록
- hyperparameter
- DB table명
- artifact 내부 디렉터리 구조

## 7. 검증 결과

### Backend compile

```bash
python -m py_compile backend\recommend\schema.py backend\recommend\service.py backend\recommend\router.py
```

결과: 통과

### Local contract smoke

로컬 저장소에는 운영 모델 artifact가 없어 `active`가 아니라 `inactive`로 표시되지만, `models.oneway` / `models.roundtrip` 구조 생성은 확인했다.

### Frontend build

```bash
cd frontend
npm.cmd run build
```

결과: 통과

### APK mode build

```bash
npm.cmd run build -- --mode apk
npx cap sync android
```

결과: 통과

## 8. API smoke 결과

운영 서버 재시작 및 live `/recommend/model-info` smoke는 이번 로컬 작업에서 수행하지 않았다.

운영 반영 후 확인해야 할 항목:

- `models.oneway.status=active`
- `models.roundtrip.status=active`
- `models.roundtrip.model_version=finaltest_roundtrip_xgb_xgb_v1` 계열
- 기존 `model_version` 하위 호환 유지

## 9. 수동 확인 여부

브라우저/APK 수동 화면 확인은 미수행.

확인 필요:

- ModelInfoPage에서 편도 추천 모델 / 왕복 추천 모델이 분리 표시되는지
- `finaltest_clean_v1` 하나만 대표 모델처럼 보이지 않는지
- 추천 결과/신뢰도/BUY·WAIT 문구 변경이 없는지

## 10. 남은 이슈

- 운영 서버 배포 후 `/recommend/model-info` live smoke 필요
- 운영 artifact 경로에서 oneway/roundtrip 모두 active로 표시되는지 확인 필요

## 11. 판정

B

구현, compile, frontend build, APK mode build, `cap sync android`는 완료되었다. 운영 서버 반영 및 수동 화면 확인은 아직 미완료다.
