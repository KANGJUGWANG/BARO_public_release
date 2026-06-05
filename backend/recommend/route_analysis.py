from __future__ import annotations

import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

ANALYSIS_VERSION = "route_analysis_v1"
SNAPSHOT_TTL_HOURS = 8
AVAILABLE_SNAPSHOT_STATUSES = {"ok", "stale", "insufficient_data", "no_data"}

MVP_ROUTES: list[dict[str, Any]] = [
    {"route_type": "oneway", "origin": "ICN", "destination": "NRT", "stay_nights": None},
    {"route_type": "oneway", "origin": "NRT", "destination": "ICN", "stay_nights": None},
    {"route_type": "oneway", "origin": "ICN", "destination": "HND", "stay_nights": None},
    {"route_type": "oneway", "origin": "HND", "destination": "ICN", "stay_nights": None},
    {"route_type": "roundtrip", "origin": "ICN", "destination": "NRT", "stay_nights": 7},
    {"route_type": "roundtrip", "origin": "NRT", "destination": "ICN", "stay_nights": 7},
    {"route_type": "roundtrip", "origin": "ICN", "destination": "HND", "stay_nights": 7},
    {"route_type": "roundtrip", "origin": "HND", "destination": "ICN", "stay_nights": 7},
]


def build_route_key(route_type: str, origin: str, destination: str, stay_nights: int | None) -> str:
    base = f"analysis:{route_type}:{origin.upper()}:{destination.upper()}"
    return f"{base}:{stay_nights}" if stay_nights is not None else base


