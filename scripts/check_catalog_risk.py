#!/usr/bin/env python3
"""生成发布风险报告，并在高风险差异存在时返回非零。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.history import build_catalog_diff
from src.quality import assess_catalog_risk, load_policy, write_quality_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=ROOT / "data/quality/baseline.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/quality/latest-report.json")
    args = parser.parse_args()
    before = json.loads(args.baseline.read_text(encoding="utf-8"))
    after = json.loads(args.candidate.read_text(encoding="utf-8"))
    report = assess_catalog_risk(before, after, build_catalog_diff(before, after), policy=load_policy(args.policy))
    write_quality_report(args.output, report)
    print(json.dumps({"status": report["status"], "high_risk": report["high_risk"]}, ensure_ascii=False))
    return 1 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
