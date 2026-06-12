#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from artifact_common import ArtifactError, EXIT_SUCCESS, load_manifest, print_result, sha256_file, verify_artifact_root, write_state


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Verify BARO reproduction artifacts against a pinned manifest.")
    p.add_argument("--manifest", type=Path, default=None)
    p.add_argument("--artifact-root", type=Path, default=None)
    p.add_argument("--category", default="model")
    p.add_argument("--tier", default=None)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--expected-version", default=None)
    p.add_argument("--expected-source-commit", default=None)
    p.add_argument("--expected-public-commit", default=None)
    p.add_argument("--expected-manifest-sha256", default=None)
    p.add_argument("--write-state", action="store_true")
    p.add_argument("--self-test", action="store_true")
    return p


def run_self_test() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        art = root / "bundle" / "models" / "stage1.bin"
        art.parent.mkdir(parents=True)
        art.write_bytes(b"baro-synthetic-stage1")
        manifest = {
            "schema_version": "synthetic",
            "reproduction_version": "synthetic-c3",
            "source_commit": "f11e8e8",
            "public_commit": "12f5028",
            "artifacts": [
                {"role": "synthetic_stage1", "bundle_path": "models/stage1.bin", "restore_path": "models/stage1.bin", "size_bytes": art.stat().st_size, "sha256": sha256_file(art), "required": True, "category": "model", "status": "ready"},
                {"role": "planned_db", "bundle_path": "database/planned.sql", "restore_path": "database/planned.sql", "size_bytes": 0, "sha256": "0" * 64, "required": False, "category": "database", "status": "planned"},
            ],
        }
        result = verify_artifact_root(manifest, root / "bundle", category="model", strict=True, expected_version="synthetic-c3")
        print_result({"artifact_verification": "PASS", "verified_files": result.verified_files, "verified_bytes": result.verified_bytes, "self_test": "PASS"})
    return EXIT_SUCCESS


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.self_test:
            return run_self_test()
        if not args.artifact_root:
            raise ArtifactError("--artifact-root is required")
        manifest, manifest_sha, manifest_path = load_manifest(args.manifest)
        result = verify_artifact_root(
            manifest,
            args.artifact_root,
            category=args.category,
            tier=args.tier,
            strict=args.strict,
            expected_version=args.expected_version,
            expected_source_commit=args.expected_source_commit,
            expected_public_commit=args.expected_public_commit,
            expected_manifest_sha256=args.expected_manifest_sha256,
            manifest_sha256=manifest_sha,
        )
        if args.write_state:
            write_state(args.artifact_root, manifest, manifest_sha, result, provider="verify", category=args.category, tier=args.tier)
        print_result({"artifact_verification": "PASS", "manifest": manifest_path.name, "verified_files": result.verified_files, "verified_bytes": result.verified_bytes, "skipped": result.skipped, "warnings": result.warnings, "error_code": 0}, args.json_output, args.quiet)
        return EXIT_SUCCESS
    except ArtifactError as exc:
        print_result({"artifact_verification": "FAIL", "error_code": exc.exit_code, "message": str(exc)}, args.json_output)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
