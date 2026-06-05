import { useNavigate, useLocation } from 'react-router-dom'
import { Home, BarChart2, Menu } from 'lucide-react'
import styles from './BottomBar.module.css'

const ANALYSIS_CONTEXT_KEY = 'baro_last_analysis_context'
const VALID_ROUTES = new Set(['ICN-NRT', 'NRT-ICN', 'ICN-HND', 'HND-ICN'])
const VALID_TRIP_TYPES = new Set(['oneway', 'round', 'roundtrip'])

function normalizeCode(value) {
  return typeof value === 'string' ? value.trim().toUpperCase() : ''
}

export default function BottomBar({ onMenuOpen }) {
  const navigate = useNavigate()
  const location = useLocation()

  if (location.pathname === '/login') return null

  const isHome = location.pathname === '/'
  const isAnalysis = location.pathname === '/search-detail'
  const handleMenuClick = () => {
    if (typeof onMenuOpen === 'function') onMenuOpen()
  }
  const handleAnalysisClick = () => {
    try {
      const raw = sessionStorage.getItem(ANALYSIS_CONTEXT_KEY)
      if (raw) {
        const ctx = JSON.parse(raw)
        const origin = normalizeCode(ctx.origin)
        const destination = normalizeCode(ctx.destination)
        const tripType = typeof ctx.tripType === 'string' ? ctx.tripType.trim() : ''
        const routeKey = `${origin}-${destination}`
        if (VALID_ROUTES.has(routeKey) && VALID_TRIP_TYPES.has(tripType)) {
          navigate('/search-detail', {
            state: {
              tripType,
              origin,
              destination,
              stayNights: ctx.stayNights || 7,
            },
          })
          return
        }
      }
    } catch {
      // fallback below
    }
    navigate('/search-detail')
  }

  return (
    <nav className={styles.bar}>
      <button className={styles.btn} onClick={handleMenuClick}>
        <Menu size={22} color="#94a3b8" />
        <span className={styles.label}>메뉴</span>
      </button>
      <button className={styles.btn} onClick={() => navigate('/')}>
        <Home size={22} color={isHome ? '#2563EB' : '#94a3b8'} />
        <span className={isHome ? styles.labelActive : styles.label}>홈</span>
      </button>
      <button className={styles.btn} onClick={handleAnalysisClick}>
        <BarChart2 size={22} color={isAnalysis ? '#2563EB' : '#94a3b8'} />
        <span className={isAnalysis ? styles.labelActive : styles.label}>분석</span>
      </button>
    </nav>
  )
}
