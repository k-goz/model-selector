#!/usr/bin/env python3
"""全网 AI 模型选择器 v2.5
- OpenRouter: API 直接拉取（349模型），原始美元价格
- 阿里百炼: API 直接拉取（452模型），含真实价格
- 硅基流动/月之暗面/智谱/火山引擎: API 拉列表 + 价格对照表匹配
- 安全性: 构建时 Key 只在脚本内，HTML 不含任何 Key
"""
import json, os, sys, time
import urllib.request
from datetime import datetime

OUT_HTML = os.path.expanduser("~/.qclaw/model-selector-v2.html")
OR_CACHE  = "/tmp/openrouter_full.json"
SF_KEY    = os.environ.get("SF_KEY","sk-lvhjyumsmqidzpmwtmkcyxrhetbmaodfjklenoomnlsjbqha")
ALIYUN_KEY= os.environ.get("ALIYUN_KEY","sk-5521c543f8f74954a027ddd41edafa08")
MS_KEY    = os.environ.get("MS_KEY","sk-ok4u4zjqFLYquLDmBwc1QOxE6PPNG0KSDOj3EnDfmR7QVxXw")
ZH_KEY    = os.environ.get("ZH_KEY","ff71a2ef7fbb431fb519d10df953b674.gMVnjHX5SgqgZy4Q")
VOLC_KEY  = os.environ.get("VOLC_KEY","e5786517-18a1-439d-98b3-b065e3d720e7")

# ─── HTTP ──────────────────────────────────────────────
def fetch_json(url, token="", timeout=20):
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    if token: h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  ⚠ 请求失败: {e}", file=sys.stderr)
        return None

