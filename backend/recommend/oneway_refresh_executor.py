from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

from core.config import settings
from crawler.collector import CrawlError

log = logging.getLogger(__name__)

_CRAWL_NO_RESULT_REASONS = frozenset(
    [
        "no flight data",
        "no response body",
        "no cards",
    ]
)
_CRAWL_NO_RESULT_PATTERNS = (
    "no flight data",
    "no response body",
    "no usable flight data",
    "empty flight data",
    "no offers",
    "no cards",
)


def build_oneway_route_key(origin: str, destination: str, depart_date: str) -> str:
    return f"oneway:{origin.upper()}:{destination.upper()}:{depart_date.strip()}"


def _effective_timeout(seconds: int) -> int:
    return min(seconds, settings.oneway_refresh_max_timeout_s)


def _allowed_routes() -> set[str]:
    return {
        item.strip().upper()
        for item in settings.oneway_refresh_allowed_routes.split(",")
        if item.strip()
    }


def is_route_allowed(origin: str, destination: str) -> bool:
    return f"{origin.upper()}-{destination.upper()}" in _allowed_routes()


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits) if digits else None
    return None


def _valid_oneway_card(card: dict[str, Any]) -> bool:
    dep = card.get("dep") or {}
    return bool(dep.get("flight_no") and _int_or_none(card.get("price_krw")) is not None)


