# Oneway Finaltest Inference Adapter

This module isolates inference logic for the BARO finaltest oneway service model.

It intentionally does not import the full training or evaluation pipeline. The adapter expects:

- finaltest service model artifacts under `MODEL_DIR`
- `enc_mappings.json` generated from the finaltest oneway feature CSV
- DB-provided `history_rows` for the same oneway trajectory

The current `/flights/search` crawler card alone is not enough for model inference because Stage1 requires trajectory history features such as `cum_*` and `price_chg_*`.

Required artifacts:

- `feature_columns.json`
- `oneway_threshold.json`
- `final_model_metadata.json`
- `enc_mappings.json`
- `oneway_stage1_random_forest.pkl`
- `oneway_stage2_xgboost.pkl`

Generate encoding mappings:

```powershell
python -m backend.ml_inference.build_enc_mappings `
  --source-csv finaltest_clean_v1\data\final_test\oneway_features_final_clean_v1.csv `
  --out finaltest_clean_v1\outputs\final_test_clean_v1\model_artifacts\enc_mappings.json
```

Feature-only smoke check:

```powershell
python -m backend.ml_inference.smoke_oneway `
  --feature-csv finaltest_clean_v1\data\final_test\oneway_features_final_clean_v1.csv `
  --model-dir finaltest_clean_v1\outputs\final_test_clean_v1\model_artifacts `
  --features-only
```

Raw-card normalization smoke check:

```powershell
python -m backend.ml_inference.smoke_oneway `
  --feature-csv finaltest_clean_v1\data\final_test\oneway_features_final_clean_v1.csv `
  --model-dir finaltest_clean_v1\outputs\final_test_clean_v1\model_artifacts `
  --raw-card-shape
```

Prediction smoke check requires `.pkl` files to be reachable from `MODEL_DIR`.
