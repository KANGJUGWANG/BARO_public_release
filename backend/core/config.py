from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.backend")


class Settings:
    kakao_rest_api_key: str = os.getenv("KAKAO_REST_API_KEY", "")
    kakao_redirect_uri: str = os.getenv("KAKAO_REDIRECT_URI", "")

    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    # 프론트 URL — JWT 콜백 리다이렉트 대상
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    apk_redirect_uri: str = os.getenv("APK_REDIRECT_URI", "baro://auth/callback")

    # CORS — 콤마 구분 복수 도메인
    allowed_origins: list[str] = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    ]

    db_host: str = os.getenv("DB_HOST", "")
    db_port: int = int(os.getenv("DB_PORT", "3306"))
    db_name: str = os.getenv("DB_NAME", "")
    db_user: str = os.getenv("DB_USER", "")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_writer_host: str = os.getenv("DB_WRITER_HOST", "")
    db_writer_port: int = int(os.getenv("DB_WRITER_PORT", "3306"))
    db_writer_user: str = os.getenv("DB_WRITER_USER", "")
    db_writer_password: str = os.getenv("DB_WRITER_PASSWORD", "")
    realtime_refresh_ttl_hours: int = int(os.getenv("REALTIME_REFRESH_TTL_HOURS", "8"))
    realtime_refresh_read_enabled: bool = (
        os.getenv("REALTIME_REFRESH_READ_ENABLED", "true").lower() == "true"
    )
    model_dir: str = os.getenv("MODEL_DIR", "")

    crawler_max_concurrency: int = int(os.getenv("CRAWLER_MAX_CONCURRENCY", "4"))
    flight_search_cache_ttl_sec: int = int(os.getenv("FLIGHT_SEARCH_CACHE_TTL_SEC", "300"))
    flight_search_wait_timeout_sec: int = int(os.getenv("FLIGHT_SEARCH_WAIT_TIMEOUT_SEC", "25"))

    roundtrip_refresh_enabled: bool = (
        os.getenv("ROUNDTRIP_REFRESH_ENABLED", "false").lower() == "true"
    )
    user_refresh_blocked: bool = os.getenv("USER_REFRESH_BLOCKED", "false").lower() == "true"
    roundtrip_refresh_mode: str = os.getenv("ROUNDTRIP_REFRESH_MODE", "disabled")
    roundtrip_refresh_allowed_routes: str = os.getenv(
        "ROUNDTRIP_REFRESH_ALLOWED_ROUTES",
        "ICN-NRT,NRT-ICN,ICN-HND,HND-ICN",
    )
    roundtrip_refresh_max_timeout_s: int = int(
        os.getenv("ROUNDTRIP_REFRESH_MAX_TIMEOUT_SECONDS", "180")
    )
    roundtrip_refresh_timeout_max_sec: int = roundtrip_refresh_max_timeout_s
    roundtrip_refresh_soft_budget_sec: int = int(
        os.getenv("ROUNDTRIP_REFRESH_SOFT_BUDGET_SEC", "165")
    )
    roundtrip_refresh_max_outbound_cards: int = int(
        os.getenv("ROUNDTRIP_REFRESH_MAX_OUTBOUND_CARDS", "5")
    )
    roundtrip_refresh_max_combos: int = int(
        os.getenv("ROUNDTRIP_REFRESH_MAX_COMBOS", "30")
    )
    roundtrip_refresh_card_timeout_s: float = float(
        os.getenv("ROUNDTRIP_REFRESH_CARD_TIMEOUT_SECONDS", "25")
    )
    roundtrip_refresh_body_timeout_s: float = float(
        os.getenv("ROUNDTRIP_REFRESH_BODY_TIMEOUT_SECONDS", "8")
    )

    oneway_refresh_enabled: bool = (
        os.getenv("ONEWAY_REFRESH_ENABLED", "false").lower() == "true"
    )
    oneway_refresh_mode: str = os.getenv("ONEWAY_REFRESH_MODE", "disabled")
    oneway_refresh_allowed_routes: str = os.getenv(
        "ONEWAY_REFRESH_ALLOWED_ROUTES",
        "ICN-NRT,NRT-ICN,ICN-HND,HND-ICN",
    )
    oneway_refresh_max_timeout_s: int = int(
        os.getenv("ONEWAY_REFRESH_MAX_TIMEOUT_SECONDS", "180")
    )
    oneway_refresh_timeout_max_sec: int = oneway_refresh_max_timeout_s


settings = Settings()
