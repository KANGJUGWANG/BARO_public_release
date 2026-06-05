import styles from './LoginPage.module.css'
import baroLoginLogo from '../../assets/baro-login-logo.png'
import { Capacitor } from '@capacitor/core'
import { Browser } from '@capacitor/browser'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://<SERVER_IP>:8000'

export default function LoginPage() {
  const handleKakaoLogin = async () => {
    const loginUrl = `${BACKEND_URL}/auth/kakao/login`
    if (Capacitor.isNativePlatform()) {
      await Browser.open({ url: `${loginUrl}?client=apk` })
      return
    }
    window.location.href = loginUrl
  }

  const handleDemoStart = () => {
    // Phase 5-1 demo entry: bypass login only for recommendation flow verification.
    localStorage.setItem('airchoice_user', JSON.stringify({ id: 'demo', demo: true }))
    window.location.href = '/'
  }

  return (
    <div className={styles.page}>
      <div className={styles.top}>
        <img src={baroLoginLogo} alt="BARO PRICE BAROMETER" className={styles.logoImg} />
        <p className={styles.desc}>항공권 구매 시점 분석 서비스</p>
      </div>

      <div className={styles.bottom}>
        <button className={styles.kakaoBtn} onClick={handleKakaoLogin}>
          <span className={styles.kakaoIcon}>K</span>
          카카오로 시작하기
        </button>
        <button className={styles.demoBtn} onClick={handleDemoStart}>
          비로그인으로 시작하기
        </button>
      </div>
    </div>
  )
}
