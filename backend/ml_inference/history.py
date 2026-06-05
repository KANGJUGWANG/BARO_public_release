"""DB history helpers for one-way model feature building.

This module only reads historical observations. It does not load model files or
run prediction.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any

logger = logging.getLogger(__name__)


_HISTORY_SQL = """
SELECT
    s.observed_at,
    s.dpd,
    f.price_krw,
    f.airline_code,
    f.flight_number,
    CAST(f.dep_time_local AS CHAR) AS dep_time_local
FROM flight_offer_observation f
JOIN search_observation s ON f.observation_id = s.observation_id
WHERE s.route_type = 'oneway'
  AND s.origin_iata = %s
  AND s.destination_iata = %s
  AND s.departure_date = %s
  AND f.flight_number = %s
  AND f.price_krw IS NOT NULL
  AND s.crawl_status = 'success'
ORDER BY s.observed_at ASC
"""


async def fetch_history_rows(
    origin: str,
    destination: str,
    departure_date: str,
    flight_number: str,
    pool,
) -> list[dict]:
    """
    Return historical DB rows for the oneway adapter.

    The current request row is not included. On invalid input, missing pool, or
    DB errors, this function returns an empty list and does not raise.
    """

    origin = _clean_code(origin)
    destination = _clean_code(destination)
    departure_date = _clean_text(departure_date)
    flight_number = _clean_code(flight_number)

    if not origin or not destination or not departure_date or not flight_number:
        return []
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    _HISTORY_SQL,
                    (origin, destination, departure_date, flight_number),
                )
                rows = await cursor.fetchall()
    except Exception as exc:  # noqa: BLE001 - DB failures must not break API flow.
        logger.warning("history rows query failed: %s", exc.__class__.__name__)
        return []

    return [_normalize_row(row) for row in rows or []]


def _normalize_row(row: Any) -> dict:
    if isinstance(row, dict):
        observed_at = row.get("observed_at")
        dpd = row.get("dpd")
        price_krw = row.get("price_krw")
        airline_code = row.get("airline_code")
        flight_number = row.get("flight_number")
        dep_time_local = row.get("dep_time_local")
    else:
        observed_at, dpd, price_krw, airline_code, flight_number, dep_time_local = row

    return {
        "observed_at": _format_datetime(observed_at),
        "dpd": _to_int(dpd),
        "price_krw": _to_int(price_krw),
        "airline_code": _clean_code(airline_code),
        "flight_number": _clean_code(flight_number),
        "dep_time_local": _format_time(dep_time_local),
    }


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_code(value: Any) -> str | None:
    text = _clean_text(value)
    return text.upper() if text else None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d 00:00:00")
    return str(value).strip() or None


def _format_time(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    if isinstance(value, time):
        return value.strftime("%H:%M")

    text = str(value).strip()
    if not text:
        return None
    return text[:5]
