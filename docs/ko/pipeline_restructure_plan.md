# BARO pipeline 재구성 계획

현재 공개 repo는 최종 제출을 위한 정리 상태이며, 학습/수집 pipeline이 발표용으로 깔끔하게 재구성된 상태는 아니다. 이 문서는 실제 파일 이동 없이 다음 단계에서 어떤 구조로 정리할지 계획만 기록한다.

## 현재 공개 repo에서 확인되는 pipeline 후보

- backend API serving 코드
- frontend UI 코드
- Android/APK 관련 코드
- 일부 tools/scripts 후보
- docs 기반 retraining and validation 기록

## private repo에서 공개 가능 후보로 검토할 영역

- crawler 실행 entrypoint 중 민감 설정 제거 가능한 부분
- dataset materialization helper 중 경로/DB credential 제거 가능한 부분
- feature/label generation logic 중 sample 기반으로 동작 가능한 부분
- training script 중 artifact 경로와 private data dependency 제거 가능한 부분
- packaging/smoke script 중 public-safe sample로 실행 가능한 부분

## 정리 대상별 후보

| 영역 | 공개 후보 | 제거해야 할 민감 정보 |
| --- | --- | --- |
| crawler | 요청/파싱 구조, timeout/fallback 정책 | 실제 API key, 운영 endpoint, 계정 정보 |
| dataset | sample materialization flow | 원천 DB 경로, raw dump, 내부 output 경로 |
| feature/label | feature column, Exp-C label 계산 | private dataset 직접 참조 |
| training | Stage1/Stage2 training skeleton | pkl artifact, raw train data |
| packaging | model-info contract, threshold schema | 실제 artifact directory |
| smoke | mock/local smoke checklist | 운영 서버 주소, raw production response |

## 권장 디렉토리 구조

```text
pipelines/
  crawler/
  dataset/
  features/
  training/
  packaging/
  smoke/
configs/
  examples/
data/
  sample/
models/
  README.md
outputs/
  README.md
```

## 공개화 작업 순서

1. private scripts 목록을 inventory로 만든다.
2. 각 script가 참조하는 private path, DB, secret, model artifact를 표시한다.
3. 공개 가능한 script는 config example과 sample data 기반으로 바꾼다.
4. 공개 불가능한 script는 문서상 flow만 남긴다.
5. README에서 “full retrain은 private data 필요”를 명시한다.

## 이번 Phase에서 하지 않은 것

- 실제 파일 이동 없음
- script 삭제 없음
- pipeline 디렉토리 생성 없음
- private repo 수정 없음
- model/data artifact 추가 없음

## Phase 3.5-D completed structure

Created public-safe structure:

- `pipelines/README.md`
- `pipelines/crawler/README.md`
- `pipelines/dataset/README.md`
- `pipelines/training/README.md`
- `pipelines/packaging/README.md`
- `pipelines/smoke/README.md`
- `configs/*.example.*`
- `data/sample/*.csv`
- `models/README.md`
- `outputs/README.md`

Document-only areas remain:

- full dataset materialization
- full Stage1/Stage2 retraining
- threshold repackaging
- live model switch

These require private data, private model artifacts, or operational environment values. The public repository now documents the flow without exposing those assets.
