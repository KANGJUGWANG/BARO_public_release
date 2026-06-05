import styles from './RoundTripCard.module.css'
import { getAirlineBranding } from '../../shared/airlineBranding'

function hasPriceValue(price) {
  return price !== null && price !== undefined && price !== ''
}

function formatPrice(price) {
  return hasPriceValue(price) ? `${Number(price).toLocaleString()}원` : '가격 정보 없음'
}

function formatDisplayTime(value) {
  if (!value) return '--:--'
  const text = String(value)
  const match = text.match(/^(\d{2}:\d{2})(?::\d{2})?(.*)$/)
  if (match) return `${match[1]}${match[2] || ''}`
  return text
}

function getPredictionTag(prediction) {
  const status = prediction?.prediction_status
  if (status === 'ok' && prediction?.decision) {
    return {
      className: prediction.decision === 'BUY' ? styles.predictionBuy : styles.predictionWait,
      label: prediction.decision === 'BUY' ? '지금 구매 추천' : '가격 하락 대기 추천',
    }
  }
  if (status === 'skipped_not_in_top_k') {
    return { className: styles.predictionPending, label: '분석 대상 외' }
  }
  if (status?.startsWith('unavailable_')) {
    return { className: styles.predictionPending, label: '추천 분석 불가' }
  }
  if (status === 'error') {
    return { className: styles.predictionPending, label: '추천 오류' }
  }
  return { className: styles.predictionPending, label: '상세에서 분석' }
}

function PredictionBadge({ prediction }) {
  const tag = getPredictionTag(prediction)
  return (
    <span className={`${styles.predictionBadge} ${tag.className}`}>
      {tag.label}
    </span>
  )
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
  return normalizeProbability(prediction?.threshold) ?? 0.65
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

export default function RoundTripCard({ group, search, onClick }) {
  const { airline, outbound, inbound } = group
  const prediction = group.prediction || outbound.prediction || outbound.rawOffer?.prediction || null
  const totalPrice = group.totalPrice ?? ((outbound.price || 0) + (inbound.price || 0))
  const outBranding = getAirlineBranding(
    outbound.rawOffer?.airline_code || airline,
    outbound.airline || airline,
  )
  const inBranding = getAirlineBranding(
    inbound.rawOffer?.ret_airline_code || inbound.rawOffer?.airline_code || inbound.airline,
    inbound.airline,
  )

  return (
    <div
      className={styles.card}
      onClick={onClick}
      style={{ borderLeft: `3px solid ${outBranding.color}` }}
    >
      <div className={styles.top}>
        <div className={styles.airlineRow}>
          {outBranding.logo ? (
            <img src={outBranding.logo} alt={outBranding.displayName} className={styles.airlineLogo} />
          ) : (
            <span
              className={styles.airlineCodeBadge}
              style={{ borderColor: outBranding.color, color: outBranding.color }}
            >
              {outBranding.code}
            </span>
          )}
          <span className={styles.airline} style={{ color: outBranding.color }}>
            {outBranding.displayName}
          </span>
          <span className={styles.directBadge}>직항</span>
        </div>
        <PredictionBadge prediction={prediction} />
      </div>

      <PriceDropGauge prediction={prediction} />

      <div className={styles.segment}>
        <div className={styles.segmentAirline}>
          {outBranding.logo ? (
            <img src={outBranding.logo} alt={outBranding.displayName} className={styles.segmentAirlineLogo} />
          ) : (
            <span
              className={styles.segmentCodeBadge}
              style={{ borderColor: outBranding.color, color: outBranding.color }}
            >
              {outBranding.code}
            </span>
          )}
          <span style={{ color: outBranding.color }}>{outBranding.displayName}</span>
        </div>
        <span className={styles.segLabel}>
          {search.origin} → {search.destination}
          <span className={styles.segDate}> · {search.departDate}</span>
        </span>
        <div className={styles.flightRow}>
          <div className={styles.timeBlock}>
            <span className={styles.time}>{formatDisplayTime(outbound.dep)}</span>
            <span className={styles.code}>{search.origin}</span>
          </div>
          <div className={styles.durationBlock}>
            <div className={styles.durationLine}>
              <span className={styles.dot} />
              <span className={styles.line} />
              <span className={styles.dotArrow} />
            </div>
            <span className={styles.duration}>{outbound.duration}</span>
          </div>
          <div className={styles.timeBlock}>
            <span className={styles.time}>{formatDisplayTime(outbound.arr)}</span>
            <span className={styles.code}>{search.destination}</span>
          </div>
        </div>
      </div>

      <div className={styles.divider} />

      <div className={styles.segment}>
        <div className={styles.segmentAirline}>
          {inBranding.logo ? (
            <img src={inBranding.logo} alt={inBranding.displayName} className={styles.segmentAirlineLogo} />
          ) : (
            <span
              className={styles.segmentCodeBadge}
              style={{ borderColor: inBranding.color, color: inBranding.color }}
            >
              {inBranding.code}
            </span>
          )}
          <span style={{ color: inBranding.color }}>{inBranding.displayName}</span>
        </div>
        <span className={styles.segLabel}>
          {search.destination} → {search.origin}
          <span className={styles.segDate}> · {search.returnDate}</span>
        </span>
        <div className={styles.flightRow}>
          <div className={styles.timeBlock}>
            <span className={styles.time}>{formatDisplayTime(inbound.dep)}</span>
            <span className={styles.code}>{search.destination}</span>
          </div>
          <div className={styles.durationBlock}>
            <div className={styles.durationLine}>
              <span className={styles.dot} />
              <span className={styles.line} />
              <span className={styles.dotArrow} />
            </div>
            <span className={styles.duration}>{inbound.duration}</span>
          </div>
          <div className={styles.timeBlock}>
            <span className={styles.time}>{formatDisplayTime(inbound.arr)}</span>
            <span className={styles.code}>{search.origin}</span>
          </div>
        </div>
      </div>

      <div className={styles.footer}>
        <div>
          <p className={styles.totalPriceLabel}>왕복 합계</p>
          <p className={hasPriceValue(totalPrice) ? styles.totalPriceValue : styles.totalPriceUnavailable}>
            {formatPrice(totalPrice)}
          </p>
        </div>
        <span className={styles.detailBtn}>상세 보기 →</span>
      </div>
    </div>
  )
}
