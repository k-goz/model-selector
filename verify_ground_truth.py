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
import json, sys, os, re, urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GT_PATH = os.path.join(SCRIPT_DIR, "ground_truth.json")
DOMESTIC_PATH = os.path.join(SCRIPT_DIR, "domestic_prices.json")
SPA_PATH = os.path.join(SCRIPT_DIR, "spa_prices.json")
CV_LOG_PATH = os.path.join(SCRIPT_DIR, "cross_validation_log.json")
DEFAULT_DATA = os.path.join(SCRIPT_DIR, "models_data.json")

PLATFORM_MAP = {
    "deepseek":    "deepseek",
    "moonshot":    "moonshot",
    "zhipu":       "zhipu",
    "volcengine":  "volcengine",
    "baidu":       "baidu",
    "tencent":     "tencent",
    "minimax":     "minimax",
    "siliconflow": "siliconflow",
    "aliyun":      "aliyun",
    "yi":          "yi",
    "baichuan":    "baichuan",
    "jieyue":      "jieyue",
    "spark":       "spark",
    "groq":        "groq",
    "together":    "together",
    "fireworks":   "fireworks",
    "cohere":      "cohere",
    "novita":      "novita",
    "deepinfra":   "deepinfra",
}

def normalize_for_match(s):
    s = s.lower().strip()
    s = re.sub(r'[\s\-_.]+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    return s

def load_ground_truth():
    with open(GT_PATH) as f:
        return json.load(f)

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
    "together": "together_ai",
    "fireworks": "fireworks_ai",
    "cohere": "cohere",
    "groq": "groq",
    "novita": "novita",
    "deepinfra": "deepinfra",
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
    strict = "--strict" in sys.argv
    source = "models_data"
    for i, a in enumerate(sys.argv):
        if a == "--source" and i + 1 < len(sys.argv):
            source = sys.argv[i + 1]

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
        data_path = DEFAULT_DATA
        for i, a in enumerate(sys.argv):
            if a == "--json" and i + 1 < len(sys.argv):
                data_path = sys.argv[i + 1]
        db = load_models_data(data_path)
        source_label = "models_data.json"

    passed = 0
    failed = 0
    skipped = 0
    errors = []

    print("=" * 70)
    print("Ground Truth 价格断言 (来源: %s, 容差: %s%%)" % (source_label, tolerance))
    print("=" * 70)

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
            print("  [MISS] %s/%s — 未找到" % (plat, model))
            continue

        i_ok = within_tolerance(act_i, exp_i, tolerance)
        o_ok = within_tolerance(act_o, exp_o, tolerance)

        if i_ok and o_ok:
            passed += 1
            print("  [PASS] %s/%s — 输入: %.2f(期望%.2f) 输出: %.2f(期望%.2f)" % (plat, model, act_i, exp_i, act_o, exp_o))
        else:
            failed += 1
            i_diff = abs(act_i - exp_i) / exp_i * 100 if exp_i else 0
            o_diff = abs(act_o - exp_o) / exp_o * 100 if exp_o else 0
            errors.append(("MISMATCH", plat, model, exp_i, exp_o, act_i, act_o, src))
            print("  [FAIL] %s/%s — 输入: %.2f(期望%.2f,偏差%.1f%%) 输出: %.2f(期望%.2f,偏差%.1f%%)" % (
                plat, model, act_i, exp_i, i_diff, act_o, exp_o, o_diff))

    print("=" * 70)
    print("结果: %d 通过 / %d 失败 / %d 跳过 / %d 总计" % (passed, failed, skipped, len(gt["models"])))
    print("=" * 70)

    if errors:
        print("\n失败详情:")
        for e in errors:
            status, plat, model, exp_i, exp_o, act_i, act_o, src = e
            if status == "MISSING":
                print("  - %s/%s: 未在%s中找到 (来源: %s)" % (plat, model, source_label, src))
            else:
                print("  - %s/%s: 实际(%.2f/%.2f) vs 期望(%.2f/%.2f) (来源: %s)" % (
                    plat, model, act_i, act_o, exp_i, exp_o, src))

    if failed > 0:
        print("\n[FAIL] %d 个模型价格不符" % failed)
        sys.exit(1)
    else:
        print("\n[OK] 所有 Ground Truth 价格验证通过")
        sys.exit(0)

if __name__ == "__main__":
    main()
