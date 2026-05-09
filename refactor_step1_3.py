#!/usr/bin/env python3
"""重构脚本：执行价格获取逻辑双轨制重构"""
import re

with open("generate.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# 第一步：删除行 610-1289（价格映射函数区）
# 保留 609 行（空行）和 1290 行之后的代码
before = lines[:609]  # 行 1-609
after = lines[1289:]  # 行 1290+

# 第二步：替换 fetch_litellm_prices 函数（行 284-317）
# 找到它在 before 中的位置并替换
new_fetch_litellm = '''# ─── LiteLLM 价格获取（按平台+模型二维字典） ───
def fetch_litellm_prices():
    prices = {}
    try:
        url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
        for raw_model_name, info in data.items():
            if not isinstance(info, dict): continue
            provider = info.get("litellm_provider", "")
            if not provider: continue
            inp_1m = float(info.get("input_cost_per_token", 0) or 0) * 1e6
            out_1m = float(info.get("output_cost_per_token", 0) or 0) * 1e6
            if inp_1m == 0: inp_1m = float(info.get("input_cost_per_million_tokens", 0) or 0)
            if out_1m == 0: out_1m = float(info.get("output_cost_per_million_tokens", 0) or 0)
            ctx = info.get("max_input_tokens", 0)
            if inp_1m > 0 or out_1m > 0:
                if provider not in prices:
                    prices[provider] = {}
                model_key = raw_model_name.replace(f"{provider}/", "")
                norm = normalize_for_match(model_key)
                price_data = {
                    "input": inp_1m,
                    "output": out_1m,
                    "context": f"{ctx//1000}k" if ctx else "N/A"
                }
                prices[provider][norm] = price_data
                prices[provider][model_key.lower()] = price_data
        total = sum(len(v) for v in prices.values())
        print("  fetch_litellm_prices: %d providers, %d entries" % (len(prices), total), file=sys.stderr)
    except Exception as e:
        print("  fetch_litellm_prices error:", e, file=sys.stderr)
    return prices

LITELLM_DB = fetch_litellm_prices()

def get_dynamic_price(platform_key, mid):
    mid_lower = mid.lower()
    norm = normalize_for_match(mid)
    if platform_key in LITELLM_DB:
        if mid_lower in LITELLM_DB[platform_key]:
            d = LITELLM_DB[platform_key][mid_lower]
            return d["input"], d["output"], d["context"]
        if norm in LITELLM_DB[platform_key]:
            d = LITELLM_DB[platform_key][norm]
            return d["input"], d["output"], d["context"]
    return 0, 0, "N/A"
'''

# 替换 before 中的旧 fetch_litellm_prices
before_str = "".join(before)
old_litellm_pattern = r'# ─── LiteLLM 价格获取（Tier 3 兜底） ───\n.*?return prices\n'
before_str = re.sub(old_litellm_pattern, new_fetch_litellm, before_str, flags=re.DOTALL)
before = before_str.splitlines(keepends=True)

# 第三步：在价格映射函数区插入国内双轨制代码
new_domestic_code = '''# ═══════════════════════════════════════════════════════════
# 双轨制价格获取：海外走 LiteLLM，国内走 domestic_prices.json
# ═══════════════════════════════════════════════════════════

DOMESTIC_DB = {}
_dp_path = os.path.join(SCRIPT_DIR, "domestic_prices.json")
if os.path.exists(_dp_path):
    try:
        with open(_dp_path, "r", encoding="utf-8") as _f:
            DOMESTIC_DB = json.load(_f)
        _dc = sum(len(v) for v in DOMESTIC_DB.values())
        print("  domestic_prices.json: %d platforms, %d entries" % (len(DOMESTIC_DB), _dc), file=sys.stderr)
    except Exception as e:
        print("  domestic_prices.json load error:", e, file=sys.stderr)

def get_domestic_price(platform_key, raw_model_id):
    if platform_key not in DOMESTIC_DB:
        return None
    platform_rules = DOMESTIC_DB[platform_key]
    model_id = raw_model_id.lower()
    if model_id in platform_rules:
        return platform_rules[model_id]
    sorted_rule_keys = sorted(platform_rules.keys(), key=len, reverse=True)
    for rule_key in sorted_rule_keys:
        if model_id.startswith(rule_key):
            return platform_rules[rule_key]
    return None

def infer_tags_and_scene(mid, inp, out, ctx):
    n = mid.lower()
    tt = []
    if inp == 0 and out == 0: tt.append("免费额度")
    elif inp < 0.1: tt.append("极便宜")
    elif inp < 1: tt.append("便宜")
    elif inp < 5: tt.append("主力")
    else: tt.append("旗舰")
    if "r1" in n or "reason" in n or "think" in n or "qwq" in n or "kimi-k2" in n: tt.append("推理")
    if "coder" in n or "code" in n: tt.append("代码")
    if "vision" in n or "vl" in n: tt.append("视觉")
    if ctx and int(re.sub(r'[^\\d]', '', str(ctx)) or 0) >= 200000: tt.append("长上下文")
    if "推理" in tt: ss = "深度推理"
    elif "代码" in tt: ss = "编程代码"
    elif "视觉" in tt: ss = "视觉图片"
    else: ss = "日常对话"
    return tt, ss

'''

# 组合完整文件
full = "".join(before) + new_domestic_code + "".join(after)

with open("generate.py", "w", encoding="utf-8") as f:
    f.write(full)
print("Step 1-3 done: deleted price funcs, replaced litellm, added domestic dual-track")
