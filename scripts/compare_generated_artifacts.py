#!/usr/bin/env python3
"""比较两份生成目录并写出机器可读差异报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.publication import compare_catalogs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-change", action="store_true")
    args = parser.parse_args()

    before = json.loads(args.baseline.read_text(encoding="utf-8"))
    after = json.loads(args.candidate.read_text(encoding="utf-8"))
    report = compare_catalogs(before, after)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if args.fail_on_change and not report["compatible"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
