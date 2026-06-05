import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { apiCall } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const saved = localStorage.getItem('airchoice_user')
    if (saved) {
      try { setUser(JSON.parse(saved)) } catch { localStorage.removeItem('airchoice_user') }
    }
    setLoading(false)
  }, [])

  // 카카오 콜백 후 JWT 토큰 받아 적재
  const handleTokenCallback = useCallback(async (token) => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      const userData = { id: payload.sub, token }

      // 백엔드에 유저 등록/last_login 갱신
      await apiCall('/users/me', { method: 'POST' }, token)

      setUser(userData)
      localStorage.setItem('airchoice_user', JSON.stringify(userData))
      return userData
    } catch (err) {
      throw new Error('로그인 실패: ' + err.message)
    }
  }, [])

  const logout = useCallback(() => {
    setUser(null)
    localStorage.removeItem('airchoice_user')
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, handleTokenCallback, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
