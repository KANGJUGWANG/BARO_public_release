const KAKAO_JS_KEY = import.meta.env.VITE_KAKAO_JS_KEY
const REDIRECT_URI = `${window.location.origin}/auth/callback`

export function initKakao() {
  if (window.Kakao && !window.Kakao.isInitialized()) {
    window.Kakao.init(KAKAO_JS_KEY)
  }
}

// 팝업 대신 리다이렉트 방식
export function kakaoLogin() {
  if (!window.Kakao) {
    console.error('Kakao SDK not loaded')
    return
  }
  window.Kakao.Auth.authorize({
    redirectUri: REDIRECT_URI,
  })
}

// 콜백에서 코드로 사용자 정보 가져오기
export async function fetchKakaoUser(accessToken) {
  const res = await fetch('https://kapi.kakao.com/v2/user/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  const data = await res.json()
  return {
    id: data.id,
    nickname: data.kakao_account?.profile?.nickname || '사용자',
    profileImage: data.kakao_account?.profile?.profile_image_url || null,
  }
}

export function kakaoLogout(onSuccess) {
  if (window.Kakao?.Auth?.getAccessToken()) {
    window.Kakao.Auth.logout(() => onSuccess?.())
  } else {
    onSuccess?.()
  }
}
