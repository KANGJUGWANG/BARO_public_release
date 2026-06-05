import { useNavigate } from 'react-router-dom'
import { X, Bookmark, Settings, Info, LogOut } from 'lucide-react'
import { useAuth } from '../../store/AuthContext'
import styles from './DrawerMenu.module.css'

export default function DrawerMenu({ open, onClose }) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const go = (path) => { navigate(path); onClose() }

  const handleLogout = () => { logout(); onClose(); navigate('/login') }

  return (
    <>
      {open && <div className={styles.overlay} onClick={onClose} />}
      <div className={`${styles.drawer} ${open ? styles.open : ''}`}>
        <div className={styles.header}>
          <span className={styles.title}>BARO</span>
          <button className={styles.closeBtn} onClick={onClose}>
            <X size={20} color="#fff" />
          </button>
        </div>

        <div className={styles.userArea}>
          <div className={styles.avatar} />
          <div className={styles.userInfo}>
            <span className={styles.userName}>
              {user ? '카카오 연동됨' : '로그인이 필요합니다'}
            </span>
            {user && <span className={styles.userId}>ID: {user.id}</span>}
          </div>
        </div>

        <nav className={styles.nav}>
          <button className={styles.item} onClick={() => go('/saved')}>
            <Bookmark size={18} color="#64748b" />
            <span>저장 목록</span>
          </button>
          <button className={styles.item} onClick={() => go('/settings')}>
            <Settings size={18} color="#64748b" />
            <span>사용자 설정</span>
          </button>
          <button className={styles.item} onClick={() => go('/model-info')}>
            <Info size={18} color="#64748b" />
            <span>모델·검색 안내</span>
          </button>
        </nav>

        <div className={styles.authArea}>
          <button className={styles.logoutBtn} onClick={handleLogout}>
            <LogOut size={16} color="#ef4444" />
            <span>로그아웃</span>
          </button>
        </div>
      </div>
    </>
  )
}