async def _has_fresh_realtime(
    origin: str,
    destination: str,
    depart_date: str,
    pool: Any,
) -> bool:
    if pool is None:
        return False

    route_key = build_oneway_route_key(origin, destination, depart_date)
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT refresh_search_id
                    FROM service_refresh_search_observation
                    WHERE route_key = %s
                      AND route_type = 'oneway'
                      AND refresh_status = 'success'
                      AND expires_at > NOW()
                    ORDER BY observed_at DESC, refresh_search_id DESC
                    LIMIT 1
                    """,
                    (route_key,),
                )
                row = await cur.fetchone()
                return bool(row and row[0])
    except Exception as exc:  # noqa: BLE001 - refresh can fall back to crawling.
        log.warning("oneway fresh realtime check failed: %s", exc.__class__.__name__)
        return False


async def insert_oneway_realtime_refresh_offers(
    origin: str,
    destination: str,
    dep_date: date,
    cards: list[dict[str, Any]],
    observed_at: datetime,
    job_id: str,
    writer_pool: Any,
    ttl_hours: int = 8,
) -> int:
    if writer_pool is None:
        raise RuntimeError("writer_pool_unavailable")

    valid_cards = [card for card in cards if _valid_oneway_card(card)]
    if not valid_cards:
        return 0

    route_key = build_oneway_route_key(origin, destination, dep_date.isoformat())
    expires_at = observed_at + timedelta(hours=ttl_hours)
    observed_text = observed_at.strftime("%Y-%m-%d %H:%M:%S")
    expires_text = expires_at.strftime("%Y-%m-%d %H:%M:%S")

    log.info(
        "insert_oneway_realtime_refresh_offers start: route=%s-%s dep=%s cards=%d valid=%d",
        origin,
        destination,
        dep_date.isoformat(),
        len(cards),
        len(valid_cards),
    )

    async with writer_pool.acquire() as conn:
        stage = "connection_ping"
        previous_autocommit = None
        try:
            previous_autocommit = getattr(conn, "get_autocommit", lambda: None)()
        except Exception:
            previous_autocommit = None

        try:
            async with conn.cursor() as ping_cur:
                await ping_cur.execute("SELECT 1")

            stage = "transaction_start"
            await conn.autocommit(False)
            async with conn.cursor() as cur:
                stage = "insert_service_refresh_search_observation"
                await cur.execute(
                    """
                    INSERT INTO service_refresh_search_observation
                        (job_id, route_type, route_key, origin_iata, destination_iata,
                         departure_date, return_date, stay_nights, observed_at, expires_at,
                         refresh_status, offer_count)
                    VALUES
                        (%s, 'oneway', %s, %s, %s,
                         %s, NULL, NULL, %s, %s,
                         'success', %s)
                    """,
                    (
                        job_id,
                        route_key,
                        origin,
                        destination,
                        dep_date.isoformat(),
                        observed_text,
                        expires_text,
                        len(valid_cards),
                    ),
                )
                refresh_search_id = cur.lastrowid
                inserted = 0

                for index, card in enumerate(valid_cards):
                    stage = f"insert_service_refresh_offer_{index}"
                    dep = card.get("dep") or {}
                    seller = card.get("official_seller") or {}
                    has_seller = bool(seller)
                    await cur.execute(
                        """
                        INSERT INTO service_refresh_flight_offer_observation
                            (refresh_search_id, job_id, route_key, observed_at, expires_at,
                             airline_code, airline_name, flight_number,
                             dep_time_local, arr_time_local, duration_min,
                             ret_airline_code, ret_flight_number,
                             ret_dep_time_local, ret_arr_time_local, ret_duration_min,
                             price_krw, seller_domain, seller_name, seller_type,
                             price_status, price_selection_reason)
                        VALUES
                            (%s, %s, %s, %s, %s,
                             %s, %s, %s,
                             %s, %s, %s,
                             NULL, NULL,
                             NULL, NULL, NULL,
                             %s, %s, %s, %s,
                             %s, %s)
                        """,
                        (
                            refresh_search_id,
                            job_id,
                            route_key,
                            observed_text,
                            expires_text,
                            card.get("airline_code"),
                            card.get("airline_name"),
                            dep.get("flight_no"),
                            dep.get("dep_time"),
                            dep.get("arr_time"),
                            _int_or_none(dep.get("duration_min")),
                            _int_or_none(card.get("price_krw")),
                            seller.get("url"),
                            seller.get("name"),
                            card.get("seller_type") or ("airline_official" if has_seller else "unknown"),
                            "official_price" if has_seller else "no_seller_tag",
                            "oneway_realtime_offer",
                        ),
                    )
                    inserted += 1

            stage = "commit"
            await conn.commit()
            log.info(
                "insert_oneway_realtime_refresh_offers committed: refresh_search_id=%s inserted=%d",
                refresh_search_id,
                inserted,
            )
            return inserted
        except Exception:
            log.exception("insert_oneway_realtime_refresh_offers failed at stage=%s", stage)
            await conn.rollback()
            raise
        finally:
            if previous_autocommit is not None:
                try:
                    await conn.autocommit(bool(previous_autocommit))
                except Exception:
                    pass


async def execute_oneway_refresh(
    origin: str,
    destination: str,
    depart_date: str,
    timeout_seconds: int,
    pool: Any,
    writer_pool: Any = None,
    job_id: str = "",
    force_refresh: bool = False,
) -> dict[str, Any]:
    mode = (settings.oneway_refresh_mode or "disabled").strip().lower()
    enabled = settings.oneway_refresh_enabled

    if not enabled or mode == "disabled":
        return {
            "status": "disabled",
            "inserted_count": 0,
            "error": "oneway refresh execution is disabled in this build",
        }

    if not is_route_allowed(origin, destination):
        return {
            "status": "route_not_allowed",
            "inserted_count": 0,
            "error": f"route {origin}-{destination} is not in allowlist",
        }

    if not force_refresh and await _has_fresh_realtime(origin, destination, depart_date, pool):
        return {
            "status": "skipped_fresh_realtime",
            "inserted_count": 0,
            "error": None,
            "message": "fresh realtime result already exists",
        }

    dep = date.fromisoformat(depart_date)

    if mode == "dry_run":
        log.info("oneway refresh dry_run: %s-%s dep=%s", origin, destination, dep)
        return {"status": "dry_run", "inserted_count": 0, "error": None}

    if mode != "enabled":
        return {
            "status": "disabled",
            "inserted_count": 0,
            "error": f"unsupported oneway refresh mode: {mode}",
        }

    if writer_pool is None:
        return {
            "status": "failed",
            "inserted_count": 0,
            "error": "writer_unavailable",
            "failure_stage": "precheck",
        }

    effective_timeout = _effective_timeout(timeout_seconds)
    stage = "precheck"
    try:
        from crawler.collector import collect_oneway_realtime

        stage = "crawl_started"
        cards = await asyncio.wait_for(
            collect_oneway_realtime(origin, destination, dep),
            timeout=effective_timeout,
        )
        stage = "crawl_completed"
        log.info("collect_oneway_realtime done: card_count=%d", len(cards) if cards else 0)

        if not cards:
            return {
                "status": "no_result",
                "inserted_count": 0,
                "error": None,
                "failure_stage": "no_cards",
            }

        stage = "insert_started"
        observed_at = datetime.now().replace(minute=0, second=0, microsecond=0)
        inserted_count = await insert_oneway_realtime_refresh_offers(
            origin,
            destination,
            dep,
            cards,
            observed_at,
            job_id=job_id,
            writer_pool=writer_pool,
            ttl_hours=settings.realtime_refresh_ttl_hours,
        )
        stage = "insert_done"
        return {
            "status": "success" if inserted_count > 0 else "no_result",
            "inserted_count": inserted_count,
            "error": None,
            "failure_stage": None,
            "offer_count": len(cards),
        }
    except CrawlError as exc:
        reason_text = (getattr(exc, "reason", None) or str(exc) or "").strip()
        reason_key = reason_text.lower()
        if reason_key in _CRAWL_NO_RESULT_REASONS or any(
            pattern in reason_key for pattern in _CRAWL_NO_RESULT_PATTERNS
        ):
            log.info("oneway refresh no_result at stage=%s: reason=%s", stage, reason_text)
            return {
                "status": "no_result",
                "inserted_count": 0,
                "error": reason_text,
                "failure_stage": "crawl_no_result",
            }

        log.warning("oneway refresh crawl failed at stage=%s: reason=%s", stage, reason_text)
        return {
            "status": "failed",
            "inserted_count": 0,
            "error": reason_text or exc.__class__.__name__,
            "failure_stage": "crawl_failed",
            "exception_detail": reason_text[:500],
        }
    except asyncio.TimeoutError:
        log.exception("execute_oneway_refresh timeout at stage=%s", stage)
        return {
            "status": "timeout",
            "inserted_count": 0,
            "error": f"timeout after {effective_timeout}s",
            "failure_stage": "crawl_timeout" if stage == "crawl_started" else stage,
        }
    except Exception as exc:  # noqa: BLE001 - job status should be fail-soft.
        detail = str(exc)[:500]
        log.exception("execute_oneway_refresh failed at stage=%s", stage)
        return {
            "status": "failed",
            "inserted_count": 0,
            "error": exc.__class__.__name__,
            "failure_stage": stage,
            "exception_detail": detail,
        }
