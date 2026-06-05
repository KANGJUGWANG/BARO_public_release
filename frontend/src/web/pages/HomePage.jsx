import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlaneTakeoff, ArrowLeftRight } from 'lucide-react'
import DatePicker from '../components/DatePicker'
import { useAuth } from '../../store/AuthContext'
import { apiCall } from '../../api/client'
import styles from './HomePage.module.css'

const AIRPORT_MAP = {
  ICN: [
    { code: 'NRT', label: '도쿄 나리타', sub: 'NRT' },
    { code: 'HND', label: '도쿄 하네다', sub: 'HND' },
  ],
  NRT: [{ code: 'ICN', label: '인천', sub: 'ICN' }],
  HND: [{ code: 'ICN', label: '인천', sub: 'ICN' }],
}

const ALL_AIRPORTS = [
  { code: 'ICN', label: '인천', sub: 'ICN' },
  { code: 'NRT', label: '도쿄 나리타', sub: 'NRT' },
  { code: 'HND', label: '도쿄 하네다', sub: 'HND' },
]

const today = () => {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const byType = Object.fromEntries(parts.map(part => [part.type, part.value]))
  return `${byType.year}-${byType.month}-${byType.day}`
}

function addDays(dateStr, days) {
  if (!dateStr) return ''
  const [y, m, d] = dateStr.split('-').map(Number)
  if (!y || !m || !d) return ''
  const date = new Date(Date.UTC(y, m - 1, d))
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return dateStr.replaceAll('-', '.')
}

export default function HomePage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [tripType, setTripType] = useState('oneway')
  const [origin, setOrigin] = useState('ICN')
  const [destination, setDestination] = useState('NRT')
  const [departDate, setDepartDate] = useState('')
  const [returnDate, setReturnDate] = useState('')

  useEffect(() => {
    if (!user?.token) return
    apiCall('/users/me/settings', {}, user.token)
      .then(s => {
        if (s?.default_route_type)
          setTripType(s.default_route_type === 'roundtrip' ? 'round' : 'oneway')
      })
      .catch(() => {})
  }, [user])

  const destOptions = AIRPORT_MAP[origin] || []

  const handleOriginChange = (code) => {
    setOrigin(code)
    const options = AIRPORT_MAP[code] || []
    if (options.length > 0) setDestination(options[0].code)
  }

  const swapAirports = () => {
    const newOrigin = destination
    const newDest = origin
    setOrigin(newOrigin)
    const options = AIRPORT_MAP[newOrigin] || []
    const valid = options.find(a => a.code === newDest)
    setDestination(valid ? newDest : options[0]?.code || '')
  }

  const handleDepartDate = (val) => {
    setDepartDate(val)
    if (tripType === 'round') {
      setReturnDate(addDays(val, 7))
    } else if (returnDate && returnDate <= val) {
      setReturnDate('')
    }
  }

  const isSearchable = () => {
    if (!departDate) return false
    return true
  }

  const handleSearch = () => {
    if (!isSearchable()) return
    const isRound = tripType === 'round'
    const computedReturnDate = isRound ? addDays(departDate, 7) : returnDate
    navigate('/search', {
      state: {
        tripType,
        origin,
        destination,
        departDate,
        returnDate: computedReturnDate,
        stayNights: isRound ? 7 : undefined,
      },
    })
  }

  const getAirport = (code) => ALL_AIRPORTS.find(a => a.code === code)

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div style={{ width: 40 }} />
        <div className={styles.logo}>
          <PlaneTakeoff size={16} color="#fff" />
          <span>BARO</span>
        </div>
        <div style={{ width: 40 }} />
      </header>

      <div className={styles.hero}>
        <h1 className={styles.heroTitle}>지금 사야 할까,<br />기다려야 할까?</h1>
        <p className={styles.heroSub}>항공권 구매 시점을 분석해드립니다</p>
      </div>

      <div className={styles.card}>
        <div className={styles.tripToggle}>
          <button
            className={tripType === 'oneway' ? styles.toggleActive : styles.toggleInactive}
            onClick={() => { setTripType('oneway'); setReturnDate('') }}
          >편도</button>
          <button
            className={tripType === 'round' ? styles.toggleActive : styles.toggleInactive}
            onClick={() => {
              setTripType('round')
              if (departDate) setReturnDate(addDays(departDate, 7))
            }}
          >왕복</button>
        </div>

        <div className={styles.airportRow}>
          <div className={styles.airportBox}>
            <span className={styles.airportLabel}>출발</span>
            <div className={styles.selectWrap}>
              <select
                className={styles.airportSelect}
                value={origin}
                onChange={e => handleOriginChange(e.target.value)}
              >
                {ALL_AIRPORTS.map(a => (
                  <option key={a.code} value={a.code}>{a.label}</option>
                ))}
              </select>
              <span className={styles.selectArrow}>▼</span>
            </div>
            <span className={styles.airportCode}>{getAirport(origin)?.sub}</span>
          </div>
          <button className={styles.swapBtn} onClick={swapAirports}>
            <ArrowLeftRight size={16} color="#1A2B5E" />
          </button>
          <div className={styles.airportBox}>
            <span className={styles.airportLabel}>도착</span>
            <div className={styles.selectWrap}>
              <select
                className={styles.airportSelect}
                value={destination}
                onChange={e => setDestination(e.target.value)}
              >
                {destOptions.map(a => (
                  <option key={a.code} value={a.code}>{a.label}</option>
                ))}
              </select>
              <span className={styles.selectArrow}>▼</span>
            </div>
            <span className={styles.airportCode}>{getAirport(destination)?.sub}</span>
          </div>
        </div>

        <div className={`${styles.dateRow} ${tripType === 'round' ? styles.dateRowRound : ''}`}>
          <DatePicker label="출발일" value={departDate} onChange={handleDepartDate} min={today()} />
          {tripType === 'round' && (
            <div className={styles.returnDateWrap}>
              <span className={styles.returnDateLabel}>귀국일</span>
              <div className={styles.returnDateDisplay} aria-readonly="true">
                <strong className={styles.returnDateValue}>
                  {formatDate(departDate ? addDays(departDate, 7) : '')}
                </strong>
              </div>
            </div>
          )}
        </div>

        {tripType === 'round' && (
          <p className={styles.hint}>왕복 추천은 출발일 기준 +7일 체류 일정으로 제공됩니다.</p>
        )}

        <button className={styles.searchBtn} onClick={handleSearch} disabled={!isSearchable()}>
          <PlaneTakeoff size={18} color="#fff" />
          항공권 분석하기
        </button>
      </div>
    </div>
  )
}
