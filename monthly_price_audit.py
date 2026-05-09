#!/usr/bin/env python3
"""
月度价格校验脚本 — 对比静态价格与官方实时价格的差异
用法: python monthly_price_audit.py [--threshold 20]
输出: 结构化报告，列出所有超过阈值的偏差模型
"""
import argparse
import json
import sys
import os
import importlib.util
from datetime import datetime, timezone

VERSION = "1.0.0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DOMESTIC_PLATFORMS = ["deepseek", "moonshot", "zhipu", "volcengine", "tencent",
                      "spark", "minimax", "yi", "baichuan", "jieyue", "infini",
                      "siliconflow", "aliyun", "baidu"]
OVERSEAS_PLATFORMS = ["groq", "together_ai", "together", "fireworks_ai", "fireworks",
                      "cohere", "novita", "deepinfra", "aihubmix"]


def load_generate_module():
    spec = importlib.util.spec_from_file_location("generate", os.path.join(SCRIPT_DIR, "generate.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate"] = mod
    spec.loader.exec_module(mod)
    return mod


def detect_platform(model_name):
    n = model_name.lower()
    platform_map = {
        "deepseek": "deepseek", "moonshot": "moonshot", "kimi": "moonshot",
        "glm": "zhipu", "chatglm": "zhipu", "qwen": "aliyun",
        "ernie": "baidu", "hunyuan": "tencent", "spark": "spark",
        "abab": "minimax", "yi-": "yi", "baichuan": "baichuan",
        "step": "jieyue", "llama": "groq", "mistral": "groq",
        "gpt": "openrouter", "claude": "openrouter",
    }
    for prefix, platform in platform_map.items():
        if prefix in n:
            return platform
    return None


def main():
    parser = argparse.ArgumentParser(description="Monthly price audit: compare static vs official prices")
    parser.add_argument("--threshold", type=float, default=20, help="Deviation threshold %% (default: 20)")
    args = parser.parse_args()
    threshold = args.threshold

    print("=" * 70, file=sys.stderr)
    print("Monthly Price Audit — static vs official (threshold: %s%%)" % threshold, file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    try:
        gen = load_generate_module()
    except Exception as e:
        print("[ERROR] Cannot load generate.py: %s" % e, file=sys.stderr)
        print("Hint: API keys environment variables may be required", file=sys.stderr)
        sys.exit(2)

    try:
        official = gen.fetch_official_prices()
        print("Official prices fetched: %d models" % len(official), file=sys.stderr)
    except Exception as e:
        print("[ERROR] Failed to fetch official prices: %s" % e, file=sys.stderr)
        sys.exit(2)

    if not official:
        print("[WARN] Official prices empty — API keys may be unconfigured or network issue", file=sys.stderr)
        sys.exit(2)

    results = []
    for model_name, api_price in official.items():
        api_i = api_price.get("input", 0)
        api_o = api_price.get("output", 0)
        if api_i == 0 and api_o == 0:
            continue

        platform = detect_platform(model_name)
        if not platform:
            continue

        if platform in DOMESTIC_PLATFORMS:
            dom = gen.get_domestic_price(platform, model_name) if hasattr(gen, 'get_domestic_price') else None
            if dom and dom.get("input", 0) > 0:
                hc_i, hc_o = dom["input"], dom["output"]
            else:
                ii, oo, cc, src = gen.get_absolute_price(platform, model_name)
                hc_i, hc_o = ii, oo
        elif platform in OVERSEAS_PLATFORMS:
            ii, oo, cc, src = gen.get_absolute_price(platform, model_name)
            hc_i, hc_o = ii, oo
        else:
            ii, oo, cc, src = gen.get_absolute_price(platform, model_name)
            hc_i, hc_o = ii, oo

        if hc_i == 0 and hc_o == 0:
            continue

        i_diff = abs(hc_i - api_i) / api_i * 100 if api_i else 0
        o_diff = abs(hc_o - api_o) / api_o * 100 if api_o else 0
        max_diff = max(i_diff, o_diff)

        results.append({
            "model": model_name,
            "platform": platform,
            "static_input": round(hc_i, 6),
            "static_output": round(hc_o, 6),
            "official_input": round(api_i, 6),
            "official_output": round(api_o, 6),
            "input_diff_pct": round(i_diff, 1),
            "output_diff_pct": round(o_diff, 1),
            "max_diff_pct": round(max_diff, 1),
        })

    if not results:
        print("\nNo comparable models found", file=sys.stderr)
        sys.exit(0)

    results.sort(key=lambda x: x["max_diff_pct"], reverse=True)
    ok_count = sum(1 for r in results if r["max_diff_pct"] <= threshold)
    warn_count = sum(1 for r in results if r["max_diff_pct"] > threshold)

    print("\n--- Deviation <= %s%% (OK) ---" % threshold, file=sys.stderr)
    for r in results:
        if r["max_diff_pct"] <= threshold:
            print("  [OK] %s/%s — static(%.4f/%.4f) official(%.4f/%.4f) diff %.1f%%" % (
                r["platform"], r["model"], r["static_input"], r["static_output"],
                r["official_input"], r["official_output"], r["max_diff_pct"]), file=sys.stderr)

    if warn_count > 0:
        print("\n--- Deviation > %s%% (needs review) ---" % threshold, file=sys.stderr)
        for r in results:
            if r["max_diff_pct"] > threshold:
                print("  [!!] %s/%s — static(%.4f/%.4f) official(%.4f/%.4f) diff %.1f%%" % (
                    r["platform"], r["model"], r["static_input"], r["static_output"],
                    r["official_input"], r["official_output"], r["max_diff_pct"]), file=sys.stderr)

    print("\n" + "=" * 70, file=sys.stderr)
    print("Result: %d OK / %d review / %d total" % (ok_count, warn_count, len(results)), file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "threshold_pct": threshold,
        "summary": {"total": len(results), "ok": ok_count, "warn": warn_count},
        "results": results,
    }
    report_path = os.path.join(SCRIPT_DIR, "price_audit_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Report saved: %s" % report_path, file=sys.stderr)

    if warn_count > 0:
        print("\n[WARN] %d models have price deviation > %s%%" % (warn_count, threshold), file=sys.stderr)
        sys.exit(1)
    else:
        print("\n[OK] All static prices match official prices", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
