#!/usr/bin/env python3
"""移除旧版 --update-db 写入 SSOT 根节点的孤立模型记录。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=Path("official_prices_db.json"))
    parser.add_argument("--write", action="store_true", help="写回清理后的数据库")
    args = parser.parse_args()

    data = json.loads(args.path.read_text(encoding="utf-8"))
    invalid_keys = [
        key for key, value in data.items()
        if key != "_meta" and (
            not isinstance(value, dict) or "_source" not in value or "_currency" not in value
        )
    ]
    print(f"发现 {len(invalid_keys)} 个 SSOT 根节点孤立记录")
    if invalid_keys:
        print("示例:", ", ".join(invalid_keys[:10]))
    if args.write and invalid_keys:
        for key in invalid_keys:
            del data[key]
        args.path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已保留 {len(data) - 1} 个合法平台命名空间")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
