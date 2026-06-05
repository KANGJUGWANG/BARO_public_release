from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ml_inference.oneway_adapter import (
    _as_dict,
    _int_or_none,
    _mapping_payload,
    _parse_date,
    _parse_datetime,
    _resolve_flight_key,
    _resolve_route_encoding,
    _unavailable,
)

logger = logging.getLogger(__name__)


_ROUNDTRIP_HISTORY_SQL = """
SELECT
    s.observed_at,
    s.dpd,
    s.origin_iata,
    s.destination_iata,
    s.departure_date,
    s.return_date,
    s.stay_nights,
    f.price_krw,
    f.airline_code,
    f.flight_number,
    CAST(f.dep_time_local AS CHAR) AS dep_time_local,
    f.ret_airline_code,
    f.ret_flight_number,
    CAST(f.ret_dep_time_local AS CHAR) AS ret_dep_time_local
FROM flight_offer_observation f
JOIN search_observation s ON f.observation_id = s.observation_id
WHERE s.route_type = 'roundtrip'
  AND s.origin_iata = %s
  AND s.destination_iata = %s
  AND s.departure_date = %s
  AND (%s IS NULL OR s.return_date = %s)
  AND (%s IS NULL OR s.stay_nights = %s)
  AND f.flight_number = %s
  AND f.ret_flight_number = %s
  AND f.price_krw IS NOT NULL
  AND s.crawl_status = 'success'
ORDER BY s.observed_at ASC
LIMIT %s
"""


_ROUNDTRIP_SAMPLE_SQL = """
SELECT
    s.origin_iata,
    s.destination_iata,
    s.departure_date,
    s.return_date,
    s.stay_nights,
    f.airline_code,
    f.flight_number,
    f.ret_airline_code,
    f.ret_flight_number,
    COUNT(*) AS history_count,
    MAX(s.observed_at) AS latest_observed_at
FROM flight_offer_observation f
JOIN search_observation s ON f.observation_id = s.observation_id
WHERE s.route_type = 'roundtrip'
  AND s.crawl_status = 'success'
  AND f.price_krw IS NOT NULL
  AND f.flight_number IS NOT NULL
  AND f.flight_number != ''
  AND f.ret_flight_number IS NOT NULL
  AND f.ret_flight_number != ''
GROUP BY
    s.origin_iata,
    s.destination_iata,
    s.departure_date,
    s.return_date,
    s.stay_nights,
    f.airline_code,
    f.flight_number,
    f.ret_airline_code,
    f.ret_flight_number
HAVING COUNT(*) >= %s
ORDER BY MAX(s.observed_at) DESC, COUNT(*) DESC
LIMIT 1
"""


async def select_roundtrip_sample(pool, min_total_rows: int = 7) -> dict[str, Any] | None:
    if pool is None:
        return None

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(_ROUNDTRIP_SAMPLE_SQL, (min_total_rows,))
                row = await cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - smoke should report unavailable, not crash APIs.
        logger.warning("roundtrip sample query failed: %s", exc.__class__.__name__)
        return None

    if not row:
        return None

    (
        origin,
        destination,
        departure_date,
        return_date,
        stay_nights,
        airline_code,
        flight_number,
        ret_airline_code,
        ret_flight_number,
        history_count,
        latest_observed_at,
    ) = row
    return {
        "origin": _clean_code(origin),
        "destination": _clean_code(destination),
        "departure_date": _format_date(departure_date),
        "return_date": _format_date(return_date),
        "stay_nights": _int_or_none(stay_nights),
        "airline_code": _clean_code(airline_code),
        "flight_number": _clean_code(flight_number),
        "ret_airline_code": _clean_code(ret_airline_code),
        "ret_flight_number": _clean_code(ret_flight_number),
        "history_count": _int_or_none(history_count),
        "latest_observed_at": _format_datetime(latest_observed_at),
    }


async def fetch_roundtrip_history_rows(
    origin: str,
    destination: str,
    departure_date: str,
    flight_number: str,
    ret_flight_number: str,
    pool,
    return_date: str | None = None,
    stay_nights: int | None = None,
    limit: int = 240,
) -> list[dict[str, Any]]:
    origin = _clean_code(origin)
    destination = _clean_code(destination)
    departure_date = _clean_text(departure_date)
    return_date = _clean_text(return_date)
    flight_number = _clean_code(flight_number)
    ret_flight_number = _clean_code(ret_flight_number)

    if not origin or not destination or not departure_date or not flight_number or not ret_flight_number:
        return []
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    _ROUNDTRIP_HISTORY_SQL,
                    (
                        origin,
                        destination,
                        departure_date,
                        return_date,
                        return_date,
                        stay_nights,
                        stay_nights,
                        flight_number,
                        ret_flight_number,
                        max(int(limit), 7),
                    ),
                )
                rows = await cursor.fetchall()
    except Exception as exc:  # noqa: BLE001 - keep history retrieval fail-soft.
        logger.warning("roundtrip history rows query failed: %s", exc.__class__.__name__)
        return []

    return [_normalize_roundtrip_row(row) for row in rows or []]


