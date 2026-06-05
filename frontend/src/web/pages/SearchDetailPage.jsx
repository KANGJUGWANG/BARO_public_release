import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { fetchRouteAnalysis } from '../../api/client'
import styles from './SearchDetailPage.module.css'

const ROUTE_SPECS = {
  oneway: [
    { origin: 'ICN', destination: 'NRT', label: 'ICN -> NRT' },
    { origin: 'NRT', destination: 'ICN', label: 'NRT -> ICN' },
    { origin: 'ICN', destination: 'HND', label: 'ICN -> HND' },
    { origin: 'HND', destination: 'ICN', label: 'HND -> ICN' },
  ],
  roundtrip: [
    { origin: 'ICN', destination: 'NRT', label: 'ICN <-> NRT' },
    { origin: 'NRT', destination: 'ICN', label: 'NRT <-> ICN' },
    { origin: 'ICN', destination: 'HND', label: 'ICN <-> HND' },
    { origin: 'HND', destination: 'ICN', label: 'HND <-> ICN' },
  ],
}

const TOP_LEVEL_ERROR_STATUSES = new Set([
  'unavailable_table_missing',
  'unavailable_db_pool',
  'unavailable_db_query_error',
  'unavailable_timeout',
])

const ITEM_UNAVAILABLE_STATUSES = new Set([
  'unavailable_analysis_snapshot',
  'unavailable_table_missing',
  'unavailable_db_pool',
  'unavailable_db_query_error',
])

function buildRouteKey(tripType, origin, destination) {
  return tripType === 'roundtrip'
    ? `analysis:roundtrip:${origin}:${destination}:7`
    : `analysis:oneway:${origin}:${destination}`
}

function formatPrice(value) {
  const num = Number(value)
  return Number.isFinite(num) && num > 0 ? `${num.toLocaleString()}원` : '-'
}

function getDpdLabel(bucket) {
  return bucket?.label || bucket?.dpd_bucket || bucket?.range || '-'
}

function getDpdPrice(bucket) {
  return bucket?.median_krw ?? bucket?.median_price_krw ?? bucket?.avg_price_krw ?? null
}

function getAirlinePrice(airline) {
  if (airline?.median_krw || airline?.median_price_krw) {
    return {
      label: '중앙값',
      value: airline.median_krw ?? airline.median_price_krw,
    }
  }
  return {
    label: '평균',
    value: airline?.avg_price_krw ?? null,
  }
}

function normalizeProbability(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  const normalized = value > 1 ? value / 100 : value
  return Math.max(0, Math.min(1, normalized))
}

function getPriceDropExpectation(item) {
  const waitProbability = normalizeProbability(item?.wait_probability)
  if (waitProbability !== null) return waitProbability

  const confidence = normalizeProbability(item?.confidence)
  if (confidence === null) return null
  return item?.decision === 'WAIT'
    ? confidence
    : 1 - confidence
}

function getDecisionThreshold(item, tripType) {
  const fromItem = normalizeProbability(item?.threshold)
  if (fromItem !== null) return fromItem
  return tripType === 'roundtrip' ? 0.65 : 0.8
}

function formatPriceDropExpectation(item) {
  const expectation = getPriceDropExpectation(item)
  return expectation === null ? '-' : `${Math.round(expectation * 100)}%`
}

function PriceDropGauge({ item, tripType }) {
  const expectation = getPriceDropExpectation(item)
  if (expectation === null) return null
  const percent = Math.round(expectation * 100)
  const thresholdPercent = Math.round(getDecisionThreshold(item, tripType) * 100)

  return (
    <div className={styles.priceDropGauge} title={`가격 하락 기대 강도 ${percent}%`}>
      <div className={styles.gaugeHeader}>
        <span>가격 하락 기대 강도</span>
        <strong>{percent}%</strong>
      </div>
      <div
        className={styles.gaugeTrack}
        role="meter"
        aria-label={`가격 하락 기대 강도 ${percent}%`}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={percent}
      >
        <span className={styles.gaugeFill} style={{ width: `${percent}%` }} />
        <span
          className={styles.gaugeMarker}
          style={{ left: `${thresholdPercent}%` }}
          title={`WAIT 전환 기준: ${thresholdPercent}%`}
        />
      </div>
      <div className={styles.gaugeThresholdRow}>
        <span>WAIT 기준 {thresholdPercent}%</span>
      </div>
    </div>
  )
}

