#!/usr/bin/env python3
"""
多源价格交叉验证模块
对每个模型，从多个价格源取共识价格，自动修正明显错误（如价格=0但实际非免费）。
输出: cross_validation_log.json
"""
import json, os, sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SCRIPT_DIR, "cross_validation_log.json")
USD_TO_CNY = 7.25

# 置信度分级
CONFIDENCE = {
    "api": 5,        # 官方 API 直接返回
    "scraper": 4,    # 官方定价页 HTML 爬取
    "spa_scraper": 4,  # SPA Playwright 爬取
    "openrouter": 3,  # 第三方聚合平台
    "litellm": 2,     # 社区维护数据库
    "domestic_json": 1,  # 手动维护
}

THRESHOLD = 0.20  # 20% 以内视为一致


def normalize_price(input_price, output_price, currency):
    """统一转为 CNY/1M tokens"""
    if currency == "USD":
        return input_price * USD_TO_CNY, output_price * USD_TO_CNY
    return input_price, output_price


def consensus_price(sources):
    """
    从多个价格源中取共识价格。
    sources: list of {"input": float, "output": float, "currency": str, "source_type": str}
    Returns: {"input": float, "output": float, "confidence": int, "source_type": str, "agreement_count": int}
    """
    # 过滤掉价格为 0 的源
    valid = []
    for s in sources:
        inp, out = normalize_price(s["input"], s["output"], s.get("currency", "CNY"))
        if inp > 0 or out > 0:
            valid.append({**s, "inp_cny": inp, "out_cny": out})

    if not valid:
        return None

    if len(valid) == 1:
        s = valid[0]
        return {"input": s["inp_cny"], "output": s["out_cny"],
                "confidence": CONFIDENCE.get(s["source_type"], 1),
                "source_type": s["source_type"], "agreement_count": 1}

    # 按置信度排序
    valid.sort(key=lambda x: CONFIDENCE.get(x["source_type"], 1), reverse=True)

    # 寻找共识组（误差 <20%）
    best_group = []
    for i, ref in enumerate(valid):
        group = [ref]
        for j, other in enumerate(valid):
            if i == j:
                continue
            # 比较 input 价格
            if ref["inp_cny"] > 0 and other["inp_cny"] > 0:
                diff = abs(ref["inp_cny"] - other["inp_cny"]) / ref["inp_cny"]
                if diff <= THRESHOLD:
                    group.append(other)
        if len(group) > len(best_group):
            best_group = group

    if len(best_group) >= 2:
        # 取共识组中置信度最高的
        best_group.sort(key=lambda x: CONFIDENCE.get(x["source_type"], 1), reverse=True)
        winner = best_group[0]
        return {"input": winner["inp_cny"], "output": winner["out_cny"],
                "confidence": CONFIDENCE.get(winner["source_type"], 1),
                "source_type": winner["source_type"], "agreement_count": len(best_group)}

    # 没有共识，取置信度最高的
    winner = valid[0]
    return {"input": winner["inp_cny"], "output": winner["out_cny"],
            "confidence": CONFIDENCE.get(winner["source_type"], 1),
            "source_type": winner["source_type"], "agreement_count": 1}


