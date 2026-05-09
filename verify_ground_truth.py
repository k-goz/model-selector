#!/usr/bin/env python3
"""
Ground Truth 价格断言脚本（双轨制版）
用法:
  python verify_ground_truth.py                     # 从 models_data.json 校验
  python verify_ground_truth.py --source domestic    # 从 domestic_prices.json 校验
  python verify_ground_truth.py --source litellm     # 从 LiteLLM 远程校验
  python verify_ground_truth.py --source spa         # 从 spa_prices.json 校验
  python verify_ground_truth.py --source cross_validated  # 从 cross_validation_log.json 校验
  python verify_ground_truth.py --strict             # 任何偏差>0即失败 (默认容差5%)
"""
import argparse
import json
import sys
import os
import re
import urllib.request
from datetime import datetime, timezone

VERSION = "1.0.0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GT_PATH = os.path.join(SCRIPT_DIR, "ground_truth.json")
DOMESTIC_PATH = os.path.join(SCRIPT_DIR, "domestic_prices.json")
SPA_PATH = os.path.join(SCRIPT_DIR, "spa_prices.json")
CV_LOG_PATH = os.path.join(SCRIPT_DIR, "cross_validation_log.json")
DEFAULT_DATA = os.path.join(SCRIPT_DIR, "models_data.json")

PLATFORM_MAP = {
    "deepseek": "deepseek", "moonshot": "moonshot", "zhipu": "zhipu",
    "volcengine": "volcengine", "baidu": "baidu", "tencent": "tencent",
    "minimax": "minimax", "siliconflow": "siliconflow", "aliyun": "aliyun",
    "yi": "yi", "baichuan": "baichuan", "jieyue": "jieyue", "spark": "spark",
    "groq": "groq", "together": "together", "fireworks": "fireworks",
    "cohere": "cohere", "novita": "novita", "deepinfra": "deepinfra",
}


