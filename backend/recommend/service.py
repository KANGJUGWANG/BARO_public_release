from __future__ import annotations

import asyncio
import json
import logging
import os
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from core.db import get_pool
from flights.schema import SearchRequest
from flights.service import search_flights
from ml_inference.history import fetch_history_rows
from ml_inference.model_runtime import (
    load_oneway_artifacts,
    load_oneway_runtime,
    load_roundtrip_artifacts,
    load_roundtrip_runtime,
    predict_oneway_from_feature,
    predict_roundtrip_from_feature,
)
from ml_inference.oneway_adapter import build_oneway_features
from ml_inference.roundtrip_feature_builder import (
    build_roundtrip_features,
    fetch_roundtrip_history_rows,
)
from recommend.job_store import cancel_job, create_job, get_job
from recommend.schema import (
    AnalyzeJobRequest,
    AnalyzeJobResponse,
    HistoryRequest,
    HistoryResponse,
    HistorySummary,
    JobPredictionItemSchema,
    JobStatusResponse,
    ModelInfoResponse,
    OnewayCandidateOffer,
    OnewayCandidatesRequest,
    OnewayCandidatesResponse,
    PredictOneRequest,
    PredictionResult,
    PricePoint,
    RecommendedFlightOffer,
    RecommendSearchRequest,
    RecommendSearchResponse,
    RoundtripCandidateOffer,
    RoundtripCandidatesRequest,
    RoundtripCandidatesResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_PREDICT_OFFERS = 3
MAX_PREDICT_OFFERS_LIMIT = 5
PER_OFFER_TIMEOUT_SECONDS = 90
HISTORY_ROW_LIMIT = 120
_ROUNDTRIP_RUNTIME_REF: dict[str, Any] = {"runtime": None}
_RT_CANDIDATES_MAX_LIMIT = 50
_OW_CANDIDATES_MAX_LIMIT = 50
_RT_REALTIME_TABLE_MISSING_CODES = {1146}


async def get_model_info() -> ModelInfoResponse:
    try:
        service_obs_count = await _get_service_observation_count()
        return _build_model_info(service_obs_count)
    except Exception as exc:  # noqa: BLE001 - endpoint should fail safely.
        logger.warning("get_model_info failed: %s", exc.__class__.__name__)
        return ModelInfoResponse(status="error", reason=exc.__class__.__name__)


async def get_roundtrip_candidates(
    request: RoundtripCandidatesRequest,
) -> RoundtripCandidatesResponse:
    """
    Return roundtrip offer candidates from realtime refresh storage first,
    falling back to stored DB observations.

    If realtime refresh tables are missing or disabled, this keeps the existing
    DB observation fallback path intact.
    """
    origin = (request.origin or "").strip().upper()
    destination = (request.destination or "").strip().upper()
    depart_date = (request.depart_date or "").strip()
    return_date = (request.return_date or "").strip() or None
    stay_nights = request.stay_nights
    limit = max(1, min(int(request.limit or 20), _RT_CANDIDATES_MAX_LIMIT))
    source_mode = (getattr(request, "source_mode", None) or "auto").strip().lower()
    if source_mode not in ("auto", "db", "realtime"):
        source_mode = "auto"

    base = {
        "origin": origin,
        "destination": destination,
        "depart_date": depart_date,
        "return_date": return_date,
        "stay_nights": stay_nights,
    }

    pool = get_pool()
    if pool is None:
        return RoundtripCandidatesResponse(
            status="unavailable_db_pool",
            reason="db pool is unavailable",
            **base,
        )

    where_parts = [
        "s.route_type = 'roundtrip'",
        "s.origin_iata = %s",
        "s.destination_iata = %s",
        "s.departure_date = %s",
        "s.crawl_status = 'success'",
    ]
    params: list[Any] = [origin, destination, depart_date]

    if return_date:
        where_parts.append("s.return_date = %s")
        params.append(return_date)
    if stay_nights is not None:
        where_parts.append("s.stay_nights = %s")
        params.append(stay_nights)

    where_clause = " AND ".join(where_parts)
    route_key = _roundtrip_route_key(origin, destination, depart_date, return_date, stay_nights)

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                db_latest_observed_at = None
                db_observed_at = None
                if source_mode != "realtime":
                    db_latest_observed_at = await _fetch_latest_observed_at(
                        cur,
                        where_clause,
                        params,
                    )
                    db_observed_at = await _fetch_latest_valid_roundtrip_observed_at(
                        cur,
                        where_clause,
                        params,
                    )
                db_fallback_reason = (
                    "latest_observation_had_no_valid_offers_used_previous_valid_observation"
                    if db_latest_observed_at
                    and db_observed_at
                    and db_observed_at != db_latest_observed_at
                    else None
                )

                rt_latest = None if source_mode == "db" else await _fetch_realtime_latest(cur, route_key)
                use_realtime = bool(
                    source_mode == "realtime"
                    or (
                        source_mode != "db"
                        and rt_latest
                        and (
                        db_observed_at is None
                        or rt_latest["observed_at"] >= db_observed_at
                        )
                    )
                )

                if source_mode == "realtime" and not rt_latest:
                    return RoundtripCandidatesResponse(
                        status="unavailable_no_realtime_refresh",
                        reason="no valid realtime refresh data",
                        **base,
                    )

                if use_realtime and rt_latest:
                    offers = await _fetch_realtime_offers(
                        cur,
                        int(rt_latest["refresh_search_id"]),
                        limit,
                    )
                    if offers:
                        return RoundtripCandidatesResponse(
                            status="ok",
                            observed_at=str(rt_latest["observed_at"]),
                            source="realtime_refresh",
                            source_label="실시간 검색 결과",
                            is_realtime=True,
                            fallback_used=False,
                            expires_at=str(rt_latest["expires_at"]),
                            offers=offers,
                            **base,
                        )
                    if source_mode == "realtime":
                        return RoundtripCandidatesResponse(
                            status="unavailable_no_realtime_refresh",
                            reason="realtime offers empty",
                            observed_at=str(rt_latest["observed_at"]),
                            source="realtime_refresh",
                            source_label="실시간 검색 결과",
                            is_realtime=True,
                            fallback_used=False,
                            expires_at=str(rt_latest["expires_at"]),
                            **base,
                        )

                if db_latest_observed_at is None:
                    return RoundtripCandidatesResponse(
                        status="unavailable_no_observation",
                        reason="no matching roundtrip observation found",
                        source="db_observation",
                        source_label="최신 DB 관측 결과",
                        is_realtime=False,
                        fallback_used=True,
                        **base,
                    )

                if db_observed_at is None:
                    return RoundtripCandidatesResponse(
                        status="unavailable_no_offers",
                        reason="no valid offers for any matching observation",
                        observed_at=str(db_latest_observed_at),
                        source="db_observation",
                        source_label="理쒖떊 DB 愿痢?寃곌낵",
                        is_realtime=False,
                        fallback_used=True,
                        **base,
                    )

                offers = await _fetch_db_roundtrip_offers(
                    cur,
                    where_clause,
                    params,
                    db_observed_at,
                    limit,
                )
    except Exception as exc:  # noqa: BLE001 - API should return a safe status.
        logger.warning("roundtrip_candidates db error: %s", exc.__class__.__name__)
        return RoundtripCandidatesResponse(
            status="unavailable_db_query_error",
            reason=exc.__class__.__name__,
            **base,
        )

    observed_at = str(db_observed_at)
    if not offers:
        return RoundtripCandidatesResponse(
            status="unavailable_no_offers",
            reason="no valid offers for latest observation",
            observed_at=observed_at,
            source="db_observation",
            source_label="최신 DB 관측 결과",
            is_realtime=False,
            fallback_used=True,
            **base,
        )

    return RoundtripCandidatesResponse(
        status="ok",
        observed_at=observed_at,
        source="db_observation",
        source_label="최신 DB 관측 결과",
        is_realtime=False,
        fallback_used=True,
        reason=db_fallback_reason,
        offers=offers,
        **base,
    )


async def get_oneway_candidates(
    request: OnewayCandidatesRequest,
) -> OnewayCandidatesResponse:
    """
    Return oneway candidates from realtime refresh storage first,
    falling back to scheduled DB observations.

    Optional offer columns are selected only when the physical table has them;
    missing columns are returned as None to keep the API response stable.
    """
    origin = (request.origin or "").strip().upper()
    destination = (request.destination or "").strip().upper()
    depart_date = (request.depart_date or "").strip()
    limit = max(1, min(int(request.limit or 20), _OW_CANDIDATES_MAX_LIMIT))
    source_mode = (getattr(request, "source_mode", None) or "auto").strip().lower()
    if source_mode not in ("auto", "db", "realtime"):
        source_mode = "auto"
    route_key = _build_oneway_route_key(origin, destination, depart_date)

    base = {
        "origin": origin,
        "destination": destination,
        "depart_date": depart_date,
    }

    pool = get_pool()
    if pool is None:
        return OnewayCandidatesResponse(
            status="unavailable_db_pool",
            reason="db pool is unavailable",
            **base,
        )

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                db_columns = await _get_table_columns(cur, "flight_offer_observation")
                rt_columns = await _get_table_columns(
                    cur,
                    "service_refresh_flight_offer_observation",
                )

                oneway_where_parts = [
                    "s.route_type = 'oneway'",
                    "s.origin_iata = %s",
                    "s.destination_iata = %s",
                    "s.departure_date = %s",
                    "s.crawl_status = 'success'",
                ]
                oneway_params: list[Any] = [origin, destination, depart_date]
                oneway_where_clause = " AND ".join(oneway_where_parts)
                db_latest_observed_at = None
                db_observed_at = None
                if source_mode != "realtime":
                    db_latest_observed_at = await _fetch_latest_observed_at(
                        cur,
                        oneway_where_clause,
                        oneway_params,
                    )
                    db_observed_at = await _fetch_latest_valid_oneway_observed_at(
                        cur,
                        oneway_where_clause,
                        oneway_params,
                        db_columns,
                    )
                db_fallback_reason = (
                    "latest_observation_had_no_valid_offers_used_previous_valid_observation"
                    if db_latest_observed_at
                    and db_observed_at
                    and db_observed_at != db_latest_observed_at
                    else None
                )

                rt_latest = None if source_mode == "db" else await _fetch_realtime_latest(cur, route_key)
                use_realtime = bool(
                    source_mode == "realtime"
                    or (
                        source_mode != "db"
                        and rt_latest
                        and (
                        db_observed_at is None
                        or rt_latest["observed_at"] >= db_observed_at
                        )
                    )
                )

                offers: list[OnewayCandidateOffer] = []
                if source_mode == "realtime" and not rt_latest:
                    return OnewayCandidatesResponse(
                        status="unavailable_no_realtime_refresh",
                        reason="no valid realtime refresh data",
                        **base,
                    )

                if use_realtime and rt_latest:
                    offers = await _fetch_realtime_oneway_offers(
                        cur,
                        int(rt_latest["refresh_search_id"]),
                        limit,
                        rt_columns,
                    )
                    if offers:
                        return OnewayCandidatesResponse(
                            status="ok",
                            observed_at=str(rt_latest["observed_at"]),
                            source="realtime_refresh",
                            source_label="실시간 검색 결과",
                            is_realtime=True,
                            fallback_used=False,
                            expires_at=str(rt_latest["expires_at"]),
                            offers=offers,
                            **base,
                        )
                    if source_mode == "realtime":
                        return OnewayCandidatesResponse(
                            status="unavailable_no_realtime_refresh",
                            reason="realtime offers empty",
                            observed_at=str(rt_latest["observed_at"]),
                            source="realtime_refresh",
                            source_label="실시간 검색 결과",
                            is_realtime=True,
                            fallback_used=False,
                            expires_at=str(rt_latest["expires_at"]),
                            **base,
                        )

                if db_latest_observed_at is None:
                    return OnewayCandidatesResponse(
                        status="unavailable_no_observation",
                        reason="no matching oneway observation found",
                        source="db_observation",
                        source_label="최신 DB 관측 결과",
                        is_realtime=False,
                        fallback_used=True,
                        **base,
                    )

                if db_observed_at is None:
                    return OnewayCandidatesResponse(
                        status="unavailable_no_offers",
                        reason="no valid offers for any matching observation",
                        observed_at=str(db_latest_observed_at),
                        source="db_observation",
                        source_label="理쒖떊 DB 愿痢?寃곌낵",
                        is_realtime=False,
                        fallback_used=True,
                        **base,
                    )

                offers = await _fetch_db_oneway_offers(
                    cur,
                    origin,
                    destination,
                    depart_date,
                    db_observed_at,
                    limit,
                    db_columns,
                )
    except Exception as exc:  # noqa: BLE001 - API should return a safe status.
        logger.warning("oneway_candidates db error: %s", exc.__class__.__name__)
        return OnewayCandidatesResponse(
            status="unavailable_db_query_error",
            reason=exc.__class__.__name__,
            **base,
        )

    observed_at = str(db_observed_at)
    if not offers:
        return OnewayCandidatesResponse(
            status="unavailable_no_offers",
            reason="no valid offers for latest observation",
            observed_at=observed_at,
            source="db_observation",
            source_label="최신 DB 관측 결과",
            is_realtime=False,
            fallback_used=True,
            **base,
        )

    return OnewayCandidatesResponse(
        status="ok",
        observed_at=observed_at,
        source="db_observation",
        source_label="최신 DB 관측 결과",
        is_realtime=False,
        fallback_used=True,
        reason=db_fallback_reason,
        offers=offers,
        **base,
    )


def _build_oneway_route_key(origin: str, destination: str, depart_date: str) -> str:
    return f"oneway:{origin.upper()}:{destination.upper()}:{depart_date.strip()}"


async def _fetch_latest_observed_at(
    cur: Any,
    where_clause: str,
    params: list[Any],
) -> Any | None:
    await cur.execute(
        f"SELECT MAX(s.observed_at) FROM search_observation s WHERE {where_clause}",
        tuple(params),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def _fetch_latest_valid_roundtrip_observed_at(
    cur: Any,
    where_clause: str,
    params: list[Any],
) -> Any | None:
    await cur.execute(
        f"""
        SELECT s.observed_at
        FROM search_observation s
        JOIN flight_offer_observation f ON f.observation_id = s.observation_id
        WHERE {where_clause}
          AND f.price_krw IS NOT NULL
          AND f.flight_number IS NOT NULL
          AND f.ret_flight_number IS NOT NULL
          AND f.price_status = 'official_price'
        GROUP BY s.observation_id, s.observed_at
        ORDER BY s.observed_at DESC, s.observation_id DESC
        LIMIT 1
        """,
        tuple(params),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def _fetch_latest_valid_oneway_observed_at(
    cur: Any,
    where_clause: str,
    params: list[Any],
    columns: set[str],
) -> Any | None:
    where_parts = [
        where_clause,
        "f.price_krw IS NOT NULL" if "price_krw" in columns else "1 = 1",
        "f.flight_number IS NOT NULL" if "flight_number" in columns else "1 = 1",
    ]
    if "price_status" in columns:
        where_parts.append("f.price_status = 'official_price'")

    await cur.execute(
        f"""
        SELECT s.observed_at
        FROM search_observation s
        JOIN flight_offer_observation f ON f.observation_id = s.observation_id
        WHERE {" AND ".join(where_parts)}
        GROUP BY s.observation_id, s.observed_at
        ORDER BY s.observed_at DESC, s.observation_id DESC
        LIMIT 1
        """,
        tuple(params),
    )
    row = await cur.fetchone()
    return row[0] if row else None


def _roundtrip_route_key(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None,
    stay_nights: int | None,
) -> str:
    return (
        f"roundtrip:{origin}:{destination}:"
        f"{depart_date}:{return_date or ''}:{stay_nights or 7}"
    )


def _is_missing_realtime_table_error(exc: Exception) -> bool:
    args = getattr(exc, "args", ())
    return bool(args and args[0] in _RT_REALTIME_TABLE_MISSING_CODES)


async def _get_table_columns(cur: Any, table_name: str) -> set[str]:
    try:
        await cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            """,
            (table_name,),
        )
        return {row[0] for row in await cur.fetchall()}
    except Exception as exc:  # noqa: BLE001 - callers can safely use NULL columns.
        if _is_missing_realtime_table_error(exc):
            return set()
        logger.warning("table column check failed for %s: %s", table_name, exc.__class__.__name__)
        return set()


def _select_optional(
    columns: set[str],
    column: str,
    *,
    alias: str = "f",
    output: str | None = None,
    cast_char: bool = False,
) -> str:
    out = output or column
    if column not in columns:
        return f"NULL AS {out}"
    expr = f"{alias}.{column}"
    if cast_char:
        expr = f"CAST({expr} AS CHAR)"
    return f"{expr} AS {out}"


async def _fetch_realtime_latest(cur: Any, route_key: str) -> dict[str, Any] | None:
    from core.config import settings

    if not settings.realtime_refresh_read_enabled:
        return None

    try:
        await cur.execute(
            """
            SELECT refresh_search_id, observed_at, expires_at
            FROM service_refresh_search_observation
            WHERE route_key = %s
              AND refresh_status = 'success'
              AND expires_at > NOW()
            ORDER BY observed_at DESC
            LIMIT 1
            """,
            (route_key,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "refresh_search_id": row[0],
            "observed_at": row[1],
            "expires_at": row[2],
        }
    except Exception as exc:  # noqa: BLE001 - fallback to DB observations.
        if _is_missing_realtime_table_error(exc):
            logger.info("realtime refresh tables not found; using db_observation fallback")
        else:
            logger.warning("realtime latest query failed: %s", exc.__class__.__name__)
        return None


async def _fetch_realtime_offers(
    cur: Any,
    refresh_search_id: int,
    limit: int,
) -> list[RoundtripCandidateOffer]:
    await cur.execute(
        """
        SELECT
            refresh_offer_id,
            airline_code,
            airline_name,
            flight_number,
            CAST(dep_time_local AS CHAR) AS dep_time_local,
            CAST(arr_time_local AS CHAR) AS arr_time_local,
            duration_min,
            ret_airline_code,
            ret_flight_number,
            CAST(ret_dep_time_local AS CHAR) AS ret_dep_time_local,
            CAST(ret_arr_time_local AS CHAR) AS ret_arr_time_local,
            ret_duration_min,
            price_krw,
            seller_domain,
            price_status
        FROM service_refresh_flight_offer_observation
        WHERE refresh_search_id = %s
          AND price_krw IS NOT NULL
          AND flight_number IS NOT NULL
          AND ret_flight_number IS NOT NULL
          AND price_status = 'official_price'
        ORDER BY price_krw ASC, refresh_offer_id ASC
        LIMIT %s
        """,
        (refresh_search_id, limit),
    )
    cols = [
        "refresh_offer_id",
        "airline_code",
        "airline_name",
        "flight_number",
        "dep_time_local",
        "arr_time_local",
        "duration_min",
        "ret_airline_code",
        "ret_flight_number",
        "ret_dep_time_local",
        "ret_arr_time_local",
        "ret_duration_min",
        "price_krw",
        "seller_domain",
        "price_status",
    ]
    return [
        RoundtripCandidateOffer(
            **{
                **dict(zip(cols, row)),
                "source_offer_id": row[0],
                "parse_status": "success",
            }
        )
        for row in await cur.fetchall()
    ]


async def _fetch_realtime_oneway_offers(
    cur: Any,
    refresh_search_id: int,
    limit: int,
    columns: set[str],
) -> list[OnewayCandidateOffer]:
    select_parts = [
        _select_optional(columns, "refresh_offer_id", alias="f"),
        _select_optional(columns, "airline_code", alias="f"),
        _select_optional(columns, "airline_name", alias="f"),
        _select_optional(columns, "flight_number", alias="f"),
        _select_optional(columns, "dep_time_local", alias="f", cast_char=True),
        _select_optional(columns, "arr_time_local", alias="f", cast_char=True),
        _select_optional(columns, "duration_min", alias="f"),
        _select_optional(columns, "stops", alias="f"),
        _select_optional(columns, "price_krw", alias="f"),
        _select_optional(columns, "seller_domain", alias="f"),
        _select_optional(columns, "seller_name", alias="f"),
        _select_optional(columns, "seller_type", alias="f"),
        _select_optional(columns, "price_source", alias="f"),
        _select_optional(columns, "price_status", alias="f"),
        _select_optional(columns, "parse_status", alias="f"),
        _select_optional(columns, "price_selection_reason", alias="f"),
    ]
    where_parts = [
        "f.refresh_search_id = %s",
        "f.price_krw IS NOT NULL" if "price_krw" in columns else "1 = 1",
        "f.flight_number IS NOT NULL" if "flight_number" in columns else "1 = 1",
    ]
    if "price_status" in columns:
        where_parts.append("f.price_status = 'official_price'")
    order_parts = []
    if "price_krw" in columns:
        order_parts.append("f.price_krw ASC")
    if "refresh_offer_id" in columns:
        order_parts.append("f.refresh_offer_id ASC")
    order_clause = ", ".join(order_parts) or "1"

    await cur.execute(
        f"""
        SELECT
            {", ".join(select_parts)}
        FROM service_refresh_flight_offer_observation f
        WHERE {" AND ".join(where_parts)}
        ORDER BY {order_clause}
        LIMIT %s
        """,
        (refresh_search_id, limit),
    )
    cols = [
        "refresh_offer_id",
        "airline_code",
        "airline_name",
        "flight_number",
        "dep_time_local",
        "arr_time_local",
        "duration_min",
        "stops",
        "price_krw",
        "seller_domain",
        "seller_name",
        "seller_type",
        "price_source",
        "price_status",
        "parse_status",
        "price_selection_reason",
    ]
    return [_map_oneway_offer(row, cols, realtime=True) for row in await cur.fetchall()]


async def _fetch_db_roundtrip_offers(
    cur: Any,
    where_clause: str,
    params: list[Any],
    observed_at: Any,
    limit: int,
) -> list[RoundtripCandidateOffer]:
    await cur.execute(
        f"""
        SELECT
            f.offer_observation_id,
            f.flight_number,
            f.ret_flight_number,
            f.airline_code,
            f.airline_name,
            f.ret_airline_code,
            CAST(f.dep_time_local AS CHAR) AS dep_time_local,
            CAST(f.arr_time_local AS CHAR) AS arr_time_local,
            CAST(f.ret_dep_time_local AS CHAR) AS ret_dep_time_local,
            CAST(f.ret_arr_time_local AS CHAR) AS ret_arr_time_local,
            f.duration_min,
            f.ret_duration_min,
            f.stops,
            f.price_krw,
            f.seller_domain,
            f.price_status,
            f.parse_status
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id = s.observation_id
        WHERE {where_clause}
          AND s.observed_at = %s
          AND f.price_krw IS NOT NULL
          AND f.flight_number IS NOT NULL
          AND f.ret_flight_number IS NOT NULL
          AND f.price_status = 'official_price'
        ORDER BY f.price_krw ASC, f.offer_observation_id ASC
        LIMIT %s
        """,
        tuple(params + [observed_at, limit]),
    )
    cols = [
        "offer_observation_id",
        "flight_number",
        "ret_flight_number",
        "airline_code",
        "airline_name",
        "ret_airline_code",
        "dep_time_local",
        "arr_time_local",
        "ret_dep_time_local",
        "ret_arr_time_local",
        "duration_min",
        "ret_duration_min",
        "stops",
        "price_krw",
        "seller_domain",
        "price_status",
        "parse_status",
    ]
    return [
        RoundtripCandidateOffer(
            **{
                **dict(zip(cols, row)),
                "source_offer_id": row[0],
            }
        )
        for row in await cur.fetchall()
    ]


async def _fetch_db_oneway_offers(
    cur: Any,
    origin: str,
    destination: str,
    depart_date: str,
    observed_at: Any,
    limit: int,
    columns: set[str],
) -> list[OnewayCandidateOffer]:
    select_parts = [
        _select_optional(columns, "offer_observation_id", alias="f"),
        _select_optional(columns, "airline_code", alias="f"),
        _select_optional(columns, "airline_name", alias="f"),
        _select_optional(columns, "flight_number", alias="f"),
        _select_optional(columns, "dep_time_local", alias="f", cast_char=True),
        _select_optional(columns, "arr_time_local", alias="f", cast_char=True),
        _select_optional(columns, "duration_min", alias="f"),
        _select_optional(columns, "stops", alias="f"),
        _select_optional(columns, "price_krw", alias="f"),
        _select_optional(columns, "seller_domain", alias="f"),
        _select_optional(columns, "seller_name", alias="f"),
        _select_optional(columns, "seller_type", alias="f"),
        _select_optional(columns, "price_source", alias="f"),
        _select_optional(columns, "price_status", alias="f"),
        _select_optional(columns, "parse_status", alias="f"),
        _select_optional(columns, "price_selection_reason", alias="f"),
    ]
    where_parts = [
        "s.route_type = 'oneway'",
        "s.origin_iata = %s",
        "s.destination_iata = %s",
        "s.departure_date = %s",
        "s.observed_at = %s",
        "s.crawl_status = 'success'",
        "f.price_krw IS NOT NULL" if "price_krw" in columns else "1 = 1",
        "f.flight_number IS NOT NULL" if "flight_number" in columns else "1 = 1",
    ]
    if "price_status" in columns:
        where_parts.append("f.price_status = 'official_price'")
    order_parts = []
    if "price_krw" in columns:
        order_parts.append("f.price_krw ASC")
    if "offer_observation_id" in columns:
        order_parts.append("f.offer_observation_id ASC")
    order_clause = ", ".join(order_parts) or "s.observed_at DESC"

    await cur.execute(
        f"""
        SELECT
            {", ".join(select_parts)}
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id = s.observation_id
        WHERE {" AND ".join(where_parts)}
        ORDER BY {order_clause}
        LIMIT %s
        """,
        (origin, destination, depart_date, observed_at, limit),
    )
    cols = [
        "offer_observation_id",
        "airline_code",
        "airline_name",
        "flight_number",
        "dep_time_local",
        "arr_time_local",
        "duration_min",
        "stops",
        "price_krw",
        "seller_domain",
        "seller_name",
        "seller_type",
        "price_source",
        "price_status",
        "parse_status",
        "price_selection_reason",
    ]
    return [_map_oneway_offer(row, cols, realtime=False) for row in await cur.fetchall()]


def _map_oneway_offer(
    row: tuple,
    cols: list[str],
    *,
    realtime: bool,
) -> OnewayCandidateOffer:
    data = dict(zip(cols, row))
    dep = data.get("dep_time_local")
    arr = data.get("arr_time_local")
    source_id = data.get("refresh_offer_id") if realtime else data.get("offer_observation_id")
    return OnewayCandidateOffer(
        offer_observation_id=None if realtime else data.get("offer_observation_id"),
        refresh_offer_id=data.get("refresh_offer_id") if realtime else None,
        source_offer_id=source_id,
        airline_code=data.get("airline_code"),
        airline_name=data.get("airline_name"),
        flight_number=data.get("flight_number"),
        dep_time=dep,
        dep_time_local=dep,
        arr_time=arr,
        arr_time_local=arr,
        duration_min=data.get("duration_min"),
        stops=data.get("stops"),
        price_krw=data.get("price_krw"),
        seller_domain=data.get("seller_domain"),
        seller_name=data.get("seller_name"),
        seller_type=data.get("seller_type"),
        price_source=data.get("price_source"),
        price_status=data.get("price_status"),
        parse_status=data.get("parse_status"),
        price_selection_reason=data.get("price_selection_reason"),
    )


def _get_model_dir() -> Path:
    from core.config import settings

    configured = getattr(settings, "model_dir", None) or os.getenv("MODEL_DIR", "")
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[1] / "models" / "finaltest_clean_v1"


def _find_artifact(model_dir: Path, fname: str) -> Path | None:
    for path in (model_dir / "model_artifacts" / fname, model_dir / fname):
        if path.exists():
            return path
    return None


def _runtime_artifact(model_dir: Path, fname: str) -> Path | None:
    path = model_dir / fname
    return path if path.exists() else None


def _read_json_safe(path: Path | None) -> dict | list | None:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - artifact parse errors are reported as missing info.
        return None


def _pkl_info(model_dir: Path, fname: str) -> dict[str, Any]:
    path = model_dir / fname
    exists = path.exists()
    size_mb = None
    if exists:
        try:
            size_mb = round(path.stat().st_size / (1024 * 1024), 1)
        except Exception:  # noqa: BLE001 - stat failure should not break API.
            pass
    return {"exists": exists, "size_mb": size_mb}


def _file_modified_at(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001 - stat failure should not break API.
        return None


def _parse_feature_columns(feat_cols: dict | list | None) -> dict[str, Any]:
    return _parse_feature_columns_for_trip(feat_cols, "oneway")


def _parse_feature_columns_for_trip(feat_cols: dict | list | None, trip_type: str) -> dict[str, Any]:
    if feat_cols is None:
        return {
            "stage1_names": [],
            "stage1_count": 0,
            "stage2_names": [],
            "stage2_count": 0,
            "total_unique_count": 0,
        }

    if isinstance(feat_cols, list):
        return {
            "stage1_names": feat_cols,
            "stage1_count": len(feat_cols),
            "stage2_names": [],
            "stage2_count": 0,
            "total_unique_count": len(feat_cols),
        }

    if isinstance(feat_cols, dict):
        trip_columns = feat_cols.get(trip_type)
        if isinstance(trip_columns, dict):
            s1 = trip_columns.get("stage1") or []
            s2 = trip_columns.get("stage2") or []
        else:
            s1 = feat_cols.get("stage1") or []
            s2 = feat_cols.get("stage2") or []

        s1 = s1 if isinstance(s1, list) else []
        s2 = s2 if isinstance(s2, list) else []
        all_unique = list(dict.fromkeys(s1 + s2))
        return {
            "stage1_names": s1,
            "stage1_count": len(s1),
            "stage2_names": s2,
            "stage2_count": len(s2),
            "total_unique_count": len(all_unique),
        }

    return {
        "stage1_names": [],
        "stage1_count": 0,
        "stage2_names": [],
        "stage2_count": 0,
        "total_unique_count": 0,
    }


def _parse_threshold(threshold_data: dict | None) -> float | None:
    if not threshold_data or not isinstance(threshold_data, dict):
        return None
    for key in (
        "selected_threshold",
        "oneway",
        "threshold",
        "oneway_threshold",
        "wait_threshold",
    ):
        value = threshold_data.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


async def _get_service_observation_count() -> int | None:
    try:
        pool = get_pool()
        if pool is None:
            return None
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT COUNT(*) FROM search_observation")
                row = await cursor.fetchone()
                return int(row[0]) if row else None
    except Exception:  # noqa: BLE001 - this is best-effort status data.
        return None


def _build_model_info(service_obs_count: int | None) -> ModelInfoResponse:
    model_dir = _get_model_dir()
    metadata = _read_json_safe(_runtime_artifact(model_dir, "final_model_metadata.json")) or {}
    threshold_data = _read_json_safe(_runtime_artifact(model_dir, "oneway_threshold.json"))
    feature_columns = _read_json_safe(_runtime_artifact(model_dir, "feature_columns.json"))

    artifact_names = [
        "feature_columns.json",
        "oneway_threshold.json",
        "roundtrip_threshold.json",
        "final_model_metadata.json",
        "enc_mappings.json",
    ]
    artifacts_status = {
        fname: _runtime_artifact(model_dir, fname) is not None
        for fname in artifact_names
    }
    oneway_artifact_names = [
        "feature_columns.json",
        "oneway_threshold.json",
        "final_model_metadata.json",
        "enc_mappings.json",
    ]

    stage1_info = _pkl_info(model_dir, "oneway_stage1_random_forest.pkl")
    stage2_info = _pkl_info(model_dir, "oneway_stage2_xgboost.pkl")
    model_version = (
        metadata.get("model_version")
        or metadata.get("version")
        or metadata.get("run_id")
        or model_dir.name
        or "unknown"
    )
    threshold_value = _parse_threshold(
        threshold_data if isinstance(threshold_data, dict) else None
    )
    feat_info = _parse_feature_columns_for_trip(feature_columns, "oneway")
    roundtrip_feat_info = _parse_feature_columns_for_trip(feature_columns, "roundtrip")
    training_date = metadata.get("training_date") or metadata.get("created_at")
    training_row_count = metadata.get("training_row_count") or metadata.get("total_rows")
    oneway_active = (
        all(artifacts_status.get(name) for name in oneway_artifact_names)
        and bool(stage1_info.get("exists"))
        and bool(stage2_info.get("exists"))
    )
    roundtrip_artifacts = load_roundtrip_artifacts()
    roundtrip_threshold = roundtrip_artifacts.get("threshold")
    roundtrip_version = _roundtrip_model_version(roundtrip_artifacts)
    roundtrip_active = roundtrip_artifacts.get("status") == "ok"
    roundtrip_stage1_info = _pkl_info(model_dir, "roundtrip_stage1_xgboost.pkl")
    roundtrip_stage2_info = _pkl_info(model_dir, "roundtrip_stage2_xgboost.pkl")
    oneway_threshold_path = _runtime_artifact(model_dir, "oneway_threshold.json")
    roundtrip_threshold_path = _runtime_artifact(model_dir, "roundtrip_threshold.json")
    models = {
        "oneway": _model_info_item(
            display_name="편도 추천 모델",
            model_version=model_version,
            active=oneway_active,
            threshold=threshold_value,
            artifact_status="ok" if oneway_active else "unavailable_artifact_missing",
            artifact_modified_at=_file_modified_at(oneway_threshold_path),
            stage1={"file_name": "oneway_stage1_random_forest.pkl", **stage1_info},
            stage2={"file_name": "oneway_stage2_xgboost.pkl", **stage2_info},
        ),
        "roundtrip": _model_info_item(
            display_name="왕복 추천 모델",
            model_version=roundtrip_version,
            active=roundtrip_active,
            threshold=roundtrip_threshold if isinstance(roundtrip_threshold, (int, float)) else None,
            artifact_status=str(roundtrip_artifacts.get("status") or "unknown"),
            artifact_modified_at=_file_modified_at(roundtrip_threshold_path),
            stage1={"file_name": "roundtrip_stage1_xgboost.pkl", **roundtrip_stage1_info},
            stage2={"file_name": "roundtrip_stage2_xgboost.pkl", **roundtrip_stage2_info},
        ),
    }
    architecture_by_trip = {
        "oneway": {
            "stage1": {
                "name": "Stage 1",
                "role": "predict future saving potential",
                "model_type": _model_type(metadata, "stage1"),
                "file_name": "oneway_stage1_random_forest.pkl",
                **stage1_info,
            },
            "stage2": {
                "name": "Stage 2",
                "role": "BUY/WAIT decision",
                "model_type": _model_type(metadata, "stage2"),
                "file_name": "oneway_stage2_xgboost.pkl",
                **stage2_info,
            },
        },
        "roundtrip": {
            "stage1": {
                "name": "Stage 1",
                "role": "predict future saving potential",
                "model_type": "xgboost",
                "file_name": "roundtrip_stage1_xgboost.pkl",
                **roundtrip_stage1_info,
            },
            "stage2": {
                "name": "Stage 2",
                "role": "BUY/WAIT decision",
                "model_type": "xgboost",
                "file_name": "roundtrip_stage2_xgboost.pkl",
                **roundtrip_stage2_info,
            },
        },
    }
    features_by_trip = {
        "oneway": feat_info,
        "roundtrip": roundtrip_feat_info,
    }
    decision_policy_by_trip = {
        "oneway": {
            "wait_threshold": threshold_value,
            "threshold_source": "root/oneway_threshold.json",
            "rule": "WAIT if wait_probability > threshold else BUY",
        },
        "roundtrip": {
            "wait_threshold": roundtrip_threshold if isinstance(roundtrip_threshold, (int, float)) else None,
            "threshold_source": "root/roundtrip_threshold.json",
            "rule": "WAIT if wait_probability > threshold else BUY",
        },
    }
    threshold_sources = {
        "oneway": {
            "active_file": str(oneway_threshold_path) if oneway_threshold_path else None,
            "active_source": "root/oneway_threshold.json",
            "value": threshold_value,
        },
        "roundtrip": {
            "active_file": str(roundtrip_threshold_path) if roundtrip_threshold_path else None,
            "active_source": "root/roundtrip_threshold.json",
            "value": roundtrip_threshold if isinstance(roundtrip_threshold, (int, float)) else None,
            "note": "runtime load_roundtrip_artifacts reads root roundtrip_threshold.json",
        },
    }

    return ModelInfoResponse(
        status="ok",
        model_version=model_version,
        models=models,
        architecture_by_trip=architecture_by_trip,
        features_by_trip=features_by_trip,
        decision_policy_by_trip=decision_policy_by_trip,
        threshold_sources=threshold_sources,
        scope={
            "trip_type": "oneway",
            "supported_trip_types": ["oneway", "roundtrip"],
            "routes": ["ICN-NRT", "ICN-HND", "NRT-ICN", "HND-ICN"],
            "roundtrip_status": "운영 중" if roundtrip_active else "사용 불가",
        },
        architecture={
            "stage1": {
                "name": "Stage 1",
                "role": "향후 가격 절감 가능성 예측",
                "model_type": _model_type(metadata, "stage1"),
                "file_name": "oneway_stage1_random_forest.pkl",
                **stage1_info,
            },
            "stage2": {
                "name": "Stage 2",
                "role": "BUY/WAIT 판단",
                "model_type": _model_type(metadata, "stage2"),
                "file_name": "oneway_stage2_xgboost.pkl",
                **stage2_info,
            },
        },
        features=feat_info,
        decision_policy={
            "wait_threshold": threshold_value,
            "rule": "WAIT 확률이 threshold를 초과하면 WAIT, 이하이면 BUY",
        },
        artifacts=artifacts_status,
        dates={
            "training_date": training_date,
            "artifact_modified_at": _file_modified_at(oneway_threshold_path),
        },
        data={
            "training_row_count": training_row_count,
            "training_row_count_note": (
                "metadata에 기록된 경우만 표시" if training_row_count else None
            ),
            "service_observation_count": service_obs_count,
            "service_observation_count_note": (
                "서비스 DB 누적 관측 수이며 모델 학습 데이터량과 다를 수 있습니다."
            ),
        },
    )


def _model_info_item(
    display_name: str,
    model_version: str | None,
    active: bool,
    threshold: float | None,
    artifact_status: str,
    artifact_modified_at: str | None,
    stage1: dict[str, Any],
    stage2: dict[str, Any],
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "status": "active" if active else "inactive",
        "display_name": display_name,
        "model_version": model_version,
        "artifact_status": artifact_status,
        "artifact_modified_at": artifact_modified_at,
        "stage1": stage1,
        "stage2": stage2,
    }
    if threshold is not None:
        item["threshold"] = float(threshold)
    return item


def _model_type(metadata: dict[str, Any], stage_key: str) -> str | None:
    stage = metadata.get(stage_key)
    if isinstance(stage, dict):
        return stage.get("model_type") or stage.get("type")
    models = metadata.get("models")
    if isinstance(models, dict):
        model_stage = models.get(stage_key)
        if isinstance(model_stage, dict):
            return model_stage.get("model_type") or model_stage.get("type")
    return None


async def submit_analyze_job(request: AnalyzeJobRequest) -> AnalyzeJobResponse:
    trip_type = request.trip_type.lower().strip()
    if trip_type not in {"oneway", "roundtrip"}:
        return AnalyzeJobResponse(
            job_id="",
            status="unsupported_trip_type",
            total_count=0,
            accepted_count=0,
            rejected_count=len(request.offers),
            reason="only oneway and roundtrip supported",
        )

    offers_raw = [
        offer.model_dump() if hasattr(offer, "model_dump") else dict(offer)
        for offer in request.offers
    ]

    try:
        job = create_job(
            origin=request.origin,
            destination=request.destination,
            depart_date=request.depart_date,
            trip_type=trip_type,
            offers=offers_raw,
        )
    except RuntimeError as exc:
        return AnalyzeJobResponse(
            job_id="",
            status="rejected_max_jobs",
            total_count=len(request.offers),
            accepted_count=0,
            rejected_count=len(request.offers),
            reason=str(exc),
        )

    return AnalyzeJobResponse(
        job_id=job.job_id,
        status=job.status,
        total_count=job.total_count,
        accepted_count=job.total_count,
    )


def get_job_status(job_id: str) -> JobStatusResponse:
    job = get_job(job_id)
    if not job:
        return JobStatusResponse(
            job_id=job_id,
            status="not_found",
            total_count=0,
            completed_count=0,
            failed_count=0,
            created_at="",
            updated_at="",
        )

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        total_count=job.total_count,
        completed_count=job.completed_count,
        failed_count=job.failed_count,
        predictions=[
            JobPredictionItemSchema(
                offer_observation_id=item.offer_observation_id,
                refresh_offer_id=item.refresh_offer_id,
                source_offer_id=item.source_offer_id,
                flight_number=item.flight_number,
                dep_time=item.dep_time,
                dep_time_local=item.dep_time_local,
                ret_flight_number=item.ret_flight_number,
                ret_dep_time_local=item.ret_dep_time_local,
                return_date=item.return_date,
                stay_nights=item.stay_nights,
                price_krw=item.price_krw,
                prediction=item.prediction,
            )
            for item in job.predictions
        ],
        errors=job.errors,
        created_at=job.created_at.isoformat(timespec="seconds"),
        updated_at=job.updated_at.isoformat(timespec="seconds"),
    )


def cancel_job_by_id(job_id: str) -> dict[str, Any]:
    return {"job_id": job_id, "cancelled": cancel_job(job_id)}


async def get_flight_history(request: HistoryRequest) -> HistoryResponse:
    trip_type = request.trip_type.lower().strip()
    flight_number = _clean_text(request.offer.flight_number)
    ret_flight_number = _clean_text(request.offer.ret_flight_number)
    return_date = _clean_text(request.offer.return_date)
    stay_nights = request.offer.stay_nights
    base = {
        "trip_type": trip_type,
        "flight_number": flight_number,
        "ret_flight_number": ret_flight_number,
        "origin": request.origin,
        "destination": request.destination,
        "depart_date": request.depart_date,
        "return_date": return_date,
        "stay_nights": stay_nights,
    }

    if trip_type not in {"oneway", "roundtrip"}:
        return HistoryResponse(
            status="unsupported_trip_type",
            reason="only oneway and roundtrip history is supported",
            **base,
        )

    if not flight_number:
        return HistoryResponse(
            status="unavailable_missing_flight_number",
            reason="flight_number is required",
            **base,
        )

    if trip_type == "roundtrip":
        if not ret_flight_number:
            return HistoryResponse(
                status="unavailable_invalid_request",
                reason="ret_flight_number is required for roundtrip history",
                **base,
            )
        if not return_date:
            return HistoryResponse(
                status="unavailable_invalid_request",
                reason="return_date is required for roundtrip history",
                **base,
            )
        if stay_nights is None:
            return HistoryResponse(
                status="unavailable_invalid_request",
                reason="stay_nights is required for roundtrip history",
                **base,
            )

    pool = get_pool()
    if pool is None:
        return HistoryResponse(
            status="unavailable_db_pool",
            reason="db pool is unavailable",
            **base,
        )

    try:
        if trip_type == "roundtrip":
            rows = await fetch_roundtrip_history_rows(
                origin=request.origin,
                destination=request.destination,
                departure_date=request.depart_date,
                return_date=return_date,
                stay_nights=stay_nights,
                flight_number=flight_number,
                ret_flight_number=ret_flight_number,
                pool=pool,
            )
        else:
            rows = await fetch_history_rows(
                origin=request.origin,
                destination=request.destination,
                departure_date=request.depart_date,
                flight_number=flight_number,
                pool=pool,
            )
    except Exception:  # noqa: BLE001 - keep endpoint fail-soft.
        logger.exception("flight history query failed")
        return HistoryResponse(status="error", reason="history query failed", **base)

    points = _history_points(rows)
    if not points:
        return HistoryResponse(
            status="unavailable_no_history",
            reason="no price history rows",
            **base,
        )

    points = points[-HISTORY_ROW_LIMIT:]
    prices = [point.price_krw for point in points]
    latest_price = prices[-1]
    current_price = (
        request.offer.price_krw
        if request.offer.price_krw is not None
        else latest_price
    )
    summary = HistorySummary(
        count=len(prices),
        min_price=min(prices),
        max_price=max(prices),
        mean_price=int(statistics.mean(prices)),
        latest_price=latest_price,
        current_price=current_price,
    )

    return HistoryResponse(
        status="ok",
        history=points,
        summary=summary,
        reason=None,
        **base,
    )


async def predict_one_offer(request: PredictOneRequest) -> PredictionResult:
    started = time.perf_counter()
    logger.info(
        "predict-one request started: origin=%s destination=%s depart_date=%s trip_type=%s flight_number=%s",
        request.origin,
        request.destination,
        request.depart_date,
        request.trip_type,
        request.offer.flight_number,
    )

    trip_type = request.trip_type.lower().strip()

    if trip_type == "roundtrip":
        pool = get_pool()
        prediction = await _predict_roundtrip_offer(
            request=request,
            pool=pool,
            runtime_ref=_ROUNDTRIP_RUNTIME_REF,
        )
        logger.info(
            "predict-one roundtrip finished: status=%s elapsed=%.3f",
            prediction.prediction_status,
            time.perf_counter() - started,
        )
        return prediction

    if trip_type != "oneway":
        return _prediction(
            "unsupported_trip_type",
            reason="only oneway and roundtrip prediction is supported",
            model_version="finaltest_clean_v1",
        )

    search_request = SearchRequest(
        origin=request.origin,
        destination=request.destination,
        depart_date=request.depart_date,
        trip_type=request.trip_type,
    )
    offer = _normalize_predict_one_offer(request.offer)
    artifacts = load_oneway_artifacts()
    pool = get_pool()
    runtime_ref: dict[str, Any] = {"runtime": None}

    prediction = await _predict_offer(
        offer=offer,
        request=search_request,
        pool=pool,
        artifacts=artifacts,
        runtime_ref=runtime_ref,
        index=0,
    )
    logger.info(
        "predict-one finished: status=%s elapsed=%.3f",
        prediction.prediction_status,
        time.perf_counter() - started,
    )
    if prediction.model_version is None:
        prediction.model_version = "finaltest_clean_v1"
    return prediction


async def recommend_search(request: RecommendSearchRequest) -> RecommendSearchResponse:
    total_started = time.perf_counter()
    logger.info(
        "recommend request started: origin=%s destination=%s depart_date=%s trip_type=%s",
        request.origin,
        request.destination,
        request.depart_date,
        request.trip_type,
    )

    search_request = SearchRequest(
        origin=request.origin,
        destination=request.destination,
        depart_date=request.depart_date,
        trip_type=request.trip_type,
    )

    logger.info("search_flights started")
    search_started = time.perf_counter()
    search_response = await search_flights(search_request)
    search_elapsed = time.perf_counter() - search_started
    logger.info("search_flights finished")
    logger.info("search elapsed seconds: %.3f", search_elapsed)
    logger.info("search offer count: %d", len(search_response.offers))

    if not search_response.offers:
        logger.info(
            "recommend total elapsed seconds: %.3f",
            time.perf_counter() - total_started,
        )
        return RecommendSearchResponse(
            origin=search_response.origin,
            destination=search_response.destination,
            depart_date=search_response.depart_date,
            offers=[],
            crawled_at=search_response.crawled_at,
            error=search_response.error,
        )

    max_predict_offers = _clamp_max_predict_offers(request.max_predict_offers)
    target_indices = _select_prediction_targets(search_response.offers, max_predict_offers)
    logger.info("prediction target offer count: %d", len(target_indices))

    artifacts = load_oneway_artifacts()
    pool = get_pool()
    runtime_ref: dict[str, Any] = {"runtime": None}
    predictions: dict[int, PredictionResult] = {}
    status_counter: Counter[str] = Counter()
    response_error = search_response.error

    for index, offer in enumerate(search_response.offers):
        if index not in target_indices:
            prediction = _prediction("skipped_not_in_top_k")
            predictions[index] = prediction
            status_counter[prediction.prediction_status] += 1
            continue

        offer_started = time.perf_counter()
        offer_data = _as_dict(offer)
        logger.info(
            "per-offer prediction started: index=%d flight_number=%s airline_code=%s price_krw=%s",
            index,
            offer_data.get("flight_number"),
            offer_data.get("airline_code"),
            offer_data.get("price_krw"),
        )

        try:
            prediction = await asyncio.wait_for(
                _predict_offer(
                    offer=offer,
                    request=search_request,
                    pool=pool,
                    artifacts=artifacts,
                    runtime_ref=runtime_ref,
                    index=index,
                ),
                timeout=PER_OFFER_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            prediction = _prediction(
                "unavailable_recommend_timeout",
                reason="recommend timeout after search",
            )
            response_error = "recommend timeout"
            logger.warning("per-offer prediction timeout: index=%d", index)

        elapsed = time.perf_counter() - offer_started
        logger.info("prediction_status per offer: index=%d status=%s", index, prediction.prediction_status)
        logger.info("prediction elapsed seconds per offer: index=%d elapsed=%.3f", index, elapsed)

        predictions[index] = prediction
        status_counter[prediction.prediction_status] += 1

        if prediction.prediction_status == "unavailable_recommend_timeout":
            _mark_remaining_after_timeout(
                start_index=index + 1,
                offers=search_response.offers,
                target_indices=target_indices,
                predictions=predictions,
                status_counter=status_counter,
            )
            break

    recommended_offers = [
        _to_recommended_offer(
            offer,
            predictions.get(index) or _prediction("unavailable_recommend_timeout", reason="recommend timeout after search"),
        )
        for index, offer in enumerate(search_response.offers)
    ]

    logger.info("prediction_status distribution: %s", dict(status_counter))
    logger.info("recommend total elapsed seconds: %.3f", time.perf_counter() - total_started)

    return RecommendSearchResponse(
        origin=search_response.origin,
        destination=search_response.destination,
        depart_date=search_response.depart_date,
        offers=recommended_offers,
        crawled_at=search_response.crawled_at,
        error=response_error,
    )


async def _predict_offer(
    offer: Any,
    request: SearchRequest,
    pool: Any,
    artifacts: dict[str, Any],
    runtime_ref: dict[str, Any],
    index: int,
) -> PredictionResult:
    if request.trip_type.lower().strip() != "oneway":
        return _prediction("error", reason="unsupported trip_type")

    offer_dict = _as_dict(offer)
    flight_number = _clean_text(offer_dict.get("flight_number"))
    if not flight_number:
        return _prediction("unavailable_missing_flight_number")

    if offer_dict.get("price_krw") is None:
        return _prediction("unavailable_invalid_price")

    if pool is None:
        return _prediction("unavailable_db_pool")

    if artifacts.get("status") != "ok":
        return _prediction(
            "unavailable_feature_build_failed",
            reason=artifacts.get("reason") or artifacts.get("status"),
        )

    history_rows = await fetch_history_rows(
        origin=request.origin,
        destination=request.destination,
        departure_date=request.depart_date,
        flight_number=flight_number,
        pool=pool,
    )
    logger.info("history row count per offer: index=%d count=%d", index, len(history_rows))
    if len(history_rows) < 6:
        return _prediction(
            "unavailable_insufficient_history",
            reason="insufficient history_rows for price_chg_6",
            history_row_count=len(history_rows),
            feature_status="prediction_unavailable",
        )

    built = build_oneway_features(
        offer=_offer_for_adapter(offer_dict, request),
        request=request,
        history_rows=history_rows,
        now=datetime.now(),
        artifacts=artifacts,
    )
    feature_status = built.get("feature_status")
    logger.info("feature_status per offer: index=%d status=%s", index, feature_status)
    if feature_status != "ok":
        return _prediction(
            _feature_status_to_prediction_status(built.get("unavailable_reason")),
            reason=built.get("unavailable_reason"),
            history_row_count=len(history_rows),
            feature_status=feature_status,
        )

    runtime = await _ensure_runtime_loaded(runtime_ref)
    result = await asyncio.to_thread(predict_oneway_from_feature, built, runtime)
    return _prediction(
        prediction_status=result.get("prediction_status", "error"),
        decision=result.get("decision"),
        pred_saving=result.get("pred_saving"),
        wait_probability=result.get("wait_probability"),
        threshold=result.get("threshold"),
        confidence=result.get("confidence"),
        model_version=result.get("model_version"),
        reason=result.get("reason"),
        history_row_count=len(history_rows),
        feature_status=feature_status,
    )


async def _predict_roundtrip_offer(
    request: PredictOneRequest,
    pool: Any,
    runtime_ref: dict[str, Any],
) -> PredictionResult:
    offer_dict = _normalize_predict_one_offer(request.offer)
    flight_number = _clean_text(offer_dict.get("flight_number"))
    ret_flight_number = _clean_text(offer_dict.get("ret_flight_number"))

    if not flight_number:
        return _prediction(
            "unavailable_feature_build_failed",
            reason="flight_number is required for roundtrip prediction",
        )

    if not ret_flight_number:
        return _prediction(
            "unavailable_feature_build_failed",
            reason="ret_flight_number is required for roundtrip prediction",
        )

    if offer_dict.get("price_krw") is None:
        return _prediction("unavailable_invalid_price")

    if pool is None:
        return _prediction("unavailable_db_pool")

    artifacts = load_roundtrip_artifacts()
    model_version = _roundtrip_model_version(artifacts)
    if artifacts.get("status") != "ok":
        return _prediction(
            "unavailable_feature_build_failed",
            reason=artifacts.get("reason") or artifacts.get("status"),
            model_version=model_version,
        )

    history_rows = await fetch_roundtrip_history_rows(
        origin=request.origin,
        destination=request.destination,
        departure_date=request.depart_date,
        return_date=offer_dict.get("return_date"),
        stay_nights=offer_dict.get("stay_nights"),
        flight_number=flight_number,
        ret_flight_number=ret_flight_number,
        pool=pool,
    )
    logger.info("roundtrip history row count: %d", len(history_rows))
    if len(history_rows) < 7:
        return _prediction(
            "unavailable_insufficient_history",
            reason="insufficient history_rows for price_chg_6",
            model_version=model_version,
            history_row_count=len(history_rows),
            feature_status="prediction_unavailable",
        )

    built = build_roundtrip_features(
        offer=_roundtrip_offer_for_adapter(offer_dict, request),
        request=_roundtrip_request_for_adapter(request, offer_dict),
        history_rows=history_rows,
        now=datetime.now(),
        artifacts=artifacts,
    )
    feature_status = built.get("feature_status")
    logger.info("roundtrip feature_status: %s", feature_status)
    if feature_status != "ok":
        return _prediction(
            _roundtrip_feature_status_to_prediction_status(
                built.get("unavailable_reason"),
                built.get("details"),
            ),
            reason=built.get("unavailable_reason"),
            model_version=model_version,
            history_row_count=len(history_rows),
            feature_status=feature_status,
        )

    runtime = await _ensure_roundtrip_runtime_loaded(runtime_ref)
    feature_row = built.get("feature_row") or {}
    result = await asyncio.to_thread(predict_roundtrip_from_feature, feature_row, runtime)
    return _prediction(
        prediction_status=result.get("prediction_status", "error"),
        decision=result.get("decision"),
        pred_saving=result.get("pred_saving"),
        wait_probability=result.get("wait_probability"),
        threshold=result.get("threshold"),
        confidence=result.get("confidence"),
        model_version=result.get("model_version") or model_version,
        reason=result.get("reason"),
        history_row_count=len(history_rows),
        feature_status=feature_status,
    )


async def _ensure_runtime_loaded(runtime_ref: dict[str, Any]) -> dict[str, Any]:
    if runtime_ref.get("runtime") is not None:
        logger.info("model_runtime_cached=true")
        return runtime_ref["runtime"]

    logger.info("model runtime load started")
    started = time.perf_counter()
    runtime = await asyncio.to_thread(load_oneway_runtime)
    elapsed = time.perf_counter() - started
    runtime_ref["runtime"] = runtime
    logger.info("model runtime load finished")
    logger.info("model load elapsed seconds: %.3f", elapsed)
    logger.info("model_runtime_cached=%s", bool(runtime.get("cache_hit")))
    return runtime


async def _ensure_roundtrip_runtime_loaded(runtime_ref: dict[str, Any]) -> dict[str, Any]:
    if runtime_ref.get("runtime") is not None:
        logger.info("roundtrip_model_runtime_cached=true")
        return runtime_ref["runtime"]

    logger.info("roundtrip model runtime load started")
    started = time.perf_counter()
    runtime = await asyncio.to_thread(load_roundtrip_runtime)
    elapsed = time.perf_counter() - started
    runtime_ref["runtime"] = runtime
    logger.info("roundtrip model runtime load finished in %.3f seconds", elapsed)
    logger.info("roundtrip_model_runtime_cached=%s", bool(runtime.get("cache_hit")))
    return runtime


def _select_prediction_targets(offers: list[Any], limit: int) -> set[int]:
    candidates = []
    for index, offer in enumerate(offers):
        data = _as_dict(offer)
        price = data.get("price_krw")
        if price is None:
            continue
        candidates.append((int(price), index))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return {index for _, index in candidates[:limit]}


def _clamp_max_predict_offers(value: int | None) -> int:
    if value is None or value <= 0:
        return DEFAULT_MAX_PREDICT_OFFERS
    return min(value, MAX_PREDICT_OFFERS_LIMIT)


def _mark_remaining_after_timeout(
    start_index: int,
    offers: list[Any],
    target_indices: set[int],
    predictions: dict[int, PredictionResult],
    status_counter: Counter[str],
) -> None:
    for index in range(start_index, len(offers)):
        if index in predictions:
            continue
        status = "unavailable_recommend_timeout" if index in target_indices else "skipped_not_in_top_k"
        prediction = _prediction(status, reason="recommend timeout after search" if index in target_indices else None)
        predictions[index] = prediction
        status_counter[prediction.prediction_status] += 1


def _to_recommended_offer(offer: Any, prediction: PredictionResult) -> RecommendedFlightOffer:
    data = _as_dict(offer)
    return RecommendedFlightOffer(
        flight_number=data.get("flight_number"),
        airline_code=data.get("airline_code"),
        airline_name=data.get("airline_name"),
        dep_time=data.get("dep_time"),
        arr_time=data.get("arr_time"),
        duration_min=data.get("duration_min"),
        stops=int(data.get("stops") or 0),
        price_krw=data.get("price_krw"),
        aircraft=data.get("aircraft"),
        seller_type=data.get("seller_type"),
        prediction=prediction,
    )


def _offer_for_adapter(offer: dict[str, Any], request: SearchRequest) -> dict[str, Any]:
    return {
        **offer,
        "departure_date": request.depart_date,
        "dep_time_local": offer.get("dep_time") or offer.get("dep_time_local"),
    }


def _normalize_predict_one_offer(offer: Any) -> dict[str, Any]:
    data = _as_dict(offer)
    dep_time = data.get("dep_time") or data.get("dep_time_local")
    arr_time = data.get("arr_time") or data.get("arr_time_local")
    return {
        **data,
        "dep_time": dep_time,
        "dep_time_local": data.get("dep_time_local") or dep_time,
        "arr_time": arr_time,
        "arr_time_local": data.get("arr_time_local") or arr_time,
        "stops": int(data.get("stops") or 0),
    }


def _roundtrip_request_for_adapter(request: PredictOneRequest, offer: dict[str, Any]) -> dict[str, Any]:
    return {
        "origin": request.origin,
        "destination": request.destination,
        "depart_date": request.depart_date,
        "departure_date": request.depart_date,
        "return_date": offer.get("return_date"),
        "stay_nights": offer.get("stay_nights"),
        "trip_type": "roundtrip",
    }


def _roundtrip_offer_for_adapter(offer: dict[str, Any], request: PredictOneRequest) -> dict[str, Any]:
    return {
        **offer,
        "origin": request.origin,
        "destination": request.destination,
        "departure_date": request.depart_date,
        "return_date": offer.get("return_date"),
        "stay_nights": offer.get("stay_nights"),
    }


def _history_points(rows: list[dict[str, Any]]) -> list[PricePoint]:
    points = []
    for row in rows or []:
        price = row.get("price_krw")
        observed_at = row.get("observed_at")
        dpd = row.get("dpd")
        if price is None or observed_at is None or dpd is None:
            continue
        try:
            points.append(
                PricePoint(
                    observed_at=str(observed_at),
                    dpd=int(dpd),
                    price_krw=int(price),
                    flight_number=row.get("flight_number"),
                    ret_flight_number=row.get("ret_flight_number"),
                    airline_code=row.get("airline_code"),
                    ret_airline_code=row.get("ret_airline_code"),
                    dep_time_local=row.get("dep_time_local"),
                    ret_dep_time_local=row.get("ret_dep_time_local"),
                )
            )
        except (TypeError, ValueError):
            continue
    return points


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _prediction(
    prediction_status: str,
    *,
    decision: str | None = None,
    pred_saving: float | None = None,
    wait_probability: float | None = None,
    threshold: float | None = None,
    confidence: float | None = None,
    model_version: str | None = None,
    reason: str | None = None,
    history_row_count: int | None = None,
    feature_status: str | None = None,
) -> PredictionResult:
    return PredictionResult(
        prediction_status=prediction_status,
        decision=decision,
        pred_saving=pred_saving,
        wait_probability=wait_probability,
        threshold=threshold,
        confidence=confidence,
        model_version=model_version,
        reason=reason,
        history_row_count=history_row_count,
        feature_status=feature_status,
    )


def _feature_status_to_prediction_status(reason: str | None) -> str:
    reason_text = reason or ""
    if "insufficient history" in reason_text:
        return "unavailable_insufficient_history"
    if "unknown encoding" in reason_text:
        return "unavailable_unknown_mapping"
    return "unavailable_feature_build_failed"


def _roundtrip_feature_status_to_prediction_status(reason: str | None, details: Any = None) -> str:
    reason_text = reason or ""
    low = reason_text.lower()
    if "insufficient history" in low:
        return "unavailable_insufficient_history"
    if "unknown" in low and ("mapping" in low or "encoding" in low):
        return "unavailable_unknown_mapping"
    if "null required" in low:
        return "unavailable_numerical_error"
    if "departure_date" in str(details or "") or "date" in low:
        return "unavailable_date_parse_error"
    return "unavailable_feature_build_failed"


def _roundtrip_model_version(artifacts: dict[str, Any] | None) -> str | None:
    metadata = (artifacts or {}).get("metadata") or {}
    if not isinstance(metadata, dict):
        return None
    return (
        metadata.get("model_version")
        or metadata.get("run_id")
        or metadata.get("version")
        or "finaltest_roundtrip_xgb_xgb_v1"
    )


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
