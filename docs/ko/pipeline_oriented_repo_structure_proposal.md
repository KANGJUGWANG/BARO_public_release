# Pipeline-oriented 공개 repo 구조 제안

## 목표

현재 공개 repo는 기능별 소스와 문서가 남아 있지만, 수집부터 학습, 패키징, smoke까지의 pipeline 흐름이 한눈에 보이도록 정리되지는 않았다. 이 문서는 실제 파일 이동 없이 다음 구조 정리 방향만 제안한다.

## 권장 구조

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
backend/
frontend/
docs/
```

## 디렉토리별 역할

| directory | 들어갈 코드 | 제외할 코드/파일 | README 필요 | sample 필요 | private artifact 필요 |
| --- | --- | --- | --- | --- | --- |
| pipelines/crawler | public-safe parser, url builder, collector skeleton | 실제 API key, 운영 endpoint 의존 코드 | yes | yes | no |
| pipelines/dataset | sample materialization flow | 원천 DB dump, private output 경로 | yes | yes | yes for full run |
| pipelines/features | feature builder, label builder skeleton | raw private dataset 참조 | yes | yes | yes for full run |
| pipelines/training | Stage1/Stage2 training skeleton | pkl output, private train data | yes | yes | yes |
| pipelines/packaging | metadata/threshold packaging example | 실제 artifact copy command | yes | no | yes |
| pipelines/smoke | mock/local smoke scripts | production API call script | yes | yes | optional |
| configs/examples | env/config examples | real secrets | yes | no | no |
| data/sample | tiny mock data | real DB export, csv dump | yes | yes | no |
| models | model artifact policy README | pkl/json real artifact | yes | no | yes |
| outputs | output policy README | real experiment output | yes | no | no |

## 현재 public repo에서 유지 가능한 영역

- `backend/`
- `frontend/`
- `frontend/android/`
- `docs/`
- `.env.example`
- `frontend/android/keystore.properties.example`

## 별도 검토가 필요한 영역

- crawler collector의 외부 source 의존성
- DB loader의 실제 DB 연결 전제
- training tools의 private data path 의존성
- deploy/systemd template의 운영값 포함 가능성
- Android signing 관련 파일 제외 상태

## 이번 Phase에서 하지 않은 것

- 실제 파일 이동 없음
- 새 pipeline 디렉토리 생성 없음
- private repo 수정 없음
- pkl/data artifact 추가 없음
- git add/commit/push 없음
