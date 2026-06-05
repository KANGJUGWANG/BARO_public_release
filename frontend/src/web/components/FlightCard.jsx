import styles from './FlightCard.module.css'
import { getAirlineBranding } from '../../shared/airlineBranding'

function getTagView(flight) {
  const predictionStatus = flight.prediction?.prediction_status
  if (flight.tag) {
    return {
      className: flight.tag === 'BUY' ? styles.buyTag : styles.waitTag,
      label: flight.tag === 'BUY' ? '지금 구매 추천' : '가격 하락 대기 추천',
    }
  }
  if (predictionStatus === 'skipped_not_in_top_k') {
    return { className: styles.pendingTag, label: '분석 대상 외' }
  }
  if (predictionStatus?.startsWith('unavailable_')) {
    return { className: styles.pendingTag, label: '추천 분석 불가' }
  }
  if (predictionStatus === 'error') {
    return { className: styles.pendingTag, label: '추천 오류' }
  }
  return { className: styles.pendingTag, label: '상세에서 분석' }
}

function formatPrice(price) {
  const hasPrice = price !== null && price !== undefined && price !== ''
  return hasPrice ? `${Number(price).toLocaleString()}원` : '가격 정보 없음'
}

function hasPriceValue(price) {
  return price !== null && price !== undefined && price !== ''
}

function formatDisplayTime(value) {
  if (!value) return '--:--'
  const text = String(value)
  const match = text.match(/^(\d{2}:\d{2})(?::\d{2})?(.*)$/)
  if (match) return `${match[1]}${match[2] || ''}`
  return text
}

function normalizeProbability(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  const normalized = value > 1 ? value / 100 : value
  return Math.max(0, Math.min(1, normalized))
}

function getPriceDropExpectation(prediction) {
  if (!prediction || prediction.prediction_status !== 'ok') return null
  const waitProbability = normalizeProbability(prediction.wait_probability)
  if (waitProbability !== null) return waitProbability

  const confidence = normalizeProbability(prediction.confidence)
  if (confidence === null) return null
  return prediction.decision === 'WAIT'
    ? confidence
    : 1 - confidence
}

function getDecisionThreshold(prediction) {
  return normalizeProbability(prediction?.threshold) ?? 0.8
}

function PriceDropGauge({ prediction }) {
  const expectation = getPriceDropExpectation(prediction)
  if (expectation === null || !Number.isFinite(expectation)) return null
  const percent = Math.round(Math.max(0, Math.min(1, expectation)) * 100)
  const thresholdPercent = Math.round(getDecisionThreshold(prediction) * 100)

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

export default function FlightCard({ flight, onClick }) {
  const tag = getTagView(flight)
  const branding = getAirlineBranding(
    flight.rawOffer?.airline_code || flight.airlineCode || flight.airline,
    flight.airline,
  )

  return (
    <div
      className={styles.card}
      onClick={onClick}
      style={{ borderLeft: `3px solid ${branding.color}` }}
    >
      <div className={styles.top}>
        <div className={styles.airlineRow}>
          {branding.logo ? (
            <img src={branding.logo} alt={branding.displayName} className={styles.airlineLogo} />
          ) : (
            <span
              className={styles.airlineCodeBadge}
              style={{ borderColor: branding.color, color: branding.color }}
            >
              {branding.code}
            </span>
          )}
          <span className={styles.airline} style={{ color: branding.color }}>
            {branding.displayName}
          </span>
          {flight.direct && <span className={styles.directBadge}>직항</span>}
        </div>
        <span className={tag.className}>{tag.label}</span>
      </div>

      <PriceDropGauge prediction={flight.prediction} />

      <div className={styles.flightInfo}>
        <div className={styles.timeBlock}>
          <span className={styles.time}>{formatDisplayTime(flight.dep)}</span>
          <span className={styles.airportCode}>출발</span>
        </div>
        <div className={styles.durationBlock}>
          <div className={styles.durationLine}>
            <div className={styles.dot} />
            <div className={styles.line} />
            <div className={styles.dotArrow} />
          </div>
          <span className={styles.duration}>{flight.duration}</span>
        </div>
        <div className={styles.timeBlock}>
          <span className={styles.time}>{formatDisplayTime(flight.arr)}</span>
          <span className={styles.airportCode}>도착</span>
        </div>
      </div>

      <div className={styles.bottom}>
        <div>
          <span className={styles.priceLabel}>최저가</span>
          <div className={hasPriceValue(flight.price) ? styles.price : styles.priceUnavailable}>
            {formatPrice(flight.price)}
          </div>
        </div>
        <span className={styles.detailBtn}>상세 보기 →</span>
      </div>
    </div>
  )
}
