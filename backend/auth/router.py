from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode

from backend.auth.kakao import (
    get_kakao_auth_url,
    exchange_code_for_token,
    get_kakao_user,
)
from backend.core.jwt import create_access_token
from backend.core.config import settings

router = APIRouter(tags=["auth"])


@router.get("/kakao/login")
async def kakao_login(client: str | None = None):
    state = "apk" if client == "apk" else "web"
    url = get_kakao_auth_url(state=state)
    return RedirectResponse(url)


@router.get("/kakao/callback")
async def kakao_callback(code: str, state: str | None = None):
    try:
        token_data = await exchange_code_for_token(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"토큰 교환 실패: {e}")

    kakao_access_token = token_data.get("access_token")
    if not kakao_access_token:
        raise HTTPException(status_code=400, detail="카카오 액세스 토큰 없음")

    try:
        user_info = await get_kakao_user(kakao_access_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"유저 정보 조회 실패: {e}")

    kakao_id = str(user_info["id"])
    jwt_token = create_access_token({"sub": kakao_id})

    # FRONTEND_URL 사용 — allowed_origins[0] 아님
    if state == "apk":
        return RedirectResponse(
            f"{settings.apk_redirect_uri}?{urlencode({'token': jwt_token})}"
        )

    return RedirectResponse(
        f"{settings.frontend_url}/auth/callback?{urlencode({'token': jwt_token})}"
    )


@router.get("/me")
async def me(token: str):
    from backend.core.jwt import decode_access_token
    from jose import JWTError
    try:
        payload = decode_access_token(token)
        return {"ok": True, "user": payload}
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
