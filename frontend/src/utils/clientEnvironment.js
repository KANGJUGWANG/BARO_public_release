import { Capacitor } from '@capacitor/core'

export function getClientEnvironment() {
  if (typeof window === 'undefined') {
    return {
      isNativeApp: false,
      isAndroid: false,
      isIOS: false,
      isMobile: false,
      isDesktop: false,
      platform: 'unknown',
    }
  }

  const nav = window.navigator || {}
  const uaData = nav.userAgentData
  const ua = nav.userAgent || ''
  const platformText = uaData?.platform || nav.platform || ''
  const maxTouchPoints = nav.maxTouchPoints || 0
  const isNativeApp = Boolean(
    Capacitor.isNativePlatform?.() ||
      window.Capacitor?.isNativePlatform?.() ||
      window.location.protocol === 'capacitor:'
  )
  const isAndroid = /Android/i.test(platformText) || /Android/i.test(ua)
  const isIPadDesktopMode = /Mac/i.test(platformText) && maxTouchPoints > 1
  const isIOS =
    /iPhone|iPad|iPod/i.test(platformText) ||
    /iPhone|iPad|iPod/i.test(ua) ||
    isIPadDesktopMode
  const isMobile = isAndroid || isIOS || Boolean(uaData?.mobile)
  const isDesktop = !isMobile && !isNativeApp

  let platform = 'unknown'
  if (isNativeApp) platform = 'native'
  else if (isAndroid) platform = 'android'
  else if (isIOS) platform = 'ios'
  else if (isDesktop) platform = 'desktop'

  return {
    isNativeApp,
    isAndroid,
    isIOS,
    isMobile,
    isDesktop,
    platform,
  }
}
