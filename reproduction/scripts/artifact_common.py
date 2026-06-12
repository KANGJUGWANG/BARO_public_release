#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXIT_SUCCESS = 0
EXIT_INVALID = 2
EXIT_MISSING = 3
EXIT_MISMATCH = 4
EXIT_UNSAFE = 5
EXIT_PROVIDER = 6
EXIT_CONFLICT = 7
EXIT_PROMOTION = 8

READY = "ready"
PLANNED = "planned"
OPTIONAL = "optional"
DEPRECATED = "deprecated"
STATE_FILE = ".artifact-state.json"
CHUNK_SIZE = 8 * 1024 * 1024


class ArtifactError(Exception):
    exit_code = EXIT_INVALID

    def __init__(self, message: str, exit_code: int | None = None):
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


@dataclass(frozen=True)
class VerifyResult:
    status: str
    verified_files: int
    verified_bytes: int
    skipped: int
    warnings: list[str]


def reproduction_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_manifest_path() -> Path:
    return reproduction_root() / "config" / "artifact_manifest.template.json"


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ArtifactError(f"json parse failed: {path.name}: {exc}", EXIT_INVALID)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_category(category: str | None) -> str | None:
    if not category:
        return None
    c = category.strip().lower()
    if c in {"model", "models"}:
        return "model"
    if c in {"metadata", "metadatas"}:
        return "metadata"
    if c in {"database", "databases", "db"}:
        return "database"
    if c in {"sample", "samples"}:
        return "sample"
    return c


def ensure_relative_path(value: str, field: str) -> Path:
    if not value:
        raise ArtifactError(f"empty path in {field}", EXIT_UNSAFE)
    raw = value.replace("\\", "/")
    p = Path(raw)
    if p.is_absolute() or ".." in p.parts:
        raise ArtifactError(f"unsafe path in {field}", EXIT_UNSAFE)
    return p


def contained_path(root: Path, relative: str | Path) -> Path:
    rel = ensure_relative_path(str(relative), "relative path")
    base = root.resolve()
    target = (base / rel).resolve(strict=False)
    if base != target and base not in target.parents:
        raise ArtifactError("path escapes root", EXIT_UNSAFE)
    return target


def ensure_no_symlink(path: Path) -> None:
    probe = path
    while True:
        if probe.exists() and probe.is_symlink():
            raise ArtifactError(f"symlink path is not allowed: {probe.name}", EXIT_UNSAFE)
        if probe.parent == probe:
            break
        probe = probe.parent


def load_manifest(path: Path | None = None) -> tuple[dict[str, Any], str, Path]:
    manifest_path = (path or default_manifest_path()).resolve()
    return read_json(manifest_path), sha256_file(manifest_path), manifest_path


def validate_manifest_structure(manifest: dict[str, Any]) -> None:
    for key in ["schema_version", "reproduction_version", "source_commit", "public_commit", "artifacts"]:
        if key not in manifest:
            raise ArtifactError(f"manifest missing {key}", EXIT_INVALID)
    roles: set[str] = set()
    paths: set[str] = set()
    for item in manifest.get("artifacts", []):
        role = item.get("role")
        bundle_path = item.get("bundle_path")
        status = item.get("status", READY)
        if status not in {READY, PLANNED, OPTIONAL, DEPRECATED}:
            raise ArtifactError(f"invalid artifact status: {role}", EXIT_INVALID)
        if role in roles:
            raise ArtifactError(f"duplicate artifact role: {role}", EXIT_INVALID)
        roles.add(role)
        if bundle_path in paths:
            raise ArtifactError(f"duplicate artifact path: {bundle_path}", EXIT_INVALID)
        paths.add(bundle_path)
        ensure_relative_path(str(bundle_path), "bundle_path")
        ensure_relative_path(str(item.get("restore_path", bundle_path)), "restore_path")
        if status == READY:
            if not isinstance(item.get("size_bytes"), int) or item.get("size_bytes") < 0:
                raise ArtifactError(f"invalid size for {role}", EXIT_INVALID)
            if not isinstance(item.get("sha256"), str) or len(item.get("sha256")) != 64:
                raise ArtifactError(f"invalid sha256 for {role}", EXIT_INVALID)


def select_artifacts(manifest: dict[str, Any], category: str | None = None, tier: str | None = None, include_optional: bool = True) -> list[dict[str, Any]]:
    target_category = normalize_category(category)
    selected: list[dict[str, Any]] = []
    for item in manifest.get("artifacts", []):
        status = item.get("status", READY)
        if status in {PLANNED, DEPRECATED}:
            continue
        if status == OPTIONAL and not include_optional:
            continue
        item_cat = normalize_category(str(item.get("category", "")))
        if target_category and target_category not in {item_cat, "all"}:
            continue
        selected.append(item)
    return selected


def find_unexpected_files(root: Path, allowed_relative_paths: set[str]) -> list[str]:
    unexpected: list[str] = []
    if not root.exists():
        return unexpected
    for p in root.rglob("*"):
        if not p.is_file() or p.name == STATE_FILE:
            continue
        rel = p.relative_to(root).as_posix()
        if rel not in allowed_relative_paths:
            unexpected.append(rel)
    return unexpected