def normalize_for_match(s):
    s = s.lower().strip()
    s = re.sub(r'[\s\-_.]+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    return s


def load_ground_truth():
    if not os.path.exists(GT_PATH):
        print("Error: ground_truth.json not found. Please create it first.", file=sys.stderr)
        sys.exit(2)
    try:
        with open(GT_PATH) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print("Error: Invalid JSON in ground_truth.json: %s" % e, file=sys.stderr)
        sys.exit(2)


def load_models_data(path):
    with open(path) as f:
        data = json.load(f)
    return data.get("models", data) if isinstance(data, dict) else data


def load_domestic_prices():
    with open(DOMESTIC_PATH) as f:
        return json.load(f)


def get_domestic_price(domestic_db, platform, model):
    if platform not in domestic_db:
        return None, None
    rules = domestic_db[platform]
    ml = model.lower()
    if ml in rules:
        return rules[ml]["input"], rules[ml]["output"]
    for k in sorted(rules.keys(), key=len, reverse=True):
        if ml.startswith(k):
            return rules[k]["input"], rules[k]["output"]
    return None, None


def fetch_litellm_db():
    prices = {}
    try:
        url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
        for raw_name, info in data.items():
            if not isinstance(info, dict): continue
            provider = info.get("litellm_provider", "")
            if not provider: continue
            inp = float(info.get("input_cost_per_token", 0) or 0) * 1e6
            out = float(info.get("output_cost_per_token", 0) or 0) * 1e6
            if inp == 0: inp = float(info.get("input_cost_per_million_tokens", 0) or 0)
            if out == 0: out = float(info.get("output_cost_per_million_tokens", 0) or 0)
            if inp > 0 or out > 0:
                if provider not in prices:
                    prices[provider] = {}
                mk = raw_name.replace(f"{provider}/", "")
                prices[provider][mk.lower()] = {"input": inp, "output": out}
        print("  LiteLLM: %d providers, %d entries" % (len(prices), sum(len(v) for v in prices.values())), file=sys.stderr)
    except Exception as e:
        print("  LiteLLM fetch error:", e, file=sys.stderr)
    return prices


LITELLM_KEY_MAP = {
    "together": "together_ai", "fireworks": "fireworks_ai",
    "cohere": "cohere", "groq": "groq", "novita": "novita", "deepinfra": "deepinfra",
}


def get_litellm_price(litellm_db, platform, model):
    provider = LITELLM_KEY_MAP.get(platform, platform)
    if provider not in litellm_db:
        return None, None
    ml = model.lower()
    norm = normalize_for_match(model)
    if ml in litellm_db[provider]:
        e = litellm_db[provider][ml]
        return e["input"], e["output"]
    if norm in litellm_db[provider]:
        e = litellm_db[provider][norm]
        return e["input"], e["output"]
    return None, None


def find_model_price(models, platform, model_name):
    allowed_pids = [PLATFORM_MAP.get(platform, platform)]
    for m in models:
        pid = m.get("platform_id", "")
        name = m.get("name", "")
        if pid not in allowed_pids:
            continue
        mn = model_name.lower()
        n = name.lower()
        if n == mn or mn in n:
            return m.get("input_price"), m.get("output_price")
        if platform == "siliconflow" and n.endswith(mn):
            return m.get("input_price"), m.get("output_price")
    return None, None


def get_spa_price(platform, model):
    if not os.path.exists(SPA_PATH):
        return None, None
    with open(SPA_PATH) as f:
        data = json.load(f)
    prices = data.get("prices", {})
    plat = prices.get(platform, {})
    ml = model.lower()
    if ml in plat:
        return plat[ml].get("input"), plat[ml].get("output")
    for k in sorted(plat.keys(), key=len, reverse=True):
        if ml.startswith(k):
            return plat[k].get("input"), plat[k].get("output")
    return None, None


def get_cross_validated_price(platform, model):
    if not os.path.exists(CV_LOG_PATH):
        return None, None
    with open(CV_LOG_PATH) as f:
        data = json.load(f)
    key = "%s/%s" % (platform, model)
    entry = data.get("models", {}).get(key)
    if entry:
        return entry.get("input"), entry.get("output")
    return None, None


def within_tolerance(actual, expected, tolerance_pct):
    if expected == 0:
        return actual == 0
    return abs(actual - expected) / expected * 100 <= tolerance_pct


def main():
    parser = argparse.ArgumentParser(description="Verify ground truth price assertions")
    parser.add_argument("--source", default="models_data",
                        choices=["models_data", "domestic", "litellm", "spa", "cross_validated"],
                        help="Price source to verify against (default: models_data)")
    parser.add_argument("--strict", action="store_true",
                        help="Any deviation >0%% is a failure (default tolerance: 5%%)")
    parser.add_argument("--json", dest="json_path", default=None,
                        help="Path to models_data.json (when --source models_data)")
    args = parser.parse_args()

    source = args.source
    strict = args.strict

    gt = load_ground_truth()
    tolerance = 0 if strict else gt["_meta"]["tolerance_pct"]

    if source == "domestic":
        db = load_domestic_prices()
        source_label = "domestic_prices.json"
    elif source == "litellm":
        db = fetch_litellm_db()
        source_label = "LiteLLM"
    elif source == "spa":
        db = None
        source_label = "spa_prices.json"
    elif source == "cross_validated":
        db = None
        source_label = "cross_validation_log.json"
    else:
        data_path = args.json_path or DEFAULT_DATA
        db = load_models_data(data_path)
        source_label = "models_data.json"

    passed = 0
    failed = 0
    skipped = 0
    errors = []
    results = []

    print("=" * 70, file=sys.stderr)
    print("Ground Truth Verification (source: %s, tolerance: %s%%)" % (source_label, tolerance), file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    for item in gt["models"]:
        plat = item["platform"]
        model = item["model"]
        exp_i = item["input"]
        exp_o = item["output"]
        src = item["source"]

        if source == "domestic":
            act_i, act_o = get_domestic_price(db, plat, model)
        elif source == "litellm":
            act_i, act_o = get_litellm_price(db, plat, model)
        elif source == "spa":
            act_i, act_o = get_spa_price(plat, model)
        elif source == "cross_validated":
            act_i, act_o = get_cross_validated_price(plat, model)
        else:
            act_i, act_o = find_model_price(db, plat, model)

        if act_i is None:
            skipped += 1
            errors.append(("MISSING", plat, model, exp_i, exp_o, None, None, src))
            results.append({"model": model, "platform": plat, "status": "MISSING"})
            print("  [MISS] %s/%s — not found" % (plat, model), file=sys.stderr)
            continue

        i_ok = within_tolerance(act_i, exp_i, tolerance)
        o_ok = within_tolerance(act_o, exp_o, tolerance)

        i_diff = abs(act_i - exp_i) / exp_i * 100 if exp_i else 0
        o_diff = abs(act_o - exp_o) / exp_o * 100 if exp_o else 0

        if i_ok and o_ok:
            passed += 1
            results.append({"model": model, "platform": plat, "status": "PASS",
                           "input_diff_pct": round(i_diff, 1), "output_diff_pct": round(o_diff, 1)})
            print("  [PASS] %s/%s — input: %.2f(exp %.2f) output: %.2f(exp %.2f)" % (plat, model, act_i, exp_i, act_o, exp_o), file=sys.stderr)
        else:
            failed += 1
            errors.append(("MISMATCH", plat, model, exp_i, exp_o, act_i, act_o, src))
            results.append({"model": model, "platform": plat, "status": "FAIL",
                           "actual_input": act_i, "actual_output": act_o,
                           "expected_input": exp_i, "expected_output": exp_o,
                           "input_diff_pct": round(i_diff, 1), "output_diff_pct": round(o_diff, 1)})
            print("  [FAIL] %s/%s — input: %.2f(exp %.2f, diff %.1f%%) output: %.2f(exp %.2f, diff %.1f%%)" % (
                plat, model, act_i, exp_i, i_diff, act_o, exp_o, o_diff), file=sys.stderr)

    print("=" * 70, file=sys.stderr)
    print("Result: %d passed / %d failed / %d skipped / %d total" % (passed, failed, skipped, len(gt["models"])), file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "source": source_label,
        "tolerance_pct": tolerance,
        "summary": {"total": len(gt["models"]), "passed": passed, "failed": failed, "skipped": skipped},
        "results": results,
    }
    report_path = os.path.join(SCRIPT_DIR, "ground_truth_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if errors:
        print("\nFailure details:", file=sys.stderr)
        for e in errors:
            status, plat, model, exp_i, exp_o, act_i, act_o, src = e
            if status == "MISSING":
                print("  - %s/%s: not found in %s (source: %s)" % (plat, model, source_label, src), file=sys.stderr)
            else:
                print("  - %s/%s: actual(%.2f/%.2f) vs expected(%.2f/%.2f) (source: %s)" % (
                    plat, model, act_i, act_o, exp_i, exp_o, src), file=sys.stderr)

    if failed > 0:
        print("\n[FAIL] %d models have price mismatches" % failed, file=sys.stderr)
        sys.exit(1)
    else:
        print("\n[OK] All ground truth price verifications passed", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
