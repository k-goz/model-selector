"""模型卡片 HTML 渲染。"""

from __future__ import annotations

import re
from typing import Any, List

from src.pricing import classify_price

OFFICIAL_PRICES: dict[str, dict[str, Any]] = {}


def set_official_prices(prices: dict[str, dict[str, Any]]) -> None:
    """设置本轮抓取到的可变官方价格。"""
    global OFFICIAL_PRICES
    OFFICIAL_PRICES = prices


def Te(s: str) -> str:
    """HTML 转义函数"""
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# ─── 标签 HTML ───
def th(tags: List[str]) -> str:
    """生成标签 HTML"""
    m = {
        "免费": "free", "免费额度": "free", "便宜": "cheap", "极便宜": "cheap", "性价比": "cheap",
        "旗舰": "hot", "主力": "hot", "最新版": "hot", "2025新": "hot", "2026新": "hot",
        "视觉": "vision", "推理": "reason", "长上下文": "long", "超长上下文": "long",
        "开源": "other", "代码": "other", "图片生成": "other", "视频生成": "other",
        "快速": "other", "高性能": "hot", "Pro订阅": "other", "蒸馏": "other",
        "轻量": "other", "已下线": "other", "即将下线": "other", "价格待确认": "other",
        "语音": "other", "TTS": "other", "ASR": "other", "向量": "other", "排序": "other",
        "OCR": "other", "多模态": "vision", "Turbo": "hot", "降价后": "cheap", "降价90%": "cheap",
        "超低价": "cheap", "编程": "other", "智能路由": "other", "满血版": "hot",
        "价格变动": "other", "涨价": "hot", "降价": "cheap", "按次计费": "other"
    }
    return "".join('<span class="tg tg-' + m.get(x, "other") + '">' + x + '</span>' for x in (tags or []))

# ─── 价格徽章 (CNY) ───
def bc(inp: float, out: float, price_classification=None) -> str:
    """生成 CNY 价格徽章 HTML"""
    inp = float(inp or 0)
    out = float(out or 0)
    if price_classification and price_classification.status != "priced":
        css_class = "price-free" if price_classification.status == "free" else "price-unknown"
        return '<span class="price-badge ' + css_class + '">' + Te(price_classification.label) + '</span>'
    if inp == out:
        c = "price-cheap" if inp < 1 else "price-mid" if inp < 10 else "price-high" if inp < 100 else "price-ultra"
        return '<span class="price-badge ' + c + '">¥' + ("%.2f" % inp) + '/M</span>'
    return '<span class="price-badge price-mid">IN:¥' + ("%.2f" % inp) + ' OUT:¥' + ("%.2f" % out) + '/M</span>'

# ─── 价格徽章 (USD) ───
def bo(inp: float, out: float, price_unit: str = "per_token", price_classification=None) -> str:
    """
    生成 USD 价格徽章 HTML
    
    Args:
        inp: 输入价格
        out: 输出价格
        price_unit: "per_token" = $/token (multiply 1e6 to display), "per_1m" = already $/1M tokens
    """
    inp = float(inp or 0)
    out = float(out or 0)
    if price_classification and price_classification.status != "priced":
        css_class = "price-free" if price_classification.status == "free" else "price-unknown"
        return '<span class="price-badge ' + css_class + '">' + Te(price_classification.label) + '</span>'
    if price_unit == "per_token":
        p = inp * 1e6
        q = out * 1e6
    else:
        p = inp; q = out
    if inp == out:
        c = "price-free" if p < 0.1 else "price-cheap" if p < 1 else "price-mid" if p < 10 else "price-high" if p < 100 else "price-ultra"
        return '<span class="price-badge ' + c + '">$' + ("%.2f" % p) + '/1M</span>'
    return '<span class="price-badge price-mid">IN:$' + ("%.1f" % p) + ' OUT:$' + ("%.1f" % q) + '/1M</span>'