async def compute_route_analysis(cur: Any, route: dict[str, Any]) -> dict[str, Any]:
    origin = route["origin"].upper()
    destination = route["destination"].upper()
    route_type = route["route_type"]
    stay_nights = route.get("stay_nights")
    route_key = build_route_key(route_type, origin, destination, stay_nights)

    generated_at = datetime.now()
    expires_at = generated_at + timedelta(hours=SNAPSHOT_TTL_HOURS)

    where_parts = [
        "s.route_type = %s",
        "s.origin_iata = %s",
        "s.destination_iata = %s",
        "s.crawl_status = 'success'",
        "f.price_krw IS NOT NULL",
        "f.flight_number IS NOT NULL",
        "f.price_status = 'official_price'",
    ]
    params: list[Any] = [route_type, origin, destination]
    if route_type == "roundtrip":
        where_parts.extend([
            "s.stay_nights = %s",
            "s.return_date IS NOT NULL",
            "f.ret_flight_number IS NOT NULL",
        ])
        params.append(stay_nights or 7)
    else:
        where_parts.append("s.return_date IS NULL")
        where_parts.append("(s.stay_nights IS NULL OR s.stay_nights = 0)")

    where_clause = " AND ".join(where_parts)

    await cur.execute(
        f"""
        SELECT
            COUNT(DISTINCT s.observation_id) AS obs_count,
            COUNT(*) AS offer_count,
            MAX(s.observed_at) AS latest_obs,
            MIN(f.price_krw) AS min_price,
            MAX(f.price_krw) AS max_price
        FROM search_observation s
        JOIN flight_offer_observation f ON f.observation_id = s.observation_id
        WHERE {where_clause}
        """,
        tuple(params),
    )
    row = await cur.fetchone()
    if not row or not row[0]:
        return _insufficient(route_key, route, generated_at, expires_at, "no_data")

    observation_count = int(row[0])
    valid_offer_count = int(row[1])
    source_latest_observed_at = row[2]
    historical_min = int(row[3]) if row[3] is not None else None
    historical_max = int(row[4]) if row[4] is not None else None

    if valid_offer_count < 10:
        return _insufficient(
            route_key,
            route,
            generated_at,
            expires_at,
            "insufficient_data",
            observation_count=observation_count,
            valid_offer_count=valid_offer_count,
            source_latest_observed_at=source_latest_observed_at,
        )

    sample_limit = 2000
    await cur.execute(
        f"""
        SELECT f.price_krw
        FROM search_observation s
        JOIN flight_offer_observation f ON f.observation_id = s.observation_id
        WHERE {where_clause}
        ORDER BY s.observed_at DESC, f.price_krw ASC
        LIMIT %s
        """,
        tuple(params + [sample_limit]),
    )
    sampled_prices = [int(r[0]) for r in await cur.fetchall() if r[0] is not None]
    if len(sampled_prices) < 5:
        return _insufficient(
            route_key,
            route,
            generated_at,
            expires_at,
            "insufficient_data",
            observation_count=observation_count,
            valid_offer_count=valid_offer_count,
            source_latest_observed_at=source_latest_observed_at,
        )

    sampled_median = int(statistics.median(sampled_prices))

    await cur.execute(
        f"""
        SELECT f.price_krw
        FROM search_observation s
        JOIN flight_offer_observation f ON f.observation_id = s.observation_id
        WHERE {where_clause}
          AND s.observed_at = %s
        ORDER BY f.price_krw ASC
        LIMIT 50
        """,
        tuple(params + [source_latest_observed_at]),
    )
    latest_prices = [int(r[0]) for r in await cur.fetchall() if r[0] is not None]
    latest_min = min(latest_prices) if latest_prices else None
    latest_median = int(statistics.median(latest_prices)) if latest_prices else None

    dpd_curve = await _compute_dpd_curve(cur, where_clause, params)
    price_time_trend = await _compute_price_time_trend(cur, where_clause, params)
    best_dpd = min(dpd_curve, key=lambda x: x["median_krw"]) if dpd_curve else None
    best_dpd_range = f"{best_dpd['dpd_min']}-{best_dpd['dpd_max']}" if best_dpd else None
    best_dpd_label = f"출발 {best_dpd['label']} 구매 권장 (관측 기준)" if best_dpd else None
    cheap_airlines = await _compute_airline_ranking(cur, where_clause, params)
    volatility_label = _compute_volatility(sampled_prices, sampled_median)
    confidence_label = _compute_confidence(valid_offer_count, len(dpd_curve))

    summary = {
        "latest_min_price_krw": latest_min,
        "latest_median_price_krw": latest_median,
        "historical_min_price_krw": historical_min,
        "historical_max_price_krw": historical_max,
        "sampled_median_price_krw": sampled_median,
        "price_sample_count": len(sampled_prices),
        "sample_limit": sample_limit,
        "trend_label": price_time_trend,
        "volatility_label": volatility_label,
        "best_dpd_range": best_dpd_range,
        "best_dpd_label": best_dpd_label,
        "summary_text": _make_summary_text(
            origin,
            destination,
            route_type,
            price_time_trend,
            historical_min,
            best_dpd_label,
        ),
        "notice": "관측 데이터 기준이며 실제 가격을 보장하지 않습니다.",
    }

    return {
        "route_key": route_key,
        "route_type": route_type,
        "origin_iata": origin,
        "destination_iata": destination,
        "stay_nights": stay_nights,
        "analysis_version": ANALYSIS_VERSION,
        "generated_at": generated_at,
        "expires_at": expires_at,
        "source_latest_observed_at": source_latest_observed_at,
        "observation_count": observation_count,
        "valid_offer_count": valid_offer_count,
        "status": "ok",
        "confidence_label": confidence_label,
        "summary_json": json.dumps(summary, ensure_ascii=False, default=str),
        "dpd_curve_json": json.dumps(dpd_curve, ensure_ascii=False, default=str),
        "airline_ranking_json": json.dumps(cheap_airlines, ensure_ascii=False, default=str),
        "payload_json": None,
    }


