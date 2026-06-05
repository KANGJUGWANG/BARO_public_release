# Pipeline code map 요약

## 목적

Phase 3.5-C에서는 문서 근거만 정리하지 않고 실제 소스코드 위치를 pipeline 단계별로 매핑했다. private repo와 public repo를 모두 read-only로 확인했고, 문서에는 repo-relative path만 기록했다.

## 주요 결과

| 영역 | 상태 | 공개 repo 처리 방향 |
| --- | --- | --- |
| crawler/parser/collector | public repo에 일부 존재 | config와 외부 source 의존성 제거 후 sample 중심 문서화 |
| DB loader/storage | public repo에 존재 | 실제 DB 없이 placeholder와 schema 설명 중심 |
| feature builder | public repo에 존재 | model artifact 없이 contract 설명 가능 |
| label/training/retraining | private repo tools 중심 | public repo에는 document_only 또는 skeleton 필요 |
| threshold/package/live switch | private repo tools 중심 | 운영 artifact 조작 영역이므로 공개는 요약 중심 |
| runtime adapter | public repo에 존재 | model 파일 제외 조건으로 유지 가능 |
| FastAPI serving | public repo에 존재 | env placeholder 기반 유지 가능 |
| frontend UI | public repo에 존재 | 유지 가능 |
| APK/Capacitor | public repo에 존재 | signing secret 제외 조건으로 유지 가능 |
| systemd/deploy | public repo에 template 존재 | 실제 운영값 제거 확인 필요 |

## 핵심 판단

공개 repo는 서비스 실행 구조와 UI/backend contract를 보여주기에는 충분하다. 다만 full retrain과 live inference를 완전히 재현하려면 private DB, materialized dataset, model artifact가 필요하다. 따라서 training pipeline은 현재 상태에서 `document_only`로 두고, 후속 phase에서 sample 기반 skeleton을 만드는 편이 안전하다.

## 다음 단계

1. `pipeline_code_map.csv`에서 `document_only`와 `needs_refactor=true` 항목을 우선 검토한다.
2. 공개 가능한 training skeleton을 별도 `pipelines/training`으로 만들지 결정한다.
3. crawler와 DB loader는 sample config 기반으로만 공개한다.
4. systemd/deploy template은 실제 운영값이 없는지 별도 scan한다.
