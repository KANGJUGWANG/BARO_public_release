# Submission ZIP File Manifest Plan

## Purpose

This file is a plan, not a generated archive manifest. No ZIP file was created during Phase 3.5-E.

## Planned Top-Level Manifest

```text
BARO_public_release/
  README.md
  README.en.md
  .env.example
  .gitignore
  backend/
  frontend/
  frontend_apk/
  src/
  docs/
  configs/
  pipelines/
  data/
  models/
  outputs/
  requirements.txt
  requirements/
  docker/
  docker-compose.yml
  deploy/
  vercel.json
```

## Pre-ZIP Gate

Before creating an actual archive:

1. Run forbidden file scan.
2. Run large file scan.
3. Confirm no generated build/dependency directories remain.
4. Confirm no generated Gradle cache directories remain.
5. Confirm no private server address, personal path, or real secret value is included.
6. Review `docs/ko/public_security_allowlist.csv`.

## Status

Ready for user review. Actual ZIP creation was not performed.
