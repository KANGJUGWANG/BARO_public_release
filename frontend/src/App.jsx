import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Capacitor } from '@capacitor/core'
import { App as CapApp } from '@capacitor/app'
import { Browser } from '@capacitor/browser'
import { useAuth } from './store/AuthContext'
import HomePage from './web/pages/HomePage'
import SearchResultPage from './web/pages/SearchResultPage'
import CardDetailPage from './web/pages/CardDetailPage'
import SearchDetailPage from './web/pages/SearchDetailPage'
import SavedListPage from './web/pages/SavedListPage'
import SettingsPage from './web/pages/SettingsPage'
import ModelInfoPage from './web/pages/ModelInfoPage'
import LoginPage from './web/pages/LoginPage'
import AuthCallbackPage from './web/pages/AuthCallbackPage'
import DrawerMenu from './web/components/DrawerMenu'
import BottomBar from './web/components/BottomBar'
import styles from './App.module.css'

// 로그인 필수 라우트 — 비로그인 시 /login으로 리다이렉트
function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  return children
}

function AppDeepLinkHandler() {
  const { handleTokenCallback } = useAuth()

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return undefined

    let removeListener = null
    CapApp.addListener('appUrlOpen', async ({ url }) => {
      if (!url?.startsWith('baro://auth/callback')) return

      try {
        const parsed = new URL(url)
        const token = parsed.searchParams.get('token')
        if (!token) return

        await Browser.close().catch(() => {})
        await handleTokenCallback(token)
        window.location.href = '/'
      } catch (err) {
        console.error('appUrlOpen error:', err)
      }
    }).then((listener) => {
      removeListener = listener
    })

    return () => {
      removeListener?.remove()
    }
  }, [handleTokenCallback])

  return null
}

function isNativeShell() {
  if (typeof window === 'undefined') return false
  const params = new URLSearchParams(window.location.search)
  return (
    Capacitor.isNativePlatform() ||
    Boolean(window.Capacitor?.isNativePlatform?.()) ||
    window.location.protocol === 'capacitor:' ||
    params.get('app') === '1' ||
    params.get('native') === '1'
  )
}

export default function App() {
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => {
    const native = isNativeShell()
    document.documentElement.classList.toggle('native-app', native)
    return () => {
      document.documentElement.classList.remove('native-app')
    }
  }, [])

  return (
    <BrowserRouter>
      <AppDeepLinkHandler />
      <div className={styles.inner}>
        <Routes>
          {/* 공개 라우트 */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />

          {/* 로그인 필수 라우트 */}
          <Route path="/" element={
            <ProtectedRoute><HomePage /></ProtectedRoute>
          } />
          <Route path="/search" element={
            <ProtectedRoute><SearchResultPage onMenuOpen={() => setDrawerOpen(true)} /></ProtectedRoute>
          } />
          <Route path="/card/:id" element={<ProtectedRoute><CardDetailPage /></ProtectedRoute>} />
          <Route path="/search-detail" element={<ProtectedRoute><SearchDetailPage /></ProtectedRoute>} />
          <Route path="/saved" element={<ProtectedRoute><SavedListPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          <Route path="/model-info" element={<ProtectedRoute><ModelInfoPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </div>
      <DrawerMenu open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <BottomBar onMenuOpen={() => setDrawerOpen(true)} />
    </BrowserRouter>
  )
}