# ─── 模型卡片生成 ───
def make_card(pid, pname, pc, mname, inp, out, ctx, tags, scen, cmd_base, cur="CNY", extra_attrs="", family="", price_unit="per_token", price_src=""):
    price_classification = classify_price(inp, out, tags, scen, cur, price_unit)
    pt = price_classification.tier
    ts = th(tags)
    bg = bc(inp, out, price_classification) if cur == "CNY" else bo(inp, out, price_unit, price_classification)
    input_display = output_display = pricing_note = ""
    variable_price = OFFICIAL_PRICES.get(str(mname).lower(), {}) if pid == "deepseek" else {}
    if all(variable_price.get(key) is not None for key in ("input_min", "input_max", "output_min", "output_max")):
        input_display = "¥%.2f–%.2f/M" % (variable_price["input_min"], variable_price["input_max"])
        output_display = "¥%.2f–%.2f/M" % (variable_price["output_min"], variable_price["output_max"])
        pricing_note = str(variable_price.get("pricing_note", ""))
        bg = (
            '<span class="price-badge price-mid" title="' + Te(pricing_note) + '">'
            'IN:' + input_display + ' OUT:' + output_display + '</span>'
        )
    src_map = {"A": "API直接采集", "H": "硬编码(可能过时)", "P": "代理平台自营价(非官方)",
               "S": "官方定价页爬取", "SP": "SPA页面爬取", "OR": "OpenRouter回填", "L": "LiteLLM社区数据",
               "D": "国内官方价格库", "DB": "官方价格数据库", "CV": "交叉验证修正"}
    src_title = src_map.get(price_src, price_src or "硬编码")
    src_cls = "price-src price-src-proxy" if price_src == "P" else ("price-src price-src-or" if price_src == "OR" else "price-src")
    src_tag = '<span class="' + src_cls + '" title="价格来源: ' + src_title + '">' + (price_src[:1] if price_src else "") + '</span>' if price_src else ''
    # data-inp/data-out: unified to $/token (consistent with OpenRouter), per_1m needs /1e6
    if price_unit == "per_1m" and cur == "USD":
        inp_s = str(inp / 1e6) if inp else "0"
        out_s = str(out / 1e6) if out else "0"
    else:
        inp_s = str(inp) if inp else "0"
        out_s = str(out) if out else "0"
    # 上下文数值用于筛选
    ctx_num = re.sub(r'[^\d]', '', ctx) if ctx else "0"
    fam_attr = ' data-family="' + family + '"' if family else ''
    return (
        '<div class="mc" style="--c:' + pc + '" data-s="' + scen + '" data-p="' + pid + '" data-pt="' + pt + '" '
        'data-inp="' + inp_s + '" data-out="' + out_s + '" data-cur="' + cur + '" '
        'data-ctx="' + ctx_num + '" data-ctx-display="' + ctx + '" data-pu="' + price_unit + '" data-src="' + price_src + '" '
        'data-inp-display="' + Te(input_display) + '" data-out-display="' + Te(output_display) + '" data-pricing-note="' + Te(pricing_note) + '" '
        'data-price-status="' + price_classification.status + '" data-billing-unit="' + price_classification.billing_unit + '" '
        'data-base-url="' + Te(cmd_base) + '" data-model-name="' + Te(mname) + '" ' + extra_attrs + fam_attr + ' '
        'onclick="showCodeModal(this.dataset.baseUrl,this.dataset.modelName,this.dataset.p)">'
        '<div class="dot"></div><div class="prov">' + pname + '</div>'
        '<div class="mname">' + mname + '</div><div class="tags">' + ts + '</div>'
        '<div class="prow">' + bg + src_tag + '</div>'
        '<div class="ctx-row"><span class="ctx">上下文: ' + ctx + '</span>'
        '<div class="ctx-bar-wrap"><div class="ctx-bar" style="width:' + str(min(100, int(ctx_num or 0) / 1000)) + '%"></div></div></div>'
        '<div class="base-url">' + cmd_base + '</div>'
        '<div class="hint">点击查看接入代码</div>'
        '<div class="card-actions">'
        '<span class="fav-btn" onclick="event.stopPropagation();toggleFav(this)" title="收藏">&#9734;</span>'
        '<div class="cb-wrap"><input type="checkbox" class="mc-cb" onclick="event.stopPropagation();toggleSel(this)"><label class="cb-lbl">对比</label></div>'
        '</div></div>'
    )

