# Phase 3.5-E Forbidden File Scan

## Scan Scope

The final scan checked the public release repository for files that must not be published.

Patterns checked:

- Real env files: `.env`, `.env.backend`
- Android signing material: `*.jks`, `*.keystore`, `keystore.properties`, `key_note.txt`
- Private model/data artifacts: `*.pkl`, `*.parquet`, `*.csv.gz`
- Mobile binaries: `*.apk`, `*.aab`
- Generated dependency/build/cache folders: `node_modules`, `dist`, `build`, `.venv`, `__pycache__`, `.gradle`

## Result

- Forbidden files found: 0
- Forbidden generated directories found: 0
- Android Gradle cache status: removed after validation; not part of public release
- Exceptions intentionally allowed: `.env.example`, `configs/backend.env.example`, `frontend/android/keystore.properties.example`

## Decision

The repository passes the forbidden file gate for public review, subject to user review before staging.
