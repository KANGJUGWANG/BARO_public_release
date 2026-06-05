# Model Packaging

The backend loads model artifacts through a model directory contract. Actual model files are not included in this public repository.

## Expected Artifact Types

A private model package contains files such as:

- feature column metadata
- encoding mappings
- threshold metadata
- model metadata
- Stage 1 model binary
- Stage 2 model binary

## Final Model Versions

- Oneway: `finaltest_expc_full_final_v1_thr065_oneway`
- Roundtrip: `finaltest_expc_full_final_v1_thr065_roundtrip`

## Public Policy

The `models/` directory in this repository is intentionally empty except for documentation placeholders. Real model binary artifacts must be provided separately in a private environment.

## Backend Loading

The backend expects a configured model directory. In this public repository, use placeholder configuration only.
