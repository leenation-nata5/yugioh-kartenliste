#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate an anonymized Just InCard scanner-corpus manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from features_v120 import benchmark_scan_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Just InCard v12 scanner benchmark")
    parser.add_argument("manifest", type=Path, help="JSON list or object with a records list")
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    parser.add_argument("--max-false-positive-rate", type=float, default=1.0)
    parser.add_argument("--max-p95-ms", type=float, default=0.0, help="0 disables the latency gate")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = payload.get("records", []) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise SystemExit("Manifest must be a JSON list or contain a records list")
    report = benchmark_scan_records(records)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    failed = report["accuracy"] < max(0.0, min(1.0, args.min_accuracy))
    failed = failed or report["false_positive_rate"] > max(0.0, min(1.0, args.max_false_positive_rate))
    if args.max_p95_ms > 0 and report["latency_p95_ms"] is not None:
        failed = failed or report["latency_p95_ms"] > args.max_p95_ms
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
