#!/usr/bin/env python3
"""从两份 v2 目录生成历史、最新差异和周期摘要。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.history import write_history_artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--history", type=Path, default=ROOT / "data/history/price-history.json")
    parser.add_argument("--diff", type=Path, default=ROOT / "data/diffs/latest.json")
    parser.add_argument("--summary", type=Path, default=ROOT / "data/history/summary.json")
    args = parser.parse_args()
    before = json.loads(args.baseline.read_text(encoding="utf-8"))
    after = json.loads(args.candidate.read_text(encoding="utf-8"))
    diff = write_history_artifacts(before, after, history_path=args.history, diff_path=args.diff, summary_path=args.summary)
    print(json.dumps(diff["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
