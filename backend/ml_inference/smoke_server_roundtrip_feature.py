"""Build a DB-backed roundtrip feature row and optionally run model smoke.

Run from backend/:
    python -m ml_inference.smoke_server_roundtrip_feature
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and smoke-test a DB-backed roundtrip feature row.")
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--min-total-rows", type=int, default=7)
    parser.add_argument("--history-limit", type=int, default=240)
    parser.add_argument("--skip-predict", action="store_true")
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()

    from core.db import close_pool, create_pool, get_pool
    from ml_inference.model_runtime import (
        load_roundtrip_artifacts,
        load_roundtrip_runtime,
        predict_roundtrip_from_feature,
    )
    from ml_inference.roundtrip_feature_builder import (
        build_roundtrip_features,
        fetch_roundtrip_history_rows,
        select_roundtrip_sample,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    feature_path = args.out_dir / "phase_7_5_roundtrip_feature_sample.json"
    meta_path = args.out_dir / "phase_7_5_roundtrip_feature_sample_meta.json"
    result_path = args.out_dir / "phase_7_5_roundtrip_smoke_result.json"

    artifacts = load_roundtrip_artifacts(args.model_dir)
    if artifacts.get("status") != "ok":
        print(json.dumps(artifacts, indent=2, ensure_ascii=False, default=str))
        return 2

    await create_pool()
    pool = get_pool()
    try:
        if pool is None:
            print("db pool unavailable")
            return 2

        sample = await select_roundtrip_sample(pool, min_total_rows=args.min_total_rows)
        if not sample:
            print("no roundtrip sample with sufficient history")
            return 1

        rows = await fetch_roundtrip_history_rows(
            origin=sample["origin"],
            destination=sample["destination"],
            departure_date=sample["departure_date"],
            return_date=sample["return_date"],
            stay_nights=sample["stay_nights"],
            flight_number=sample["flight_number"],
            ret_flight_number=sample["ret_flight_number"],
            pool=pool,
            limit=args.history_limit,
        )
        if len(rows) < args.min_total_rows:
            print(f"insufficient fetched rows: {len(rows)}")
            return 1

        current = rows[-1]
        history_rows = rows[:-1]
        request = {
            "origin": sample["origin"],
            "destination": sample["destination"],
            "depart_date": sample["departure_date"],
            "departure_date": sample["departure_date"],
            "return_date": sample["return_date"],
            "trip_type": "roundtrip",
        }
        offer = {
            **current,
            "origin": sample["origin"],
            "destination": sample["destination"],
        }

        built = build_roundtrip_features(
            offer=offer,
            request=request,
            history_rows=history_rows,
            now=datetime.now(),
            artifacts=artifacts,
        )
        if built.get("feature_status") != "ok":
            payload = {
                "sample": sample,
                "history_row_count": len(history_rows),
                "build_result": built,
            }
            meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
            return 1

        feature_row = built["feature_row"]
        expected_cols = artifacts.get("stage1_features", [])
        order_ok = list(feature_row.keys()) == expected_cols
        feature_path.write_text(json.dumps(feature_row, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        meta = {
            "sample": sample,
            "current_row": current,
            "history_row_count": len(history_rows),
            "total_rows_used": len(rows),
            "feature_path": str(feature_path),
            "feature_count": len(feature_row),
            "expected_stage1_features": expected_cols,
            "feature_order_ok": order_ok,
            "builder_metadata": built.get("metadata", {}),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        result = None
        if not args.skip_predict:
            runtime = load_roundtrip_runtime(args.model_dir)
            result = predict_roundtrip_from_feature(feature_row, runtime)
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        summary = {
            "feature_path": str(feature_path),
            "meta_path": str(meta_path),
            "result_path": str(result_path) if result is not None else None,
            "feature_count": len(feature_row),
            "feature_order_ok": order_ok,
            "prediction_status": result.get("prediction_status") if result else None,
            "decision": result.get("decision") if result else None,
            "ret_flight_enc_policy": built.get("metadata", {}).get("ret_flight_enc_policy"),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
        return 0 if order_ok and (args.skip_predict or result.get("prediction_status") == "ok") else 1
    finally:
        await close_pool()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
