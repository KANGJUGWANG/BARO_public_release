#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

EXPECTED_SOURCE = "f11e8e8"
EXPECTED_PUBLIC = "12f5028"
EXPECTED_TOTAL_SIZE = 1984585323
EXPECTED_ROLES = {"oneway_stage1_model", "oneway_stage2_model", "roundtrip_stage1_model", "roundtrip_stage2_model", "feature_contract", "encoding_mapping", "oneway_threshold", "roundtrip_threshold", "oneway_metadata", "roundtrip_metadata"}
EXPECTED_PROFILES = {"public-smoke", "local-full", "hosted-frontend", "split-server", "refresh"}
EXPECTED_PROVIDERS = {"already-present", "manual-copy", "rclone-private", "public-drive"}


def load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"json parse failed: {path.name}: {exc}")
        return None


def reject_path(value: str, field: str, errors: list[str]) -> None:
    if not value:
        return
    text = str(value).replace("\\", "/")
    if ".." in text.split("/"):
        errors.append(f"path traversal in {field}")
    if re.match(r"^[A-Za-z]:/", text):
        errors.append(f"host absolute path in {field}")


def scan_security(root: Path, errors: list[str]) -> None:
    targets = [root / ".env.repro.example"] + list((root / "reproduction").rglob("*"))
    patterns = [
        (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key header"),
        (re.compile(r"(?<![\d.])(?!(?:127\.0\.0\.1|127\.0\.0\.11|0\.0\.0\.0)(?![\d.]))\d{1,3}(?:\.\d{1,3}){3}(?![\d.])"), "literal IPv4"),
        (re.compile(r"[A-Za-z]:\\Users\\", re.I), "personal Windows path"),
        (re.compile(r"/home/[A-Za-z0-9_.-]+/"), "Linux home path"),
        (re.compile(r"https?://(?!(?:localhost|127\.0\.0\.1|baro-backend|\$baro_backend_upstream)\b)(?!json-schema\.org\b)[^\s\"<>]+", re.I), "non-local URL"),
        (re.compile("shell" + r"\\s*=\\s*" + "True"), "shell=True"),
        (re.compile("/var/run/docker" + r"\\.sock"), "docker socket"),
        (re.compile("privileged:" + r"\\s*true"), "privileged container"),
    ]
    for path in targets:
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for rx, label in patterns:
            if rx.search(text):
                errors.append(f"security candidate {label}: {path.relative_to(root)}")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    repro = root / "reproduction"
    errors: list[str] = []
    version = (repro / "VERSION").read_text(encoding="utf-8").strip()
    manifest = load_json(repro / "config" / "artifact_manifest.template.json", errors)
    providers = load_json(repro / "config" / "artifact_provider_contracts.json", errors)
    profiles = load_json(repro / "config" / "profile_contracts.json", errors)
    env = load_json(repro / "config" / "env_contract.json", errors)
    schema = load_json(repro / "config" / "artifact_manifest.schema.json", errors)
    if manifest:
        if manifest.get("reproduction_version") != version:
            errors.append("manifest reproduction_version does not match VERSION")
        if manifest.get("source_commit") != EXPECTED_SOURCE or manifest.get("public_commit") != EXPECTED_PUBLIC:
            errors.append("manifest commit mismatch")
        artifacts = manifest.get("artifacts", [])
        roles = [a.get("role") for a in artifacts]
        if set(roles) != EXPECTED_ROLES or len(roles) != 10:
            errors.append("artifact role set mismatch")
        if len(roles) != len(set(roles)):
            errors.append("duplicate artifact roles")
        bundle_paths = [a.get("bundle_path") for a in artifacts]
        if len(bundle_paths) != len(set(bundle_paths)):
            errors.append("duplicate bundle paths")
        total_size = 0
        for art in artifacts:
            if art.get("status") not in {"ready", "planned", "optional", "deprecated"}:
                errors.append(f"invalid artifact status: {art.get('role')}")
            if not isinstance(art.get("size_bytes"), int) or art.get("size_bytes", -1) < 0:
                errors.append(f"invalid size for {art.get('role')}")
            else:
                total_size += art["size_bytes"]
            if not re.fullmatch(r"[0-9a-f]{64}", str(art.get("sha256", ""))):
                errors.append(f"invalid sha256 for {art.get('role')}")
            reject_path(str(art.get("bundle_path", "")), "artifact bundle_path", errors)
            reject_path(str(art.get("restore_path", "")), "artifact restore_path", errors)
        if total_size != EXPECTED_TOTAL_SIZE:
            errors.append(f"artifact total size mismatch: {total_size}")
    if providers:
        names = [p.get("name") for p in providers.get("providers", [])]
        if set(names) != EXPECTED_PROVIDERS:
            errors.append("provider set mismatch")
        defaults = [p for p in providers.get("providers", []) if p.get("default")]
        if len(defaults) != 1 or defaults[0].get("name") != "rclone-private":
            errors.append("default provider mismatch")
        implemented = {p.get("name") for p in providers.get("providers", []) if str(p.get("implementation_status", "")).startswith("implemented")}
        if not {"already-present", "manual-copy", "rclone-private"}.issubset(implemented):
            errors.append("implemented provider mismatch")
    if profiles:
        names = [p.get("name") for p in profiles.get("profiles", [])]
        if set(names) != EXPECTED_PROFILES:
            errors.append("profile set mismatch")
    env_names: set[str] = set()
    if env:
        variables = env.get("variables", [])
        names = [v.get("name") for v in variables]
        env_names = set(names)
        if len(names) != len(env_names):
            errors.append("duplicate environment variables")
        for required in ["ARTIFACT_PROVIDER", "ARTIFACT_SOURCE", "ARTIFACT_ROOT", "ARTIFACT_BUNDLE_VERSION", "MODEL_BUNDLE_SUBDIR", "ARTIFACT_MANIFEST_PATH", "ARTIFACT_MANIFEST_SHA256", "ARTIFACT_CATEGORY", "ARTIFACT_SNAPSHOT_TIER", "RCLONE_REMOTE", "RCLONE_RELEASE_PATH"]:
            if required not in env_names:
                errors.append(f"env contract missing {required}")
        valid_profiles = EXPECTED_PROFILES | {"all"}
        for var in variables:
            name = var.get("name")
            for profile in var.get("profiles", []):
                if profile not in valid_profiles:
                    errors.append(f"env {name} references unknown profile {profile}")
            if var.get("secret") and var.get("default") not in (None, ""):
                errors.append(f"secret env has real default: {name}")
            if var.get("secret") and var.get("expose_to_frontend") and not str(name).startswith("VITE_"):
                errors.append(f"backend secret exposed to frontend: {name}")
            if not var.get("example_placeholder"):
                errors.append(f"env missing example placeholder: {name}")
    env_example = root / ".env.repro.example"
    if env_example.exists() and env_names:
        example_vars = set()
        for raw in env_example.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                line = line[1:].strip()
            if "=" in line:
                candidate = line.split("=", 1)[0]
                if re.fullmatch(r"[A-Z0-9_]+", candidate):
                    example_vars.add(candidate)
        missing = env_names - example_vars
        if missing:
            errors.append("env example missing variables: " + ",".join(sorted(missing)))
    else:
        errors.append(".env.repro.example missing")
    if not schema or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("schema draft marker mismatch")
    required_files = [
        root / ".dockerignore",
        repro / ".gitattributes",
        repro / "compose.yaml",
        repro / "docker" / "backend.Dockerfile",
        repro / "docker" / "frontend.Dockerfile",
        repro / "nginx" / "default.conf.template",
        repro / "scripts" / "artifact_common.py",
        repro / "scripts" / "fetch_artifacts.py",
        repro / "scripts" / "verify_artifacts.py",
        repro / "scripts" / "fetch-artifacts.ps1",
        repro / "scripts" / "fetch-artifacts.sh",
        repro / "scripts" / "verify-artifacts.ps1",
        repro / "scripts" / "verify-artifacts.sh",
    ]
    for required in required_files:
        if not required.exists():
            errors.append(f"required C3 file missing: {required.relative_to(root)}")
    text_targets = [p for p in required_files if p.exists()] + [repro / "README.md", repro / "artifacts" / "README.md"]
    for path in text_targets:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if ":latest" in text:
            errors.append(f"latest tag is not allowed: {path.relative_to(root)}")
        if "privileged: true" in text:
            errors.append(f"privileged container is not allowed: {path.relative_to(root)}")
        if "/var/run/docker.sock" in text:
            errors.append(f"Docker socket mount is not allowed: {path.relative_to(root)}")
    compose_text = (repro / "compose.yaml").read_text(encoding="utf-8")
    for service_name in ("baro-frontend", "baro-backend", "baro-mysql", "baro-artifact-check"):
        if service_name not in compose_text:
            errors.append(f"compose service missing: {service_name}")
    if "3306:" in compose_text:
        errors.append("MySQL host port publish is not allowed")
    if "8000:" in compose_text:
        errors.append("backend host port publish is not allowed")
    if "${FRONTEND_HOST_PORT:-8080}:80" not in compose_text:
        errors.append("frontend host port contract missing")
    if "MODEL_BUNDLE_SUBDIR:-baro-runtime-v1" not in compose_text:
        errors.append("model bundle subdir contract missing")
    if ":/app/runtime/models:ro" not in compose_text:
        errors.append("model mount must be read-only")
    if 'network_mode: "none"' not in compose_text:
        errors.append("artifact-check must disable networking")
    if "cap_drop:" not in compose_text or "no-new-privileges:true" not in compose_text:
        errors.append("artifact-check hardening missing")
    nested_ignore = (repro / ".gitignore").read_text(encoding="utf-8")
    for token in ["artifacts/extracted/", "artifacts/downloads/", "artifacts/.partial/", ".artifact-state.json"]:
        if token not in nested_ignore:
            errors.append(f"nested ignore missing {token}")
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8", errors="ignore")
    for token in ["reproduction/artifacts/extracted/", "reproduction/artifacts/downloads/", "reproduction/artifacts/.partial/"]:
        if token not in dockerignore:
            errors.append(f"dockerignore missing {token}")

    c4_files = [
        repro / "database" / "README.md",
        repro / "database" / "schema.sql",
        repro / "database" / "snapshot_manifest.schema.json",
        repro / "database" / "snapshot_tiers.json",
        repro / "database" / "export.env.example",
        repro / "scripts" / "db_snapshot_common.py",
        repro / "scripts" / "export_db_snapshot.py",
        repro / "scripts" / "verify_db_snapshot.py",
        repro / "scripts" / "restore_db_snapshot.py",
        repro / "scripts" / "export-db-snapshot.ps1",
        repro / "scripts" / "export-db-snapshot.sh",
        repro / "scripts" / "verify-db-snapshot.ps1",
        repro / "scripts" / "verify-db-snapshot.sh",
        repro / "scripts" / "restore-db-snapshot.ps1",
        repro / "scripts" / "restore-db-snapshot.sh",
    ]
    for required in c4_files:
        if not required.exists():
            errors.append(f"required C4 file missing: {required.relative_to(root)}")
    schema_sql = (repro / "database" / "schema.sql").read_text(encoding="utf-8", errors="ignore")
    for token in ["baro-repro-db-v1", "search_observation", "flight_offer_observation", "baro_reproduction_state"]:
        if token not in schema_sql:
            errors.append(f"schema.sql missing {token}")
    tiers = load_json(repro / "database" / "snapshot_tiers.json", errors)
    if tiers:
        tier_names = [t.get("name") for t in tiers.get("tiers", [])]
        if set(tier_names) != {"minimal-repro", "extended-repro"}:
            errors.append("snapshot tier set mismatch")
        defaults = [t for t in tiers.get("tiers", []) if t.get("default")]
        if len(defaults) != 1 or defaults[0].get("name") != "minimal-repro":
            errors.append("default snapshot tier mismatch")
    for env_name in ["DB_SNAPSHOT_TIER", "DB_SNAPSHOT_ROOT", "DB_SCHEMA_VERSION", "DB_RESTORE_BATCH_SIZE", "DB_INIT_MODE", "DB_ALLOW_EXISTING_SAME_SNAPSHOT"]:
        if env_name not in env_names:
            errors.append(f"env contract missing {env_name}")
    if "baro-db-init" not in compose_text:
        errors.append("compose service missing: baro-db-init")
    if ":/snapshot:ro" not in compose_text:
        errors.append("snapshot mount must be read-only")
    if "service_completed_successfully" not in compose_text:
        errors.append("backend dependency on db-init missing")

    scan_security(root, errors)
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1
    print("contract_validation=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




# C4.1H bounded selector checks
try:
    import json as _json
    from pathlib import Path as _Path
    _root = _Path(__file__).resolve().parents[1]
    _tiers = _json.loads((_root / "database" / "snapshot_tiers.json").read_text(encoding="utf-8"))
    _tier_items = _tiers.get("tiers", [])
    assert _tier_items, "C4.1H: tiers missing"
    for _tier in _tier_items:
        assert _tier.get("selectors"), "C4.1H: tier selector missing"
        _limits = _tier.get("limits", {})
        for _key in ["max_search_rows","max_offer_rows","max_optional_rows","max_total_rows","max_uncompressed_bytes","max_compressed_bytes","max_selectors","max_history_limit_per_selector"]:
            assert int(_limits.get(_key, 0)) > 0, f"C4.1H: invalid limit {_key}"
        assert len(_tier["selectors"]) <= int(_limits["max_selectors"]), "C4.1H: selector count above max"
    _minimal = next(t for t in _tier_items if t.get("name") == "minimal-repro")
    assert {s["route_type"] for s in _minimal["selectors"]} == {"oneway", "roundtrip"}, "C4.1H: minimal must cover oneway and roundtrip"
    _export = (_root / "scripts" / "export_db_snapshot.py").read_text(encoding="utf-8")
    assert "compile_selection" in _export and "exact_preflight" in _export, "C4.1H: export must use shared compiler/preflight"
    assert "--db-driver" in _export, "C4.1R2: export must expose DB driver selection"
    _common = (_root / "scripts" / "db_snapshot_common.py").read_text(encoding="utf-8")
    assert "choose_db_driver" in _common and "_PyMySQLConnectionAdapter" in _common, "C4.1R2: DB driver abstraction missing"
    assert "pymysql.cursors.SSCursor" in _common, "C4.1R2: PyMySQL streaming cursor missing"
    assert "START TRANSACTION READ ONLY" in _common, "C4.1R2: read-only transaction contract missing"
    assert "validate_source_schema" in _common and "information_schema.columns" in _common, "C4.1R3: source schema compatibility preflight missing"
    assert "offer_observation_id" in _common, "C4.1R3: canonical offer PK missing"
    assert "\"offer_id\"" not in _common, "C4.1R3: legacy offer_id column remains in common contract"
    assert "\"offer_id\"" not in _export, "C4.1R3: legacy offer_id column remains in exporter"
    assert "SOURCE_TABLE_COLUMNS" in _common and "SNAPSHOT_TABLE_COLUMNS" in _common, "C4.1R4: source/snapshot column contracts must be separated"
    for _bad in ["f.route_type", "f.origin_iata", "f.destination_iata", "f.departure_date", "f.return_date", "f.is_direct", "r.return_date"]:
        assert _bad not in _common, f"C4.1R4: invalid source column reference remains: {_bad}"
    for _required in ["card_index", "stops", "price_status", "parse_status", "price_selection_reason", "payload_json"]:
        assert _required in _common, f"C4.1R4: operating source column missing from contract: {_required}"
    assert "database_query_contract_error" in _export and "unknown_column" in _export, "C4.1R4: sanitized DB diagnostics missing"
    assert 'clean["seller_domain"] = None' in _common, "C4.1R4H: seller_domain sanitizer missing"
    assert 'seller_domain not sanitized' in _common, "C4.1R4H: seller_domain verifier guard missing"
    assert '"seller_domain": "null"' in _export, "C4.1R4H: seller_domain manifest sanitization rule missing"
    assert "FROM search_observation ORDER BY observation_id" not in _export, "C4.1H: unbounded search scan remains"
    assert "force-unbounded" not in _export, "C4.1H: forbidden bypass option"
except Exception as _exc:
    raise SystemExit(str(_exc))