export default function SearchDetailPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state || {}

  const initTripType = state.tripType === 'roundtrip' || state.tripType === 'round' ? 'roundtrip' : 'oneway'
  const initOrigin = state.origin || 'ICN'
  const initDestination = state.destination || 'NRT'

  const [tripType, setTripType] = useState(initTripType)
  const [origin, setOrigin] = useState(initOrigin)
  const [destination, setDestination] = useState(initDestination)
  const [analysisData, setAnalysisData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    fetchRouteAnalysis()
      .then(data => {
        if (cancelled) return
        setAnalysisData(data)
        if (TOP_LEVEL_ERROR_STATUSES.has(data?.status)) {
          setError('분석 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.')
        }
      })
      .catch(() => {
        if (!cancelled) setError('분석 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const activeItem = useMemo(() => {
    if (!analysisData?.items) return null
    const routeKey = buildRouteKey(tripType, origin, destination)
    return analysisData.items.find(item => item.route_key === routeKey) || null
  }, [analysisData, tripType, origin, destination])

  const handleTripType = (nextType) => {
    setTripType(nextType)
    const specs = ROUTE_SPECS[nextType]
    const sameRoute = specs.find(spec => spec.origin === origin && spec.destination === destination)
    if (!sameRoute && specs[0]) {
      setOrigin(specs[0].origin)
      setDestination(specs[0].destination)
    }
  }

  const activeUnavailable = activeItem && ITEM_UNAVAILABLE_STATUSES.has(activeItem.status)

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate(-1)}>
          <ArrowLeft size={22} color="#fff" />
        </button>
        <span className={styles.title}>
          {tripType === 'roundtrip'
            ? `${origin} <-> ${destination} 7일 분석`
            : `${origin} -> ${destination} 분석`}
        </span>
        <div style={{ width: 36 }} />
      </header>

      <main className={styles.main}>
        <RouteControls
          tripType={tripType}
          origin={origin}
          destination={destination}
          onTripType={handleTripType}
          onRoute={(spec) => {
            setOrigin(spec.origin)
            setDestination(spec.destination)
          }}
        />

        {loading && (
          <StatusMessage color="#94a3b8">
            노선 분석 데이터를 불러오는 중...
          </StatusMessage>
        )}

        {!loading && error && (
          <StatusMessage color="#ef4444">
            {error}
          </StatusMessage>
        )}

        {!loading && !error && analysisData?.status === 'unavailable_analysis_snapshot' && (
          <StatusMessage>
            아직 노선 분석 데이터가 준비되지 않았습니다.
          </StatusMessage>
        )}

        {!loading && !error && activeItem && !activeUnavailable && (
          <>
            <div style={{ textAlign: 'center', padding: '2px 4px 0' }}>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                {activeItem.is_stale
                  ? '이전 분석 기준 · 최신 관측 이후 갱신 대기 중'
                  : `관측 기준: ${activeItem.latest_observed_at?.slice(0, 10) || '-'}`}
              </span>
            </div>

            {(activeItem.status === 'insufficient_data' || activeItem.status === 'no_data') && (
              <StatusMessage>
                관측 데이터가 아직 부족합니다.
                <br />
                <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                  관측 횟수: {activeItem.observation_count ?? 0}회
                </span>
              </StatusMessage>
            )}

            {(activeItem.status === 'ok' || activeItem.status === 'stale') && activeItem.summary && (
              <AnalysisSummaryCard summary={activeItem.summary} item={activeItem} tripType={tripType} />
            )}

            {(activeItem.status === 'ok' || activeItem.status === 'stale')
              && Array.isArray(activeItem.dpd_curve)
              && activeItem.dpd_curve.length > 0 && (
                <DpdCurveCard dpd={activeItem.dpd_curve} />
            )}

            {(activeItem.status === 'ok' || activeItem.status === 'stale')
              && Array.isArray(activeItem.cheap_airlines)
              && activeItem.cheap_airlines.length > 0 && (
                <CheapAirlinesCard airlines={activeItem.cheap_airlines} />
            )}

            {(activeItem.status === 'ok' || activeItem.status === 'stale') && (
              <div style={{ textAlign: 'center', padding: '0 4px 12px' }}>
                <p style={{ fontSize: '11px', color: '#94a3b8', lineHeight: '1.6', margin: 0 }}>
                  관측 데이터 기준이며 실제 가격을 보장하지 않습니다.
                  <br />
                  실시간 항공권 검색 결과와 다를 수 있습니다.
                </p>
              </div>
            )}
          </>
        )}

        {!loading && !error && (!activeItem || activeUnavailable) && (
          <StatusMessage>
            해당 노선 분석 준비 중입니다.
          </StatusMessage>
        )}
      </main>
    </div>
  )
}