def cross_validate_model(platform, model_name, current_input, current_output, current_currency,
                         or_lookup, litellm_db, spa_prices, official_prices):
    """
    对单个模型进行交叉验证。
    Returns: {
        "input": float, "output": float,
        "source": str, "confidence": int,
        "flags": list, "all_sources": dict,
        "action": str  # "keep" | "auto_fill" | "corrected"
    }
    """
    from generate import normalize_for_match, get_domestic_price, get_dynamic_price, USD_TO_CNY

    sources = []
    all_sources = {}

    # 收集所有可用价格源
    # 1. 当前价格
    if current_input > 0 or current_output > 0:
        src_type = "domestic_json"  # 默认
        sources.append({"input": current_input, "output": current_output,
                        "currency": current_currency, "source_type": src_type})
        all_sources["current"] = {"input": current_input, "output": current_output, "currency": current_currency}

    # 2. 官方爬取
    mn_lower = model_name.lower()
    official = official_prices.get(mn_lower)
    if not official:
        for sf_pfx in ["sf:", "sf:deepseek-ai/", "sf:thudm/", "sf:qwen/"]:
            official = official_prices.get(sf_pfx + mn_lower)
            if official:
                break
    if official and (official.get("input", 0) > 0 or official.get("output", 0) > 0):
        sources.append({"input": official["input"], "output": official["output"],
                        "currency": official.get("currency", "CNY"), "source_type": "scraper"})
        all_sources["official_scraper"] = official

    # 3. SPA 爬取
    spa_platform = spa_prices.get(platform, {})
    spa_entry = spa_platform.get(mn_lower)
    if not spa_entry:
        for k in sorted(spa_platform.keys(), key=len, reverse=True):
            if mn_lower.startswith(k):
                spa_entry = spa_platform[k]
                break
    if spa_entry and (spa_entry.get("input", 0) > 0 or spa_entry.get("output", 0) > 0):
        sources.append({"input": spa_entry["input"], "output": spa_entry["output"],
                        "currency": "CNY", "source_type": "spa_scraper"})
        all_sources["spa_scraper"] = spa_entry

    # 4. OpenRouter
    if or_lookup:
        norm = normalize_for_match(model_name)
        or_ref = or_lookup.get(norm)
        if not or_ref:
            for or_pfx in ["deepseek/", "qwen/", "bytedance/"]:
                or_ref = or_lookup.get(normalize_for_match(or_pfx + model_name))
                if or_ref:
                    break
        if or_ref and (or_ref.get("input_per_1m", 0) > 0 or or_ref.get("output_per_1m", 0) > 0):
            sources.append({"input": or_ref["input_per_1m"], "output": or_ref["output_per_1m"],
                            "currency": "USD", "source_type": "openrouter"})
            all_sources["openrouter"] = {"input_per_1m": or_ref["input_per_1m"],
                                          "output_per_1m": or_ref["output_per_1m"]}

    # 5. LiteLLM
    if litellm_db:
        ll_i, ll_o, ll_c, _, _ = get_dynamic_price(platform, model_name)
        if ll_i > 0 or ll_o > 0:
            sources.append({"input": ll_i, "output": ll_o,
                            "currency": "USD" if ll_c != "N/A" else "CNY", "source_type": "litellm"})
            all_sources["litellm"] = {"input": ll_i, "output": ll_o}

    # 进行共识投票
    result = consensus_price(sources)
    if not result:
        return {"input": 0, "output": 0, "source": "", "confidence": 0,
                "flags": ["no_data"], "all_sources": all_sources, "action": "keep"}

    flags = []
    action = "keep"

    # 检查是否需要自动修正（当前价格=0 但有共识价格）
    if current_input == 0 and current_output == 0 and result["input"] > 0:
        flags.append("zero_price_auto_corrected")
        action = "auto_fill"

    # 检查高分歧
    if result["agreement_count"] == 1 and len(sources) > 1:
        flags.append("single_source_consensus")

    return {
        "input": result["input"],
        "output": result["output"],
        "source": result["source_type"],
        "confidence": result["confidence"],
        "flags": flags,
        "all_sources": all_sources,
        "action": action,
    }


def cross_validate_all(all_models, or_lookup, litellm_db, spa_prices, official_prices):
    """
    对所有模型进行交叉验证。
    Returns: dict of (platform, model_name) -> validation result
    """
    from generate import normalize_for_match

    results = {}
    corrections = 0

    for m in all_models:
        p = m.get("p", "")
        mn = m.get("n", "")
        cur_i = float(m.get("i", 0) or 0)
        cur_o = float(m.get("o", 0) or 0)
        cur = m.get("cur", "CNY")

        result = cross_validate_model(
            p, mn, cur_i, cur_o, cur,
            or_lookup, litellm_db, spa_prices, official_prices
        )

        if result["action"] == "auto_fill":
            corrections += 1

        results[(p, mn)] = result

    if corrections > 0:
        print("  Cross-validation: %d models auto-corrected" % corrections, file=sys.stderr)

    return results


def save_log(results):
    """保存交叉验证日志"""
    log = {}
    for (p, mn), result in results.items():
        key = "%s/%s" % (p, mn)
        log[key] = {
            "input": result["input"],
            "output": result["output"],
            "source": result["source"],
            "confidence": result["confidence"],
            "flags": result["flags"],
            "action": result["action"],
        }
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump({"validated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total": len(log),
                    "corrections": sum(1 for v in log.values() if "zero_price_auto_corrected" in v.get("flags", [])),
                    "models": log}, f, ensure_ascii=False, indent=2)
    print("  Cross-validation log saved: %s (%d models)" % (LOG_PATH, len(log)), file=sys.stderr)
