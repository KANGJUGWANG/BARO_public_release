"""Batch smoke for the roundtrip feature builder.

Run from backend/:
    python -m ml_inference.smoke_server_roundtrip_batch \
      --samples-json /tmp/phase_7_6_batch_samples.json \
      --out /tmp/phase_7_6_batch_results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SAMPLES: list[dict[str, Any]] = [
    {
        "origin": "ICN",
        "destination": "NRT",
        "depart_date": "2026-08-10",
        "return_date": "2026-08-17",
        "stay_nights": 7,
        "flight_number": "ZG46",
        "ret_flight_number": "ZG45",
        "airline_code": "ZG",
        "ret_airline_code": "ZG",
    }
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch smoke-test DB-backed roundtrip features.")
    parser.add_argument("--samples-json", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("/tmp/phase_7_6_batch_results.json"))
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--history-limit", type=int, default=240)
    return parser.parse_args()


async def smoke_one(sample: dict[str, Any], pool, artifacts: dict[str, Any], runtime: dict[str, Any], history_limit: int) -> dict[str, Any]:
    from ml_inference.model_runtime import predict_roundtrip_from_feature
    from ml_inference.roundtrip_feature_builder import (
        build_roundtrip_features,
        fetch_roundtrip_history_rows,
    )

    sample_id = (
        f"{sample.get('origin')}_{sample.get('destination')}_"
        f"{sample.get('depart_date') or sample.get('departure_date')}_"
        f"{sample.get('flight_number')}_{sample.get('ret_flight_number')}"
    )
    result: dict[str, Any] = {
        "sample_id": sample_id,
        "origin": sample.get("origin"),
        "destination": sample.get("destination"),
        "depart_date": sample.get("depart_date") or sample.get("departure_date"),
        "return_date": sample.get("return_date"),
        "stay_nights": sample.get("stay_nights"),
        "flight_number": sample.get("flight_number"),
        "ret_flight_number": sample.get("ret_flight_number"),
        "airline_code": sample.get("airline_code"),
        "ret_airline_code": sample.get("ret_airline_code"),
        "expected_obs_count": sample.get("obs_count"),
        "history_row_count": 0,
        "feature_count": None,
        "feature_order_ok": None,
        "route_enc_status": None,
        "airline_enc_status": None,
        "flight_enc_status": None,
        "ret_flight_enc_status": None,
        "prediction_status": None,
        "decision": None,
        "pred_saving": None,
        "wait_probability": None,
        "threshold": None,
        "confidence": None,
        "reason": None,
    }

    rows = await fetch_roundtrip_history_rows(
        origin=str(sample.get("origin") or ""),
        destination=str(sample.get("destination") or ""),
        departure_date=str(sample.get("depart_date") or sample.get("departure_date") or ""),
        return_date=sample.get("return_date"),
        stay_nights=sample.get("stay_nights"),
        flight_number=str(sample.get("flight_number") or ""),
        ret_flight_number=str(sample.get("ret_flight_number") or ""),
        pool=pool,
        limit=history_limit,
    )
    result["history_row_count"] = len(rows)
    if len(rows) < 7:
        result["prediction_status"] = "unavailable_insufficient_history"
        result["reason"] = "insufficient history rows for price_chg_6"
        return result

    current = rows[-1]
    history_rows = rows[:-1]
    request = {
        "origin": sample.get("origin"),
        "destination": sample.get("destination"),
        "depart_date": sample.get("depart_date") or sample.get("departure_date"),
        "departure_date": sample.get("depart_date") or sample.get("departure_date"),
        "return_date": sample.get("return_date"),
        "trip_type": "roundtrip",
    }
    offer = {
        **current,
        "origin": sample.get("origin"),
        "destination": sample.get("destination"),
    }

    built = build_roundtrip_features(
        offer=offer,
        request=request,
        history_rows=history_rows,
        now=datetime.now(),
        artifacts=artifacts,
    )
    if built.get("feature_status") != "ok":
        result["prediction_status"] = _feature_reason_to_status(built.get("unavailable_reason"))
        result["reason"] = built.get("unavailable_reason")
        return result

    feature_row = built["feature_row"]
    stage1_cols = artifacts.get("stage1_features", [])
    result["feature_count"] = len(feature_row)
    result["feature_order_ok"] = list(feature_row.keys()) == stage1_cols
    result["route_enc_status"] = "ok" if feature_row.get("route_enc") is not None else "missing"
    result["airline_enc_status"] = "ok" if feature_row.get("airline_enc") is not None else "missing"
    result["flight_enc_status"] = "ok" if feature_row.get("flight_enc") is not None else "missing"
    result["ret_flight_enc_status"] = "ok" if feature_row.get("ret_flight_enc") is not None else "missing"

    pred = predict_roundtrip_from_feature(feature_row, runtime)
    result["prediction_status"] = pred.get("prediction_status")
    result["decision"] = pred.get("decision")
    result["pred_saving"] = pred.get("pred_saving")
    result["wait_probability"] = pred.get("wait_probability")
    result["threshold"] = pred.get("threshold")
    result["confidence"] = pred.get("confidence")
    result["reason"] = pred.get("reason")
    return result


async def async_main() -> int:
    args = parse_args()

    from core.db import close_pool, create_pool, get_pool
    from ml_inference.model_runtime import load_roundtrip_artifacts, load_roundtrip_runtime

    samples = _load_samples(args.samples_json)
    artifacts = load_roundtrip_artifacts(args.model_dir)
    if artifacts.get("status") != "ok":
        print(json.dumps(artifacts, indent=2, ensure_ascii=False, default=str))
        return 2

    runtime = load_roundtrip_runtime(args.model_dir)
    if runtime.get("status") != "ok":
        print(json.dumps(runtime, indent=2, ensure_ascii=False, default=str))
        return 2

    await create_pool()
    pool = get_pool()
    if pool is None:
        print("db pool unavailable")
        return 2

    results = []
    try:
        for sample in samples:
            print(f"\n--- {sample.get('flight_number')}/{sample.get('ret_flight_number')} ---")
            item = await smoke_one(sample, pool, artifacts, runtime, args.history_limit)
            results.append(item)
            print(
                "  history: {history_row_count}  feature: {feature_count}"
                "  order_ok: {feature_order_ok}  status: {prediction_status}"
                "  decision: {decision}".format(**item)
            )
    finally:
        await close_pool()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nsaved: {args.out}")

    ok_count = sum(1 for item in results if item.get("prediction_status") == "ok")
    print(f"\nsummary: {ok_count}/{len(results)} ok")
    for item in results:
        marker = "OK" if item.get("prediction_status") == "ok" else "FAIL"
        print(f"  {marker} {item['sample_id']} -> {item.get('prediction_status')} {item.get('decision') or ''}")
    return 0 if ok_count == len(results) else 1


def _load_samples(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return DEFAULT_SAMPLES
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("selected_samples"), list):
        payload = payload["selected_samples"]
    if not isinstance(payload, list):
        raise ValueError("samples json must be a list or contain selected_samples list")
    return [dict(item) for item in payload]


def _feature_reason_to_status(reason: Any) -> str:
    reason_text = str(reason or "")
    if "insufficient history" in reason_text:
        return "unavailable_insufficient_history"
    if "unknown encoding" in reason_text:
        return "unavailable_unknown_mapping"
    if "missing required" in reason_text:
        return "prediction_unavailable"
    if "null required" in reason_text:
        return "prediction_unavailable"
    return "prediction_unavailable"


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
