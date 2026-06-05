# Internal Phase Logs Excluded

원본 비공개 레포에는 phase별 구현 로그, smoke 결과, 실험 노트가 다수 포함되어 있습니다.

공개 레포에서는 해당 내부 로그 원문을 제외하고, `docs/ko`와 `docs/en` 아래의 공개용 요약 문서로 대체합니다.

제외 대상:

- phase별 내부 구현 로그
- private path 또는 URL이 포함된 server smoke evidence
- raw experiment output 설명
- 일반 사용자에게 필요하지 않은 cleanup audit manifest

공개 레포는 프로젝트 개요, 아키텍처, API contract, 모델 요약, 실행 가능한 소스 구조에 집중합니다.
