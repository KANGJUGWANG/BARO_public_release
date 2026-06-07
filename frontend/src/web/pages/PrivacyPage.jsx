import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import styles from './LegalPage.module.css'

export default function PrivacyPage() {
  const navigate = useNavigate()

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate(-1)} aria-label="뒤로가기">
          <ArrowLeft size={22} />
        </button>
        <span className={styles.title}>개인정보처리방침</span>
        <div style={{ width: 36 }} />
      </header>

      <main className={styles.main}>
        <section className={styles.section}>
          <h1 className={styles.sectionTitle}>서비스 개요</h1>
          <p className={styles.text}>
            BARO는 항공권 검색 결과와 가격 관측 데이터를 바탕으로 구매 시점 판단을 돕는 서비스입니다.
            비로그인 상태에서도 항공권 검색과 추천 조회가 가능하며, 카카오 로그인 사용자는 저장 목록과 기본 설정을 사용할 수 있습니다.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>수집하는 정보</h2>
          <ul className={styles.list}>
            <li>카카오 로그인으로 전달받는 사용자 식별값</li>
            <li>사용자가 저장한 항공권 정보</li>
            <li>기본 검색 설정 및 알림 설정값</li>
            <li>서비스 요청 처리에 필요한 검색 조건과 최소한의 서버 로그</li>
          </ul>
          <p className={styles.note}>
            BARO는 카카오 비밀번호를 수집하거나 저장하지 않습니다. 카카오 인증은 카카오 OAuth를 통해 처리됩니다.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>이용 목적</h2>
          <ul className={styles.list}>
            <li>사용자 로그인 상태 확인</li>
            <li>저장 항공권 목록 제공</li>
            <li>사용자 기본 설정 저장 및 불러오기</li>
            <li>항공권 가격 분석, 추천 결과, 가격 추이 제공</li>
            <li>서비스 안정성 확인과 오류 대응</li>
          </ul>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>보관 및 삭제</h2>
          <p className={styles.text}>
            로그인 사용자 데이터는 서비스 제공을 위해 보관되며, 사용자가 BARO 탈퇴를 요청하면 BARO 서버에 저장된 사용자 식별 정보,
            저장 항공권, 설정값을 삭제하고 BARO와 카카오계정의 연결을 해제합니다. 카카오계정 자체는 삭제되지 않습니다.
            공용 항공권 관측 데이터와 통계 데이터는 특정 사용자 계정과 직접 연결되지 않는 서비스 공용 데이터로 유지될 수 있습니다.
          </p>
          <p className={styles.note}>
            계정 및 데이터 삭제 방법은 <Link className={styles.link} to="/account-deletion">계정 및 데이터 삭제 안내</Link>에서 확인할 수 있습니다.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>전송 및 제3자 제공</h2>
          <p className={styles.text}>
            BARO는 로그인 처리를 위해 카카오 OAuth API와 통신합니다. 서비스 API 통신은 HTTPS 환경에서 전송 중 암호화됩니다.
            BARO는 사용자 데이터를 광고 판매 목적으로 제3자에게 제공하지 않습니다.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>사용자 권리와 문의</h2>
          <p className={styles.text}>
            사용자는 앱의 설정 화면에서 BARO 계정과 저장 데이터를 삭제할 수 있습니다. 앱 접근이 어려운 경우 Google Play 스토어의 BARO 개발자 연락처를 통해 삭제를 요청할 수 있습니다.
            요청 시 비밀번호, OAuth 토큰, 민감한 인증값은 보내지 마세요.
          </p>
        </section>
      </main>
    </div>
  )
}
