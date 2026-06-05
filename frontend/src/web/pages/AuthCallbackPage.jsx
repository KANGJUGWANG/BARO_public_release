import { useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAuth } from '../../store/AuthContext'
import styles from './AuthCallbackPage.module.css'

export default function AuthCallbackPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { handleTokenCallback } = useAuth()
  const [status, setStatus] = useState('로그인 처리 중...')

  useEffect(() => {
    const token = searchParams.get('token')
    const error = searchParams.get('error')

    if (error) {
      setStatus('로그인이 취소되었습니다')
      setTimeout(() => navigate('/login'), 1500)
      return
    }

    if (!token) {
      setStatus('토큰이 없습니다')
      setTimeout(() => navigate('/login'), 1500)
      return
    }

    // async로 처리 — await 후 navigate (완료 전 이동 방지)
    const process = async () => {
      try {
        await handleTokenCallback(token)
        setStatus('로그인 성공!')
        navigate('/', { replace: true })
      } catch (err) {
        console.error('콜백 실패:', err)
        setStatus('로그인 실패: ' + err.message)
        setTimeout(() => navigate('/login'), 2000)
      }
    }

    process()
  }, [])

  return (
    <div className={styles.page}>
      <div className={styles.spinner} />
      <p className={styles.status}>{status}</p>
    </div>
  )
}
