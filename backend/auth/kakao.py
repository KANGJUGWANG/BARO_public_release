from __future__ import annotations

import httpx
from urllib.parse import urlencode

from backend.core.config import settings

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_URL  = "https://kapi.kakao.com/v2/user/me"
KAKAO_AUTH_URL  = "https://kauth.kakao.com/oauth/authorize"


def get_kakao_auth_url(state: str | None = None) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.kakao_rest_api_key,
        "redirect_uri": settings.kakao_redirect_uri,
    }
    if state:
        params["state"] = state
    return f"{KAKAO_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            KAKAO_TOKEN_URL,
            data={
                "grant_type":   "authorization_code",
                "client_id":    settings.kakao_rest_api_key,
                "redirect_uri": settings.kakao_redirect_uri,
                "code":         code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        # 실패 시 카카오 에러 본문 포함해서 예외 발생
        if resp.status_code != 200:
            raise Exception(
                f"HTTP {resp.status_code} — 카카오 응답: {resp.text}"
            )
        return resp.json()


async def get_kakao_user(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            KAKAO_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            raise Exception(
                f"HTTP {resp.status_code} — 카카오 응답: {resp.text}"
            )
        return resp.json()