async def upsert_route_analysis_snapshot(writer_pool: Any, data: dict[str, Any]) -> bool:
    if writer_pool is None:
        logger.warning("upsert route analysis snapshot skipped: writer pool unavailable")
        return False
    try:
        async with writer_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO service_route_analysis_snapshot
                        (route_key, route_type, origin_iata, destination_iata, stay_nights,
                         analysis_version, generated_at, expires_at, source_latest_observed_at,
                         observation_count, valid_offer_count, status, confidence_label,
                         summary_json, dpd_curve_json, airline_ranking_json, payload_json)
                    VALUES
                        (%s, %s, %s, %s, %s,
                         %s, %s, %s, %s,
                         %s, %s, %s, %s,
                         %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        analysis_version = VALUES(analysis_version),
                        generated_at = VALUES(generated_at),
                        expires_at = VALUES(expires_at),
                        source_latest_observed_at = VALUES(source_latest_observed_at),
                        observation_count = VALUES(observation_count),
                        valid_offer_count = VALUES(valid_offer_count),
                        status = VALUES(status),
                        confidence_label = VALUES(confidence_label),
                        summary_json = VALUES(summary_json),
                        dpd_curve_json = VALUES(dpd_curve_json),
                        airline_ranking_json = VALUES(airline_ranking_json),
                        payload_json = VALUES(payload_json),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        data["route_key"],
                        data["route_type"],
                        data["origin_iata"],
                        data["destination_iata"],
                        data["stay_nights"],
                        data["analysis_version"],
                        data["generated_at"],
                        data["expires_at"],
                        data.get("source_latest_observed_at"),
                        data["observation_count"],
                        data["valid_offer_count"],
                        data["status"],
                        data.get("confidence_label"),
                        data.get("summary_json"),
                        data.get("dpd_curve_json"),
                        data.get("airline_ranking_json"),
                        data.get("payload_json"),
                    ),
                )
        return True
    except Exception as exc:  # noqa: BLE001 - script should continue per route.
        logger.warning(
            "upsert route analysis snapshot failed for %s: %s",
            data.get("route_key"),
            exc.__class__.__name__,
        )
        return False


