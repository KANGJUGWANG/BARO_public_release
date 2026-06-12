# BARO Reproduction Package

This directory contains the public reproduction scaffold for BARO. It keeps private runtime artifacts outside Git while documenting how a reviewer can restore and verify them.

## Implemented through Phase 3.6-C4.2

- Contract/schema files for the reproduction bundle.
- Docker core topology for frontend, backend, and MySQL.
- Docker image build/runtime smoke coverage.
- Artifact provider contract with four providers: `already-present`, `manual-copy`, `rclone-private`, and `public-drive`.
- `verify_artifacts.py` for manifest-based size/SHA/version/commit verification.
- `fetch_artifacts.py` for `already-present`, `manual-copy`, and safe `rclone-private` command construction/execution.
- Thin PowerShell and POSIX shell wrappers.
- `baro-artifact-check` Compose tools service, isolated from the network and mounted read-only.

## Not implemented yet

- Actual Google Drive release upload.
- Actual 1.9GB model fetch from Drive.
- DB snapshot export and restore.
- DB init/smoke services.
- Full `local-full` end-to-end compose startup.
- Predict/analyze runtime smoke with restored DB/model artifacts.

## Verify artifacts

```powershell
python .\reproduction\scripts\verify_artifacts.py `
  --manifest .\reproduction\config\artifact_manifest.template.json `
  --artifact-root .\reproduction\artifacts\extracted\baro-repro-12f5028-r1 `
  --category models `
  --strict
```

## Manual copy provider

```powershell
python .\reproduction\scripts\fetch_artifacts.py `
  --provider manual-copy `
  --source <LOCAL_BUNDLE_SOURCE> `
  --destination .\reproduction\artifacts\extracted\baro-repro-12f5028-r1 `
  --category models
```

Only manifest-listed files are copied. The destination is promoted only after size and SHA-256 verification succeeds.

## Already-present provider

```powershell
python .\reproduction\scripts\fetch_artifacts.py `
  --provider already-present `
  --destination .\reproduction\artifacts\extracted\baro-repro-12f5028-r1 `
  --manifest .\reproduction\config\artifact_manifest.template.json `
  --category models
```

## Rclone private provider

`rclone-private` is the default provider contract. Configure rclone outside this repository. The CLI uses subprocess list arguments and does not store rclone config or tokens in Git.

Planning without network execution:

```powershell
python .\reproduction\scripts\fetch_artifacts.py `
  --provider rclone-private `
  --source "<RCLONE_REMOTE>:<RELEASE_PATH>" `
  --destination .\reproduction\artifacts\extracted\baro-repro-12f5028-r1 `
  --category models `
  --plan
```

## Artifact check service

```powershell
docker compose --env-file <TEMP_VALIDATION_ENV> -f .\reproduction\compose.yaml --profile tools run --rm baro-artifact-check
```

The tools service has no network, no published ports, `cap_drop: ALL`, and read-only artifact/config/script mounts.

## Security boundary

Do not commit `.env.repro`, rclone config, model binaries, DB snapshots, archives, private URLs, credentials, or restored artifacts. Runtime artifact directories are ignored by Git and excluded from Docker build context.


## DB snapshot pipeline

Phase 3.6-C4 adds a sanitized DB snapshot contract and tools:

- `reproduction/database/schema.sql`
- `reproduction/database/snapshot_tiers.json`
- `export_db_snapshot.py`
- `verify_db_snapshot.py`
- `restore_db_snapshot.py`
- `baro-db-init` one-shot Compose service

C4.2 validates the actual production sanitized `minimal-repro` snapshot through server export evidence, local deep verification, isolated MySQL 8.4 clean restore, and idempotent rerun.

## C4.2 official minimal DB snapshot baseline

The official DB reproduction baseline for project closure is `minimal-repro`.

- Snapshot version: `minimal-c4-1r4h`
- Tables: `search_observation`, `flight_offer_observation`
- Rows: 80 search rows, 6,133 offer rows, 6,213 total rows
- Coverage: one-way and round-trip selectors
- Selection fingerprint: `707c677d5aa49ad6b4b72a5d9b8797468e1e0809b90e1621fb42a01cc9dc76af`
- Operating DB write: none; export used `START TRANSACTION READ ONLY`
- Server deep verification: PASS
- Local deep verification: PASS
- Isolated MySQL 8.4 clean restore: PASS
- Idempotent second restore: PASS
- MySQL host port: unpublished in restore validation
- `seller_domain`: exported as `null` in the snapshot only

`extended-repro` was not generated and is not required for project closure. Actual snapshot files are not committed to Git; they are provided through the private Drive/artifact bundle.

When running Compose from Windows or an external working directory, pass the public repository root explicitly:

```powershell
docker compose `
  --project-directory "$PublicRepo" `
  --env-file "$EnvFile" `
  -p "$Project" `
  -f "$PublicRepo\reproduction\compose.yaml" `
  up -d baro-mysql
```

Using only `-f reproduction/compose.yaml` from another directory can make relative mounts resolve incorrectly.

## Model bundle path contract

The private bundle stores active runtime model artifacts under models/baro-runtime-v1. Set MODEL_BUNDLE_SUBDIR=baro-runtime-v1; Compose mounts that directory to /app/runtime/models:ro. The legacy server directory name is intentionally not used in the private bundle layout.
