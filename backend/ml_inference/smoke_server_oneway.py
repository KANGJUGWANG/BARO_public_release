"""Server-side smoke test for BARO oneway model inference.

Run from backend/:
    python -m ml_inference.smoke_server_oneway
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.db import close_pool, create_pool, get_pool
from ml_inference.history import fetch_history_rows
from ml_inference.model_runtime import (
    load_oneway_artifacts,
    load_oneway_runtime,
    predict_oneway_from_feature,
)
from ml_inference.oneway_adapter import build_oneway_features


DEFAULT_ORIGIN = "ICN"
DEFAULT_DESTINATION = "NRT"
DEFAULT_DEPARTURE_DATE = "2026-07-01"
DEFAULT_FLIGHT_NUMBER = "RS701"

DEFAULT_OFFER = {
    "flight_number": DEFAULT_FLIGHT_NUMBER,
    "airline_code": "RS",
    "price_krw": 153500,
    "dep_time_local": "09:20",
    "dep_time": "09:20",
    "arr_time": "11:50",
    "duration_min": 150,
    "stops": 0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test oneway inference with server DB history.")
    parser.add_argument("--origin", default=DEFAULT_ORIGIN)
    parser.add_argument("--destination", default=DEFAULT_DESTINATION)
    parser.add_argument("--departure-date", default=DEFAULT_DEPARTURE_DATE)
    parser.add_argument("--flight-number", default=DEFAULT_FLIGHT_NUMBER)
    parser.add_argument("--airline-code", default=DEFAULT_OFFER["airline_code"])
    parser.add_argument("--price-krw", default=DEFAULT_OFFER["price_krw"], type=int)
    parser.add_argument("--dep-time-local", default=DEFAULT_OFFER["dep_time_local"])
    parser.add_argument("--model-dir", default=None, type=Path)
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    await create_pool()
    try:
        result = await run_smoke(args)
    finally:
        await close_pool()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("prediction_status") in _ACCEPTED_STATUSES else 2


async def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    pool = get_pool()
    if pool is None:
        return {
            "history_row_count": 0,
            "feature_status": "prediction_unavailable",
            "prediction_status": "unavailable_db_pool",
            "reason": "DB pool is unavailable",
        }

    history_rows = await fetch_history_rows(
        origin=args.origin,
        destination=args.destination,
        departure_date=args.departure_date,
        flight_number=args.flight_number,
        pool=pool,
    )

    offer = {
        "flight_number": args.flight_number,
        "airline_code": args.airline_code,
        "price_krw": args.price_krw,
        "dep_time_local": args.dep_time_local,
        "dep_time": args.dep_time_local,
        "departure_date": args.departure_date,
    }
    request = {
        "origin": args.origin,
        "destination": args.destination,
        "depart_date": args.departure_date,
        "trip_type": "oneway",
    }

    artifacts = load_oneway_artifacts(args.model_dir)
    if artifacts.get("status") != "ok":
        return {
            "history_row_count": len(history_rows),
            "feature_status": "prediction_unavailable",
            "prediction_status": artifacts.get("status"),
            "reason": artifacts.get("reason"),
            "model_dir": artifacts.get("model_dir"),
        }

    built = build_oneway_features(
        offer=offer,
        request=request,
        history_rows=history_rows,
        now=datetime.now(),
        artifacts=artifacts,
    )
    feature_status = built.get("feature_status")
    if feature_status != "ok":
        reason = built.get("unavailable_reason")
        return {
            "history_row_count": len(history_rows),
            "feature_status": feature_status,
            "prediction_status": _feature_unavailable_status(reason),
            "reason": reason,
            "details": built.get("details", {}),
        }

    runtime = load_oneway_runtime(args.model_dir)
    prediction = predict_oneway_from_feature(built, runtime)

    return {
        "history_row_count": len(history_rows),
        "feature_status": feature_status,
        "feature_metadata": built.get("metadata", {}),
        "model_load_seconds": runtime.get("load_seconds"),
        **prediction,
    }


def _feature_unavailable_status(reason: str | None) -> str:
    reason_text = reason or ""
    if "insufficient history" in reason_text:
        return "unavailable_insufficient_history"
    if "unknown encoding" in reason_text:
        return "unavailable_unknown_mapping"
    return "prediction_unavailable"


_ACCEPTED_STATUSES = {
    "ok",
    "unavailable_insufficient_history",
    "unavailable_unknown_mapping",
    "unavailable_model_load_failed",
}


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
