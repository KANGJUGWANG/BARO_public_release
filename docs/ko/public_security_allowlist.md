# Public Security Allowlist

Phase 3.5-E ran a broad keyword scan over the public release repository. The scan intentionally catches symbolic environment variable names, HTTP header names, and documentation terms. These are not automatically removal targets.

## Classification Policy

- `ALLOW_ENV_PLACEHOLDER`: example config placeholders only
- `ALLOW_CODE_IDENTIFIER`: source code identifiers, environment variable names, standard HTTP header names, or runtime contract names
- `ALLOW_DOC_EXPLANATION`: documentation that describes security boundaries or redaction rules
- `ALLOW_LOCKFILE_HASH`: dependency lockfile integrity hash false positive
- `REMOVE_REQUIRED`: real secret, real server address, personal path, or private artifact reference

## Result

- `REMOVE_REQUIRED`: 0
- Real secret values found: none
- Production server addresses found: none
- Personal local paths found: none
- Private model artifacts found: none

## Notes

The public repository keeps symbolic configuration names because they are required for source readability and local setup. Runtime contract names are not secrets by themselves. Future cleanup should continue to block real values while allowing placeholders and code identifiers.

See `docs/ko/public_security_allowlist.csv` for row-level classification.
