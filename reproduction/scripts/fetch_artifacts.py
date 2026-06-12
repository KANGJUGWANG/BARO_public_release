#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from artifact_common import ArtifactError, EXIT_INVALID, EXIT_PROVIDER, EXIT_SUCCESS, copy_manifest_files, load_manifest, partial_root_for, print_result, promote_partial, verify_artifact_root, write_state

PROVIDERS = {"already-present", "manual-copy", "rclone-private", "public-drive"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fetch BARO reproduction artifacts using a declared provider.")
    p.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    p.add_argument("--source", default=None)
    p.add_argument("--destination", type=Path, required=True)
    p.add_argument("--manifest", type=Path, default=None)
    p.add_argument("--category", default="model")
    p.add_argument("--tier", default=None)
    p.add_argument("--expected-version", default=None)
    p.add_argument("--expected-manifest-sha256", default=None)
    p.add_argument("--replace", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--discard-partial", action="store_true")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--quiet", action="store_true")
    return p


def try_verified(destination: Path, manifest: dict, manifest_sha: str, args) -> bool:
    if not destination.exists():
        return False
    try:
        verify_artifact_root(manifest, destination, category=args.category, tier=args.tier, strict=True, expected_version=args.expected_version, expected_manifest_sha256=args.expected_manifest_sha256, manifest_sha256=manifest_sha)
        return True
    except ArtifactError:
        return False


def do_already_present(args, manifest, manifest_sha) -> int:
    result = verify_artifact_root(manifest, args.destination, category=args.category, tier=args.tier, strict=True, expected_version=args.expected_version, expected_manifest_sha256=args.expected_manifest_sha256, manifest_sha256=manifest_sha)
    write_state(args.destination, manifest, manifest_sha, result, provider="already-present", category=args.category, tier=args.tier)
    print_result({"artifact_fetch": "PASS_ALREADY_PRESENT", "provider": "already-present", "verified_files": result.verified_files, "verified_bytes": result.verified_bytes, "skipped": False, "warnings": result.warnings, "error_code": 0}, args.json_output, args.quiet)
    return EXIT_SUCCESS


def do_manual_copy(args, manifest, manifest_sha) -> int:
    if not args.source:
        raise ArtifactError("--source is required for manual-copy", EXIT_INVALID)
    source = Path(args.source).resolve()
    if not source.exists() or source.is_symlink():
        raise ArtifactError("manual source is missing or unsafe", EXIT_INVALID)
    if try_verified(args.destination, manifest, manifest_sha, args) and not args.replace:
        print_result({"artifact_fetch": "SKIPPED_ALREADY_VERIFIED", "provider": "manual-copy", "skipped": True, "error_code": 0}, args.json_output, args.quiet)
        return EXIT_SUCCESS
    if args.destination.exists() and not args.replace:
        raise ArtifactError("destination exists but is not verified; use --replace", 7)
    partial = partial_root_for(args.destination, manifest.get("reproduction_version", "bundle"))
    if partial.exists() and args.discard_partial:
        shutil.rmtree(partial)
    partial.mkdir(parents=True, exist_ok=True)
    copied = copy_manifest_files(source, partial, manifest, category=args.category, tier=args.tier)
    result = verify_artifact_root(manifest, partial, category=args.category, tier=args.tier, strict=True, expected_version=args.expected_version, expected_manifest_sha256=args.expected_manifest_sha256, manifest_sha256=manifest_sha)
    write_state(partial, manifest, manifest_sha, result, provider="manual-copy", category=args.category, tier=args.tier)
    promote_partial(partial, args.destination, replace=args.replace)
    print_result({"artifact_fetch": "PASS", "provider": "manual-copy", "copied_files": copied, "verified_files": result.verified_files, "verified_bytes": result.verified_bytes, "skipped": False, "error_code": 0}, args.json_output, args.quiet)
    return EXIT_SUCCESS


def rclone_command_plan(source: str, destination: Path, manifest: dict, args) -> list[list[str]]:
    commands: list[list[str]] = []
    category = args.category.rstrip("s") if args.category else None
    for item in manifest.get("artifacts", []):
        if item.get("status", "ready") != "ready":
            continue
        if category and item.get("category") not in {category, args.category}:
            continue
        rel = item["bundle_path"].replace("\\", "/")
        commands.append(["rclone", "copyto", f"{source.rstrip('/')}/{rel}", str(destination / rel), "--retries", "3", "--low-level-retries", "5", "--stats-one-line"])
    return commands


def do_rclone(args, manifest, manifest_sha) -> int:
    if not args.source:
        raise ArtifactError("--source is required for rclone-private", EXIT_INVALID)
    commands = rclone_command_plan(args.source, args.destination, manifest, args)
    if args.plan:
        print_result({"artifact_fetch": "PLAN", "provider": "rclone-private", "commands": len(commands), "command_names": [c[0:2] for c in commands], "error_code": 0}, args.json_output, args.quiet)
        return EXIT_SUCCESS
    if shutil.which("rclone") is None:
        raise ArtifactError("rclone_not_found", EXIT_PROVIDER)
    partial = partial_root_for(args.destination, manifest.get("reproduction_version", "bundle"))
    partial.mkdir(parents=True, exist_ok=True)
    for command in rclone_command_plan(args.source, partial, manifest, args):
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False, timeout=3600)
        if completed.returncode != 0:
            raise ArtifactError("rclone command failed; output suppressed", EXIT_PROVIDER)
    result = verify_artifact_root(manifest, partial, category=args.category, tier=args.tier, strict=True, expected_version=args.expected_version, expected_manifest_sha256=args.expected_manifest_sha256, manifest_sha256=manifest_sha)
    write_state(partial, manifest, manifest_sha, result, provider="rclone-private", category=args.category, tier=args.tier)
    promote_partial(partial, args.destination, replace=args.replace)
    print_result({"artifact_fetch": "PASS", "provider": "rclone-private", "verified_files": result.verified_files, "verified_bytes": result.verified_bytes, "error_code": 0}, args.json_output, args.quiet)
    return EXIT_SUCCESS


def main() -> int:
    args = parser().parse_args()
    try:
        manifest, manifest_sha, _ = load_manifest(args.manifest)
        if args.provider == "already-present":
            return do_already_present(args, manifest, manifest_sha)
        if args.provider == "manual-copy":
            return do_manual_copy(args, manifest, manifest_sha)
        if args.provider == "rclone-private":
            return do_rclone(args, manifest, manifest_sha)
        raise ArtifactError("public-drive is contract_only in C3", EXIT_PROVIDER)
    except ArtifactError as exc:
        print_result({"artifact_fetch": "FAIL", "provider": args.provider if "args" in locals() else None, "error_code": exc.exit_code, "message": str(exc)}, json_output=getattr(args, "json_output", False))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
