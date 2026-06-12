#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from db_snapshot_common import SnapshotError, verify_snapshot, print_result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot-root", type=Path, required=True)
    p.add_argument("--tier")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--deep", action="store_true")
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    try:
        result = verify_snapshot(args.snapshot_root, tier=args.tier, strict=args.strict, deep=args.deep)
        print_result({"snapshot_verification": "PASS", "total_rows": result["total_rows"], "table_counts": result["table_counts"], "error_code": 0}, args.json_output, args.quiet)
        return 0
    except SnapshotError as exc:
        print_result({"snapshot_verification": "FAIL", "error_code": exc.exit_code, "message": str(exc)}, args.json_output)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
