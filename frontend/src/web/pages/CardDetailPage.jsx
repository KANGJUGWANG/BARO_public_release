import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Bookmark, BookmarkCheck } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useAuth } from '../../store/AuthContext'
import { apiCall, fetchFlightHistory, predictOne } from '../../api/client'
import { getAirlineBranding } from '../../shared/airlineBranding'
import styles from './CardDetailPage.module.css'

export default function CardDetailPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const [bookmarked, setBookmarked] = useState(false)
  const [saving, setSaving] = useState(false)
  const [detailPrediction, setDetailPrediction] = useState(null)
  const [predictionLoading, setPredictionLoading] = useState(false)
  const [historyData, setHistoryData] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState(null)
  const pageRef = useRef(null)
  const state = location.state || {}
  const { flight, returnFlight, search } = state

  useLayoutEffect(() => {
    let frameOne = null
    let frameTwo = null

    const resetScrollTop = () => {
      const page = pageRef.current
      const appScroller = page?.parentElement || document.querySelector('#root > div')
      if (appScroller) appScroller.scrollTop = 0
      const main = page?.querySelector('main')
      if (main) main.scrollTop = 0
      window.scrollTo(0, 0)
      if (document.scrollingElement) document.scrollingElement.scrollTop = 0
    }

    resetScrollTop()
    frameOne = requestAnimationFrame(() => {
      resetScrollTop()
      frameTwo = requestAnimationFrame(resetScrollTop)
    })

    return () => {
      if (frameOne !== null) cancelAnimationFrame(frameOne)
      if (frameTwo !== null) cancelAnimationFrame(frameTwo)
    }
  }, [])

  useEffect(() => {
    if (!flight) return

    const initialPrediction = flight.prediction || null
    setDetailPrediction(initialPrediction)

    const status = initialPrediction?.prediction_status
    if (status === 'ok') return
    if (status && status !== 'skipped_not_in_top_k') return

    if (!search?.origin || !search?.destination || !search?.departDate) {
      setDetailPrediction({
        prediction_status: 'unavailable_feature_build_failed',
        reason: 'missing search context',
      })
      return
    }

    let cancelled = false
    setPredictionLoading(true)

    predictOne(buildPredictOneRequest(flight, search))
      .then(result => {
        if (cancelled) return
        setDetailPrediction(result)
        if (result?.prediction_status === 'ok') {
          updateCachePrediction(search, flight, result)
        }
      })
      .catch(() => {
        if (cancelled) return
        setDetailPrediction({
          prediction_status: 'error',
          reason: 'predict-one request failed',
        })
      })
      .finally(() => {
        if (cancelled) return
        setPredictionLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [flight, search])

  useEffect(() => {
    if (!flight) return
    if (!search?.origin || !search?.destination || !search?.departDate) return

    const isRoundtrip = search?.tripType === 'round' || search?.tripType === 'roundtrip'
    const offer = isRoundtrip
      ? buildRoundtripHistoryOffer(flight, returnFlight, search)
      : buildHistoryOffer(flight)
    const flightNumber = offer.flight_number

    if (!flightNumber) {
      setHistoryData(null)
      setHistoryLoading(false)
      setHistoryError('가격 이력 조회에 필요한 항공편 번호가 없습니다.')
      return
    }

    if (isRoundtrip && !isValidRoundtripHistoryOffer(offer)) {
      setHistoryData(null)
      setHistoryLoading(false)
      setHistoryError('왕복 가격 추이를 표시하기 위한 항공편 정보가 부족합니다.')
      return
    }

    const cacheKey = buildHistoryCacheKey({
      origin: search.origin,
      destination: search.destination,
      departDate: search.departDate,
      flightNumber,
      retFlightNumber: offer.ret_flight_number,
      returnDate: offer.return_date,
      stayNights: offer.stay_nights,
      tripType: isRoundtrip ? 'roundtrip' : 'oneway',
    })

    try {
      const cached = sessionStorage.getItem(cacheKey)
      if (cached) {
        const parsed = JSON.parse(cached)
        if (parsed?.data) {
          setHistoryData(parsed.data)
          setHistoryError(null)
          return
        }
      }
    } catch {
      // Ignore cache read errors and fetch fresh history.
    }

    let cancelled = false
    setHistoryLoading(true)
    setHistoryError(null)

    fetchFlightHistory({
      origin: search.origin,
      destination: search.destination,
      depart_date: search.departDate,
      trip_type: isRoundtrip ? 'roundtrip' : 'oneway',
      offer,
    })
      .then(data => {
        if (cancelled) return
        if (data?.status === 'ok') {
          setHistoryData(data)
          try {
            sessionStorage.setItem(cacheKey, JSON.stringify({
              savedAt: Date.now(),
              data,
            }))
          } catch {
            // History cache is best-effort.
          }
        } else {
          setHistoryData(null)
          setHistoryError(historyStatusMessage(data?.status, isRoundtrip))
        }
      })
      .catch(() => {
        if (cancelled) return
        setHistoryData(null)
        setHistoryError('가격 추이를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.')
      })
      .finally(() => {
        if (cancelled) return
        setHistoryLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [flight, returnFlight, search])

  if (!flight) {
    return (
      <div className={styles.page} ref={pageRef}>
        <header className={styles.header}>
          <button
            className={styles.backBtn}
            onClick={() => {
              if (window.history.length > 1) {
                navigate(-1)
              } else {
                navigate('/')
              }
            }}
          >
            <ArrowLeft size={22} color="#fff" />
          </button>
          <span className={styles.title}>항공편 상세</span>
          <div style={{ width: 36 }} />
        </header>

        <main className={styles.main}>
          <div className={styles.judgmentCard}>
            <p className={styles.judgmentLabel}>안내</p>
            <div className={styles.judgmentEmpty}>
              <p className={styles.emptyTitle}>정보를 불러올 수 없습니다</p>
              <p className={styles.emptyDesc}>
                검색 결과 화면에서 항공편을 선택해주세요.
              </p>
            </div>
          </div>
        </main>
      </div>
    )
  }

  const prediction = predictionLoading
    ? { prediction_status: 'loading' }
    : detailPrediction || flight.prediction || null
  const isRound = !!returnFlight || search?.tripType === 'round' || search?.tripType === 'roundtrip'
  const branding = getAirlineBranding(
    flight?.rawOffer?.airline_code || flight?.airlineCode || flight?.airline,
    flight?.airline,
  )
  const returnBranding = getAirlineBranding(
    returnFlight?.rawOffer?.ret_airline_code || returnFlight?.rawOffer?.airline_code || returnFlight?.airline,
    returnFlight?.airline,
  )

  const totalPrice = isRound
    ? (flight?.price || 0) + (returnFlight?.price || 0)
    : flight?.price || 0

  const handleSave = async () => {
    if (!user?.token || bookmarked || saving) return
    setSaving(true)
    try {
      await apiCall('/users/me/saved', {
        method: 'POST',
        body: JSON.stringify({
          airline:     flight?.airline,
          origin:      search?.origin,
          destination: search?.destination,
          departDate:  search?.departDate,
          returnDate:  search?.returnDate || null,
          price:       totalPrice,
          dep:         flight?.dep,
          arr:         flight?.arr,
          isRound,
        }),
      }, user.token)
      setBookmarked(true)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={styles.page} ref={pageRef}>
      <header className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate(-1)}>
          <ArrowLeft size={22} color="#fff" />
        </button>
        <span className={styles.title}>
          {branding.displayName || flight?.airline || '항공편 상세'}
        </span>
        {/* 북마크 아이콘: 저장안됨=흡색, 저장됨=노란색 */}
        <button
          className={styles.saveBtn}
          onClick={handleSave}
          disabled={bookmarked}
          title={bookmarked ? '저장됨' : '저장하기'}
        >
          {saving
            ? <Bookmark size={22} color="rgba(255,255,255,0.4)" />
            : bookmarked
              ? <BookmarkCheck size={22} color="#FEE500" />
              : <Bookmark size={22} color="#fff" />}
        </button>
      </header>

      <main className={styles.main}>
        <div className={styles.priceCard} style={{ borderTop: `4px solid ${branding.color}` }}>
          <div className={styles.airlineIdentity}>
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
            <span style={{ color: branding.color }}>{branding.displayName}</span>
          </div>
          <p className={styles.priceLabel}>
            {isRound ? '왕복 합계 가격' : '현재 가격'}
          </p>
          <p className={styles.price}>{totalPrice.toLocaleString()}원</p>

          <div className={styles.segmentInfo}>
            <span className={styles.segRoute}>
              {search?.origin} → {search?.destination} · {search?.departDate}
            </span>
            <span className={styles.segTime}>
              {flight?.dep} → {flight?.arr} · {flight?.duration}
            </span>
            {isRound && (
              <span className={styles.segPrice}>
                {flight?.price?.toLocaleString()}원
              </span>
            )}
          </div>

          {isRound && returnFlight && (
            <>
              <div className={styles.segDivider} />
              <div className={styles.segmentInfo}>
                <span className={styles.returnAirlineIdentity}>
                  {returnBranding.logo ? (
                    <img src={returnBranding.logo} alt={returnBranding.displayName} className={styles.airlineLogoSmall} />
                  ) : (
                    <span
                      className={styles.airlineCodeBadgeSmall}
                      style={{ borderColor: returnBranding.color, color: returnBranding.color }}
                    >
                      {returnBranding.code}
                    </span>
                  )}
                  <span style={{ color: returnBranding.color }}>{returnBranding.displayName}</span>
                </span>
                <span className={styles.segRoute}>
                  {search?.destination} → {search?.origin} · {search?.returnDate}
                </span>
                <span className={styles.segTime}>
                  {returnFlight.dep} → {returnFlight.arr} · {returnFlight.duration}
                </span>
                <span className={styles.segPrice}>
                  {returnFlight.price?.toLocaleString()}원
                </span>
              </div>
            </>
          )}
        </div>

        <div className={styles.judgmentCard}>
          <p className={styles.judgmentLabel}>구매 판단</p>
          <JudgmentContentPolished prediction={prediction} tripType={search?.tripType} />
        </div>

        <div className={styles.chartCard}>
          <p className={styles.chartLabel}>가격 추이</p>
          <HistoryContentPolished
            data={historyData}
            loading={historyLoading}
            error={historyError}
            isRoundtrip={isRound}
          />
        </div>
      </main>
    </div>
  )
}

function buildPredictOneRequest(flight, search) {
  const rawOffer = flight.rawOffer || {}
  const isRoundtrip = search?.tripType === 'round' || search?.tripType === 'roundtrip'

  if (isRoundtrip) {
    return {
      origin: search.origin,
      destination: search.destination,
      depart_date: search.departDate,
      trip_type: 'roundtrip',
      offer: {
        flight_number: rawOffer.flight_number || flight.flightNumber || flight.id,
        ret_flight_number: rawOffer.ret_flight_number || flight.retFlightNumber || null,
        airline_code: rawOffer.airline_code || flight.airlineCode || null,
        ret_airline_code: rawOffer.ret_airline_code || null,
        dep_time_local: rawOffer.dep_time_local || flight.dep || null,
        ret_dep_time_local: rawOffer.ret_dep_time_local || flight.retDep || null,
        price_krw: rawOffer.price_krw ?? flight.price ?? null,
        return_date: search.returnDate || rawOffer.return_date || null,
        stay_nights: search.stayNights || rawOffer.stay_nights || 7,
      },
    }
  }

  const offer = Object.keys(rawOffer).length > 0
    ? { ...rawOffer }
    : {
        flight_number: flight.flightNumber || flight.id,
        airline_code: flight.airlineCode || null,
        airline_name: flight.airline || null,
        dep_time: flight.dep,
        dep_time_local: flight.dep,
        arr_time: flight.arr,
        arr_time_local: flight.arr,
        duration_min: null,
        stops: flight.direct ? 0 : null,
        price_krw: flight.price,
        aircraft: null,
        seller_type: null,
      }

  return {
    origin: search.origin,
    destination: search.destination,
    depart_date: search.departDate,
    trip_type: 'oneway',
    offer: {
      ...offer,
      flight_number: offer.flight_number || flight.flightNumber || flight.id,
      airline_name: offer.airline_name || flight.airline || null,
      dep_time: offer.dep_time || offer.dep_time_local || flight.dep,
      dep_time_local: offer.dep_time_local || offer.dep_time || flight.dep,
      arr_time: offer.arr_time || offer.arr_time_local || flight.arr,
      arr_time_local: offer.arr_time_local || offer.arr_time || flight.arr,
      price_krw: offer.price_krw ?? flight.price ?? null,
      stops: offer.stops ?? (flight.direct ? 0 : null),
    },
  }
}

function buildSearchCacheKey({ origin, destination, departDate, returnDate, tripType }) {
  const o = String(origin || '').trim().toUpperCase()
  const d = String(destination || '').trim().toUpperCase()
  const dt = String(departDate || '').trim()
  if (tripType === 'round' || tripType === 'roundtrip') {
    const rt = String(returnDate || '').trim()
    return `baro_search_${o}_${d}_${dt}_${rt}_roundtrip_7d`
  }
  return `baro_search_${o}_${d}_${dt}_oneway`
}

function buildHistoryCacheKey({
  origin,
  destination,
  departDate,
  flightNumber,
  retFlightNumber,
  returnDate,
  stayNights,
  tripType,
}) {
  const o = String(origin || '').trim().toUpperCase()
  const d = String(destination || '').trim().toUpperCase()
  const dt = String(departDate || '').trim()
  const fn = String(flightNumber || '').trim()
  if (tripType === 'roundtrip' || tripType === 'round') {
    const rfn = String(retFlightNumber || '').trim()
    const rt = String(returnDate || '').trim()
    const stay = String(stayNights || 7).trim()
    return `baro_history_${o}_${d}_${dt}_${rt}_${fn}_${rfn}_${stay}_roundtrip`
  }
  return `baro_history_${o}_${d}_${dt}_${fn}`
}

function buildHistoryOffer(flight) {
  if (flight?.rawOffer) return flight.rawOffer

  return {
    flight_number: flight?.flightNumber || flight?.id || null,
    airline_code: flight?.airlineCode || null,
    airline_name: flight?.airline || null,
    dep_time: flight?.dep || null,
    dep_time_local: flight?.dep || null,
    arr_time: flight?.arr || null,
    arr_time_local: flight?.arr || null,
    price_krw: flight?.price ?? null,
  }
}

function buildRoundtripHistoryOffer(flight, returnFlight, search) {
  const rawOffer = flight?.rawOffer || {}
  const returnRawOffer = returnFlight?.rawOffer || {}
  const stayNights = rawOffer.stay_nights ?? search?.stayNights ?? 7

  return {
    ...rawOffer,
    flight_number: rawOffer.flight_number || flight?.flightNumber || flight?.id || null,
    ret_flight_number: rawOffer.ret_flight_number || flight?.retFlightNumber || returnFlight?.flightNumber || returnFlight?.id || null,
    airline_code: rawOffer.airline_code || flight?.airlineCode || null,
    ret_airline_code: rawOffer.ret_airline_code || returnRawOffer.ret_airline_code || returnRawOffer.airline_code || returnFlight?.airlineCode || null,
    price_krw: rawOffer.price_krw ?? flight?.price ?? null,
    return_date: rawOffer.return_date || search?.returnDate || null,
    stay_nights: stayNights,
    dep_time_local: rawOffer.dep_time_local || rawOffer.dep_time || flight?.dep || null,
    ret_dep_time_local: rawOffer.ret_dep_time_local || returnRawOffer.ret_dep_time_local || returnRawOffer.dep_time_local || returnFlight?.dep || null,
  }
}

function isValidRoundtripHistoryOffer(offer) {
  return Boolean(
    offer?.flight_number &&
    offer?.ret_flight_number &&
    offer?.return_date &&
    offer?.stay_nights &&
    offer?.price_krw !== null &&
    offer?.price_krw !== undefined,
  )
}

function updateCachePrediction(search, flight, predictResult) {
  if (!search?.origin || !search?.destination || !search?.departDate) return
  const flightNumber = flight?.flightNumber || flight?.rawOffer?.flight_number
  if (!flightNumber) return

  const cacheKey = buildSearchCacheKey({
    origin: search.origin,
    destination: search.destination,
    departDate: search.departDate,
    returnDate: search.returnDate,
    tripType: search.tripType,
  })
  const isRoundtrip = search.tripType === 'round' || search.tripType === 'roundtrip'

  try {
    const raw = sessionStorage.getItem(cacheKey)
    if (!raw) return

    const parsed = JSON.parse(raw)
    let offers
    if (Array.isArray(parsed)) {
      offers = parsed
    } else if (Array.isArray(parsed?.offers)) {
      offers = parsed.offers
    } else {
      return
    }

    const targetIndex = offers.findIndex(offer => {
      if (isRoundtrip) {
        const raw = flight?.rawOffer || {}
        const offerId = offer.offer_observation_id
        if (offerId && raw.offer_observation_id && offerId === raw.offer_observation_id) return true

        const offerFn = offer.flight_number || offer.rawOffer?.flight_number
        const offerRet = offer.ret_flight_number || offer.rawOffer?.ret_flight_number
        const offerPrice = offer.price_krw ?? offer.rawOffer?.price_krw
        const targetRet = raw.ret_flight_number || flight.retFlightNumber
        const targetPrice = raw.price_krw ?? flight.price
        return offerFn === flightNumber && offerRet === targetRet && offerPrice === targetPrice
      }

      const offerFn = offer.flight_number || offer.rawOffer?.flight_number
      if (offerFn && offerFn === flightNumber) return true

      const offerDep = offer.dep_time || offer.dep_time_local
      const depTime = flight?.dep || flight?.rawOffer?.dep_time
      if (depTime && offerDep && offerDep === depTime) return true
      return false
    })

    if (targetIndex === -1) return

    offers[targetIndex] = {
      ...offers[targetIndex],
      prediction: predictResult,
    }

    if (Array.isArray(parsed)) {
      sessionStorage.setItem(cacheKey, JSON.stringify(offers))
    } else {
      sessionStorage.setItem(cacheKey, JSON.stringify({
        ...parsed,
        offers,
      }))
    }
  } catch {
    // Cache updates are best-effort; the detail page result should remain visible.
  }
}

function historyStatusMessage(status, isRoundtrip = false) {
  if (status === 'unavailable_missing_flight_number') {
    return '가격 이력 조회에 필요한 항공편 번호가 없습니다.'
  }
  if (status === 'unavailable_invalid_request') {
    return isRoundtrip
      ? '왕복 가격 추이를 표시하기 위한 항공편 정보가 부족합니다.'
      : '가격 이력 조회에 필요한 요청 정보가 부족합니다.'
  }
  if (status === 'unavailable_no_history') {
    return isRoundtrip
      ? '해당 왕복 조합의 관측 이력이 부족합니다.'
      : '이 항공편의 과거 가격 이력이 아직 충분하지 않습니다.'
  }
  if (status === 'unavailable_db_pool') {
    return '가격 이력 DB 연결을 사용할 수 없습니다.'
  }
  if (status === 'unsupported_trip_type') {
    return '왕복 가격 추이 API가 아직 반영되지 않았습니다.'
  }
  return '가격 추이를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.'
}

function formatPrice(value) {
  if (value === null || value === undefined) return '-'
  return `${Number(value).toLocaleString()}원`
}

function formatAxisPrice(value) {
  const price = Number(value)
  if (!Number.isFinite(price)) return '-'
  if (Math.abs(price) >= 10000) return `${Math.round(price / 10000)}만원`
  return `${price.toLocaleString()}원`
}

function HistoryContentPolished({ data, loading, error, isRoundtrip = false }) {
  if (loading) {
    return (
      <div className={styles.chartEmpty}>
        <p className={styles.emptyDesc}>가격 이력을 불러오는 중입니다.</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.chartEmpty}>
        <p className={styles.emptyDesc}>{error}</p>
      </div>
    )
  }

  const history = data?.history || []
  const summary = data?.summary
  if (data?.status !== 'ok' || history.length === 0 || !summary) {
    return (
      <div className={styles.chartEmpty}>
        <p className={styles.emptyDesc}>
          {isRoundtrip
            ? '해당 왕복 조합의 관측 이력이 부족합니다.'
            : '이 항공편의 과거 가격 이력이 아직 충분하지 않습니다.'}
        </p>
      </div>
    )
  }

  return (
    <div>
      <div className={styles.chartHeaderRow}>
        <span className={styles.chartSubLabel}>
          {isRoundtrip ? '왕복 조합 가격 추이' : '과거 가격 흐름'}
        </span>
        <span className={styles.chartUnitLabel}>가격 기준: 원</span>
      </div>
      {isRoundtrip && (
        <p className={styles.emptyDesc}>출국편 + 귀국편 조합 가격 기준</p>
      )}
      <HistoryChart history={history} />
      <div className={styles.chartDirectionRow}>
        <span>과거</span>
        <span className={styles.chartDirectionLine} />
        <span>최근</span>
      </div>
      <div className={styles.historySummary}>
        <div className={styles.historySummaryItem}>
          <span className={styles.historySummaryLabel}>현재 가격</span>
          <span className={styles.historySummaryValue}>{formatPrice(summary.current_price)}</span>
        </div>
        <div className={styles.historySummaryItem}>
          <span className={styles.historySummaryLabel}>이 기간 최저</span>
          <span className={styles.historySummaryValue}>{formatPrice(summary.min_price)}</span>
        </div>
        <div className={styles.historySummaryItem}>
          <span className={styles.historySummaryLabel}>이 기간 평균</span>
          <span className={styles.historySummaryValue}>{formatPrice(summary.mean_price)}</span>
        </div>
        <div className={styles.historySummaryItem}>
          <span className={styles.historySummaryLabel}>관측 횟수</span>
          <span className={styles.historySummaryValue}>{summary.count}회</span>
        </div>
      </div>
    </div>
  )
}

function HistoryChart({ history }) {
  const points = history
    .slice(-120)
    .filter(point => Number.isFinite(Number(point.price_krw)))
  if (points.length === 0) return null
  const prices = points.map(point => Number(point.price_krw))

  const minPrice = Math.min(...prices)
  const maxPrice = Math.max(...prices)
  const span = maxPrice - minPrice
  const width = 300
  const height = 142
  const plotTop = 14
  const plotHeight = 94
  const leftPad = 42
  const rightPad = 12
  const bottomLabelY = 132
  const line = points.map((point, index) => {
    const x = points.length === 1
      ? (leftPad + width - rightPad) / 2
      : leftPad + (index / (points.length - 1)) * (width - leftPad - rightPad)
    const price = Number(point.price_krw)
    const y = span === 0
      ? plotTop + plotHeight / 2
      : plotTop + plotHeight - ((price - minPrice) / span) * plotHeight
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')

  return (
    <svg className={styles.historyChart} viewBox="0 0 300 142" role="img" aria-label="가격 추이 차트">
      <line className={styles.historyGridLine} x1={leftPad} y1={plotTop} x2={width - rightPad} y2={plotTop} />
      <line className={styles.historyGridLine} x1={leftPad} y1={plotTop + plotHeight} x2={width - rightPad} y2={plotTop + plotHeight} />
      <text className={styles.historyAxisLabel} x="4" y={plotTop + 4}>{formatAxisPrice(maxPrice)}</text>
      <text className={styles.historyAxisLabel} x="4" y={plotTop + plotHeight + 4}>{formatAxisPrice(minPrice)}</text>
      <polyline className={styles.historyLine} points={line} />
      <text className={styles.historyAxisLabel} x={leftPad} y={bottomLabelY}>과거</text>
      <text className={styles.historyAxisLabel} x={width - rightPad} y={bottomLabelY} textAnchor="end">최근</text>
      <text className={styles.historyAxisTitle} x={width / 2} y={bottomLabelY}>관측 흐름</text>
    </svg>
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

function getDecisionThreshold(prediction, tripType) {
  const fromPrediction = normalizeProbability(prediction?.threshold)
  if (fromPrediction !== null) return fromPrediction
  return tripType === 'round' || tripType === 'roundtrip' ? 0.65 : 0.8
}

function PriceDropGauge({ prediction, tripType }) {
  const expectation = getPriceDropExpectation(prediction)
  if (expectation === null || !Number.isFinite(expectation)) return null
  const percent = Math.round(Math.max(0, Math.min(1, expectation)) * 100)
  const thresholdPercent = Math.round(getDecisionThreshold(prediction, tripType) * 100)

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
        <span>WAIT 전환 기준 {thresholdPercent}%</span>
      </div>
      <p className={styles.gaugeHelp}>
        모델이 계산한 추가 하락 가능성입니다. 실제 가격을 보장하지 않습니다.
      </p>
    </div>
  )
}

function JudgmentContentPolished({ prediction, tripType }) {
  const status = prediction?.prediction_status

  if (status === 'loading') {
    return (
      <div className={styles.judgmentEmpty}>
        <p className={styles.emptyTitle}>추천 분석 중입니다</p>
        <p className={styles.emptyDesc}>잠시만 기다려주세요.</p>
      </div>
    )
  }

  if (status === 'ok') {
    return (
      <div className={styles.judgmentResult}>
        <div
          className={
            prediction.decision === 'BUY'
              ? styles.buyBadge
              : styles.waitBadge
          }
        >
          {prediction.decision === 'BUY' ? '지금 구매 추천' : '가격 하락 대기 추천'}
        </div>
        <p className={styles.recommendationHelp}>
          {prediction.decision === 'BUY'
            ? '현재 가격 기준 구매 권장'
            : '추가 하락 가능성을 고려해 대기 권장'}
        </p>
        <PriceDropGauge prediction={prediction} tripType={tripType} />
      </div>
    )
  }

  if (status === 'skipped_not_in_top_k') {
    return (
      <div className={styles.judgmentEmpty}>
        <p className={styles.emptyTitle}>분석 대상 외</p>
        <p className={styles.emptyDesc}>이 항공편은 우선 분석 대상에 포함되지 않았습니다.</p>
      </div>
    )
  }

  if (status?.startsWith('unavailable_')) {
    const message = unavailableMessagePolished(status)
    return (
      <div className={styles.judgmentEmpty}>
        <p className={styles.emptyTitle}>{message.title}</p>
        <p className={styles.emptyDesc}>{message.desc}</p>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className={styles.judgmentEmpty}>
        <p className={styles.emptyTitle}>추천 오류</p>
        <p className={styles.emptyDesc}>추천 오류가 발생했습니다.</p>
      </div>
    )
  }

  return (
    <div className={styles.judgmentEmpty}>
      <p className={styles.emptyTitle}>추천 분석 전</p>
      <p className={styles.emptyDesc}>상세 분석이 완료되면 BUY / WAIT 판단이 표시됩니다.</p>
    </div>
  )
}

function unavailableMessagePolished(status) {
  if (status === 'unavailable_insufficient_history') {
    return {
      title: '추천 분석 불가',
      desc: '이 항공편의 과거 가격 이력이 부족합니다.',
    }
  }
  if (status === 'unavailable_missing_flight_number') {
    return {
      title: '추천 분석 불가',
      desc: '항공편 번호 정보가 없어 추천 분석이 불가합니다.',
    }
  }
  if (status === 'unavailable_unknown_mapping') {
    return {
      title: '추천 분석 불가',
      desc: '이 항공편의 분석 패턴 정보가 부족합니다.',
    }
  }
  return {
    title: '추천 분석 불가',
    desc: '추천 분석 불가',
  }
}