def make_or_card(pv, nn, inp, out, cc, tt, ss, mid2, family="", price_unit="per_token", price_src=""):
    price_classification = classify_price(inp, out, tt, ss, "USD", price_unit)
    pp = price_classification.tier
    tts = th(tt)
    bg = bo(inp, out, price_unit, price_classification)
    src_map = {"A": "API直接采集", "H": "硬编码(可能过时)", "P": "代理平台自营价(非官方)",
               "S": "官方定价页爬取", "SP": "SPA页面爬取", "OR": "OpenRouter回填", "L": "LiteLLM社区数据",
               "D": "国内官方价格库", "DB": "官方价格数据库", "CV": "交叉验证修正"}
    src_title = src_map.get(price_src, price_src or "硬编码")
    src_cls = "price-src price-src-proxy" if price_src == "P" else ("price-src price-src-or" if price_src == "OR" else "price-src")
    src_tag = '<span class="' + src_cls + '" title="价格来源: ' + src_title + '">' + (price_src[:1] if price_src else "") + '</span>' if price_src else ''
    # data-inp/data-out: unified to $/token, per_1m needs /1e6
    if price_unit == "per_1m":
        inp_s = str(inp / 1e6) if inp else "0"
        out_s = str(out / 1e6) if out else "0"
    else:
        inp_s = str(inp) if inp else "0"
        out_s = str(out) if out else "0"
    or_base = "https://openrouter.ai/api/v1/chat/completions"
    cmd = or_base
    ctx_num = re.sub(r'[^\d]', '', cc) if cc else "0"
    fam_attr = ' data-family="' + family + '"' if family else ''
    return (
        '<div class="mc" style="--c:#6366f1" data-s="' + ss + '" data-p="openrouter" data-pt="' + pp + '" '
        'data-inp="' + inp_s + '" data-out="' + out_s + '" data-cur="USD" '
        'data-ctx="' + ctx_num + '" data-ctx-display="' + cc + '" data-pu="' + price_unit + '" data-src="' + price_src + '" '
        'data-price-status="' + price_classification.status + '" data-billing-unit="' + price_classification.billing_unit + '" '
        'data-base-url="' + Te(cmd) + '" data-model-name="' + Te(nn) + '" ' + fam_attr + ' '
        'onclick="showCodeModal(this.dataset.baseUrl,this.dataset.modelName,this.dataset.p)">'
        '<div class="dot"></div><div class="prov">OPENROUTER:' + pv + '</div>'
        '<div class="mname">' + nn + '</div><div class="tags">' + tts + '</div>'
        '<div class="prow">' + bg + src_tag + '</div>'
        '<div class="ctx-row"><span class="ctx">上下文: ' + cc + '</span>'
        '<div class="ctx-bar-wrap"><div class="ctx-bar" style="width:' + str(min(100, int(ctx_num or 0) / 1000)) + '%"></div></div></div>'
        '<div class="base-url">' + or_base + '</div>'
        '<div class="hint">点击查看接入代码</div>'
        '<div class="card-actions">'
        '<span class="fav-btn" onclick="event.stopPropagation();toggleFav(this)" title="收藏">&#9734;</span>'
        '<div class="cb-wrap"><input type="checkbox" class="mc-cb" onclick="event.stopPropagation();toggleSel(this)"><label class="cb-lbl">对比</label></div>'
        '</div></div>'
    )
