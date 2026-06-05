import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuth } from '../../store/AuthContext'
import { apiCall } from '../../api/client'
import styles from './SavedListPage.module.css'

export default function SavedListPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [saved, setSaved] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user?.token) {
      setSaved([])
      setLoading(false)
      return
    }
    setLoading(true)
    apiCall('/users/me/saved', {}, user.token)
      .then(r => setSaved(r.saved || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [user])

  const handleDelete = async (id) => {
    try {
      await apiCall(`/users/me/saved/${id}`, { method: 'DELETE' }, user.token)
      setSaved(prev => prev.filter(f => f.id !== id))
    } catch (e) { console.error(e) }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate(-1)}>
          <ArrowLeft size={22} color="#fff" />
        </button>
        <span className={styles.title}>저장 목록</span>
        <div style={{ width: 36 }} />
      </header>

      <main className={styles.main}>
        {!user?.token ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>🔒</div>
            <p className={styles.emptyTitle}>로그인이 필요합니다</p>
            <p className={styles.emptyDesc}>
              저장한 항공권을 확인하려면<br />로그인해주세요.
            </p>
          </div>
        ) : loading ? null : saved.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>🔖</div>
            <p className={styles.emptyTitle}>저장된 항공편이 없습니다</p>
            <p className={styles.emptyDesc}>항공편 상세에서 저장하면<br />가격 변동을 추적할 수 있습니다</p>
          </div>
        ) : (
          saved.map(f => (
            <div key={f.id} className={styles.card}>
              <div className={styles.cardLeft}>
                <div className={styles.cardTop}>
                  <span className={styles.routeLabel}>
                    {f.origin} → {f.destination}
                  </span>
                  {f.isRound && <span className={styles.roundBadge}>왕복</span>}
                </div>
                <span className={styles.airline}>{f.airline}</span>
                <span className={styles.meta}>
                  출발 {f.departDate}
                  {f.returnDate && ` · 귀국 ${f.returnDate}`}
                  {' · '}{f.price?.toLocaleString()}원
                </span>
              </div>
              <button className={styles.deleteBtn} onClick={() => handleDelete(f.id)}>삭제</button>
            </div>
          ))
        )}
      </main>
    </div>
  )
}