async def get_all_route_analysis_snapshots(pool: Any) -> list[dict[str, Any]]:
    if pool is None:
        return [_snapshot_unavailable(r, "unavailable_db_pool") for r in MVP_ROUTES]

    route_keys = [
        build_route_key(r["route_type"], r["origin"], r["destination"], r.get("stay_nights"))
        for r in MVP_ROUTES
    ]
    placeholders = ", ".join(["%s"] * len(route_keys))
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'service_route_analysis_snapshot'
                    LIMIT 1
                    """
                )
                if not await cur.fetchone():
                    return [_snapshot_unavailable(r, "unavailable_table_missing") for r in MVP_ROUTES]

                await cur.execute(
                    f"""
                    SELECT route_key, route_type, origin_iata, destination_iata, stay_nights,
                           status, confidence_label, generated_at, expires_at,
                           source_latest_observed_at, observation_count, valid_offer_count,
                           summary_json, dpd_curve_json, airline_ranking_json
                    FROM service_route_analysis_snapshot
                    WHERE route_key IN ({placeholders})
                    """,
                    tuple(route_keys),
                )
                rows = {r[0]: r for r in await cur.fetchall()}
    except Exception as exc:  # noqa: BLE001 - endpoint should fail soft.
        logger.warning("get route analysis snapshots failed: %s", exc.__class__.__name__)
        return [_snapshot_unavailable(r, "unavailable_db_query_error") for r in MVP_ROUTES]

    now = datetime.now()
    result = []
    for spec, route_key in zip(MVP_ROUTES, route_keys):
        row = rows.get(route_key)
        if not row:
            result.append(_snapshot_unavailable(spec, "unavailable_analysis_snapshot"))
            continue
        expires_at = row[8]
        is_stale = expires_at is not None and expires_at < now
        status = "stale" if is_stale and row[5] == "ok" else row[5]
        result.append(
            {
                "route_key": row[0],
                "route_type": row[1],
                "origin": row[2],
                "destination": row[3],
                "stay_nights": row[4],
                "status": status,
                "is_stale": is_stale,
                "confidence": row[6],
                "generated_at": _format_dt(row[7]),
                "expires_at": _format_dt(row[8]),
                "latest_observed_at": _format_dt(row[9]),
                "observation_count": int(row[10] or 0),
                "valid_offer_count": int(row[11] or 0),
                "summary": _parse_json_safe(row[12]),
                "dpd_curve": _parse_json_safe(row[13]) or [],
                "cheap_airlines": _parse_json_safe(row[14]) or [],
            }
        )
    return result


def summarize_route_analysis_status(items: list[Any]) -> tuple[str, int, str | None, str | None]:
    if not items:
        return "unavailable_analysis_snapshot", 0, None, None

    statuses = [getattr(item, "status", None) if not isinstance(item, dict) else item.get("status") for item in items]
    if statuses and len(set(statuses)) == 1:
        only = statuses[0]
        if only in {
            "unavailable_table_missing",
            "unavailable_db_pool",
            "unavailable_db_query_error",
            "unavailable_analysis_snapshot",
        }:
            return only, 0, None, None

    available_count = sum(1 for s in statuses if s in AVAILABLE_SNAPSHOT_STATUSES)
    generated_values = [
        getattr(item, "generated_at", None) if not isinstance(item, dict) else item.get("generated_at")
        for item in items
    ]
    expires_values = [
        getattr(item, "expires_at", None) if not isinstance(item, dict) else item.get("expires_at")
        for item in items
    ]
    generated_at = max((v for v in generated_values if v), default=None)
    expires_at = min((v for v in expires_values if v), default=None)
    status = "ok" if available_count == len(items) else ("partial" if available_count > 0 else "unavailable_analysis_snapshot")
    return status, available_count, generated_at, expires_at


async def _compute_dpd_curve(cur: Any, where_clause: str, params: list[Any]) -> list[dict[str, Any]]:
    dpd_curve = []
    for dpd_min, dpd_max in [(0, 7), (8, 14), (15, 30), (31, 60), (61, 90), (91, 120)]:
        await cur.execute(
            f"""
            SELECT f.price_krw
            FROM search_observation s
            JOIN flight_offer_observation f ON f.observation_id = s.observation_id
            WHERE {where_clause}
              AND DATEDIFF(s.departure_date, DATE(s.observed_at)) BETWEEN %s AND %s
            ORDER BY f.price_krw ASC
            LIMIT 500
            """,
            tuple(params + [dpd_min, dpd_max]),
        )
        prices = [int(r[0]) for r in await cur.fetchall() if r[0] is not None]
        if len(prices) >= 3:
            dpd_curve.append(
                {
                    "dpd_min": dpd_min,
                    "dpd_max": dpd_max,
                    "label": f"{dpd_min}-{dpd_max}일 전",
                    "median_krw": int(statistics.median(prices)),
                    "min_krw": min(prices),
                    "sample_count": len(prices),
                }
            )
    return dpd_curve


async def _compute_price_time_trend(cur: Any, where_clause: str, params: list[Any]) -> str:
    await cur.execute(
        f"""
        SELECT s.observed_at, f.price_krw
        FROM search_observation s
        JOIN flight_offer_observation f ON f.observation_id = s.observation_id
        WHERE {where_clause}
        ORDER BY s.observed_at DESC, f.price_krw ASC
        LIMIT 1200
        """,
        tuple(params),
    )
    rows = await cur.fetchall()
    if len(rows) < 20:
        return "insufficient"
    latest_times = sorted({r[0] for r in rows if r[0]}, reverse=True)
    if len(latest_times) < 2:
        return "insufficient"
    latest_set = set(latest_times[: max(1, min(3, len(latest_times) // 2))])
    recent = [int(r[1]) for r in rows if r[0] in latest_set and r[1] is not None]
    previous = [int(r[1]) for r in rows if r[0] not in latest_set and r[1] is not None]
    if len(recent) < 5 or len(previous) < 5:
        return "insufficient"
    recent_median = statistics.median(recent)
    previous_median = statistics.median(previous)
    if previous_median == 0:
        return "insufficient"
    change_pct = (recent_median - previous_median) / previous_median
    if change_pct > 0.05:
        return "rising"
    if change_pct < -0.05:
        return "falling"
    return "stable"


async def _compute_airline_ranking(cur: Any, where_clause: str, params: list[Any]) -> list[dict[str, Any]]:
    await cur.execute(
        f"""
        SELECT f.airline_code, f.airline_name, COUNT(*) AS cnt,
               CAST(AVG(f.price_krw) AS UNSIGNED) AS avg_price,
               MIN(f.price_krw) AS min_price
        FROM search_observation s
        JOIN flight_offer_observation f ON f.observation_id = s.observation_id
        WHERE {where_clause}
          AND f.airline_code IS NOT NULL
        GROUP BY f.airline_code, f.airline_name
        HAVING cnt >= 3
        ORDER BY avg_price ASC
        LIMIT 3
        """,
        tuple(params),
    )
    return [
        {
            "airline_code": r[0],
            "airline_name": r[1] or r[0],
            "offer_count": int(r[2]),
            "avg_price_krw": int(r[3]) if r[3] is not None else None,
            "min_price_krw": int(r[4]) if r[4] is not None else None,
        }
        for r in await cur.fetchall()
    ]


def _insufficient(
    route_key: str,
    route: dict[str, Any],
    generated_at: datetime,
    expires_at: datetime,
    status: str,
    observation_count: int = 0,
    valid_offer_count: int = 0,
    source_latest_observed_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "route_key": route_key,
        "route_type": route["route_type"],
        "origin_iata": route["origin"].upper(),
        "destination_iata": route["destination"].upper(),
        "stay_nights": route.get("stay_nights"),
        "analysis_version": ANALYSIS_VERSION,
        "generated_at": generated_at,
        "expires_at": expires_at,
        "source_latest_observed_at": source_latest_observed_at,
        "observation_count": observation_count,
        "valid_offer_count": valid_offer_count,
        "status": status,
        "confidence_label": "insufficient",
        "summary_json": None,
        "dpd_curve_json": None,
        "airline_ranking_json": None,
        "payload_json": None,
    }


def _snapshot_unavailable(spec: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "route_key": build_route_key(spec["route_type"], spec["origin"], spec["destination"], spec.get("stay_nights")),
        "route_type": spec["route_type"],
        "origin": spec["origin"].upper(),
        "destination": spec["destination"].upper(),
        "stay_nights": spec.get("stay_nights"),
        "status": status,
        "is_stale": False,
        "confidence": "insufficient",
        "generated_at": None,
        "expires_at": None,
        "latest_observed_at": None,
        "observation_count": 0,
        "valid_offer_count": 0,
        "summary": None,
        "dpd_curve": [],
        "cheap_airlines": [],
    }


def _compute_volatility(prices: list[int], median_price: int) -> str:
    if not prices or median_price == 0:
        return "insufficient"
    sorted_prices = sorted(prices)
    q1 = sorted_prices[len(sorted_prices) // 4]
    q3 = sorted_prices[3 * len(sorted_prices) // 4]
    iqr_pct = (q3 - q1) / median_price
    if iqr_pct < 0.15:
        return "low"
    if iqr_pct < 0.35:
        return "medium"
    return "high"


def _compute_confidence(valid_offer_count: int, dpd_bucket_count: int) -> str:
    if valid_offer_count >= 200 and dpd_bucket_count >= 4:
        return "high"
    if valid_offer_count >= 50 and dpd_bucket_count >= 2:
        return "medium"
    if valid_offer_count >= 10:
        return "low"
    return "insufficient"


def _make_summary_text(
    origin: str,
    destination: str,
    route_type: str,
    trend_label: str,
    historical_min: int | None,
    best_dpd_label: str | None,
) -> str:
    trip = "왕복" if route_type == "roundtrip" else "편도"
    trend_map = {"rising": "상승 추세", "falling": "하락 추세", "stable": "안정적"}
    trend_str = trend_map.get(trend_label, "데이터 분석 중")
    min_text = f"최저 {historical_min:,}원 관측" if historical_min else "최저가 분석 중"
    text = f"{origin}→{destination} {trip}: {min_text}. 가격 {trend_str}."
    if best_dpd_label:
        text += f" {best_dpd_label}."
    return f"{text} 관측 데이터 기준이며 실제 가격을 보장하지 않습니다."


def _parse_json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def _format_dt(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)
