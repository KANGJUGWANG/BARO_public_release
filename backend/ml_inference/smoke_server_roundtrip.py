"""Roundtrip model smoke test.

Run from backend/:
    python -m ml_inference.smoke_server_roundtrip --artifact-only
    python -m ml_inference.smoke_server_roundtrip --feature-json /tmp/rt_feature.json

Default mode uses a zero-filled synthetic row. That verifies model/feature
shape compatibility only; the prediction has no recommendation meaning.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test roundtrip XGB/XGB artifacts.")
    parser.add_argument("--artifact-only", action="store_true")
    parser.add_argument("--feature-json", type=Path, default=None)
    parser.add_argument("--model-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from ml_inference.model_runtime import (
        load_roundtrip_artifacts,
        load_roundtrip_runtime,
        predict_roundtrip_from_feature,
    )

    artifacts = load_roundtrip_artifacts(args.model_dir)
    print(json.dumps(_artifact_summary(artifacts), indent=2, ensure_ascii=False, default=str))
    if artifacts.get("status") != "ok":
        return 2

    if args.artifact_only:
        print("\nartifact-only smoke done")
        return 0

    runtime = load_roundtrip_runtime(args.model_dir)
    if runtime.get("status") != "ok":
        print(json.dumps(runtime, indent=2, ensure_ascii=False, default=str))
        return 2

    print(f"\nmodels loaded in {runtime.get('load_seconds', '?')}s")
    stage1 = runtime["models"]["stage1"]
    stage2 = runtime["models"]["stage2"]
    print("stage1 n_features_in_:", getattr(stage1, "n_features_in_", None))
    print("stage2 n_features_in_:", getattr(stage2, "n_features_in_", None))

    _warn_feature_count_mismatch(artifacts, stage1, stage2)

    if args.feature_json:
        try:
            feature_row = json.loads(args.feature_json.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - smoke output should carry reason.
            print("feature-json read failed:", exc)
            return 2
    else:
        print("\ngenerating synthetic feature row (shape smoke only)")
        print("note: zero-filled synthetic row has no recommendation meaning")
        feature_row = {col: 0.0 for col in artifacts.get("stage1_features", [])}

    result = predict_roundtrip_from_feature(feature_row, runtime)
    print("\nsmoke result:")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("prediction_status") == "ok" else 1


def _artifact_summary(artifacts: dict) -> dict:
    enc_mappings = artifacts.get("enc_mappings") or {}
    mappings = enc_mappings.get("mappings", enc_mappings) if isinstance(enc_mappings, dict) else {}
    mapping_keys = list(mappings.keys()) if isinstance(mappings, dict) else []
    watched_mapping_counts = {}
    for key in (
        "route",
        "route_enc",
        "route_pair",
        "route_pair_enc",
        "airline",
        "airline_enc",
        "flight",
        "flight_enc",
        "ret_flight",
        "ret_flight_enc",
        "return_flight",
        "return_flight_enc",
    ):
        if isinstance(mappings, dict) and key in mappings:
            value = mappings[key]
            watched_mapping_counts[key] = len(value) if hasattr(value, "__len__") else None

    return {
        "status": artifacts.get("status"),
        "model_dir": artifacts.get("model_dir"),
        "reason": artifacts.get("reason"),
        "stage1_features": len(artifacts.get("stage1_features", [])),
        "stage2_features": len(artifacts.get("stage2_features", [])),
        "stage2_feature_names": artifacts.get("stage2_features", []),
        "threshold": artifacts.get("threshold"),
        "enc_mapping_keys": mapping_keys,
        "watched_mapping_counts": watched_mapping_counts,
    }


def _warn_feature_count_mismatch(artifacts: dict, stage1, stage2) -> None:
    expected_s1 = len(artifacts.get("stage1_features", []))
    expected_s2 = len(artifacts.get("stage2_features", []))
    actual_s1 = getattr(stage1, "n_features_in_", None)
    actual_s2 = getattr(stage2, "n_features_in_", None)

    if actual_s1 is not None and actual_s1 != expected_s1:
        print(f"WARNING: stage1 feature mismatch: feature_columns={expected_s1}, model={actual_s1}")
    if actual_s2 is not None and actual_s2 != expected_s2:
        print(f"WARNING: stage2 feature mismatch: feature_columns={expected_s2}, model={actual_s2}")


if __name__ == "__main__":
    sys.exit(main())
