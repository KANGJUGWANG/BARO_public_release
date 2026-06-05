# BARO Pipelines

This directory documents the public, reproducibility-oriented view of the BARO pipeline. It does not include private datasets, production model artifacts, credentials, or production deployment values.

## End-to-end Flow

1. Collect flight observations
2. Normalize flight offers
3. Store search and offer observations
4. Materialize a frozen dataset
5. Build features and labels
6. Train Stage 1 models
7. Generate `pred_saving`
8. Train Stage 2 models
9. Sweep and select thresholds
10. Package model artifacts
11. Smoke test backend runtime
12. Serve backend APIs and frontend UI

## Public Repository Scope

Available in this repository:

- Public source structure
- Backend and frontend code
- Pipeline documentation
- Example configs
- Synthetic sample rows
- Model/output directory policy

Not included:

- Production database
- Training datasets
- Model binary artifacts
- Private credentials
- Production endpoint values

## Subdirectories

- [crawler](crawler/README.md): observation collection and parser flow
- [dataset](dataset/README.md): storage, freeze dataset, feature/label flow
- [training](training/README.md): Stage 1 / Stage 2 training concept
- [packaging](packaging/README.md): model artifact contract
- [smoke](smoke/README.md): public-safe validation scope
