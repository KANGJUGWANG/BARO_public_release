from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from backend.ml_inference.oneway_adapter import (
    build_oneway_features,
    load_oneway_models,
    predict_oneway,
)


def _select_sample(df: pd.DataFrame) -> pd.Series:
    work = df.copy()
    work["observed_at_parsed"] = pd.to_datetime(work["observed_at"], errors="coerce")
    work = work.sort_values(["traj_id", "observed_at_parsed"], kind="mergesort")
    work["_available_history_count"] = work.groupby("traj_id").cumcount()
    candidates = work[work["_available_history_count"] >= 6]
    if candidates.empty:
        raise ValueError("No sample row with at least 6 prior rows in the provided CSV")
    return candidates.iloc[0]


def _history_for_sample(df: pd.DataFrame, sample: pd.Series) -> list[dict]:
    same_traj = df[df["traj_id"] == sample["traj_id"]].copy()
    same_traj["observed_at_parsed"] = pd.to_datetime(same_traj["observed_at"], errors="coerce")
    sample_time = pd.to_datetime(sample["observed_at"], errors="coerce")
    history = same_traj[same_traj["observed_at_parsed"] < sample_time].sort_values("observed_at_parsed")
    return history.drop(columns=["observed_at_parsed"]).to_dict(orient="records")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test isolated oneway finaltest inference adapter.")
    parser.add_argument("--feature-csv", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--features-only", action="store_true")
    parser.add_argument(
        "--raw-card-shape",
        action="store_true",
        help="Build the sample offer without route/flight_key to exercise origin/destination and flight_number normalization.",
    )
    parser.add_argument(
        "--strict-feature-compare",
        action="store_true",
        help="Return non-zero when regenerated features differ from the source CSV row.",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.feature_csv)
    sample = _select_sample(df)
    history_rows = _history_for_sample(df, sample)

    if args.features_only:
        artifacts = {
            "feature_columns": json.loads((args.model_dir / "feature_columns.json").read_text(encoding="utf-8")),
            "enc_mappings": json.loads((args.model_dir / "enc_mappings.json").read_text(encoding="utf-8")),
        }
        models = None
    else:
        models, artifacts = load_oneway_models(args.model_dir)

    if args.raw_card_shape:
        offer = {
            "airline_code": sample["airline_code"],
            "flight_number": str(sample["flight_key"]).split("_", 1)[0],
            "departure_date": sample["departure_date"],
            "observed_at": sample["observed_at"],
            "dpd": int(sample["dpd"]),
            "price_krw": int(sample["price_krw"]),
        }
    else:
        offer = {
            "route": sample["route"],
            "airline_code": sample["airline_code"],
            "flight_key": sample["flight_key"],
            "departure_date": sample["departure_date"],
            "observed_at": sample["observed_at"],
            "dpd": int(sample["dpd"]),
            "price_krw": int(sample["price_krw"]),
        }
    request = {
        "origin": str(sample["traj_id"]).split("_")[0],
        "destination": str(sample["traj_id"]).split("_")[1],
        "depart_date": sample["departure_date"],
        "trip_type": "oneway",
    }
    built = build_oneway_features(offer, request, history_rows, pd.to_datetime(sample["observed_at"]).to_pydatetime(), artifacts)
    if built["feature_status"] != "ok":
        print(json.dumps(built, ensure_ascii=False, indent=2))
        return 2

    if args.features_only:
        expected_cols = artifacts["feature_columns"]["oneway"]["stage1"]
        diffs = {}
        for col in expected_cols:
            expected = sample[col]
            actual = built["feature_row"][col]
            if pd.isna(expected) and pd.isna(actual):
                continue
            try:
                if abs(float(expected) - float(actual)) > 1e-9:
                    diffs[col] = {"expected": expected, "actual": actual}
            except (TypeError, ValueError):
                if expected != actual:
                    diffs[col] = {"expected": expected, "actual": actual}
        print(json.dumps({
            "feature_status": "ok",
            "exact_match_to_source_csv": not bool(diffs),
            "diffs": diffs,
            "note": (
                "final feature CSV may not contain early rows dropped during feature export; "
                "strict comparison is optional and requires complete raw history_rows"
            ),
        }, ensure_ascii=False, indent=2, default=str))
        return 1 if diffs and args.strict_feature_compare else 0

    result = predict_oneway(built, models, artifacts)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
