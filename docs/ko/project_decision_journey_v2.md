# BARO 프로젝트 의사결정 여정 v2

Phase 3.5-A 문서는 모델 개선과 Exp-C 중심이었다. 이 v2 문서는 `docs/` 전수 인덱싱 결과를 반영해 기획, 데이터, DB, 모델, backend, frontend, APK, 공개 repo까지 포함한다.

## 1. 왜 항공권 구매 시점 추천인가

문제는 단순 항공권 검색이 아니라 구매 타이밍 판단이었다. 사용자는 최저가 후보를 볼 수 있어도 현재 가격이 앞으로 더 내려갈지 알기 어렵다. BARO는 이 불확실성을 줄이기 위해 가격 관측 이력과 현재 후보 가격을 함께 분석하는 서비스로 정의됐다.

- 문제: 가격 변동 맥락 없이 현재 가격만 보고 구매 결정을 해야 함
- 판단: 검색 결과 나열보다 구매 시점 추천이 더 차별화됨
- 실행: BUY/WAIT 추천 UX를 MVP 중심으로 설계
- 결과: 서비스 핵심 문구와 모델 목적이 “구매 보조”로 정리됨
- 근거 문서: v0.x anchor/checklist, v1.0.0 anchor

## 2. 왜 단순 검색이 아니라 BUY/WAIT인가

단순 검색은 현재 후보 가격을 보여주지만, “지금 구매할지”에 대한 행동 결정을 직접 돕지 않는다. BUY/WAIT은 모델 출력과 가격 이력을 사용자가 바로 이해할 수 있는 행동 단위로 변환한다.

- 문제: 회귀값이나 확률만 보여주면 사용자가 행동하기 어려움
- 판단: 구매 권장/대기 권장이라는 이진 표현이 MVP에 적합
- 실행: prediction decision을 카드와 상세 화면에 표시
- 결과: 검색 결과가 가격 목록에서 의사결정 보조 화면으로 전환됨
- 근거 문서: modeling summary, Phase 8~11 frontend 문서

## 3. 왜 데이터 수집부터 직접 해야 했는가

구매 시점 추천은 현재 가격 하나로 만들 수 없다. 같은 항공편이 시간에 따라 어떻게 변했는지 알아야 하므로 반복 관측 데이터가 필요했다.

- 문제: 외부 검색 API 응답은 순간 가격만 제공함
- 판단: 가격 history를 직접 축적해야 모델 feature를 만들 수 있음
- 실행: 대상 노선/날짜/항공사 관측, search observation과 offer observation 저장
- 결과: 후보 조회, 가격 추이, 모델 추론의 기반 생성
- 근거 문서: v0.4~v0.5 수집 문서, schema/observation 문서

## 4. 왜 DB 관측 구조가 필요했는가

가격 history를 카드, 상세, 모델, 분석 페이지가 모두 재사용해야 했다. 그래서 검색 조건 단위 관측과 항공권 후보 단위 관측을 분리해 저장하는 구조가 필요했다.

- 문제: raw 응답만 저장하면 후보별 가격 변화 추적이 어려움
- 판단: 검색 관측과 offer 관측을 분리해야 history와 candidates를 안정적으로 만들 수 있음
- 실행: route/date/trip 조건과 항공편 후보 row를 연결
- 결과: DB 후보 조회, 실시간 refresh fallback, 가격 추이 API 기반 마련
- 근거 문서: schema 계열 문서, Phase 9 후보/history 문서

## 5. 왜 Stage1/Stage2 구조인가

처음부터 BUY/WAIT만 직접 맞추면 가격 하락 규모 정보가 사라질 수 있다. BARO는 먼저 예상 절약 가능성을 추정하고, 그 값을 다시 WAIT 확률 판단에 넣는 2단계 구조를 선택했다.

- 문제: 가격 하락 크기와 구매 행동 판단은 다르다
- 판단: Stage1은 예상 절약 가능성, Stage2는 WAIT 확률을 맡기는 구조가 설명 가능함
- 실행: Stage1 output인 pred_saving을 Stage2 input으로 사용
- 결과: decision은 WAIT probability와 threshold 비교로 결정
- 근거 문서: label_design, final_modeling_summary_clean_v1, runtime artifact contract

## 6. 기존 라벨은 왜 부족했는가

초기 라벨은 미래 절약 가능성이 변동성 기준을 넘는지를 사용했다. 이 방식은 수학적으로 일관성이 있지만, 사용자가 체감하는 “기다릴 가치”와 완전히 같지는 않았다.