function RouteControls({ tripType, origin, destination, onTripType, onRoute }) {
  return (
    <>
      <div style={{ display: 'flex', gap: '8px', justifyContent: 'center' }}>
        {['oneway', 'roundtrip'].map(type => (
          <button
            key={type}
            onClick={() => onTripType(type)}
            style={{
              padding: '6px 18px',
              borderRadius: '20px',
              border: 'none',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              background: tripType === type ? '#1A2B5E' : '#e2e8f0',
              color: tripType === type ? '#fff' : '#64748b',
            }}
          >
            {type === 'oneway' ? '편도' : '왕복'}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'center' }}>
        {ROUTE_SPECS[tripType].map(spec => {
          const active = spec.origin === origin && spec.destination === destination
          return (
            <button
              key={`${tripType}-${spec.origin}-${spec.destination}`}
              onClick={() => onRoute(spec)}
              style={{
                padding: '5px 12px',
                borderRadius: '16px',
                border: 'none',
                fontSize: '12px',
                fontWeight: 500,
                cursor: 'pointer',
                background: active ? '#1A2B5E' : '#e2e8f0',
                color: active ? '#fff' : '#475569',
              }}
            >
              {spec.label}
            </button>
          )
        })}
      </div>
    </>
  )
}

function StatusMessage({ children, color = '#64748b' }) {
  return (
    <div style={{ textAlign: 'center', padding: '32px 16px', color, fontSize: '13px', lineHeight: '1.7' }}>
      {children}
    </div>
  )
}

function AnalysisSummaryCard({ summary, item, tripType }) {
  const trendLabel = {
    rising: '상승 추세',
    falling: '하락 추세',
    stable: '안정',
    insufficient: '데이터 부족',
  }[summary.trend_label] || summary.trend_label || '-'

  const volatilityLabel = {
    low: '낮음',
    medium: '보통',
    high: '높음',
    insufficient: '데이터 부족',
  }[summary.volatility_label] || summary.volatility_label || '-'

  const metrics = [
    ['최신 최저가', summary.latest_min_price_krw],
    ['최신 중앙값', summary.latest_median_price_krw],
    ['이력 최저가', summary.historical_min_price_krw],
    ['이력 최고가', summary.historical_max_price_krw],
    ['샘플 중앙값', summary.sampled_median_price_krw ?? summary.historical_median_price_krw],
    ['샘플 수', summary.price_sample_count],
  ]

  return (
    <div className={styles.section}>
      <p className={styles.sectionTitle}>가격 요약</p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        {metrics.map(([label, value]) => (
          <div
            key={label}
            style={{
              background: '#f8fafc',
              borderRadius: '10px',
              padding: '10px 12px',
              textAlign: 'center',
            }}
          >
            <p style={{ fontSize: '11px', color: '#94a3b8', margin: '0 0 4px' }}>{label}</p>
            <p style={{ fontSize: '14px', fontWeight: 700, color: '#1A2B5E', margin: 0 }}>
              {label === '샘플 수' ? (value ? `${Number(value).toLocaleString()}건` : '-') : formatPrice(value)}
            </p>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 8px', marginTop: '2px' }}>
        <span style={{ fontSize: '12px', color: '#475569' }}>추세: {trendLabel}</span>
        <span style={{ fontSize: '12px', color: '#94a3b8' }}>|</span>
        <span style={{ fontSize: '12px', color: '#475569' }}>변동성: {volatilityLabel}</span>
        <span style={{ fontSize: '12px', color: '#94a3b8' }}>|</span>
        <span style={{ fontSize: '12px', color: '#475569' }}>가격 하락 기대 강도: {formatPriceDropExpectation(item)}</span>
      </div>
      <PriceDropGauge item={item} tripType={tripType} />
      {summary.best_dpd_label && (
        <p style={{ fontSize: '12px', color: '#2563EB', margin: '2px 0 0' }}>
          {summary.best_dpd_label}
        </p>
      )}
    </div>
  )
}

function DpdCurveCard({ dpd }) {
  const prices = dpd.map(getDpdPrice).filter(value => Number.isFinite(Number(value)))
  const maxMedian = Math.max(...prices.map(Number), 1)

  return (
    <div className={styles.section}>
      <p className={styles.sectionTitle}>출발 전 기간별 가격 패턴</p>
      {dpd.map((bucket, index) => {
        const price = getDpdPrice(bucket)
        const width = price ? Math.max(8, Math.round((Number(price) / maxMedian) * 100)) : 0
        return (
          <div key={`${getDpdLabel(bucket)}-${index}`} style={{ marginBottom: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#475569', marginBottom: '3px' }}>
              <span>{getDpdLabel(bucket)}</span>
              <span style={{ fontWeight: 600 }}>{formatPrice(price)}</span>
            </div>
            <div style={{ background: '#e2e8f0', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
              <div
                style={{
                  background: '#1A2B5E',
                  borderRadius: '4px',
                  height: '100%',
                  width: `${width}%`,
                }}
              />
            </div>
            {bucket.sample_count ? (
              <p style={{ fontSize: '10px', color: '#94a3b8', margin: '2px 0 0' }}>
                관측 {Number(bucket.sample_count).toLocaleString()}건
              </p>
            ) : null}
          </div>
        )
      })}
      <p style={{ fontSize: '11px', color: '#94a3b8', margin: '2px 0 0' }}>중앙값 기준</p>
    </div>
  )
}

function CheapAirlinesCard({ airlines }) {
  return (
    <div className={styles.section}>
      <p className={styles.sectionTitle}>저가 항공사 경향</p>
      {airlines.slice(0, 5).map((airline, index) => {
        const price = getAirlinePrice(airline)
        return (
          <div
            key={`${airline.airline_code || airline.airline_name || index}`}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '10px',
              padding: '8px 4px',
              borderBottom: index === airlines.length - 1 ? 'none' : '1px solid #f1f5f9',
            }}
          >
            <span style={{ fontSize: '13px', color: '#1A2B5E', fontWeight: index === 0 ? 700 : 500 }}>
              {index + 1}. {airline.airline_name || airline.airline_code || '-'}
            </span>
            <span style={{ fontSize: '12px', color: '#64748b', textAlign: 'right' }}>
              {price.label} {formatPrice(price.value)}
              {airline.offer_count ? ` · 관측 ${Number(airline.offer_count).toLocaleString()}건` : ''}
            </span>
          </div>
        )
      })}
    </div>
  )
}
