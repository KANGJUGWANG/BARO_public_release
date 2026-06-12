# BARO Reproduction Artifacts

This directory is intentionally empty in Git except for documentation.

Expected runtime layout after an external artifact provider restores files:

```text
artifacts/
  extracted/<ARTIFACT_BUNDLE_VERSION>/
    models/baro-runtime-v1/...
    .artifact-state.json
  downloads/
  .partial/
```

Rules:

- Do not commit model binaries, DB snapshots, archives, or downloaded manifests.
- `verify_artifacts.py` is the source of truth for size and SHA-256 validation.
- `fetch_artifacts.py` promotes a bundle only after verification succeeds.
- Partial downloads remain under ignored `.partial/` paths until explicitly resumed or discarded.
- Private rclone config and tokens must live outside the repository.

Runtime model path contract: set `MODEL_BUNDLE_SUBDIR=baro-runtime-v1`. Compose mounts `${ARTIFACT_ROOT}/${ARTIFACT_BUNDLE_VERSION}/models/${MODEL_BUNDLE_SUBDIR}` to `/app/runtime/models:ro`.
