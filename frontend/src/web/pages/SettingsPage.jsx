import { useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { ArrowLeft, LogOut } from 'lucide-react'
import { useAuth } from '../../store/AuthContext'
import { apiCall } from '../../api/client'
import styles from './SettingsPage.module.css'

export default function SettingsPage() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [settings, setSettings] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // 백엔드에서 설정 로드
  useEffect(() => {
    if (!user?.token) return
    apiCall('/users/me/settings', {}, user.token)
      .then(setSettings)
      .catch(() => setSettings({ notification: true, default_route_type: 'oneway' }))
  }, [user])

  const updateSetting = async (key, value) => {
    const next = { ...settings, [key]: value }
    setSettings(next)
    setSaving(true)
    try {
      await apiCall('/users/me/settings', {
        method: 'PUT',
        body: JSON.stringify({ [key]: value }),
      }, user.token)
      setSaved(true)
      setTimeout(() => setSaved(false), 1500)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button onClick={() => navigate(-1)}><ArrowLeft size={24} /></button>
        <span className={styles.title}>설정</span>
        <div style={{ width: 36 }} />
      </header>

      <main className={styles.main}>
        {/* 계정 정보 */}
        <div className={styles.section}>
          <p className={styles.sectionTitle}>계정</p>
          <div className={styles.item}>
            <span>카카오 연동</span>
            <span className={styles.valueOk}>연동됨</span>
          </div>
          <div className={styles.item}>
            <span>사용자 ID</span>
            <span className={styles.value}>{user?.id ?? '-'}</span>
          </div>
        </div>

        {/* 알림 설정 */}
        <div className={styles.section}>
          <p className={styles.sectionTitle}>알림</p>
          <div className={styles.item}>
            <span>가격 변동 알림(준비 중)</span>
            {/*
            <input
              type="checkbox"
              checked={settings?.notification ?? true}
              onChange={e => updateSetting('notification', e.target.checked)}
            />
            */}
            <input
              type="checkbox"
              checked={false}
              disabled
              aria-disabled="true"
            />
          </div>
        </div>

        {/* 기본 노선 */}
        <div className={styles.section}>
          <p className={styles.sectionTitle}>기본 설정</p>
          <div className={styles.item}>
            <span>편도/왕복</span>
            <select
              value={settings?.default_route_type ?? 'oneway'}
              onChange={e => updateSetting('default_route_type', e.target.value)}
              className={styles.select}
            >
              <option value="oneway">편도</option>
              <option value="roundtrip">왕복</option>
            </select>
          </div>
        </div>

        {saving && <p className={styles.hint}>저장 중...</p>}
        {saved && <p className={styles.hintOk}>저장됨!</p>}

        {/* 로그아웃 */}
        <div className={styles.section}>
          <button className={styles.logoutBtn} onClick={handleLogout}>
            <LogOut size={16} />
            로그아웃
          </button>
        </div>
      </main>
    </div>
  )
}
