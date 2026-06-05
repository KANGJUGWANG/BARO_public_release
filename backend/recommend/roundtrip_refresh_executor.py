from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

from core.config import settings

log = logging.getLogger(__name__)

STAY_NIGHTS = 7


def _effective_timeout(seconds: int) -> int:
    return min(seconds, settings.roundtrip_refresh_max_timeout_s)


def _soft_budget(seconds: int) -> int:
    return max(30, min(settings.roundtrip_refresh_soft_budget_sec, seconds - 10))


def _stats_message(stats: dict[str, Any]) -> str:
    if not stats:
        return ""
    return (
        f"combo_count={stats.get('combo_count', 0)} "
        f"processed={stats.get('processed_card_count', 0)} "
        f"failed={stats.get('failed_card_count', 0)} "
        f"card_timeout={stats.get('card_timeout_count', 0)} "
        f"body_timeout={stats.get('response_body_timeout_count', 0)} "
        f"soft_budget_exhausted={stats.get('soft_budget_exhausted', False)}"
    )


def _allowed_routes() -> set[str]:
    return {
        item.strip().upper()
        for item in settings.roundtrip_refresh_allowed_routes.split(",")
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


def _price_meta(has_seller: bool) -> dict[str, str]:
    return {
        "price_source": "roundtrip_stage2_card_price",
        "price_status": "official_price" if has_seller else "no_seller_tag",
        "parse_status": "success",
        "price_selection_reason": "same_airline_stage2_roundtrip_total",
    }


def _valid_roundtrip_combo(combo: dict) -> bool:
    return bool(
        combo.get("outbound_flight_no")
        and combo.get("inbound_flight_no")
        and _int_or_none(combo.get("price_krw")) is not None
    )


async def insert_realtime_refresh_offers(
    origin: str,
    destination: str,
    dep_date: date,
    ret_date: date,
    combos: list[dict],
    observed_at: datetime,
    job_id: str,
    writer_pool: Any,
    stay_nights: int = STAY_NIGHTS,
    ttl_hours: int = 8,
) -> int:
    if writer_pool is None:
        raise RuntimeError("writer_pool_unavailable")

    valid_combos = [combo for combo in combos if _valid_roundtrip_combo(combo)]
    if not valid_combos:
        return 0

    route_key = (
        f"roundtrip:{origin}:{destination}:"
        f"{dep_date.isoformat()}:{ret_date.isoformat()}:{stay_nights}"
    )
    expires_at = observed_at + timedelta(hours=ttl_hours)
    observed_text = observed_at.strftime("%Y-%m-%d %H:%M:%S")
    expires_text = expires_at.strftime("%Y-%m-%d %H:%M:%S")

    log.info(
        "insert_realtime_refresh_offers start: route=%s-%s dep=%s ret=%s combos=%d valid=%d",
        origin,
        destination,
        dep_date.isoformat(),
        ret_date.isoformat(),
        len(combos),
        len(valid_combos),
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
                        (%s, 'roundtrip', %s, %s, %s,
                         %s, %s, %s, %s, %s,
                         'success', %s)
                    """,
                    (
                        job_id,
                        route_key,
                        origin,
                        destination,
                        dep_date.isoformat(),
                        ret_date.isoformat(),
                        stay_nights,
                        observed_text,
                        expires_text,
                        len(valid_combos),
                    ),
                )
                refresh_search_id = cur.lastrowid
                inserted = 0
                log.info("service_refresh_search_observation inserted: refresh_search_id=%s", refresh_search_id)

                for card_index, combo in enumerate(valid_combos):
                    stage = f"insert_service_refresh_offer_{card_index}"
                    seller = combo.get("official_seller") or {}
                    meta = _price_meta(bool(seller))
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
                             %s, %s,
                             %s, %s, %s, %s,
                             %s, %s, %s,
                             %s, %s)
                        """,
                        (
                            refresh_search_id,
                            job_id,
                            route_key,
                            observed_text,
                            expires_text,
                            combo.get("airline_code"),
                            combo.get("airline_name"),
                            combo.get("outbound_flight_no"),
                            combo.get("outbound_dep_time"),
                            combo.get("outbound_arr_time"),
                            _int_or_none(combo.get("outbound_duration_min")),
                            combo.get("inbound_airline_code"),
                            combo.get("inbound_flight_no"),
                            combo.get("inbound_dep_time"),
                            combo.get("inbound_arr_time"),
                            _int_or_none(combo.get("inbound_duration_min")),
                            _int_or_none(combo.get("price_krw")),
                            seller.get("url"),
                            seller.get("name"),
                            combo.get("seller_type") or "unknown",
                            meta["price_status"],
                            meta["price_selection_reason"],
                        ),
                    )
                    inserted += 1

            stage = "commit"
            await conn.commit()
            log.info(
                "insert_realtime_refresh_offers committed: refresh_search_id=%s inserted=%d",
                refresh_search_id,
                inserted,
            )
            return inserted
        except Exception:
            log.exception("insert_realtime_refresh_offers failed at stage=%s", stage)
            await conn.rollback()
            raise
        finally:
            if previous_autocommit is not None:
                try:
                    await conn.autocommit(bool(previous_autocommit))
                except Exception:
                    pass


async def execute_roundtrip_refresh(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    timeout_seconds: int,
    pool: Any,
    writer_pool: Any = None,
    job_id: str = "",
) -> dict[str, Any]:
    mode = (settings.roundtrip_refresh_mode or "disabled").strip().lower()
    enabled = settings.roundtrip_refresh_enabled

    if not enabled or mode == "disabled":
        return {
            "status": "disabled",
            "inserted_count": 0,
            "error": "roundtrip refresh execution is disabled in this build",
        }

    if not is_route_allowed(origin, destination):
        return {
            "status": "route_not_allowed",
            "inserted_count": 0,
            "error": f"route {origin}-{destination} is not in allowlist",
        }

    dep = date.fromisoformat(depart_date)
    ret = date.fromisoformat(return_date)
    if (ret - dep).days != STAY_NIGHTS:
        return {
            "status": "failed",
            "inserted_count": 0,
            "error": "only 7-night roundtrip refresh is supported",
        }

    if mode == "dry_run":
        log.info("roundtrip refresh dry_run: %s-%s dep=%s ret=%s", origin, destination, dep, ret)
        return {"status": "dry_run", "inserted_count": 0, "error": None}

    if mode != "enabled":
        return {
            "status": "disabled",
            "inserted_count": 0,
            "error": f"unsupported roundtrip refresh mode: {mode}",
        }

    if writer_pool is None:
        return {
            "status": "failed",
            "inserted_count": 0,
            "error": "writer_unavailable",
            "failure_stage": "precheck",
        }

    effective_timeout = _effective_timeout(timeout_seconds)
    soft_budget_seconds = _soft_budget(effective_timeout)
    stage = "precheck"
    try:
        from crawler.collector import collect_roundtrip_realtime

        stage = "crawl_started"
        crawl_result = await collect_roundtrip_realtime(
            origin,
            destination,
            dep,
            ret,
            max_outbound_cards=settings.roundtrip_refresh_max_outbound_cards,
            max_combos=settings.roundtrip_refresh_max_combos,
            card_timeout_s=settings.roundtrip_refresh_card_timeout_s,
            body_timeout_s=settings.roundtrip_refresh_body_timeout_s,
            soft_budget_seconds=soft_budget_seconds,
        )
        stage = "crawl_completed"
        if isinstance(crawl_result, dict):
            combos = crawl_result.get("combos") or []
            stats = crawl_result.get("stats") or {}
        else:
            combos = crawl_result or []
            stats = {}
        log.info("collect_roundtrip_realtime done: combo_count=%d", len(combos) if combos else 0)
        if combos:
            log.info("combo sample keys: %s, total=%d", sorted(combos[0].keys()), len(combos))

        if not combos:
            return {
                "status": "no_result",
                "inserted_count": 0,
                "error": None,
                "failure_stage": "no_combos",
                "stats": stats,
                "message": _stats_message(stats),
            }

        stage = "insert_started"
        observed_at = datetime.now().replace(minute=0, second=0, microsecond=0)
        inserted_count = await insert_realtime_refresh_offers(
            origin,
            destination,
            dep,
            ret,
            combos,
            observed_at,
            job_id=job_id,
            writer_pool=writer_pool,
            stay_nights=STAY_NIGHTS,
            ttl_hours=settings.realtime_refresh_ttl_hours,
        )
        stage = "insert_done"
        partial = bool(
            stats.get("failed_card_count")
            or stats.get("skipped_card_count")
            or stats.get("card_timeout_count")
            or stats.get("target_combo_reached")
        )
        if inserted_count <= 0:
            status = "no_result"
        elif stats.get("soft_budget_exhausted"):
            status = "timeout_with_partial"
        elif partial:
            status = "partial_success"
        else:
            status = "success"
        return {
            "status": status,
            "inserted_count": inserted_count,
            "error": None,
            "failure_stage": None,
            "combo_count": len(combos),
            "stats": stats,
            "message": _stats_message(stats),
        }
    except asyncio.TimeoutError:
        log.exception("execute_roundtrip_refresh timeout at stage=%s", stage)
        return {
            "status": "timeout",
            "inserted_count": 0,
            "error": f"timeout after {effective_timeout}s",
            "failure_stage": "crawl_timeout" if stage == "crawl_started" else stage,
        }
    except Exception as exc:  # noqa: BLE001 - job status should be fail-soft.
        detail = str(exc)[:500]
        log.exception("execute_roundtrip_refresh failed at stage=%s", stage)
        return {
            "status": "failed",
            "inserted_count": 0,
            "error": exc.__class__.__name__,
            "failure_stage": stage,
            "exception_detail": detail,
        }