- 문제: BUY 추천 후 실제로 가까운 시간 안에 가격이 내려가는 BUY regret이 남음
- 판단: BUY 비율 자체보다 BUY regret이 서비스 품질의 핵심
- 실행: realistic outcome, 72h, 20,000원, 3% 기준을 평가 후보로 확장
- 결과: Exp-C 기준이 주요 후보가 됨
- 근거 문서: Phase 13-4, Phase 13-5, Phase 14 문서

## 7. 왜 Exp-C 기준인가

Exp-C는 72시간 안에 20,000원 이상이면서 3% 이상 하락하는지를 기준으로 삼는다. 72시간은 사용자가 실제로 기다릴 수 있는 시간 범위이고, 20,000원과 3%는 절대/상대 가격 체감을 동시에 반영한다.

- 문제: 미래 최저가 전체 기준은 사용자가 실제로 기다릴 수 있는 시간과 다를 수 있음
- 판단: 시간 제한과 체감 절약 기준을 함께 둬야 함
- 실행: Exp-A 대비 Exp-C의 BUY regret과 WAIT success 비교
- 결과: Phase 14-8에서 BUY regret 20.79%에서 15.94%, WAIT success 31.37%에서 41.52%로 개선
- 근거 문서: Phase 14-8, Phase 14-9B

## 8. 왜 편도/왕복을 분리했는가

왕복은 출국편과 귀국편 조합, return date, stay nights, 귀국편 번호까지 포함한다. 편도와 동일 모델/threshold로 묶으면 feature 의미와 후보 분포가 달라진다.

- 문제: 왕복은 단일 항공편 가격 흐름보다 조합 복잡도가 큼
- 판단: 모델 파일, feature contract, threshold를 trip별로 분리해야 함
- 실행: oneway와 roundtrip runtime/artifact contract 분리
- 결과: 최종 운영 기준 편도 threshold 0.80, 왕복 threshold 0.65
- 근거 문서: Phase 13-1, Phase 16C~16E

## 9. 왜 threshold를 편도 80%, 왕복 65%로 분리했는가

같은 WAIT probability라도 편도와 왕복의 분포와 regret/success tradeoff가 다르다. Phase 16B-3C threshold review에서 편도는 0.80이 유지됐고, 왕복은 0.65가 BUY regret 감소와 WAIT success 유지 사이에서 더 적합한 후보로 정리됐다.

- 문제: 하나의 threshold로 trip별 tradeoff를 동시에 맞추기 어려움
- 판단: trip별 threshold가 더 안전함
- 실행: threshold review 후 artifact repackaging과 runtime smoke 수행
- 결과: live model-info와 predict-one에서 trip별 threshold 확인
- 근거 문서: Phase 16B-3C, Phase 16B-3D, Phase 16C, Phase 16D

## 10. 왜 UI에서 신뢰도 대신 가격 하락 기대 강도인가

confidence는 실제 검증 정확도가 아니라 모델 판단 강도에 가까웠다. 사용자가 “정확도 99%”로 오해할 수 있으므로 표현을 바꿨다.

- 문제: 신뢰도라는 표현이 모델 정확도로 오해될 수 있음
- 판단: wait probability 기반 표시를 가격 하락 기대 강도로 설명하는 편이 정확함
- 실행: 카드, 상세, 분석 화면의 표현 정리와 threshold marker 추가
- 결과: 추천 결과의 의미가 사용자에게 더 명확해짐
- 근거 문서: Phase 16E, Phase 16E-1, Phase 16E-2

## 11. 왜 공개 repo에는 모델/데이터를 포함하지 않는가

모델 바이너리와 원천 데이터는 용량, 라이선스, 보안, 재현 환경 문제를 가진다. 공개 repo는 구조와 의사결정 근거를 보여주는 목적이고, 운영 자산 배포가 목적이 아니다.

- 문제: 모델과 DB 원본을 공개하면 용량과 민감정보 위험이 큼
- 판단: 공개 repo는 code/docs/example 중심으로 구성해야 함
- 실행: secret scan, large file scan, cleanup inventory, README 정리
- 결과: public release repo는 구조 설명과 로컬 smoke 중심으로 정리됨
- 근거 문서: repo cleanup Phase 0~3 문서

## 12. 어느 수준까지 재현 가능하게 만들 것인가

공개 repo만으로 최종 운영 예측값을 완전히 재현할 수는 없다. 대신 코드 구조, API contract, UI, 문서화된 모델 구조와 평가 기준은 확인할 수 있게 한다.

- 문제: private DB/model 없이는 full retrain과 live inference 재현이 불가능
- 판단: 재현 범위를 단계별로 명시해야 함
- 실행: reproducibility scope v2에서 Level 0~4로 범위 분리
- 결과: public repo와 제출용 zip의 역할 차이가 명확해짐
- 근거 문서: public cleanup 문서, Phase 16 final docs
