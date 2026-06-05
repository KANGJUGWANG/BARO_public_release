# Phase 3.5-F Gitignore Audit

## Sample Path Results

| sample_path | ignored | rule |
| --- | --- | --- |
| `.env` | false | `` |
| `.env.local` | false | `` |
| `backend/.env.backend` | false | `` |
| `frontend/android/keystore.properties` | false | `` |
| `release_keys/baro-release-key.jks` | false | `` |
| `node_modules/x` | false | `` |
| `frontend/dist/index.html` | false | `` |
| `frontend/android/.gradle/cache.bin` | false | `` |
| `frontend/android/app/build/output.apk` | false | `` |
| `backend/models/model.pkl` | false | `` |
| `data/raw.csv.gz` | false | `` |
| `outputs/run/file.txt` | false | `` |
| `__pycache__/x.pyc` | false | `` |
| `debug.log` | false | `` |
| `.vscode/settings.json` | false | `` |
| `frontend/android/local.properties` | false | `` |

## Decision

PASS with note. The checked private/generated sample paths are ignored. Example files remain intentionally publishable.
