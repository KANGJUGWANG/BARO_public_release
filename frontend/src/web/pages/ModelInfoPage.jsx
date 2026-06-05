import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { fetchModelInfo } from '../../api/client'
import styles from './ModelInfoPage.module.css'

const FINAL_TRAINING_DATA = {
  collectedRange: '2026-04-16 08:00 ~ 2026-06-04 00:00',
  observationPoints: 147,
  serviceObservationCount: 141120,
  totalRows: 4562741,
  onewayRows: 989669,
  roundtripRows: 3573072,
}

export default function ModelInfoPage() {
  const navigate = useNavigate()
  const [modelInfo, setModelInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')

    fetchModelInfo()
      .then(data => {
        if (cancelled) return
        if (data?.status === 'ok') {
          setModelInfo(data)
        } else {
          setError('모델 정보를 불러오지 못했습니다.')
        }
      })
      .catch(() => {
        if (cancelled) return
        setError('모델 정보를 불러오지 못했습니다.')
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const info = modelInfo || fallbackModelInfo
  const stage1 = info.architecture?.stage1 || {}
  const stage2 = info.architecture?.stage2 || {}
  const decisionPolicyByTrip = info.decision_policy_by_trip || {}
  const onewayThreshold = decisionPolicyByTrip.oneway?.wait_threshold ?? info.models?.oneway?.threshold ?? info.decision_policy?.wait_threshold
  const roundtripThreshold = decisionPolicyByTrip.roundtrip?.wait_threshold ?? info.models?.roundtrip?.threshold
  const featureCount = info.features?.total_unique_count
  const artifacts = info.artifacts || {}
  const artifactValues = Object.values(artifacts)
  const artifactsOk = artifactValues.length > 0 && artifactValues.every(Boolean)
  const serviceCount = info.data?.service_observation_count ?? FINAL_TRAINING_DATA.serviceObservationCount
  const trainingData = {
    collectedRange: info.data?.collection_period || FINAL_TRAINING_DATA.collectedRange,
    observationPoints: info.data?.observation_points ?? FINAL_TRAINING_DATA.observationPoints,
    totalRows: info.data?.training_row_count ?? info.data?.total_training_rows ?? FINAL_TRAINING_DATA.totalRows,
    onewayRows: info.data?.oneway_training_rows ?? FINAL_TRAINING_DATA.onewayRows,
    roundtripRows: info.data?.roundtrip_training_rows ?? FINAL_TRAINING_DATA.roundtripRows,
  }
  const modelVersion = info.model_version || '모델 버전 정보 없음'
  const modelEntries = getModelEntries(info, modelVersion)
  const artifactModifiedAt = info.dates?.artifact_modified_at || '기준일 정보 없음'

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate(-1)}>
          <ArrowLeft size={22} color="#fff" />
        </button>
        <span className={styles.title}>모델·검색 안내</span>
        <div style={{ width: 36 }} />
      </header>

      <main className={styles.main}>
        {loading && (
          <div className={styles.section}>
            <p className={styles.sectionTitle}>모델·검색 안내</p>
            <div className={styles.emptyBox}>모델·검색 정보를 불러오는 중입니다.</div>
          </div>
        )}

        {error && (
          <div className={styles.section}>
            <p className={styles.sectionTitle}>안내</p>
            <div className={styles.emptyBox}>
              {error}<br />
              편도 추천 기능은 현재 운영 중입니다.
            </div>
          </div>
        )}

        <Section title="모델 개요">
          <span className={styles.badge}>편도·왕복 추천 운영 중</span>
          <p className={styles.desc}>
            BARO는 7주간 수집한 항공권 가격 관측 데이터를 기반으로 현재 구매할지, 가격 하락을 기다릴지 판단합니다.<br />
            추천 결과는 구매 보조 정보이며 실제 가격을 보장하지 않습니다.
          </p>
        </Section>

        <Section title="BUY / WAIT 의미">
          <p className={styles.desc}>
            BUY: 현재 가격 기준 구매 권장<br />
            WAIT: 추가 하락 가능성을 고려해 대기 권장<br />
            추천은 구매 보조 정보이며 실제 가격을 보장하지 않습니다.
          </p>
        </Section>

        <Section title="검색 동작 방식">
          <p className={styles.desc}>
            편도 검색: 실시간 항공권 검색 후 가격 분석<br />
            왕복 검색: 최신 관측 결과를 먼저 표시하고, 가능한 경우 백그라운드 실시간 갱신을 시도합니다.<br />
            왕복은 출국편과 귀국편 조합 확인이 필요해 편도보다 시간이 오래 걸릴 수 있습니다.<br />
            서비스 안정성을 위해 왕복 실시간 검색에는 최대 3분 제한이 적용됩니다.<br />
            제한 시간 안에 확인된 결과만 반영되며, 지연되거나 실패한 경우 기존 최신 관측 결과를 유지합니다.
          </p>
        </Section>

        <Section title="현재 제공 범위">
          <p className={styles.desc}>
            편도 추천 운영 중 (ICN ↔ NRT / ICN ↔ HND)<br />
            왕복 추천 운영 중 (7일 체류 기준)<br />
            과거 이력이 충분한 항공편 우선 분석
          </p>
          <div className={styles.modelStatusGroup}>
            {modelEntries.map(model => (
              <div key={model.key} className={styles.modelStatusCard}>
                <div>
                  <p className={styles.modelStatusName}>{model.displayName}</p>
                  <p className={styles.modelStatusVersion}>{model.modelVersion}</p>
                </div>
                <span
                  className={
                    model.status === 'active'
                      ? styles.modelStatusActive
                      : styles.modelStatusInactive
                  }
                >
                  {model.statusLabel}
                </span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="이용 안내">
          <p className={styles.desc}>
            추천 결과는 구매를 보조하는 정보이며 항공권 가격은 실시간으로 변동할 수 있습니다.<br />
            실시간 검색 timeout은 오류가 아니라 서비스 안정성을 위한 보호 장치입니다.
          </p>
        </Section>

        <div className={styles.detailDivider}>
          <span className={styles.detailLabel}>상세 정보</span>
        </div>

        <div className={styles.compactGroup}>
          <Section title="분석에 사용하는 정보" compact>
            <p className={styles.desc}>
              현재 항공편 가격<br />
              과거 관측 가격 이력<br />
              출발일까지 남은 기간(DPD)<br />
              항공사 및 항공편 패턴<br />
              {featureCount > 0
                ? `총 ${featureCount}개 분석 지표 활용`
                : '분석 지표 정보 없음'}
            </p>
          </Section>

          <Section title="모델 구조" compact>
            <p className={styles.desc}>
              Stage 1: {stage1.role || '향후 가격 절감 가능성 예측'}
              {stage1.model_type ? ` / ${stage1.model_type}` : ''}<br />
              Stage 2: {stage2.role || 'BUY/WAIT 판단'}
              {stage2.model_type ? ` / ${stage2.model_type}` : ''}<br />
              {formatDecisionPolicy(onewayThreshold, roundtripThreshold)}<br />
              Stage 2는 72시간 내 20,000원 이상 또는 3% 이상 가격 하락 가능성을 기준으로 학습했습니다.<br />
              가격 하락 기대 강도는 모델이 계산한 추가 하락 가능성의 표시값이며 실제 가격 하락을 보장하지 않습니다.
            </p>
          </Section>

          <Section title="데이터 현황" compact>
            <p className={styles.modelNote}>
              수집 기간: {trainingData.collectedRange}<br />
              관측 시점: {formatCount(trainingData.observationPoints, '개')}<br />
              서비스 DB 관측 수: {formatCount(serviceCount)}<br />
              현재 서비스 누적 관측 수이며 학습 row 수와 다를 수 있습니다.<br />
              학습 가능 항공권 row: {formatCount(trainingData.totalRows)}<br />
              편도 학습 row: {formatCount(trainingData.onewayRows)}<br />
              왕복 학습 row: {formatCount(trainingData.roundtripRows)}
            </p>
          </Section>

          <Section title="모델 파일 상태" compact>
            <div className={styles.modelFileGroup}>
              {modelEntries.map(model => (
                <div key={model.key} className={styles.modelFileItem}>
                  <p className={styles.modelFileTitle}>{model.displayName}</p>
                  <div className={styles.stageFileGrid}>
                    <ModelStageStatus
                      title="Stage 1"
                      role="향후 가격 절감 가능성 예측"
                      stage={model.stage1 || stage1}
                    />
                    <ModelStageStatus
                      title="Stage 2"
                      role="BUY/WAIT 판단"
                      stage={model.stage2 || stage2}
                      threshold={model.threshold}
                    />
                  </div>
                  <p className={styles.modelNote}>
                    artifact 기준일: {model.artifactModifiedAt || artifactModifiedAt}<br />
                    artifact 파일: {formatArtifactStatus(model.artifactStatus, artifactsOk)}<br />
                    model_version: {model.modelVersion}
                  </p>
                </div>
              ))}
            </div>
          </Section>
        </div>
      </main>
    </div>
  )
}

function Section({ title, compact = false, children }) {
  return (
    <div className={compact ? `${styles.section} ${styles.compactSection}` : styles.section}>
      <p className={styles.sectionTitle}>{title}</p>
      {children}
    </div>
  )
}

function ModelStageStatus({ title, role, stage, threshold }) {
  return (
    <div className={styles.stageFileCard}>
      <p className={styles.stageFileTitle}>{title}</p>
      <p className={styles.stageFileMeta}>역할: {role}</p>
      <p className={styles.stageFileMeta}>모델: {formatModelType(stage)}</p>
      <p className={styles.stageFileMeta}>파일: {stage?.file_name || '정보 없음'}</p>
      <p className={styles.stageFileMeta}>크기: {formatModelFile(stage)}</p>
      {typeof threshold === 'number' && (
        <p className={styles.stageFileMeta}>threshold: {threshold.toFixed(2)}</p>
      )}
      <p className={styles.stageFileMeta}>상태: {stage?.exists ? '정상' : '확인 필요'}</p>
    </div>
  )
}

function formatModelFile(stage) {
  if (!stage?.exists) return '없음'
  return typeof stage.size_mb === 'number' ? `${stage.size_mb.toLocaleString()}MB` : '존재'
}

function formatModelType(stage) {
  if (stage?.model_type) return stage.model_type
  const fileName = stage?.file_name || ''
  if (fileName.includes('random_forest')) return 'RandomForest'
  if (fileName.includes('xgboost')) return 'XGBoost'
  return '정보 없음'
}

function formatDecisionPolicy(onewayThreshold, roundtripThreshold) {
  if (typeof onewayThreshold === 'number' && typeof roundtripThreshold === 'number') {
    return `판단 기준: 편도 WAIT 확률 ${(onewayThreshold * 100).toFixed(0)}% 초과, 왕복 WAIT 확률 ${(roundtripThreshold * 100).toFixed(0)}% 초과 시 대기 추천`
  }
  if (typeof onewayThreshold === 'number') {
    return `판단 기준: 편도 WAIT 확률 ${(onewayThreshold * 100).toFixed(0)}% 초과 시 대기 추천`
  }
  if (typeof roundtripThreshold === 'number') {
    return `판단 기준: 왕복 WAIT 확률 ${(roundtripThreshold * 100).toFixed(0)}% 초과 시 대기 추천`
  }
  return '판단 기준 정보 없음'
}

function formatCount(value, unit = '건') {
  return typeof value === 'number' ? `${value.toLocaleString()}${unit}` : '정보 없음'
}

function getModelEntries(info, fallbackVersion) {
  const models = info?.models || {}
  const entries = [
    ['oneway', '편도 추천 모델'],
    ['roundtrip', '왕복 추천 모델'],
  ]
    .map(([key, fallbackName]) => {
      const item = models[key]
      if (!item) return null
      return {
        key,
        displayName: item.display_name || fallbackName,
        modelVersion: item.model_version || '모델 버전 정보 없음',
        status: item.status || 'inactive',
        statusLabel: item.status === 'active' ? '운영 중' : '확인 필요',
        artifactStatus: item.artifact_status,
        artifactModifiedAt: item.artifact_modified_at,
        stage1: item.stage1,
        stage2: item.stage2,
        threshold: item.threshold,
      }
    })
    .filter(Boolean)

  if (entries.length > 0) return entries

  return [
    {
      key: 'oneway',
      displayName: '추천 모델',
      modelVersion: fallbackVersion,
      status: fallbackVersion ? 'active' : 'inactive',
      statusLabel: fallbackVersion ? '운영 중' : '확인 필요',
      artifactStatus: null,
      artifactModifiedAt: null,
      stage1: null,
      stage2: null,
    },
  ]
}

function formatArtifactStatus(status, fallbackOk) {
  if (status === 'ok') return '정상'
  if (status) return '일부 누락 또는 확인 필요'
  return fallbackOk ? '정상' : '일부 누락 또는 정보 없음'
}

const fallbackModelInfo = {
  status: 'fallback',
  model_version: null,
  models: {},
  architecture: {
    stage1: {
      role: '향후 가격 절감 가능성 예측',
    },
    stage2: {
      role: 'BUY/WAIT 판단',
    },
  },
  features: {},
  decision_policy: {},
  artifacts: {},
  dates: {},
  data: {},
}
