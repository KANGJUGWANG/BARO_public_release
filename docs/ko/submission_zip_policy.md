# Submission ZIP Policy

This document defines how to create a submission ZIP from the BARO public release repository.

## Include

- `README.md`
- `README.en.md`
- `.env.example`
- `.gitignore`
- `backend/`
- `frontend/`
- `frontend_apk/`
- `src/`
- `docs/`
- `configs/`
- `pipelines/`
- `data/README.md`
- `data/sample/`
- `models/README.md`
- `models/.gitkeep`
- `outputs/README.md`
- `outputs/.gitkeep`
- `requirements.txt`
- `requirements/`
- `docker/`
- `docker-compose.yml`
- `deploy/`
- `vercel.json`

## Exclude

- `.git/`
- `.env`
- `.env.*` except approved example files
- `node_modules/`
- `dist/`
- `build/`
- `.venv/`
- `__pycache__/`
- `.gradle/`
- `frontend/android/app/build/`
- `*.pkl`
- `*.parquet`
- `*.csv.gz`
- `*.apk`
- `*.aab`
- `*.jks`
- `*.keystore`
- `keystore.properties`
- `key_note.txt`
- raw DB dumps
- raw training data
- private model artifacts
- production output directories

## Rule

Create the ZIP only after the forbidden file scan and large file scan pass.