def build_roundtrip_features(
    offer: Any,
    request: Any,
    history_rows: list[dict[str, Any]],
    now: datetime | None,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import pandas as pd

    if artifacts is None:
        return _unavailable("enc_mappings artifact is required to build roundtrip features")

    offer_dict = _as_dict(offer)
    request_dict = _as_dict(request)
    mappings = _mapping_payload(artifacts)
    now_dt = now or datetime.now()

    route, route_enc = _resolve_route_encoding(request_dict, offer_dict, mappings)
    airline_code = _clean_code(offer_dict.get("airline_code"))
    flight_key = _resolve_flight_key(offer_dict, mappings)
    ret_flight_number = _clean_code(offer_dict.get("ret_flight_number"))
    ret_flight_key = _resolve_ret_flight_key(ret_flight_number, mappings)
    price_krw = _int_or_none(offer_dict.get("price_krw"))
    depart_date = _parse_date(
        offer_dict.get("departure_date")
        or request_dict.get("depart_date")
        or request_dict.get("departure_date")
    )
    return_date = _parse_date(offer_dict.get("return_date") or request_dict.get("return_date"))

    missing_identity = [
        name
        for name, value in {
            "route": route,
            "airline_code": airline_code,
            "flight_key": flight_key,
            "ret_flight_key": ret_flight_key,
            "price_krw": price_krw,
            "departure_date": depart_date,
        }.items()
        if value is None
    ]
    if missing_identity:
        return _unavailable("missing required current roundtrip fields", {"missing": missing_identity})

    unknown = {}
    if route_enc is None:
        unknown["route"] = route
    if airline_code not in mappings["airline_enc"]:
        unknown["airline_code"] = airline_code
    if flight_key not in mappings["flight_enc"]:
        unknown["flight_key"] = flight_key
    if ret_flight_key not in mappings["flight_enc"]:
        unknown["ret_flight_key"] = ret_flight_key
    if unknown:
        return _unavailable("unknown encoding category", unknown)

    observed_at = _parse_datetime(offer_dict.get("observed_at")) or now_dt
    dpd = _int_or_none(offer_dict.get("dpd"))
    if dpd is None:
        dpd = max((depart_date - observed_at.date()).days, 0)

    traj_id = offer_dict.get("traj_id") or _roundtrip_traj_id(
        route=route,
        flight_key=flight_key,
        ret_flight_key=ret_flight_key,
        departure_date=depart_date.isoformat(),
        return_date=return_date.isoformat() if return_date else None,
    )
    current_row = {
        "traj_id": traj_id,
        "route": route,
        "airline_code": airline_code,
        "flight_key": flight_key,
        "ret_flight_key": ret_flight_key,
        "departure_date": depart_date.isoformat(),
        "return_date": return_date.isoformat() if return_date else None,
        "observed_at": observed_at,
        "dpd": dpd,
        "price_krw": price_krw,
        "_is_current": True,
    }

    normalized_history = []
    for idx, row in enumerate(history_rows or []):
        hist = dict(row)
        hist_price = _int_or_none(hist.get("price_krw"))
        hist_observed = _parse_datetime(hist.get("observed_at"))
        hist_dpd = _int_or_none(hist.get("dpd"))
        if hist_price is None or hist_observed is None or hist_dpd is None:
            continue
        normalized_history.append(
            {
                "traj_id": traj_id,
                "route": hist.get("route") or route,
                "airline_code": hist.get("airline_code") or airline_code,
                "flight_key": hist.get("flight_key") or flight_key,
                "ret_flight_key": hist.get("ret_flight_key") or ret_flight_key,
                "departure_date": str(hist.get("departure_date") or current_row["departure_date"])[:10],
                "return_date": str(hist.get("return_date") or current_row.get("return_date") or "")[:10],
                "observed_at": hist_observed,
                "dpd": hist_dpd,
                "price_krw": hist_price,
                "_is_current": False,
                "_history_index": idx,
            }
        )

    rows = normalized_history + [current_row]
    if len(rows) < 7:
        return _unavailable(
            "insufficient history_rows for price_chg_6",
            {"required_total_rows": 7, "available_total_rows": len(rows)},
        )

    df = pd.DataFrame(rows).sort_values(["observed_at", "_is_current"], kind="mergesort").reset_index(drop=True)
    df["scan_hour"] = pd.to_datetime(df["observed_at"]).dt.hour
    df["scan_seq"] = df.groupby(["traj_id", "dpd"]).cumcount()
    df["dpd_max"] = df.groupby("traj_id")["dpd"].transform("max")
    df["dpd_ratio"] = df["dpd"] / df["dpd_max"].clip(lower=1)

    grouped = df.groupby("traj_id")["price_krw"]
    df["cum_min"] = grouped.transform(lambda x: x.expanding().min())
    df["cum_max"] = grouped.transform(lambda x: x.expanding().max())
    df["cum_mean"] = grouped.transform(lambda x: x.expanding().mean())
    df["cum_std"] = grouped.transform(lambda x: x.expanding().std().fillna(0))
    df["cum_count"] = grouped.transform(lambda x: x.expanding().count())
    df["price_pct_from_cum_min"] = (df["price_krw"] - df["cum_min"]) / df["cum_min"] * 100
    df["price_pct_from_cum_max"] = (df["price_krw"] - df["cum_max"]) / df["cum_max"] * 100
    df["price_pct_from_cum_mean"] = (df["price_krw"] - df["cum_mean"]) / df["cum_mean"] * 100
    df["price_chg_1"] = grouped.pct_change(1) * 100
    df["price_chg_3"] = grouped.pct_change(3) * 100
    df["price_chg_6"] = grouped.pct_change(6) * 100
    df["route_enc"] = route_enc
    df["airline_enc"] = mappings["airline_enc"][airline_code]
    df["flight_enc"] = mappings["flight_enc"][flight_key]
    df["ret_flight_enc"] = mappings["flight_enc"][ret_flight_key]

    current = df[df["_is_current"]].tail(1)
    if current.empty:
        return _unavailable("current row was not found after roundtrip feature build")

    feature_columns = artifacts.get("feature_columns", {}).get("roundtrip", {}).get("stage1", [])
    missing_features = [col for col in feature_columns if col not in current.columns]
    if missing_features:
        return _unavailable("missing required roundtrip stage1 feature columns", {"missing": missing_features})
    null_features = [col for col in feature_columns if pd.isna(current.iloc[0][col])]
    if null_features:
        return _unavailable("null required roundtrip stage1 feature columns", {"null_features": null_features})

    feature_row = {
        col: current.iloc[0][col].item() if hasattr(current.iloc[0][col], "item") else current.iloc[0][col]
        for col in feature_columns
    }
    return {
        "feature_status": "ok",
        "unavailable_reason": None,
        "feature_row": feature_row,
        "metadata": {
            "route": route,
            "airline_code": airline_code,
            "flight_key": flight_key,
            "ret_flight_number": ret_flight_number,
            "ret_flight_key": ret_flight_key,
            "ret_flight_enc_policy": "ret_flight_number -> flight_number_key -> flight_enc",
            "history_row_count": len(normalized_history),
            "cum_count": float(current.iloc[0]["cum_count"]),
        },
    }


def _resolve_ret_flight_key(ret_flight_number: str | None, mappings: dict[str, dict[str, int]]) -> str | None:
    if not ret_flight_number:
        return None
    mapped = mappings.get("flight_number_key", {}).get(ret_flight_number)
    if mapped:
        return mapped
    prefix = f"{ret_flight_number}_"
    matches = [key for key in mappings["flight_enc"] if key.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    return None


def _roundtrip_traj_id(
    route: str,
    flight_key: str,
    ret_flight_key: str,
    departure_date: str,
    return_date: str | None,
) -> str:
    return f"{route}_{flight_key}_{ret_flight_key}_{departure_date}_{return_date or 'no_return'}"


def _normalize_roundtrip_row(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        observed_at = row.get("observed_at")
        dpd = row.get("dpd")
        origin_iata = row.get("origin_iata")
        destination_iata = row.get("destination_iata")
        departure_date = row.get("departure_date")
        return_date = row.get("return_date")
        stay_nights = row.get("stay_nights")
        price_krw = row.get("price_krw")
        airline_code = row.get("airline_code")
        flight_number = row.get("flight_number")
        dep_time_local = row.get("dep_time_local")
        ret_airline_code = row.get("ret_airline_code")
        ret_flight_number = row.get("ret_flight_number")
        ret_dep_time_local = row.get("ret_dep_time_local")
    else:
        (
            observed_at,
            dpd,
            origin_iata,
            destination_iata,
            departure_date,
            return_date,
            stay_nights,
            price_krw,
            airline_code,
            flight_number,
            dep_time_local,
            ret_airline_code,
            ret_flight_number,
            ret_dep_time_local,
        ) = row

    return {
        "observed_at": _format_datetime(observed_at),
        "dpd": _int_or_none(dpd),
        "origin_iata": _clean_code(origin_iata),
        "destination_iata": _clean_code(destination_iata),
        "departure_date": _format_date(departure_date),
        "return_date": _format_date(return_date),
        "stay_nights": _int_or_none(stay_nights),
        "price_krw": _int_or_none(price_krw),
        "airline_code": _clean_code(airline_code),
        "flight_number": _clean_code(flight_number),
        "dep_time_local": _format_time(dep_time_local),
        "ret_airline_code": _clean_code(ret_airline_code),
        "ret_flight_number": _clean_code(ret_flight_number),
        "ret_dep_time_local": _format_time(ret_dep_time_local),
    }


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_code(value: Any) -> str | None:
    text = _clean_text(value)
    return text.upper() if text else None


def _format_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value).strip() or None


def _format_date(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip()[:10] or None


def _format_time(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:5]
