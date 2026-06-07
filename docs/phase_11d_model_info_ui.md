# Phase 11D: Model Info UI

## 1. 작업 목표

`ModelInfoPage`의 안내 화면을 일반 사용자 설명이 먼저 보이도록 정리하고, 소제목 가독성을 높였다.

수정 범위는 `ModelInfoPage` 화면으로 한정했다.

## 2. Section Title CSS 변경

기존:

- `font-size: 12px`
- muted gray
- uppercase

변경:

- `font-size: 15px`
- navy `var(--primary, #1A2B5E)`
- `font-weight: 800`
- uppercase 제거
- 좌측 `3px` accent bar 추가

## 3. 섹션 순서 변경

변경 후 흐름:

1. 모델 개요
2. BUY / WAIT 의미
3. 검색 동작 방식
4. 현재 제공 범위
5. 이용 안내
6. 상세 정보 구분선
7. 분석에 사용하는 정보
8. 모델 구조
9. 데이터 현황
10. 모델 파일 상태

일반 사용자용 설명을 상단에 두고, 세부 구현/파일/데이터 정보는 하단 compact 영역으로 묶었다.

## 4. Badge 텍스트 변경

기존:

- `편도 추천 운영 중`

변경:

- `편도·왕복 추천 운영 중`

## 5. 모델 개요 문구 보강

기존:

- `BARO는 편도 항공권의 구매 시점을 BUY/WAIT으로 추천합니다.`

변경:

- `BARO는 편도/왕복 항공권의 구매 시점을 BUY/WAIT으로 추천합니다.`

추천 결과 표현, 신뢰도 문구, BUY/WAIT badge/문구는 수정하지 않았다.

## 6. 분석 정보 Compact화

`분석에 사용하는 정보` 섹션을 compact 카드로 변경하고 기존 `compactGroup`에 포함했다.

기존 내용은 유지했다.

## 7. Build 결과

통과:

```bash
cd frontend
npm.cmd run build
```

결과: `vite build` 성공.

## 8. APK Build 결과

통과:

```bash
npm.cmd run build -- --mode apk
npx cap sync android
```

결과: APK mode build와 Capacitor sync 성공.

## 9. 수동 확인 결과

미수행.

남은 확인:

- `/model-info` 화면에서 소제목이 navy + 좌측 accent bar로 표시
- 일반 사용자 설명이 상단에 표시
- 상세 정보가 하단 compact 카드로 표시
- `편도·왕복 추천 운영 중` badge 표시
- APK 화면 깨짐 없음

## 10. 판정

B.

구현, 일반 build, APK mode build, Capacitor sync는 완료했다. 브라우저/APK 수동 확인은 아직 미수행이다.
