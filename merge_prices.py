#!/usr/bin/env python3
"""
价格合并脚本 — 将 domestic_prices.json 和 tencent_prices.json 合并到 official_prices_db.json
用法:
  python merge_prices.py
  python merge_prices.py --dry-run
"""
import argparse
import json
import os
from datetime import datetime, timezone

VERSION = "1.0.0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_json(f):
    if os.path.exists(f):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception:
            pass
    return {}


def save_json(f, d):
    with open(f, 'w', encoding='utf-8') as file:
        json.dump(d, file, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Merge price data into official_prices_db.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview merge without modifying official_prices_db.json")
    args = parser.parse_args()

    db = load_json(os.path.join(SCRIPT_DIR, "official_prices_db.json"))
    merged_count = 0
    skipped_count = 0

    # Merge domestic_prices.json
    domestic = load_json(os.path.join(SCRIPT_DIR, "domestic_prices.json"))
    for provider, models in domestic.items():
        for model_name, info in models.items():
            if model_name not in db:
                db[model_name] = {}
            ip = float(info.get("input", 0))
            op = float(info.get("output", 0))
            if "input_price" not in db[model_name] or db[model_name].get("input_price", 0) == 0:
                db[model_name]["input_price"] = ip
                merged_count += 1
            else:
                skipped_count += 1
            if "output_price" not in db[model_name] or db[model_name].get("output_price", 0) == 0:
                db[model_name]["output_price"] = op
            db[model_name]["currency"] = "CNY"
            db[model_name]["source"] = "merged_from_legacy_domestic_prices"
            db[model_name]["provider"] = provider

    # Merge tencent_prices.json (非覆盖: 已有非零价格不覆盖)
    tencent = load_json(os.path.join(SCRIPT_DIR, "tencent_prices.json"))
    tencent_merged = 0
    tencent_skipped = 0
    for model_key, info in tencent.items():
        model_name = info.get("model_id")
        if not model_name:
            continue
        if model_name not in db:
            db[model_name] = {}
        ip = float(info.get("input_price", 0))
        op = float(info.get("output_price", 0))
        if "input_price" not in db[model_name] or db[model_name].get("input_price", 0) == 0:
            db[model_name]["input_price"] = ip
            tencent_merged += 1
        else:
            tencent_skipped += 1
        if "output_price" not in db[model_name] or db[model_name].get("output_price", 0) == 0:
            db[model_name]["output_price"] = op
        db[model_name]["currency"] = info.get("currency", "CNY")
        db[model_name]["source"] = "tencent_prices.json"
        db[model_name]["provider"] = "tencent"

    total_merged = merged_count + tencent_merged
    total_skipped = skipped_count + tencent_skipped

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "summary": {
            "merged_count": total_merged,
            "skipped_count": total_skipped,
            "total_count": len(db),
            "domestic_merged": merged_count,
            "domestic_skipped": skipped_count,
            "tencent_merged": tencent_merged,
            "tencent_skipped": tencent_skipped,
        },
    }

    if args.dry_run:
        report["dry_run"] = True
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("[DRY-RUN] No files modified", file=__import__('sys').stderr)
    else:
        db_path = os.path.join(SCRIPT_DIR, "official_prices_db.json")
        save_json(db_path, db)
        report["output"] = db_path
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("Merged into official_prices_db.json. Total keys: %d (merged: %d, skipped: %d)" % (
            len(db), total_merged, total_skipped), file=__import__('sys').stderr)


if __name__ == "__main__":
    main()
