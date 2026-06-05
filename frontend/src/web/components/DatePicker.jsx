import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import styles from './DatePicker.module.css'

const DAYS = ['일', '월', '화', '수', '목', '금', '토']
const MONTHS = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월']

function toYMD(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function fromYMD(str) {
  if (!str) return null
  const [y, m, d] = str.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function getKstTodayDate() {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const byType = Object.fromEntries(parts.map(part => [part.type, part.value]))
  return fromYMD(`${byType.year}-${byType.month}-${byType.day}`)
}

export default function DatePicker({ label, value, onChange, min }) {
  const today = getKstTodayDate()

  const minDate = min ? fromYMD(min) : today
  const selected = fromYMD(value)

  const [open, setOpen] = useState(false)
  const [cursor, setCursor] = useState(() => {
    const base = selected || minDate || today
    return new Date(base.getFullYear(), base.getMonth(), 1)
  })

  const year = cursor.getFullYear()
  const month = cursor.getMonth()

  // 이전 다음 월
  const prevMonth = () => setCursor(new Date(year, month - 1, 1))
  const nextMonth = () => setCursor(new Date(year, month + 1, 1))

  // 달력 셀 생성
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  const handleSelect = (day) => {
    if (!day) return
    const picked = new Date(year, month, day)
    picked.setHours(0, 0, 0, 0)
    if (minDate && picked < minDate) return
    onChange(toYMD(picked))
    setOpen(false)
  }

  const isDisabled = (day) => {
    if (!day) return false
    const d = new Date(year, month, day)
    return minDate && d < minDate
  }

  const isSelected = (day) => {
    if (!day || !selected) return false
    return selected.getFullYear() === year &&
      selected.getMonth() === month &&
      selected.getDate() === day
  }

  const isToday = (day) => {
    if (!day) return false
    return today.getFullYear() === year &&
      today.getMonth() === month &&
      today.getDate() === day
  }

  const displayValue = selected
    ? `${selected.getFullYear()}.${String(selected.getMonth()+1).padStart(2,'0')}.${String(selected.getDate()).padStart(2,'0')}`
    : null

  return (
    <div className={styles.wrap}>
      <span className={styles.label}>{label}</span>

      {/* 선택버튼 */}
      <button
        className={`${styles.trigger} ${open ? styles.triggerOpen : ''} ${value ? styles.triggerFilled : ''}`}
        onClick={() => setOpen(v => !v)}
        type="button"
      >
        {displayValue
          ? <span className={styles.triggerValue}>{displayValue}</span>
          : <span className={styles.triggerPlaceholder}>날짜 선택</span>
        }
        <ChevronRight size={14} color={value ? '#2563EB' : '#94a3b8'}
          style={{ transform: open ? 'rotate(90deg)' : 'none', transition: '0.2s' }} />
      </button>

      {/* 달력 패널 */}
      {open && (
        <div className={styles.panel}>
          {/* 네비게이션 */}
          <div className={styles.nav}>
            <button className={styles.navBtn} onClick={prevMonth} type="button">
              <ChevronLeft size={18} color="#1e293b" />
            </button>
            <span className={styles.navTitle}>{year}년 {MONTHS[month]}</span>
            <button className={styles.navBtn} onClick={nextMonth} type="button">
              <ChevronRight size={18} color="#1e293b" />
            </button>
          </div>

          {/* 요일 */}
          <div className={styles.weekRow}>
            {DAYS.map((d, i) => (
              <span key={d} className={`${styles.weekDay} ${i === 0 ? styles.sun : i === 6 ? styles.sat : ''}`}>{d}</span>
            ))}
          </div>

          {/* 날짜 그리드 */}
          <div className={styles.grid}>
            {cells.map((day, i) => (
              <button
                key={i}
                type="button"
                className={[
                  styles.cell,
                  !day ? styles.empty : '',
                  isDisabled(day) ? styles.disabled : '',
                  isToday(day) ? styles.today : '',
                  isSelected(day) ? styles.selected : '',
                ].join(' ')}
                onClick={() => handleSelect(day)}
                disabled={isDisabled(day) || !day}
              >
                {day || ''}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