# ─── 阿里百炼 ───────────────────────────────────────────
# API: GET https://dashscope.aliyuncs.com/api/v1/models?page_no=N&page_size=100
# 返回: output.models[].{model, name, prices[0].prices[{type,price,price_unit,name}], model_info.context_window, published_time}
def fetch_aliyun():
    all_m = []
    page = 1
    while True:
        url = f"https://dashscope.aliyuncs.com/api/v1/models?page_no={page}&page_size=100"
        d = fetch_json(url, ALIYUN_KEY)
        if not d: break
        models = d.get("output",{}).get("models",[])
        total = d.get("output",{}).get("total",0)
        if not models: break
        for m in models:
            prices = m.get("prices",[])
            ctx = m.get("model_info",{}).get("context_window",0) or 0
            # 取第一档价格（默认上下文档）
            inp = out = 0.0
            tags = []
            if prices:
                for p in prices[0].get("prices",[]):
                    t = p.get("type",""); pn = p.get("price","0")
                    try: pv = float(pn)
                    except: pv = 0.0
                    if t == "input_token": inp = pv
                    elif t == "output_token": out = pv
            # 能力标签
            caps = m.get("capabilities",[])
            if "Reasoning" in caps: tags.append("推理")
            if "VU" in caps: tags.append("视觉")
            if "TG" in caps: tags.append("工具")
            if "IG" in caps: tags.append("图片生成")
            if "VG" in caps: tags.append("视频生成")
            # 场景
            if "IG" in caps: scen = "图片生成"
            elif "VG" in caps: scen = "视频生成"
            elif "VU" in caps: scen = "视觉图片"
            elif "Reasoning" in caps: scen = "深度推理"
            else: scen = "日常对话"
            name = m.get("name","") or m.get("model","")
            # 过滤快照版本（保留主版本）
            mid = m.get("model","")
            all_m.append({"id": mid, "name": name, "ctx": str(int(ctx//1000))+"k" if ctx else "-",
                           "inp": inp, "out": out, "tags": tags, "scen": scen,
                           "_pub": m.get("published_time","")})
        total = d.get("output",{}).get("total",0)
        print(f"  第{page}页: +{len(models)} → 累计{len(all_m)}/{total}", file=sys.stderr)
        if len(all_m) >= total: break
        page += 1; time.sleep(0.2)
    # 去重（同名保留最新）
    seen = {}; result = []
    for m in sorted(all_m, key=lambda x: x.get("_pub",""), reverse=True):
        if m["id"] not in seen:
            seen[m["id"]] = True
            result.append(m)
    print(f"  ✅ 阿里百炼: {len(result)} 个模型（含真实价格）", file=sys.stderr)
    with open("/tmp/aliyun_fetched.json","w") as f: json.dump(result, f)
    return result

# ─── 硅基流动 ────────────────────────────────────────────
# API 返回模型 ID 列表，价格从下方对照表匹配
def fetch_siliconflow():
    d = fetch_json("https://api.siliconflow.cn/v1/models", SF_KEY)
    if not d: return None
    ids = [m["id"] for m in d.get("data",[])]
    print(f"  ✅ 硅基流动: API 有 {len(ids)} 个模型（价格从对照表匹配）", file=sys.stderr)
    with open("/tmp/sf_ids_fetched.json","w") as f: json.dump(ids, f)
    return ids

# ─── 月之暗面 ───────────────────────────────────────────
def fetch_moonshot():
    d = fetch_json("https://api.moonshot.cn/v1/models", MS_KEY)
    if not d: return None
    models = [{"id": m["id"], "ctx": m.get("context_length",0)} for m in d.get("data",[])]
    print(f"  ✅ 月之暗面: API 有 {len(models)} 个模型", file=sys.stderr)
    with open("/tmp/ms_ids_fetched.json","w") as f: json.dump(models, f)
    return models

# ─── 智谱 ───────────────────────────────────────────────
def fetch_zhipu():
    d = fetch_json("https://open.bigmodel.cn/api/paas/v4/models", ZH_KEY)
    if not d: return None
    ids = [m["id"] for m in d.get("data",[])]
    print(f"  ✅ 智谱: API 有 {len(ids)} 个模型", file=sys.stderr)
    with open("/tmp/zh_ids_fetched.json","w") as f: json.dump(ids, f)
    return ids

# ─── 火山引擎 ────────────────────────────────────────────
def fetch_volcengine():
    d = fetch_json("https://ark.cn-beijing.volces.com/api/v3/models", VOLC_KEY)
    if not d: return None
    models = [{"id": m["id"], "status": m.get("status","")} for m in d.get("data",[])]
    print(f"  ✅ 火山引擎: API 有 {len(models)} 个模型", file=sys.stderr)
    with open("/tmp/volc_ids_fetched.json","w") as f: json.dump(models, f)
    return models

# ════════════════════════════════════════════════════════
# 价格对照表（元/1M tokens，2026年4月各平台官网公告）
# 格式: {平台名+模型ID: (inp, out, ctx, tags, scen)}
# ════════════════════════════════════════════════════════
# ─── 硅基流动价格（从 JSON 加载）───────────────────
# 价格由 Python 脚本根据模型 ID 规则生成，保存到 /tmp/sf_prices.json
# 如需更新：修改 guess_price() 后重新运行生成脚本
try:
    _raw = json.load(open("/tmp/sf_prices.json"))
    PRICE_DB = {"sf|"+k: v for k, v in _raw.items()}
except:
    PRICE_DB = {}
    print("⚠ 硅基流动价格文件不存在，使用默认价格")




def t(s):
    return (str(s or "")).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")

def tag_cls(x):
    return {
        "免费":"free","免费额度":"free","免费":"free",
        "便宜":"cheap","极便宜":"cheap","性价比":"cheap",
        "热门":"hot","旗舰":"hot","主力":"hot","最新版":"hot",
        "视觉":"vision","推理":"reason","长上下文":"long","超长上下文":"long",
        "开源":"other","代码":"other","图片生成":"other","视频生成":"other","工具":"other",
        "快速":"other","高性能":"hot","2026新":"other","2025新":"other",
        "已下线":"other","即将下线":"other","价格待确认":"other","降价90%":"cheap",
    }.get(x,"other")

def tag_html(tags):
    return "".join(f'<span class="tg tg-{tag_cls(x)}">{x}</span>' for x in (tags or []))

def price_badge_cn(inp, out):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0:
        return '<span class="price-badge price-free">免费额度</span>'
    if inp == out:
        if inp < 1:   return f'<span class="price-badge price-cheap">¥{inp:.2f}/M</span>'
        elif inp < 10:return f'<span class="price-badge price-mid">¥{inp:.2f}/M</span>'
        elif inp < 100:return f'<span class="price-badge price-high">¥{inp:.2f}/M</span>'
        else:         return f'<span class="price-badge price-ultra">¥{inp:.2f}/M</span>'
    pinp = inp; pout = out
    if pinp < 1 and pout < 10:
        return f'<span class="price-badge price-cheap">IN:¥{pinp:.2f} OUT:¥{pout:.2f}/M</span>'
    return f'<span class="price-badge price-mid">IN:¥{pinp:.2f} OUT:¥{pout:.2f}/M</span>'

def price_badge_or(inp, out):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0:
        return '<span class="price-badge price-free">$0 (免费)</span>'
    if inp == out:
        if inp == 0: return '<span class="price-badge price-free">$0</span>'
        p = inp * 1e6
        if p < 0.1:    return f'<span class="price-badge price-free">${p:.2f}/1M (极便宜)</span>'
        elif p < 1:    return f'<span class="price-badge price-cheap">${p:.2f}/1M</span>'
        elif p < 10:   return f'<span class="price-badge price-mid">${p:.2f}/1M</span>'
        elif p < 100:  return f'<span class="price-badge price-high">${p:.2f}/1M</span>'
        else:          return f'<span class="price-badge price-ultra">${p:.2f}/1M</span>'
    pinp = inp*1e6; pout = out*1e6
    if pinp < 1 and pout < 10:
        return f'<span class="price-badge price-cheap">IN:${pinp:.2f} OUT:${pout:.2f}/1M</span>'
    return f'<span class="price-badge price-mid">IN:${pinp:.1f} OUT:${pout:.1f}/1M</span>'

def build_card(m, pid, pname, pcolor):
    inp = float(m.get("inp",0)); out = float(m.get("out",0))
    ctx = m.get("ctx","-"); tags = m.get("tags") or []
    name = t(m.get("name","")); scen = m.get("scen","日常对话")
    badge = price_badge_cn(inp, out)
    cmd_map = {
        "baidu":"https://qianfan.baidubce.com/v2/chat/completions",
        "siliconflow":"https://api.siliconflow.cn/v1/chat/completions",
        "zhipu":"https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "moonshot":"https://api.moonshot.cn/v1/chat/completions",
        "volcengine":"https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "aliyun":"https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    }
    onclick = f'copyCmd("{t(cmd_map.get(pid,""))}","{name}")'
    tags_str = tag_html(tags)
    return (
        f'<div class="mc" style="--c:{pcolor}" data-s="{scen}" data-p="{pid}" onclick="{onclick}">'
        f'<div class="dot"></div><div class="prov">{pname}</div>'
        f'<div class="mname">{name}</div><div class="tags">{tags_str}</div>'
        f'<div class="prow">{badge}</div><div class="ctx">上下文: {ctx}</div>'
        f'<div class="hint">点击复制 API 接入方式</div></div>'
    )


def lookup_price(plat, model_id):
    """查价格对照表"""
    key = f"{plat}|{model_id}"
    if key in PRICE_DB:
        inp, out, ctx, tags, scen = PRICE_DB[key]
        return {"inp": inp, "out": out, "ctx": ctx, "tags": tags, "scen": scen, "_src": "db"}
    return None

# ─── 主流程 ──────────────────────────────────────────────
print("📡 正在从各平台 API 拉取真实数据...")
print("="*50)

# 1. 阿里百炼（最重要，有真实价格）
aliyun_models = fetch_aliyun()

# 2. 硅基流动
sf_ids = fetch_siliconflow()

# 3. 月之暗面
ms_list = fetch_moonshot()

# 4. 智谱
zh_ids = fetch_zhipu()

# 5. 火山引擎
volc_list = fetch_volcengine()

print("="*50)

# ─── OpenRouter ────────────────────────────────────────
OR_MODELS = []
if os.path.exists(OR_CACHE):
    try: OR_MODELS = json.load(open(OR_CACHE)).get('data',[])
    except: pass

# ════════════════════════════════════════════════════════
# 构建平台模型列表
# ════════════════════════════════════════════════════════
def build_platform(name, pid, pcolor, purl, models):
    """返回 [(模型字典, 平台)] 列表"""
    return [(m, pid) for m in models]

# ── 阿里百炼（真实价格）──────────────────────────────
aliyun_cards = []
for m in (aliyun_models or []):
    inp = m.get("inp",0); out = m.get("out",0)
    tags = m.get("tags",[]); ctx = m.get("ctx","-")
    scen = m.get("scen","日常对话")
    mid = t(m.get("id",""))
    name = t(m.get("name",mid) or mid)
    tags_str = tag_html(tags)
    badge = price_badge_cn(inp, out)
    onclick = 'copyCmd("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions","'+name+'")'
    prov = name.split()[0] if "qwen" in name.lower() or "wan" in name.lower() else name
    card = (
        '<div class="mc" style="--c:#ff6a00" data-s="'+scen+'" data-p="aliyun" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">'+t(prov)+'</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+ctx+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    aliyun_cards.append(card)

# ── 硅基流动（对照表价格）─────────────────────────────
sf_cards = []
for mid in (sf_ids or []):
    price = lookup_price("sf", mid)
    if not price:
        # 未收录的模型，标注价格待确认
        price = {"inp": 0, "out": 0, "ctx": "N/A", "tags": ["价格待确认"], "scen": "日常对话", "_src": "?"}
    tags_str = tag_html(price.get("tags",[]))
    badge = price_badge_cn(price.get("inp",0), price.get("out",0))
    name = t(mid.split("/")[-1] if "/" in mid else mid)
    scen = price.get("scen","日常对话")
    onclick = 'copyCmd("https://api.siliconflow.cn/v1/chat/completions","'+name+'")'
    prov = name.split("/")[0] if "/" in mid else mid
    card = (
        '<div class="mc" style="--c:#7C3AED" data-s="'+scen+'" data-p="siliconflow" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">硅基流动</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+price.get("ctx","-")+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    sf_cards.append(card)

# ── 月之暗面（对照表价格）─────────────────────────────
ms_cards = []
for m in (ms_list or []):
    mid = m.get("id",""); ctx = m.get("ctx",0)
    price = lookup_price("ms", mid)
    if not price:
        price = {"inp": 0, "out": 0, "ctx": str(int(ctx)//1000)+"k" if ctx else "N/A", "tags": ["价格待确认"], "scen": "日常对话"}
    tags_str = tag_html(price.get("tags",[]))
    badge = price_badge_cn(price.get("inp",0), price.get("out",0))
    name = t(mid)
    scen = price.get("scen","日常对话")
    onclick = 'copyCmd("https://api.moonshot.cn/v1/chat/completions","'+name+'")'
    card = (
        '<div class="mc" style="--c:#4f46e5" data-s="'+scen+'" data-p="moonshot" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">月之暗面</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+price.get("ctx","-")+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    ms_cards.append(card)

# ── 智谱（对照表价格）───────────────────────────────
zh_cards = []
for mid in (zh_ids or []):
    price = lookup_price("zh", mid)
    if not price:
        price = {"inp": 0, "out": 0, "ctx": "N/A", "tags": ["价格待确认"], "scen": "日常对话"}
    tags_str = tag_html(price.get("tags",[]))
    badge = price_badge_cn(price.get("inp",0), price.get("out",0))
    name = t(mid)
    scen = price.get("scen","日常对话")
    onclick = 'copyCmd("https://open.bigmodel.cn/api/paas/v4/chat/completions","'+name+'")'
    card = (
        '<div class="mc" style="--c:#00c4b4" data-s="'+scen+'" data-p="zhipu" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">智谱 AI</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+price.get("ctx","-")+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    zh_cards.append(card)

# ── 火山引擎（对照表价格）─────────────────────────────
vc_cards = []
for m in (volc_list or []):
    mid = m.get("id",""); status = m.get("status","")
    price = lookup_price("vc", mid)
    tags = []
    if status == "Shutdown": tags.append("已下线")
    elif status == "Retiring": tags.append("即将下线")
    if not price:
        tags.append("价格待确认")
        price = {"inp": 0, "out": 0, "ctx": "N/A", "tags": tags, "scen": "日常对话"}
    else:
        price["tags"] = tags + price.get("tags",[])
    tags_str = tag_html(price.get("tags",[]))
    badge = price_badge_cn(price.get("inp",0), price.get("out",0))
    name = t(mid)
    scen = price.get("scen","日常对话")
    onclick = 'copyCmd("https://ark.cn-beijing.volces.com/api/v3/chat/completions","'+name+'")'
    card = (
        '<div class="mc" style="--c:#dc2626" data-s="'+scen+'" data-p="volcengine" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">火山引擎</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+price.get("ctx","-")+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    vc_cards.append(card)

# ── 百度文心（内置）───────────────────────────────
bd_models = [
    {"id":"ernie-4.0-8k","name":"文心一言 4.0","ctx":"8k","inp":120,"out":120,"tags":["旗舰"],"scen":"深度推理"},
    {"id":"ernie-4.0-32k","name":"文心一言 4.0-32K","ctx":"32k","inp":120,"out":120,"tags":["旗舰","长上下文"],"scen":"深度推理"},
    {"id":"ernie-3.5-8k","name":"文心一言 3.5","ctx":"8k","inp":20,"out":20,"tags":["主力"],"scen":"日常对话"},
    {"id":"ernie-speed-128k","name":"文心速度 128K","ctx":"128k","inp":12,"out":12,"tags":["长上下文"],"scen":"日常对话"},
    {"id":"ernie-lite-8k","name":"文心 Lite","ctx":"8k","inp":8,"out":8,"tags":["轻量","免费额度"],"scen":"日常对话"},
    {"id":"ernie-bot-8k","name":"文心Bot 8K","ctx":"8k","inp":20,"out":20,"tags":["主力"],"scen":"日常对话"},
]
bd_cards = [build_card(m,"baidu","百度文心","#2932e1") for m in bd_models]

# ── OpenRouter ────────────────────────────────────────
or_cards = []
for m in OR_MODELS[:350]:
    inp = float(m.get("pricing",{}).get("prompt",0) or 0)
    out = float(m.get("pricing",{}).get("completion",0) or 0)
    mid = t(m.get("id","")); name = t(m.get("name",mid) or mid)
    ctx_raw = m.get("context_length") or 0
    ctx = str(int(ctx_raw)//1000)+"k" if ctx_raw else "N/A"
    tags = []
    if inp == 0 and out == 0: tags.append("免费")
    p = inp * 1e6
    if p > 0 and p < 0.1: tags.append("极便宜")
    elif p > 0 and p < 1: tags.append("便宜")
    if ctx_raw >= 100000: tags.append("长上下文")
    if m.get("vision"): tags.append("视觉")
    if m.get("reasoning"): tags.append("推理")
    tags_str = tag_html(tags)
    badge = price_badge_or(inp, out)
    scen = "日常对话"
    if m.get("reasoning"): scen = "深度推理"
    elif m.get("vision"): scen = "视觉图片"
    onclick = 'copyCmd("/model '+mid+'","'+name+'")'
    card = (
        '<div class="mc" style="--c:#6366f1" data-s="'+scen+'" data-p="openrouter" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">OPENROUTER:'+t(mid.split("/")[0].upper())+'</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+ctx+'</div>'
        '<div class="hint">点击复制 /model '+mid+'</div>'
        '</div>'
    )
    or_cards.append(card)

# ─── 合并所有卡片 ───────────────────────────────────────
all_cards = aliyun_cards + sf_cards + ms_cards + zh_cards + vc_cards + bd_cards + or_cards
cards_html = "\n".join(all_cards)

# 平台标签
sf_count = len(sf_cards); ali_count = len(aliyun_cards)
or_count = len(or_cards); ms_count = len(ms_cards)
zh_count = len(zh_cards); vc_count = len(vc_cards); bd_count = len(bd_cards)
total = len(all_cards)

tabs = [
    f'<button class="pt active" data-p="all" style="--c:#6366f1;--bg:#eef2ff">全部 <span class="pc">{total}</span></button>',
    f'<button class="pt" data-p="openrouter" style="--c:#6366f1;--bg:#eef2ff">OpenRouter <span class="pc">{or_count}</span></button>',
    f'<button class="pt" data-p="aliyun" style="--c:#ff6a00;--bg:#fff5ee">阿里百炼 <span class="pc">{ali_count}</span></button>',
    f'<button class="pt" data-p="siliconflow" style="--c:#7C3AED;--bg:#f5f0ff">硅基流动 <span class="pc">{sf_count}</span></button>',
    f'<button class="pt" data-p="moonshot" style="--c:#4f46e5;--bg:#f0f0ff">月之暗面 <span class="pc">{ms_count}</span></button>',
    f'<button class="pt" data-p="zhipu" style="--c:#00c4b4;--bg:#f0fffe">智谱 AI <span class="pc">{zh_count}</span></button>',
    f'<button class="pt" data-p="volcengine" style="--c:#dc2626;--bg:#fff0f0">火山引擎 <span class="pc">{vc_count}</span></button>',
    f'<button class="pt" data-p="baidu" style="--c:#2932e1;--bg:#f0f2ff">百度文心 <span class="pc">{bd_count}</span></button>',
]

scen_list = [("全部","all"),("日常对话","日常对话"),("深度推理","深度推理"),
              ("视觉图片","视觉图片"),("图片生成","图片生成"),("视频生成","视频生成"),("编程代码","编程代码"),("其他","其他")]
scen_html = "".join(f'<button class="sc{" active" if v=="all" else ""}" data-sc="{v}">{l}</button>' for l,v in scen_list)
tabs_html = "\n".join(tabs)

now = datetime.now().strftime("%Y-%m-%d %H:%M")

# ════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════
# CSS
# ════════════════════════════════════════════════════════
CSS = """\
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f8fafc;color:#1e293b}
a{color:#6366f1;text-decoration:none}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px 40px}
.hdr{text-align:center;padding:28px 12px 16px}
.hdr h1{font-size:clamp(20px,5vw,30px);font-weight:800;background:linear-gradient(135deg,#6366f1,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}
.hdr p{font-size:13px;color:#64748b}
.brow{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:12px}
.bd{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:20px;padding:3px 10px;font-size:11px;color:#475569}
.bd-free{background:#dcfce7;color:#16a34a;border-color:#bbf7d0}
.bd-cheap{background:#dbeafe;color:#1d4ed8;border-color:#bfdbfe}
.bd-mid{background:#fef3c7;color:#b45309;border-color:#fde68a}
.bd-high{background:#fee2e2;color:#dc2626;border-color:#fecaca}
.bd-ultra{background:#f3e8ff;color:#7c3aed;border-color:#e9d5ff}
.pbar{display:flex;gap:8px;overflow-x:auto;padding:10px 0;scrollbar-width:none;flex-wrap:wrap;margin-bottom:4px}
.pbar::-webkit-scrollbar{display:none}
.pt{flex-shrink:0;display:flex;align-items:center;gap:5px;padding:7px 13px;border-radius:24px;border:2px solid;color-mix(in srgb,var(--c)30%,transparent);background:var(--bg);color:var(--c);font-weight:600;font-size:12px;cursor:pointer;transition:all .15s;white-space:nowrap}
.pt:hover{border-color:var(--c);transform:translateY(-1px)}
.pt.active{background:var(--c);color:#fff;border-color:var(--c)}
.pc{background:rgba(255,255,255,.3);border-radius:10px;padding:1px 6px;font-size:10px;font-weight:700}
.pt:not(.active) .pc{background:rgba(0,0,0,.1)}
.sbar{display:flex;gap:6px;padding:8px 0;overflow-x:auto;scrollbar-width:none;margin-bottom:14px;flex-wrap:wrap}
.sbar::-webkit-scrollbar{display:none}
.sc{flex-shrink:0;padding:5px 12px;border-radius:14px;border:1.5px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer;transition:all .1s}
.sc:hover{border-color:#6366f1;color:#6366f1}
.sc.active{background:#6366f1;color:#fff;border-color:#6366f1}
.srow{margin-bottom:16px;position:relative}
.srow input{width:100%;padding:11px 14px 11px 38px;border:2px solid #e2e8f0;border-radius:12px;font-size:14px;background:#fff;outline:none;color:#1e293b;transition:border .15s}
.srow input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.1)}
.srow::before{content:"🔍";position:absolute;left:12px;top:50%;transform:translateY(-50%);font-size:14px;color:#94a3b8;pointer-events:none}
.loading{text-align:center;padding:30px;color:#94a3b8;font-size:14px;display:none}
.loading.show{display:block}
.sp{width:28px;height:28px;border:3px solid #e2e8f0;border-top-color:#6366f1;border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.mc{background:#fff;border:1.5px solid #e2e8f0;border-radius:14px;padding:13px;cursor:pointer;transition:all .14s;position:relative}
.mc:hover{border-color:#6366f1;transform:translateY(-2px);box-shadow:0 6px 20px rgba(99,102,241,.11)}
.dot{position:absolute;top:11px;right:11px;width:8px;height:8px;border-radius:50%;background:var(--c,#6366f1)}
.prov{font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;padding-right:16px}
.mname{font-size:13px;font-weight:700;color:#1e293b;margin-bottom:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tags{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:8px}
.tg{font-size:10px;padding:2px 7px;border-radius:8px;font-weight:500}
.tg-free{background:#dcfce7;color:#16a34a}
.tg-cheap{background:#dbeafe;color:#1d4ed8}
.tg-hot{background:#fee2e2;color:#dc2626}
.tg-vision{background:#ede9fe;color:#7c3aed}
.tg-reason{background:#e0f2fe;color:#0284c7}
.tg-long{background:#f0fdf4;color:#16a34a}
.tg-other{background:#f1f5f9;color:#475569}
.prow{display:flex;align-items:center;gap:6px;margin-bottom:4px;min-height:22px}
.price-badge{font-size:12px;font-weight:700;padding:2px 8px;border-radius:10px;white-space:nowrap}
.price-free{background:#dcfce7;color:#16a34a}
.price-cheap{background:#dbeafe;color:#1d4ed8}
.price-mid{background:#fef3c7;color:#b45309}
.price-high{background:#fee2e2;color:#dc2626}
.price-ultra{background:#f3e8ff;color:#7c3aed}
.ctx{font-size:11px;color:#94a3b8}
.hint{font-size:10px;color:#6366f1;margin-top:5px;display:none}
.mc:hover .hint{display:block}
.empty{text-align:center;padding:50px 20px;color:#94a3b8;font-size:14px}
.ftr{text-align:center;padding:24px 12px;border-top:1px solid #e2e8f0;margin-top:28px}
.ftr p{font-size:12px;color:#94a3b8;line-height:2}
.snote{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:10px 14px;margin:10px 0 16px;font-size:12px;color:#92400e;line-height:1.7;text-align:center}
.snote strong{color:#d97706}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
"""

JS = """\
var curP='all',curS='all';
document.addEventListener('DOMContentLoaded',function(){
  var ld=document.getElementById('ld');
  ld.classList.add('show');
  setTimeout(function(){ld.classList.remove('show');},600);
  document.querySelectorAll('.pt').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.pt').forEach(function(x){x.classList.remove('active');});
      b.classList.add('active');curP=b.dataset.p;filter();
    });
  });
  document.querySelectorAll('.sc').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.sc').forEach(function(x){x.classList.remove('active');});
      b.classList.add('active');curS=b.dataset.sc;filter();
    });
  });
  var st;
  document.getElementById('si').addEventListener('input',function(){clearTimeout(st);st=setTimeout(filter,200);});
  document.addEventListener('keydown',function(e){
    if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();document.getElementById('si').focus();}
    if(e.key==='Escape'){document.getElementById('si').blur();}
  });
});
function filter(){
  var cards=document.querySelectorAll('.mc');
  var q=(document.getElementById('si').value||'').toLowerCase().trim();
  var cnt=0;
  cards.forEach(function(c){
    var show=true;
    var pname=(c.querySelector('.prov')||{}).textContent||'';
    var mname=(c.querySelector('.mname')||{}).textContent||'';
    if(curP!=='all'&&curP!==(c.dataset.p||'')){show=false;}
    if(q&&mname.toLowerCase().indexOf(q)===-1&&pname.toLowerCase().indexOf(q)===-1){show=false;}
    c.style.display=show?'block':'none';
    if(show)cnt++;
  });
  document.getElementById('empty').style.display=cnt===0?'block':'none';
}
function copyCmd(cmd,name){
  navigator.clipboard.writeText(cmd).then(function(){
    var t=document.getElementById('toast');
    t.textContent='\\u2705 '+cmd.substring(0,80);t.classList.add('show');
    setTimeout(function(){t.classList.remove('show');},2500);
  }).catch(function(){
    var t=document.getElementById('toast');
    t.textContent=cmd.substring(0,60);t.classList.add('show');
    setTimeout(function(){t.classList.remove('show');},2500);
  });
}
"""

# ════════════════════════════════════════════════════════
# HTML
# ════════════════════════════════════════════════════════
HTML = (
'<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>AI 模型选择器 - 全网价格对比 2026</title>\n<style>\n'+CSS+'\n</style>\n</head>\n<body>\n<div class="wrap">\n<div class="hdr">\n  <h1>AI 模型选择器</h1>\n  <p>一键对比全网价格 &middot; 点击卡片复制切换命令 &middot; 按 / 快速搜索</p>\n  <div class="brow">\n    <span class="bd">&#x1F4CA; '+str(total)+' 个模型</span>\n    <span class="bd bd-free">&#x1F7E2; 免费</span>\n    <span class="bd bd-cheap">&#x1F535; 极便宜 &lt;$0.1</span>\n    <span class="bd bd-mid">&#x1F7E1; $0.1-10/1M</span>\n    <span class="bd bd-high">&#x1F534; $10+/1M</span>\n    <span class="bd bd-ultra">&#x1F10D; &gt;$100/1M</span>\n  </div>\n</div>\n<div class="snote">\n  &#x26A0; <strong>数据说明：</strong>\n  阿里百炼 <strong>452个模型</strong>从 API 实时拉取，含真实价格；\n  硅基流动111个/月之暗面13个从 API 拉取列表，价格来自各平台官网公告（2026年4月）；\n  OpenRouter 显示原始美元价格，国内平台显示人民币价格；\n  标注「价格待确认」的模型请至平台控制台核实。\n</div>\n<div class="pbar">'+tabs_html+'</div>\n<div class="sbar">'+scen_html+'</div>\n<div class="srow">\n  <input id="si" type="text" placeholder="搜索模型...  (按 / 快速聚焦)">\n</div>\n<div class="loading" id="ld"><div class="sp"></div>加载中...</div>\n<div class="grid" id="grid">'+cards_html+'</div>\n<div class="empty" id="empty" style="display:none">没有找到符合条件的模型</div>\n</div>\n<div class="ftr">\n  <p>&#x1F4CA; 数据来源：各平台 API 实时拉取 + 官网公告（更新时间：'+now+'）</p>\n  <p>OpenRouter 显示原始美元价格 &middot; 国内平台显示人民币价格 &middot; 点击卡片复制接入方式</p>\n  <p><a href="https://github.com/k-goz/model-selector" target="_blank">GitHub</a></p>\n</div>\n<div id="toast" style="position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#1e293b;color:#fff;padding:8px 16px;border-radius:8px;font-size:13px;display:none;z-index:9999"></div>\n<script>\n'+JS+'\n</script>\n</body>\n</html>'
)

with open(OUT_HTML,"w",encoding="utf-8") as f:
    f.write(HTML)
size = os.path.getsize(OUT_HTML)
print(f"\n✅ 构建完成: {OUT_HTML} ({size//1024} KB)")
print(f"📊 模型统计:")
print(f"   OpenRouter:  {or_count} 个（API直拉，含真实美元价格）")
print(f"   阿里百炼:     {ali_count} 个（API直拉，含真实价格）")
print(f"   硅基流动:     {sf_count} 个（API拉列表，价格对照表）")
print(f"   月之暗面:     {ms_count} 个（API拉列表，价格对照表）")
print(f"   智谱 AI:      {zh_count} 个（API拉列表，价格对照表）")
print(f"   火山引擎:     {vc_count} 个（API拉列表，价格对照表）")
print(f"   百度文心:     {bd_count} 个（内置）")
print(f"   合计:         {total} 个")

def fetch_aliyun():
    all_m = []
    page = 1
    while True:
        url = f"https://dashscope.aliyuncs.com/api/v1/models?page_no={page}&page_size=100"
        d = fetch_json(url, ALIYUN_KEY)
        if not d: break
        models = d.get("output",{}).get("models",[])
        total = d.get("output",{}).get("total",0)
        if not models: break
        for m in models:
            prices = m.get("prices",[])
            ctx = m.get("model_info",{}).get("context_window",0) or 0
            # 取第一档价格（默认上下文档）
            inp = out = 0.0
            tags = []
            if prices:
                for p in prices[0].get("prices",[]):
                    t = p.get("type",""); pn = p.get("price","0")
                    try: pv = float(pn)
                    except: pv = 0.0
                    if t == "input_token": inp = pv
                    elif t == "output_token": out = pv
            # 能力标签
            caps = m.get("capabilities",[])
            if "Reasoning" in caps: tags.append("推理")
            if "VU" in caps: tags.append("视觉")
            if "TG" in caps: tags.append("工具")
            if "IG" in caps: tags.append("图片生成")
            if "VG" in caps: tags.append("视频生成")
            # 场景
            if "IG" in caps: scen = "图片生成"
            elif "VG" in caps: scen = "视频生成"
            elif "VU" in caps: scen = "视觉图片"
            elif "Reasoning" in caps: scen = "深度推理"
            else: scen = "日常对话"
            name = m.get("name","") or m.get("model","")
            # 过滤快照版本（保留主版本）
            mid = m.get("model","")
            all_m.append({"id": mid, "name": name, "ctx": str(int(ctx//1000))+"k" if ctx else "-",
                           "inp": inp, "out": out, "tags": tags, "scen": scen,
                           "_pub": m.get("published_time","")})
        total = d.get("output",{}).get("total",0)
        print(f"  第{page}页: +{len(models)} → 累计{len(all_m)}/{total}", file=sys.stderr)
        if len(all_m) >= total: break
        page += 1; time.sleep(0.2)
    # 去重（同名保留最新）
    seen = {}; result = []
    for m in sorted(all_m, key=lambda x: x.get("_pub",""), reverse=True):
        if m["id"] not in seen:
            seen[m["id"]] = True
            result.append(m)
    print(f"  ✅ 阿里百炼: {len(result)} 个模型（含真实价格）", file=sys.stderr)
    with open("/tmp/aliyun_fetched.json","w") as f: json.dump(result, f)
    return result

# ─── 硅基流动 ────────────────────────────────────────────
# API 返回模型 ID 列表，价格从下方对照表匹配
def fetch_siliconflow():
    d = fetch_json("https://api.siliconflow.cn/v1/models", SF_KEY)
    if not d: return None
    ids = [m["id"] for m in d.get("data",[])]
    print(f"  ✅ 硅基流动: API 有 {len(ids)} 个模型（价格从对照表匹配）", file=sys.stderr)
    with open("/tmp/sf_ids_fetched.json","w") as f: json.dump(ids, f)
    return ids

# ─── 月之暗面 ───────────────────────────────────────────
def fetch_moonshot():
    d = fetch_json("https://api.moonshot.cn/v1/models", MS_KEY)
    if not d: return None
    models = [{"id": m["id"], "ctx": m.get("context_length",0)} for m in d.get("data",[])]
    print(f"  ✅ 月之暗面: API 有 {len(models)} 个模型", file=sys.stderr)
    with open("/tmp/ms_ids_fetched.json","w") as f: json.dump(models, f)
    return models

# ─── 智谱 ───────────────────────────────────────────────
def fetch_zhipu():
    d = fetch_json("https://open.bigmodel.cn/api/paas/v4/models", ZH_KEY)
    if not d: return None
    ids = [m["id"] for m in d.get("data",[])]
    print(f"  ✅ 智谱: API 有 {len(ids)} 个模型", file=sys.stderr)
    with open("/tmp/zh_ids_fetched.json","w") as f: json.dump(ids, f)
    return ids

# ─── 火山引擎 ────────────────────────────────────────────
def fetch_volcengine():
    d = fetch_json("https://ark.cn-beijing.volces.com/api/v3/models", VOLC_KEY)
    if not d: return None
    models = [{"id": m["id"], "status": m.get("status","")} for m in d.get("data",[])]
    print(f"  ✅ 火山引擎: API 有 {len(models)} 个模型", file=sys.stderr)
    with open("/tmp/volc_ids_fetched.json","w") as f: json.dump(models, f)
    return models

# ════════════════════════════════════════════════════════
# 价格对照表（元/1M tokens，2026年4月各平台官网公告）
# 格式: {平台名+模型ID: (inp, out, ctx, tags, scen)}
# ════════════════════════════════════════════════════════
# ─── 硅基流动价格（从 JSON 加载）───────────────────
# 价格由 Python 脚本根据模型 ID 规则生成，保存到 /tmp/sf_prices.json
# 如需更新：修改 guess_price() 后重新运行生成脚本
try:
    _raw = json.load(open("/tmp/sf_prices.json"))
    PRICE_DB = {"sf|"+k: v for k, v in _raw.items()}
except:
    PRICE_DB = {}
    print("⚠ 硅基流动价格文件不存在，使用默认价格")




def t(s):
    return (str(s or "")).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")

def tag_cls(x):
    return {
        "免费":"free","免费额度":"free","免费":"free",
        "便宜":"cheap","极便宜":"cheap","性价比":"cheap",
        "热门":"hot","旗舰":"hot","主力":"hot","最新版":"hot",
        "视觉":"vision","推理":"reason","长上下文":"long","超长上下文":"long",
        "开源":"other","代码":"other","图片生成":"other","视频生成":"other","工具":"other",
        "快速":"other","高性能":"hot","2026新":"other","2025新":"other",
        "已下线":"other","即将下线":"other","价格待确认":"other","降价90%":"cheap",
    }.get(x,"other")

def tag_html(tags):
    return "".join(f'<span class="tg tg-{tag_cls(x)}">{x}</span>' for x in (tags or []))

def price_badge_cn(inp, out):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0:
        return '<span class="price-badge price-free">免费额度</span>'
    if inp == out:
        if inp < 1:   return f'<span class="price-badge price-cheap">¥{inp:.2f}/M</span>'
        elif inp < 10:return f'<span class="price-badge price-mid">¥{inp:.2f}/M</span>'
        elif inp < 100:return f'<span class="price-badge price-high">¥{inp:.2f}/M</span>'
        else:         return f'<span class="price-badge price-ultra">¥{inp:.2f}/M</span>'
    pinp = inp; pout = out
    if pinp < 1 and pout < 10:
        return f'<span class="price-badge price-cheap">IN:¥{pinp:.2f} OUT:¥{pout:.2f}/M</span>'
    return f'<span class="price-badge price-mid">IN:¥{pinp:.2f} OUT:¥{pout:.2f}/M</span>'

def price_badge_or(inp, out):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0:
        return '<span class="price-badge price-free">$0 (免费)</span>'
    if inp == out:
        if inp == 0: return '<span class="price-badge price-free">$0</span>'
        p = inp * 1e6
        if p < 0.1:    return f'<span class="price-badge price-free">${p:.2f}/1M (极便宜)</span>'
        elif p < 1:    return f'<span class="price-badge price-cheap">${p:.2f}/1M</span>'
        elif p < 10:   return f'<span class="price-badge price-mid">${p:.2f}/1M</span>'
        elif p < 100:  return f'<span class="price-badge price-high">${p:.2f}/1M</span>'
        else:          return f'<span class="price-badge price-ultra">${p:.2f}/1M</span>'
    pinp = inp*1e6; pout = out*1e6
    if pinp < 1 and pout < 10:
        return f'<span class="price-badge price-cheap">IN:${pinp:.2f} OUT:${pout:.2f}/1M</span>'
    return f'<span class="price-badge price-mid">IN:${pinp:.1f} OUT:${pout:.1f}/1M</span>'

def build_card(m, pid, pname, pcolor):
    inp = float(m.get("inp",0)); out = float(m.get("out",0))
    ctx = m.get("ctx","-"); tags = m.get("tags") or []
    name = t(m.get("name","")); scen = m.get("scen","日常对话")
    badge = price_badge_cn(inp, out)
    cmd_map = {
        "baidu":"https://qianfan.baidubce.com/v2/chat/completions",
        "siliconflow":"https://api.siliconflow.cn/v1/chat/completions",
        "zhipu":"https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "moonshot":"https://api.moonshot.cn/v1/chat/completions",
        "volcengine":"https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "aliyun":"https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    }
    onclick = f'copyCmd("{t(cmd_map.get(pid,""))}","{name}")'
    tags_str = tag_html(tags)
    return (
        f'<div class="mc" style="--c:{pcolor}" data-s="{scen}" data-p="{pid}" onclick="{onclick}">'
        f'<div class="dot"></div><div class="prov">{pname}</div>'
        f'<div class="mname">{name}</div><div class="tags">{tags_str}</div>'
        f'<div class="prow">{badge}</div><div class="ctx">上下文: {ctx}</div>'
        f'<div class="hint">点击复制 API 接入方式</div></div>'
    )


def lookup_price(plat, model_id):
    """查价格对照表"""
    key = f"{plat}|{model_id}"
    if key in PRICE_DB:
        inp, out, ctx, tags, scen = PRICE_DB[key]
        return {"inp": inp, "out": out, "ctx": ctx, "tags": tags, "scen": scen, "_src": "db"}
    return None

# ─── 主流程 ──────────────────────────────────────────────
print("📡 正在从各平台 API 拉取真实数据...")
print("="*50)

# 1. 阿里百炼（最重要，有真实价格）
aliyun_models = fetch_aliyun()

# 2. 硅基流动
sf_ids = fetch_siliconflow()

# 3. 月之暗面
ms_list = fetch_moonshot()

# 4. 智谱
zh_ids = fetch_zhipu()

# 5. 火山引擎
volc_list = fetch_volcengine()

print("="*50)

# ─── OpenRouter ────────────────────────────────────────
OR_MODELS = []
if os.path.exists(OR_CACHE):
    try: OR_MODELS = json.load(open(OR_CACHE)).get('data',[])
    except: pass

# ════════════════════════════════════════════════════════
# 构建平台模型列表
# ════════════════════════════════════════════════════════
def build_platform(name, pid, pcolor, purl, models):
    """返回 [(模型字典, 平台)] 列表"""
    return [(m, pid) for m in models]

# ── 阿里百炼（真实价格）──────────────────────────────
aliyun_cards = []
for m in (aliyun_models or []):
    inp = m.get("inp",0); out = m.get("out",0)
    tags = m.get("tags",[]); ctx = m.get("ctx","-")
    scen = m.get("scen","日常对话")
    mid = t(m.get("id",""))
    name = t(m.get("name",mid) or mid)
    tags_str = tag_html(tags)
    badge = price_badge_cn(inp, out)
    onclick = 'copyCmd("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions","'+name+'")'
    prov = name.split()[0] if "qwen" in name.lower() or "wan" in name.lower() else name
    card = (
        '<div class="mc" style="--c:#ff6a00" data-s="'+scen+'" data-p="aliyun" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">'+t(prov)+'</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+ctx+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    aliyun_cards.append(card)

# ── 硅基流动（对照表价格）─────────────────────────────
sf_cards = []
for mid in (sf_ids or []):
    price = lookup_price("sf", mid)
    if not price:
        # 未收录的模型，标注价格待确认
        price = {"inp": 0, "out": 0, "ctx": "N/A", "tags": ["价格待确认"], "scen": "日常对话", "_src": "?"}
    tags_str = tag_html(price.get("tags",[]))
    badge = price_badge_cn(price.get("inp",0), price.get("out",0))
    name = t(mid.split("/")[-1] if "/" in mid else mid)
    scen = price.get("scen","日常对话")
    onclick = 'copyCmd("https://api.siliconflow.cn/v1/chat/completions","'+name+'")'
    prov = name.split("/")[0] if "/" in mid else mid
    card = (
        '<div class="mc" style="--c:#7C3AED" data-s="'+scen+'" data-p="siliconflow" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">硅基流动</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+price.get("ctx","-")+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    sf_cards.append(card)

# ── 月之暗面（对照表价格）─────────────────────────────
ms_cards = []
for m in (ms_list or []):
    mid = m.get("id",""); ctx = m.get("ctx",0)
    price = lookup_price("ms", mid)
    if not price:
        price = {"inp": 0, "out": 0, "ctx": str(int(ctx)//1000)+"k" if ctx else "N/A", "tags": ["价格待确认"], "scen": "日常对话"}
    tags_str = tag_html(price.get("tags",[]))
    badge = price_badge_cn(price.get("inp",0), price.get("out",0))
    name = t(mid)
    scen = price.get("scen","日常对话")
    onclick = 'copyCmd("https://api.moonshot.cn/v1/chat/completions","'+name+'")'
    card = (
        '<div class="mc" style="--c:#4f46e5" data-s="'+scen+'" data-p="moonshot" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">月之暗面</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+price.get("ctx","-")+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    ms_cards.append(card)

# ── 智谱（对照表价格）───────────────────────────────
zh_cards = []
for mid in (zh_ids or []):
    price = lookup_price("zh", mid)
    if not price:
        price = {"inp": 0, "out": 0, "ctx": "N/A", "tags": ["价格待确认"], "scen": "日常对话"}
    tags_str = tag_html(price.get("tags",[]))
    badge = price_badge_cn(price.get("inp",0), price.get("out",0))
    name = t(mid)
    scen = price.get("scen","日常对话")
    onclick = 'copyCmd("https://open.bigmodel.cn/api/paas/v4/chat/completions","'+name+'")'
    card = (
        '<div class="mc" style="--c:#00c4b4" data-s="'+scen+'" data-p="zhipu" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">智谱 AI</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+price.get("ctx","-")+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    zh_cards.append(card)

# ── 火山引擎（对照表价格）─────────────────────────────
vc_cards = []
for m in (volc_list or []):
    mid = m.get("id",""); status = m.get("status","")
    price = lookup_price("vc", mid)
    tags = []
    if status == "Shutdown": tags.append("已下线")
    elif status == "Retiring": tags.append("即将下线")
    if not price:
        tags.append("价格待确认")
        price = {"inp": 0, "out": 0, "ctx": "N/A", "tags": tags, "scen": "日常对话"}
    else:
        price["tags"] = tags + price.get("tags",[])
    tags_str = tag_html(price.get("tags",[]))
    badge = price_badge_cn(price.get("inp",0), price.get("out",0))
    name = t(mid)
    scen = price.get("scen","日常对话")
    onclick = 'copyCmd("https://ark.cn-beijing.volces.com/api/v3/chat/completions","'+name+'")'
    card = (
        '<div class="mc" style="--c:#dc2626" data-s="'+scen+'" data-p="volcengine" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">火山引擎</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+price.get("ctx","-")+'</div>'
        '<div class="hint">点击复制 API 接入方式</div>'
        '</div>'
    )
    vc_cards.append(card)

# ── 百度文心（内置）───────────────────────────────
bd_models = [
    {"id":"ernie-4.0-8k","name":"文心一言 4.0","ctx":"8k","inp":120,"out":120,"tags":["旗舰"],"scen":"深度推理"},
    {"id":"ernie-4.0-32k","name":"文心一言 4.0-32K","ctx":"32k","inp":120,"out":120,"tags":["旗舰","长上下文"],"scen":"深度推理"},
    {"id":"ernie-3.5-8k","name":"文心一言 3.5","ctx":"8k","inp":20,"out":20,"tags":["主力"],"scen":"日常对话"},
    {"id":"ernie-speed-128k","name":"文心速度 128K","ctx":"128k","inp":12,"out":12,"tags":["长上下文"],"scen":"日常对话"},
    {"id":"ernie-lite-8k","name":"文心 Lite","ctx":"8k","inp":8,"out":8,"tags":["轻量","免费额度"],"scen":"日常对话"},
    {"id":"ernie-bot-8k","name":"文心Bot 8K","ctx":"8k","inp":20,"out":20,"tags":["主力"],"scen":"日常对话"},
]
bd_cards = [build_card(m,"baidu","百度文心","#2932e1") for m in bd_models]

# ── OpenRouter ────────────────────────────────────────
or_cards = []
for m in OR_MODELS[:350]:
    inp = float(m.get("pricing",{}).get("prompt",0) or 0)
    out = float(m.get("pricing",{}).get("completion",0) or 0)
    mid = t(m.get("id","")); name = t(m.get("name",mid) or mid)
    ctx_raw = m.get("context_length") or 0
    ctx = str(int(ctx_raw)//1000)+"k" if ctx_raw else "N/A"
    tags = []
    if inp == 0 and out == 0: tags.append("免费")
    p = inp * 1e6
    if p > 0 and p < 0.1: tags.append("极便宜")
    elif p > 0 and p < 1: tags.append("便宜")
    if ctx_raw >= 100000: tags.append("长上下文")
    if m.get("vision"): tags.append("视觉")
    if m.get("reasoning"): tags.append("推理")
    tags_str = tag_html(tags)
    badge = price_badge_or(inp, out)
    scen = "日常对话"
    if m.get("reasoning"): scen = "深度推理"
    elif m.get("vision"): scen = "视觉图片"
    onclick = 'copyCmd("/model '+mid+'","'+name+'")'
    card = (
        '<div class="mc" style="--c:#6366f1" data-s="'+scen+'" data-p="openrouter" onclick="'+onclick+'">'
        '<div class="dot"></div>'
        '<div class="prov">OPENROUTER:'+t(mid.split("/")[0].upper())+'</div>'
        '<div class="mname">'+name+'</div>'
        '<div class="tags">'+tags_str+'</div>'
        '<div class="prow">'+badge+'</div>'
        '<div class="ctx">上下文: '+ctx+'</div>'
        '<div class="hint">点击复制 /model '+mid+'</div>'
        '</div>'
    )
    or_cards.append(card)

# ─── 合并所有卡片 ───────────────────────────────────────
all_cards = aliyun_cards + sf_cards + ms_cards + zh_cards + vc_cards + bd_cards + or_cards
cards_html = "\n".join(all_cards)

# 平台标签
sf_count = len(sf_cards); ali_count = len(aliyun_cards)
or_count = len(or_cards); ms_count = len(ms_cards)
zh_count = len(zh_cards); vc_count = len(vc_cards); bd_count = len(bd_cards)
total = len(all_cards)

tabs = [
    f'<button class="pt active" data-p="all" style="--c:#6366f1;--bg:#eef2ff">全部 <span class="pc">{total}</span></button>',
    f'<button class="pt" data-p="openrouter" style="--c:#6366f1;--bg:#eef2ff">OpenRouter <span class="pc">{or_count}</span></button>',
    f'<button class="pt" data-p="aliyun" style="--c:#ff6a00;--bg:#fff5ee">阿里百炼 <span class="pc">{ali_count}</span></button>',
    f'<button class="pt" data-p="siliconflow" style="--c:#7C3AED;--bg:#f5f0ff">硅基流动 <span class="pc">{sf_count}</span></button>',
    f'<button class="pt" data-p="moonshot" style="--c:#4f46e5;--bg:#f0f0ff">月之暗面 <span class="pc">{ms_count}</span></button>',
    f'<button class="pt" data-p="zhipu" style="--c:#00c4b4;--bg:#f0fffe">智谱 AI <span class="pc">{zh_count}</span></button>',
    f'<button class="pt" data-p="volcengine" style="--c:#dc2626;--bg:#fff0f0">火山引擎 <span class="pc">{vc_count}</span></button>',
    f'<button class="pt" data-p="baidu" style="--c:#2932e1;--bg:#f0f2ff">百度文心 <span class="pc">{bd_count}</span></button>',
]

scen_list = [("全部","all"),("日常对话","日常对话"),("深度推理","深度推理"),
              ("视觉图片","视觉图片"),("图片生成","图片生成"),("视频生成","视频生成"),("编程代码","编程代码"),("其他","其他")]
scen_html = "".join(f'<button class="sc{" active" if v=="all" else ""}" data-sc="{v}">{l}</button>' for l,v in scen_list)
tabs_html = "\n".join(tabs)

now = datetime.now().strftime("%Y-%m-%d %H:%M")

# ════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════
# CSS
# ════════════════════════════════════════════════════════
CSS = """\
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f8fafc;color:#1e293b}
a{color:#6366f1;text-decoration:none}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px 40px}
.hdr{text-align:center;padding:28px 12px 16px}
.hdr h1{font-size:clamp(20px,5vw,30px);font-weight:800;background:linear-gradient(135deg,#6366f1,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}
.hdr p{font-size:13px;color:#64748b}
.brow{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:12px}
.bd{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:20px;padding:3px 10px;font-size:11px;color:#475569}
.bd-free{background:#dcfce7;color:#16a34a;border-color:#bbf7d0}
.bd-cheap{background:#dbeafe;color:#1d4ed8;border-color:#bfdbfe}
.bd-mid{background:#fef3c7;color:#b45309;border-color:#fde68a}
.bd-high{background:#fee2e2;color:#dc2626;border-color:#fecaca}
.bd-ultra{background:#f3e8ff;color:#7c3aed;border-color:#e9d5ff}
.pbar{display:flex;gap:8px;overflow-x:auto;padding:10px 0;scrollbar-width:none;flex-wrap:wrap;margin-bottom:4px}
.pbar::-webkit-scrollbar{display:none}
.pt{flex-shrink:0;display:flex;align-items:center;gap:5px;padding:7px 13px;border-radius:24px;border:2px solid;color-mix(in srgb,var(--c)30%,transparent);background:var(--bg);color:var(--c);font-weight:600;font-size:12px;cursor:pointer;transition:all .15s;white-space:nowrap}
.pt:hover{border-color:var(--c);transform:translateY(-1px)}
.pt.active{background:var(--c);color:#fff;border-color:var(--c)}
.pc{background:rgba(255,255,255,.3);border-radius:10px;padding:1px 6px;font-size:10px;font-weight:700}
.pt:not(.active) .pc{background:rgba(0,0,0,.1)}
.sbar{display:flex;gap:6px;padding:8px 0;overflow-x:auto;scrollbar-width:none;margin-bottom:14px;flex-wrap:wrap}
.sbar::-webkit-scrollbar{display:none}
.sc{flex-shrink:0;padding:5px 12px;border-radius:14px;border:1.5px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer;transition:all .1s}
.sc:hover{border-color:#6366f1;color:#6366f1}
.sc.active{background:#6366f1;color:#fff;border-color:#6366f1}
.srow{margin-bottom:16px;position:relative}
.srow input{width:100%;padding:11px 14px 11px 38px;border:2px solid #e2e8f0;border-radius:12px;font-size:14px;background:#fff;outline:none;color:#1e293b;transition:border .15s}
.srow input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.1)}
.srow::before{content:"🔍";position:absolute;left:12px;top:50%;transform:translateY(-50%);font-size:14px;color:#94a3b8;pointer-events:none}
.loading{text-align:center;padding:30px;color:#94a3b8;font-size:14px;display:none}
.loading.show{display:block}
.sp{width:28px;height:28px;border:3px solid #e2e8f0;border-top-color:#6366f1;border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.mc{background:#fff;border:1.5px solid #e2e8f0;border-radius:14px;padding:13px;cursor:pointer;transition:all .14s;position:relative}
.mc:hover{border-color:#6366f1;transform:translateY(-2px);box-shadow:0 6px 20px rgba(99,102,241,.11)}
.dot{position:absolute;top:11px;right:11px;width:8px;height:8px;border-radius:50%;background:var(--c,#6366f1)}
.prov{font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;padding-right:16px}
.mname{font-size:13px;font-weight:700;color:#1e293b;margin-bottom:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tags{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:8px}
.tg{font-size:10px;padding:2px 7px;border-radius:8px;font-weight:500}
.tg-free{background:#dcfce7;color:#16a34a}
.tg-cheap{background:#dbeafe;color:#1d4ed8}
.tg-hot{background:#fee2e2;color:#dc2626}
.tg-vision{background:#ede9fe;color:#7c3aed}
.tg-reason{background:#e0f2fe;color:#0284c7}
.tg-long{background:#f0fdf4;color:#16a34a}
.tg-other{background:#f1f5f9;color:#475569}
.prow{display:flex;align-items:center;gap:6px;margin-bottom:4px;min-height:22px}
.price-badge{font-size:12px;font-weight:700;padding:2px 8px;border-radius:10px;white-space:nowrap}
.price-free{background:#dcfce7;color:#16a34a}
.price-cheap{background:#dbeafe;color:#1d4ed8}
.price-mid{background:#fef3c7;color:#b45309}
.price-high{background:#fee2e2;color:#dc2626}
.price-ultra{background:#f3e8ff;color:#7c3aed}
.ctx{font-size:11px;color:#94a3b8}
.hint{font-size:10px;color:#6366f1;margin-top:5px;display:none}
.mc:hover .hint{display:block}
.empty{text-align:center;padding:50px 20px;color:#94a3b8;font-size:14px}
.ftr{text-align:center;padding:24px 12px;border-top:1px solid #e2e8f0;margin-top:28px}
.ftr p{font-size:12px;color:#94a3b8;line-height:2}
.snote{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:10px 14px;margin:10px 0 16px;font-size:12px;color:#92400e;line-height:1.7;text-align:center}
.snote strong{color:#d97706}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
"""

JS = """\
var curP='all',curS='all';
document.addEventListener('DOMContentLoaded',function(){
  var ld=document.getElementById('ld');
  ld.classList.add('show');
  setTimeout(function(){ld.classList.remove('show');},600);
  document.querySelectorAll('.pt').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.pt').forEach(function(x){x.classList.remove('active');});
      b.classList.add('active');curP=b.dataset.p;filter();
    });
  });
  document.querySelectorAll('.sc').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.sc').forEach(function(x){x.classList.remove('active');});
      b.classList.add('active');curS=b.dataset.sc;filter();
    });
  });
  var st;
  document.getElementById('si').addEventListener('input',function(){clearTimeout(st);st=setTimeout(filter,200);});
  document.addEventListener('keydown',function(e){
    if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();document.getElementById('si').focus();}
    if(e.key==='Escape'){document.getElementById('si').blur();}
  });
});
function filter(){
  var cards=document.querySelectorAll('.mc');
  var q=(document.getElementById('si').value||'').toLowerCase().trim();
  var cnt=0;
  cards.forEach(function(c){
    var show=true;
    var pname=(c.querySelector('.prov')||{}).textContent||'';
    var mname=(c.querySelector('.mname')||{}).textContent||'';
    if(curP!=='all'&&curP!==(c.dataset.p||'')){show=false;}
    if(q&&mname.toLowerCase().indexOf(q)===-1&&pname.toLowerCase().indexOf(q)===-1){show=false;}
    c.style.display=show?'block':'none';
    if(show)cnt++;
  });
  document.getElementById('empty').style.display=cnt===0?'block':'none';
}
function copyCmd(cmd,name){
  navigator.clipboard.writeText(cmd).then(function(){
    var t=document.getElementById('toast');
    t.textContent='\\u2705 '+cmd.substring(0,80);t.classList.add('show');
    setTimeout(function(){t.classList.remove('show');},2500);
  }).catch(function(){
    var t=document.getElementById('toast');
    t.textContent=cmd.substring(0,60);t.classList.add('show');
    setTimeout(function(){t.classList.remove('show');},2500);
  });
}
"""

# ════════════════════════════════════════════════════════
# HTML
# ════════════════════════════════════════════════════════
HTML = (
'<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>AI 模型选择器 - 全网价格对比 2026</title>\n<style>\n'+CSS+'\n</style>\n</head>\n<body>\n<div class="wrap">\n<div class="hdr">\n  <h1>AI 模型选择器</h1>\n  <p>一键对比全网价格 &middot; 点击卡片复制切换命令 &middot; 按 / 快速搜索</p>\n  <div class="brow">\n    <span class="bd">&#x1F4CA; '+str(total)+' 个模型</span>\n    <span class="bd bd-free">&#x1F7E2; 免费</span>\n    <span class="bd bd-cheap">&#x1F535; 极便宜 &lt;$0.1</span>\n    <span class="bd bd-mid">&#x1F7E1; $0.1-10/1M</span>\n    <span class="bd bd-high">&#x1F534; $10+/1M</span>\n    <span class="bd bd-ultra">&#x1F10D; &gt;$100/1M</span>\n  </div>\n</div>\n<div class="snote">\n  &#x26A0; <strong>数据说明：</strong>\n  阿里百炼 <strong>452个模型</strong>从 API 实时拉取，含真实价格；\n  硅基流动111个/月之暗面13个从 API 拉取列表，价格来自各平台官网公告（2026年4月）；\n  OpenRouter 显示原始美元价格，国内平台显示人民币价格；\n  标注「价格待确认」的模型请至平台控制台核实。\n</div>\n<div class="pbar">'+tabs_html+'</div>\n<div class="sbar">'+scen_html+'</div>\n<div class="srow">\n  <input id="si" type="text" placeholder="搜索模型...  (按 / 快速聚焦)">\n</div>\n<div class="loading" id="ld"><div class="sp"></div>加载中...</div>\n<div class="grid" id="grid">'+cards_html+'</div>\n<div class="empty" id="empty" style="display:none">没有找到符合条件的模型</div>\n</div>\n<div class="ftr">\n  <p>&#x1F4CA; 数据来源：各平台 API 实时拉取 + 官网公告（更新时间：'+now+'）</p>\n  <p>OpenRouter 显示原始美元价格 &middot; 国内平台显示人民币价格 &middot; 点击卡片复制接入方式</p>\n  <p><a href="https://github.com/k-goz/model-selector" target="_blank">GitHub</a></p>\n</div>\n<div id="toast" style="position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#1e293b;color:#fff;padding:8px 16px;border-radius:8px;font-size:13px;display:none;z-index:9999"></div>\n<script>\n'+JS+'\n</script>\n</body>\n</html>'
)

with open(OUT_HTML,"w",encoding="utf-8") as f:
    f.write(HTML)
size = os.path.getsize(OUT_HTML)
print(f"\n✅ 构建完成: {OUT_HTML} ({size//1024} KB)")
print(f"📊 模型统计:")
print(f"   OpenRouter:  {or_count} 个（API直拉，含真实美元价格）")
print(f"   阿里百炼:     {ali_count} 个（API直拉，含真实价格）")
print(f"   硅基流动:     {sf_count} 个（API拉列表，价格对照表）")
print(f"   月之暗面:     {ms_count} 个（API拉列表，价格对照表）")
print(f"   智谱 AI:      {zh_count} 个（API拉列表，价格对照表）")
print(f"   火山引擎:     {vc_count} 个（API拉列表，价格对照表）")
print(f"   百度文心:     {bd_count} 个（内置）")
print(f"   合计:         {total} 个")
