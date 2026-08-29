#!/usr/bin/env python3
"""把现有目录无损补齐为 v2 合同。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.contract import enrich_catalog_contract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=PROJECT_ROOT / "models_data.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    catalog = json.loads(args.path.read_text(encoding="utf-8"))
    enrich_catalog_contract(catalog)
    output = args.output or args.path
    output.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Migrated {len(catalog.get('models', []))} models to schema {catalog['meta']['schema_version']}: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