def verify_artifact_root(
    manifest: dict[str, Any],
    artifact_root: Path,
    category: str | None = None,
    tier: str | None = None,
    strict: bool = False,
    expected_version: str | None = None,
    expected_source_commit: str | None = None,
    expected_public_commit: str | None = None,
    expected_manifest_sha256: str | None = None,
    manifest_sha256: str | None = None,
) -> VerifyResult:
    validate_manifest_structure(manifest)
    if expected_version and manifest.get("reproduction_version") != expected_version:
        raise ArtifactError("reproduction version mismatch", EXIT_INVALID)
    if expected_source_commit and manifest.get("source_commit") != expected_source_commit:
        raise ArtifactError("source commit mismatch", EXIT_INVALID)
    if expected_public_commit and manifest.get("public_commit") != expected_public_commit:
        raise ArtifactError("public commit mismatch", EXIT_INVALID)
    if expected_manifest_sha256 and manifest_sha256 and expected_manifest_sha256 != manifest_sha256:
        raise ArtifactError("manifest sha256 mismatch", EXIT_INVALID)
    root = artifact_root.resolve(strict=False)
    if root.exists() and root.is_symlink():
        raise ArtifactError("artifact root symlink is not allowed", EXIT_UNSAFE)
    warnings: list[str] = []
    verified_files = 0
    verified_bytes = 0
    skipped = 0
    allowed_paths: set[str] = set()
    for item in select_artifacts(manifest, category=category, tier=tier):
        status = item.get("status", READY)
        rel = ensure_relative_path(item["bundle_path"], "bundle_path")
        allowed_paths.add(rel.as_posix())
        path = contained_path(root, rel)
        ensure_no_symlink(path)
        if not path.exists():
            if status == OPTIONAL or not item.get("required", False):
                warnings.append(f"optional missing: {item.get('role')}")
                skipped += 1
                continue
            raise ArtifactError(f"required artifact missing: {item.get('role')}", EXIT_MISSING)
        if not path.is_file():
            raise ArtifactError(f"artifact is not a file: {item.get('role')}", EXIT_UNSAFE)
        size = path.stat().st_size
        if size != item.get("size_bytes"):
            raise ArtifactError(f"size mismatch: {item.get('role')}", EXIT_MISMATCH)
        digest = sha256_file(path)
        if digest != item.get("sha256"):
            raise ArtifactError(f"sha256 mismatch: {item.get('role')}", EXIT_MISMATCH)
        verified_files += 1
        verified_bytes += size
    if strict:
        unexpected = find_unexpected_files(root, allowed_paths)
        if unexpected:
            raise ArtifactError("unexpected files: " + ",".join(unexpected[:5]), EXIT_UNSAFE)
    return VerifyResult("PASS", verified_files, verified_bytes, skipped, warnings)


def write_state(artifact_root: Path, manifest: dict[str, Any], manifest_sha256: str, result: VerifyResult, provider: str, category: str | None = None, tier: str | None = None) -> None:
    write_json(
        artifact_root / STATE_FILE,
        {
            "reproduction_version": manifest.get("reproduction_version"),
            "manifest_sha256": manifest_sha256,
            "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "verified_files": result.verified_files,
            "verified_total_bytes": result.verified_bytes,
            "provider": provider,
            "category": category,
            "tier": tier,
            "source_commit": manifest.get("source_commit"),
            "public_commit": manifest.get("public_commit"),
            "verification_tool_version": "phase3.6-c3",
        },
    )


def copy_manifest_files(source_root: Path, dest_root: Path, manifest: dict[str, Any], category: str | None = None, tier: str | None = None) -> int:
    copied = 0
    for item in select_artifacts(manifest, category=category, tier=tier):
        rel = ensure_relative_path(item["bundle_path"], "bundle_path")
        src = contained_path(source_root, rel)
        dst = contained_path(dest_root, rel)
        ensure_no_symlink(src)
        if not src.exists():
            raise ArtifactError(f"source artifact missing: {item.get('role')}", EXIT_MISSING)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied


def partial_root_for(destination: Path, version: str) -> Path:
    return destination.parent / ".partial" / f"{version}-{int(time.time())}"


def promote_partial(partial: Path, destination: Path, replace: bool = False) -> None:
    if destination.exists():
        if not replace:
            raise ArtifactError("destination exists; use --replace", EXIT_CONFLICT)
        backup = destination.with_name(destination.name + f".previous-{int(time.time())}")
        try:
            destination.replace(backup)
        except Exception as exc:
            raise ArtifactError(f"failed to move existing destination: {exc}", EXIT_PROMOTION)
    try:
        partial.replace(destination)
    except Exception as exc:
        raise ArtifactError(f"atomic promotion failed: {exc}", EXIT_PROMOTION)


def safe_extract_zip(zip_path: Path, dest_root: Path, allowed_paths: set[str], max_uncompressed_bytes: int = 3 * 1024 * 1024 * 1024) -> None:
    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            rel = ensure_relative_path(name, "zip entry")
            if name.endswith("/"):
                continue
            if rel.as_posix() not in allowed_paths:
                raise ArtifactError(f"zip contains unregistered file: {name}", EXIT_UNSAFE)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ArtifactError("zip symlink entry is not allowed", EXIT_UNSAFE)
            total += info.file_size
            if total > max_uncompressed_bytes:
                raise ArtifactError("zip uncompressed size limit exceeded", EXIT_UNSAFE)


def print_result(payload: dict[str, Any], json_output: bool = False, quiet: bool = False) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    if quiet:
        return
    for key, value in payload.items():
        if isinstance(value, (list, dict)):
            print(f"{key}={json.dumps(value, ensure_ascii=False)}")
        else:
            print(f"{key}={value}")
