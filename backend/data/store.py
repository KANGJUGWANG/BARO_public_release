from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

DATA_DIR   = Path(__file__).parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SETTINGS = {
    "notification": True,
    "default_route": None,
    "default_route_type": "oneway",
}


# ── 무결성 보장 로드/저장 ───────────────────────────────────────────────────
def _load() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_or_create(users: dict, kakao_id: str) -> dict:
    if kakao_id not in users:
        now = datetime.utcnow().isoformat()
        users[kakao_id] = {
            "kakao_id":   kakao_id,
            "created_at": now,
            "last_login": now,
            "saved":      [],
            "settings":   DEFAULT_SETTINGS.copy(),
        }
    return users[kakao_id]


# ── 유저 ───────────────────────────────────────────────────────────────────────────
def get_user(kakao_id: str) -> dict | None:
    return _load().get(kakao_id)


def upsert_user(kakao_id: str) -> dict:
    """로그인 시 자동 등록. 이미 있으면 last_login만 갱신."""
    users = _load()
    user = _get_or_create(users, kakao_id)
    user["last_login"] = datetime.utcnow().isoformat()
    _save(users)
    return user


# ── 저장 항공편 ────────────────────────────────────────────────────────────────────
def get_saved(kakao_id: str) -> list:
    user = _load().get(kakao_id)
    return user["saved"] if user else []


def add_saved(kakao_id: str, flight: dict) -> dict:
    users = _load()
    user = _get_or_create(users, kakao_id)
    if "id" not in flight:
        flight["id"] = f"{kakao_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    flight["saved_at"] = datetime.utcnow().isoformat()
    user["saved"].append(flight)
    _save(users)
    return flight


def delete_saved(kakao_id: str, flight_id: str) -> bool:
    users = _load()
    user = users.get(kakao_id)
    if not user:
        return False
    before = len(user["saved"])
    user["saved"] = [f for f in user["saved"] if f.get("id") != flight_id]
    if len(user["saved"]) == before:
        return False
    _save(users)
    return True


# ── 설정 ─────────────────────────────────────────────────────────────────────────────
def get_settings(kakao_id: str) -> dict:
    user = _load().get(kakao_id)
    if not user:
        return DEFAULT_SETTINGS.copy()
    return {**DEFAULT_SETTINGS, **user.get("settings", {})}


def update_settings(kakao_id: str, patch: dict) -> dict:
    users = _load()
    user = _get_or_create(users, kakao_id)
    user["settings"] = {**DEFAULT_SETTINGS, **user.get("settings", {}), **patch}
    _save(users)
    return user["settings"]
