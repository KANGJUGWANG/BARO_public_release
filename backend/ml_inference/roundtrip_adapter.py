from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

BANNED_FEATURE_TOKENS = (
    "cv_pct",
    "saving_pct",
    "label",
    "pred_margin",
    "future_obs_count",
)


def predict_roundtrip(
    feature_row: dict[str, Any],
    models: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    """
    Predict roundtrip BUY/WAIT from a ready-made stage1 feature row.

    This adapter does not build DB history features. It only verifies the
    artifact/model contract for an already prepared feature dict.
    """
    import pandas as pd

    if not feature_row:
        return {
            "feature_status": "prediction_unavailable",
            "unavailable_reason": "empty feature_row",
        }
    if feature_row.get("feature_status") == "prediction_unavailable":
        return feature_row

    actual_row = feature_row.get("feature_row", feature_row)
    banned = [col for col in actual_row if any(token in col for token in BANNED_FEATURE_TOKENS)]
    if banned:
        raise ValueError(f"banned feature columns: {banned}")

    stage1_cols = artifacts.get("stage1_features", [])
    stage2_cols = artifacts.get("stage2_features", [])

    missing_stage1 = [col for col in stage1_cols if col not in actual_row]
    if missing_stage1:
        return {
            "feature_status": "prediction_unavailable",
            "unavailable_reason": f"missing stage1 features: {missing_stage1}",
        }

    stage1_frame = pd.DataFrame([{col: actual_row[col] for col in stage1_cols}])
    pred_saving = float(models["stage1"].predict(stage1_frame)[0])

    stage2_row = dict(actual_row)
    stage2_row["pred_saving"] = pred_saving
    missing_stage2 = [col for col in stage2_cols if col not in stage2_row]
    if missing_stage2:
        return {
            "feature_status": "prediction_unavailable",
            "unavailable_reason": f"missing stage2 features: {missing_stage2}",
        }

    stage2_frame = pd.DataFrame([{col: stage2_row[col] for col in stage2_cols}])
    if hasattr(models["stage2"], "predict_proba"):
        proba = models["stage2"].predict_proba(stage2_frame)
        wait_probability = float(proba[:, 1][0])
    else:
        wait_probability = float(models["stage2"].predict(stage2_frame)[0])

    threshold = float(artifacts.get("threshold", 0.34))
    decision = "WAIT" if wait_probability > threshold else "BUY"
    metadata = artifacts.get("metadata", {})
    model_version = (
        metadata.get("model_version")
        or metadata.get("run_id")
        or "roundtrip_xgb"
    )

    return {
        "feature_status": "ok",
        "decision": decision,
        "pred_saving": pred_saving,
        "wait_probability": wait_probability,
        "threshold": threshold,
        "model_version": model_version,
    }
