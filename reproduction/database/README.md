# BARO Sanitized DB Snapshot Contract

Schema version: `baro-repro-db-v1`

This directory defines the sanitized database snapshot pipeline for public reproduction. It does not contain a real database dump.

## Bounded export policy

All exports require a machine-readable bounded tier selector from `snapshot_tiers.json`.

- `--plan` and actual export use the same compiled selector and fingerprint.
- Preflight performs exact count queries before export.
- Search rows, linked offer rows, optional rows, total rows, uncompressed bytes, and compressed bytes are limited by tier safety limits.
- Actual export rechecks row and byte limits while streaming.
- Full table export is not supported.
- Arbitrary SQL input is not supported.
- Empty selectors, wildcard routes, invalid route/date contracts, and unsafe limits are rejected.
- Operating DB actual export is only allowed in a later C4.1R user-executed step after this hotfix validation.

## Tables

- Required: `search_observation`, `flight_offer_observation`
- Optional: `service_route_analysis_snapshot`
- Excluded: auth/user/token/session/bookmark/settings/raw capture tables

## Sanitization

- `search_observation.search_url` is exported as `<REDACTED_SEARCH_URL>`.
- `search_observation.raw_file_path` is exported as `null`.
- Private host/IP/path patterns are rejected during verification.


## Seller domain sanitization

`seller_domain` is retained as a nullable column in the canonical snapshot schema, but exported snapshot rows always set `seller_domain` to `null`. The exporter does not normalize hostnames and does not preserve original URLs. Deep verification rejects non-null `flight_offer_observation.seller_domain` values.

## Format

Snapshots use UTF-8 gzip JSON Lines with one JSON object per row.

Expected layout:

```text
database/<tier>/
  snapshot_manifest.json
  schema.sql
  search_observation.jsonl.gz
  flight_offer_observation.jsonl.gz
  service_route_analysis_snapshot.jsonl.gz
```




## Source and snapshot column contracts

`SOURCE_TABLE_COLUMNS` follows the operating DB projection used by the service. `SNAPSHOT_TABLE_COLUMNS` defines the sanitized reproduction JSONL/restore schema. R4 keeps them explicit so source SQL never projects columns that do not exist in production.

For `flight_offer_observation`, route/date fields are inherited through `observation_id` from `search_observation`; the offer source projection does not read `route_type`, `origin_iata`, `destination_iata`, `departure_date`, `return_date`, or `is_direct` from `f.*`.

For `service_route_analysis_snapshot`, optional bounded selection uses `route_type`, `origin_iata`, `destination_iata`, and `stay_nights`; it does not reference `return_date`.

## Source schema compatibility

The canonical primary key for `flight_offer_observation` is `offer_observation_id`.

Before exact count preflight or export, the exporter checks required source columns through `information_schema.columns` in a read-only session. If required source columns are missing, the CLI returns a sanitized `schema_contract_mismatch` failure without printing SQL text, DB host/name, credentials, traceback paths, or row data.
## DB driver compatibility

The exporter supports `--db-driver auto`, `--db-driver aiomysql`, and `--db-driver pymysql`.

- `auto` prefers `aiomysql` when available and falls back to `pymysql`.
- `pymysql` uses `pymysql.cursors.SSCursor` and `fetchmany()` for streaming reads.
- Both driver paths use the same bounded selector compiler, exact preflight, fingerprint, and runtime safety limits.
- Source sessions are opened with `START TRANSACTION READ ONLY`; export tools must not write to the source database.
- Production C4.1R2 execution uses the existing `capstone-loader` container and maps its `MYSQL_*` variables to `BARO_EXPORT_DB_*` inside the container without printing secret values.
## Status

C4.2 closes the actual `minimal-repro` DB snapshot baseline. Future bundle assembly should reference the private artifact bundle instead of committing snapshot files.

## Official closure snapshot

The official DB reproduction snapshot for project closure is `minimal-repro`.

- Snapshot version: `minimal-c4-1r4h`
- Required tables: `search_observation`, `flight_offer_observation`
- Optional table `service_route_analysis_snapshot`: not included in the minimal bundle
- Search rows: 80
- Offer rows: 6,133
- Total rows: 6,213
- Selector coverage: one-way and round-trip
- Selection fingerprint: `707c677d5aa49ad6b4b72a5d9b8797468e1e0809b90e1621fb42a01cc9dc76af`
- Server and local deep verification: PASS
- Isolated MySQL 8.4 clean restore: PASS
- Idempotent second restore: PASS
- Operating DB write: none
- Snapshot storage: private Drive/artifact bundle, not Git

`extended-repro` was not generated and is not required for project closure.