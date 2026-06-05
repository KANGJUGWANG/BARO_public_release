from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header
from typing import Any

from backend.data.store import (
    get_user, upsert_user,
    get_saved, add_saved, delete_saved,
    get_settings, update_settings,
)
from backend.core.jwt import decode_access_token
from jose import JWTError

router = APIRouter(tags=["users"])


def _get_kakao_id(authorization: str | None) -> str:
    """Authorization: Bearer <JWT> 헤더에서 카카오 ID 추출."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 토큰 없음")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
        return payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")


# ── 유저 ─────────────────────────────────────────────────────────────────────────────
@router.get("/me")
async def get_me(authorization: str | None = Header(default=None)):
    kakao_id = _get_kakao_id(authorization)
    user = get_user(kakao_id)
    if not user:
        raise HTTPException(status_code=404, detail="유저 없음")
    return user


@router.post("/me")
async def register_me(authorization: str | None = Header(default=None)):
    """JWT 소지 시 자동 등록. 이미 있으면 last_login 갱신."""
    kakao_id = _get_kakao_id(authorization)
    user = upsert_user(kakao_id)
    return user


# ── 저장 항공편 ────────────────────────────────────────────────────────────────────
@router.get("/me/saved")
async def list_saved(authorization: str | None = Header(default=None)):
    kakao_id = _get_kakao_id(authorization)
    return {"saved": get_saved(kakao_id)}


@router.post("/me/saved")
async def save_flight(
    flight: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    kakao_id = _get_kakao_id(authorization)
    saved = add_saved(kakao_id, flight)
    return {"ok": True, "saved": saved}


@router.delete("/me/saved/{flight_id}")
async def remove_saved(
    flight_id: str,
    authorization: str | None = Header(default=None),
):
    kakao_id = _get_kakao_id(authorization)
    ok = delete_saved(kakao_id, flight_id)
    if not ok:
        raise HTTPException(status_code=404, detail="저장된 항공편 없음")
    return {"ok": True}


# ── 설정 ─────────────────────────────────────────────────────────────────────────────
@router.get("/me/settings")
async def get_my_settings(authorization: str | None = Header(default=None)):
    kakao_id = _get_kakao_id(authorization)
    return get_settings(kakao_id)


@router.put("/me/settings")
async def update_my_settings(
    patch: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    kakao_id = _get_kakao_id(authorization)
    updated = update_settings(kakao_id, patch)
    return {"ok": True, "settings": updated}
