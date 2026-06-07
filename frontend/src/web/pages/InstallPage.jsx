import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Browser } from '@capacitor/browser'
import { ArrowLeft, Check, Copy, Download, ExternalLink, Home, Settings } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { INSTALL_CONFIG } from '../../config/installConfig'
import { getClientEnvironment } from '../../utils/clientEnvironment'
import styles from './InstallPage.module.css'

async function openExternal(url, environment) {
  if (!url) return
  if (environment.isNativeApp) {
    await Browser.open({ url })
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

function InfoRow({ label, value }) {
  return (
    <div className={styles.infoRow}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function Section({ title, description, children }) {
  return (
    <section className={styles.section}>
      <p className={styles.sectionTitle}>{title}</p>
      {description && <p className={styles.sectionDesc}>{description}</p>}
      {children}
    </section>
  )
}

export default function InstallPage() {
  const navigate = useNavigate()
  const environment = useMemo(() => getClientEnvironment(), [])
  const [copied, setCopied] = useState(false)
  const [showPlayGuide, setShowPlayGuide] = useState(false)

  const handleBack = () => {
    if (window.history.length > 1) navigate(-1)
    else navigate('/')
  }

  const copyInstallLink = async () => {
    try {
      await navigator.clipboard.writeText(INSTALL_CONFIG.installPageUrl)
    } catch {
      const input = document.createElement('input')
      input.value = INSTALL_CONFIG.installPageUrl
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  const openGithubApk = () => openExternal(INSTALL_CONFIG.githubApkUrl, environment)
  const openInternalSharing = () => openExternal(INSTALL_CONFIG.internalAppSharingUrl, environment)

  const renderVersionSection = () => (
    <Section title="BARO 앱 정보">
      <div className={styles.infoPanel}>
        <InfoRow label="현재 버전" value={INSTALL_CONFIG.androidVersion} />
        <InfoRow label="패키지" value={INSTALL_CONFIG.packageName} />
      </div>
    </Section>
  )

  const renderApkSection = () => (
    <Section
      title="APK로 바로 설치"
      description="이메일이나 테스트 등록 없이 바로 다운로드할 수 있습니다."
    >
      <button className={styles.primaryButton} onClick={openGithubApk} aria-label="BARO Android APK 다운로드">
        <Download size={18} />
        APK 다운로드
      </button>
      <ol className={styles.guideList}>
        <li>APK 파일을 다운로드합니다.</li>
        <li>브라우저가 설치 권한을 요청하면 이 출처 허용을 선택합니다.</li>
        <li>설치 화면에서 설치를 완료합니다.</li>
        <li>Google Play Protect 확인 화면이 표시될 수 있습니다.</li>
      </ol>
      <p className={styles.warningText}>Google Play 밖 직접 설치 방식입니다.</p>
      {INSTALL_CONFIG.apkSha256 && (
        <p className={styles.hashText}>SHA-256 {INSTALL_CONFIG.apkSha256}</p>
      )}
    </Section>
  )

  const renderPlaySection = () => (
    <Section
      title="Google Play로 설치"
      description="Google Play 내부 앱 공유를 사용해 설치합니다. 처음 사용하는 경우 Google Play에서 내부 앱 공유 기능을 먼저 활성화해야 합니다."
    >
      <div className={styles.choiceGroup}>
        <button
          className={styles.secondaryButton}
          onClick={openInternalSharing}
          disabled={!INSTALL_CONFIG.internalAppSharingUrl}
          aria-label="Google Play 내부 앱 공유에서 바로 BARO 설치"
        >
          <ExternalLink size={18} />
          내부 앱 공유가 설정되어 있습니다
        </button>
        <button className={styles.ghostButton} onClick={() => setShowPlayGuide((value) => !value)}>
          {showPlayGuide ? '설정 안내 접기' : '처음 사용하거나 설정 여부를 모르겠습니다'}
        </button>
      </div>

      {!INSTALL_CONFIG.internalAppSharingUrl && (
        <p className={styles.mutedText}>현재 내부 앱 공유 링크를 준비 중입니다.</p>
      )}

      {showPlayGuide && (
        <div className={styles.guidePanel}>
          <ol className={styles.guideList}>
            <li>Google Play 스토어 앱을 엽니다.</li>
            <li>오른쪽 위 프로필 사진을 누릅니다.</li>
            <li>설정, 정보로 이동합니다.</li>
            <li>Play 스토어 버전을 7번 연속 누릅니다.</li>
            <li>개발자 옵션이 활성화되었다는 안내를 확인합니다.</li>
            <li>설정 화면에서 내부 앱 공유를 활성화합니다.</li>
            <li>이 페이지로 돌아와 아래 설치 버튼을 누릅니다.</li>
          </ol>
          <button
            className={styles.secondaryButton}
            onClick={openInternalSharing}
            disabled={!INSTALL_CONFIG.internalAppSharingUrl}
          >
            <ExternalLink size={18} />
            설정을 완료했습니다. Google Play에서 설치
          </button>
          <p className={styles.noticeText}>
            Google 계정 또는 앱 접근 권한 상태에 따라 설치가 제한될 수 있습니다. 설치되지 않으면 APK 직접 설치 방식을 이용하세요.
          </p>
        </div>
      )}
    </Section>
  )

  const renderAndroid = () => (
    <>
      <Section title="Android 앱 설치" description="현재 기기에서 이용할 수 있는 설치 방법을 선택하세요." />
      {renderApkSection()}
      {renderPlaySection()}
    </>
  )

  const renderDesktop = () => (
    <>
      <Section
        title="Android 앱 설치"
        description="휴대폰으로 QR 코드를 스캔하면 기기에 맞는 설치 방법을 확인할 수 있습니다."
      >
        <div className={styles.qrCard}>
          <div className={styles.qrBox} aria-label="BARO 설치 페이지 QR 코드">
            <QRCodeSVG value={INSTALL_CONFIG.installPageUrl} size={176} level="M" includeMargin />
          </div>
          <p className={styles.visibleUrl}>{INSTALL_CONFIG.installPageUrl}</p>
          <button className={styles.secondaryButton} onClick={copyInstallLink}>
            {copied ? <Check size={18} /> : <Copy size={18} />}
            {copied ? '복사됨' : '설치 링크 복사'}
          </button>
        </div>
      </Section>
      <Section title="PC에서 이용">
        <div className={styles.actionRow}>
          <button className={styles.primaryButton} onClick={() => navigate('/')}>
            <Home size={18} />
            웹에서 계속 이용하기
          </button>
          <button className={styles.ghostButton} onClick={openGithubApk}>
            <Download size={18} />
            APK 파일을 PC에 다운로드
          </button>
        </div>
      </Section>
    </>
  )

  const renderIOS = () => (
    <>
      <Section
        title="iPhone/iPad 이용"
        description="iPhone과 iPad에서는 BARO 웹을 바로 이용할 수 있습니다."
      >
        <ol className={styles.guideList}>
          <li>Safari에서 BARO 웹을 엽니다.</li>
          <li>공유 버튼을 누릅니다.</li>
          <li>홈 화면에 추가를 선택합니다.</li>
          <li>추가를 눌러 바로가기를 만듭니다.</li>
        </ol>
        <button className={styles.primaryButton} onClick={() => navigate('/')}>
          <Home size={18} />
          웹에서 계속 이용하기
        </button>
      </Section>
    </>
  )

  const renderNative = () => (
    <>
      <Section
        title="BARO 앱 정보"
        description={`현재 BARO Android 앱을 사용 중입니다. 현재 버전: ${INSTALL_CONFIG.androidVersion}`}
      >
        <p className={styles.noticeText}>
          새 버전이 제공된 경우 현재 앱 위에 업데이트 설치할 수 있습니다. 설치 경로가 작동하지 않는 경우 기존 앱 삭제가 필요할 수 있습니다.
        </p>
      </Section>
      <Section title="업데이트 또는 재설치 방법 확인">
        <div className={styles.actionRow}>
          <button className={styles.primaryButton} onClick={openGithubApk}>
            <Download size={18} />
            APK로 업데이트 설치
          </button>
          <button
            className={styles.secondaryButton}
            onClick={openInternalSharing}
            disabled={!INSTALL_CONFIG.internalAppSharingUrl}
          >
            <ExternalLink size={18} />
            Google Play 내부 앱 공유로 설치
          </button>
          {!INSTALL_CONFIG.internalAppSharingUrl && (
            <p className={styles.mutedText}>현재 내부 앱 공유 링크를 준비 중입니다.</p>
          )}
        </div>
      </Section>
      <Section title="앱 이동">
        <div className={styles.actionRow}>
          <button className={styles.secondaryButton} onClick={() => navigate('/settings')}>
            <Settings size={18} />
            설정으로 돌아가기
          </button>
          <button className={styles.ghostButton} onClick={() => navigate('/')}>
            <Home size={18} />
            홈으로 이동
          </button>
        </div>
      </Section>
    </>
  )

  const renderUnknown = () => (
    <>
      <Section
        title="BARO 설치 안내"
        description="BARO 웹을 이용 중입니다. Android 기기에서는 APK 설치가 가능하며 iPhone과 iPad에서는 웹으로 이용할 수 있습니다."
      >
        <div className={styles.actionRow}>
          <button className={styles.primaryButton} onClick={() => navigate('/')}>
            <Home size={18} />
            웹에서 계속 이용하기
          </button>
          <button className={styles.secondaryButton} onClick={openGithubApk}>
            <Download size={18} />
            APK 다운로드
          </button>
        </div>
      </Section>
    </>
  )

  let body = renderUnknown()
  if (environment.isNativeApp) body = renderNative()
  else if (environment.isAndroid) body = renderAndroid()
  else if (environment.isIOS) body = renderIOS()
  else if (environment.isDesktop) body = renderDesktop()

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button type="button" className={styles.backBtn} onClick={handleBack} aria-label="뒤로가기">
          <ArrowLeft size={22} color="#fff" />
        </button>
        <span className={styles.title}>앱 설치 및 다운로드</span>
        <div className={styles.headerSpacer} aria-hidden="true" />
      </header>
      <main className={styles.main}>
        {renderVersionSection()}
        {body}
      </main>
    </div>
  )
}
