#!/usr/bin/env python3
"""AI 模型选择器 - 数据抓取与页面生成脚本
支持平台: 阿里百炼, 硅基流动, 月之暗面, 智谱AI, 火山引擎, 百度文心, OpenRouter,
           腾讯混元, 讯飞星火, MiniMax, 零一万物, 百川智能, 阶跃星辰, DeepSeek, Groq,
           Together AI, Fireworks AI, Cohere
"""
import os, time, json, sys, urllib.request, hashlib, re
from datetime import datetime
from collections import Counter

# ─── API Keys (仅从环境变量读取，无硬编码默认值) ───
SF  = os.environ.get("SF_KEY", "")
ALI = os.environ.get("ALIYUN_KEY", "")
MS  = os.environ.get("MS_KEY", "")
ZH  = os.environ.get("ZH_KEY", "")
VC  = os.environ.get("VOLC_KEY", "")
TX  = os.environ.get("TENCENT_KEY", "")
XH  = os.environ.get("SPARK_KEY", "")
MM  = os.environ.get("MINIMAX_KEY", "")
YW  = os.environ.get("YI_KEY", "")
BC  = os.environ.get("BAICHUAN_KEY", "")
JC  = os.environ.get("JIEYUE_KEY", "")
DS  = os.environ.get("DEEPSEEK_KEY", "")
GQ  = os.environ.get("GROQ_KEY", "")
BDK = os.environ.get("BAIDU_KEY", "")
TG  = os.environ.get("TOGETHER_KEY", "")
FW  = os.environ.get("FIREWORKS_KEY", "")
CO  = os.environ.get("COHERE_KEY", "")
INFINI = os.environ.get("INFINI_KEY", "")
NOVITA = os.environ.get("NOVITA_KEY", "")
DEEPINFRA = os.environ.get("DEEPINFRA_KEY", "")

# ─── 输出路径 (支持 OUTPUT_FILE 环境变量覆盖，适配 CI 环境) ───
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUTPUT_FILE", os.path.expanduser("~/.qclaw/model-selector-v2.html"))
CACHE_DIR = os.environ.get("CACHE_DIR", os.path.expanduser("~/.qclaw/cache"))
PREV_DATA = os.path.join(CACHE_DIR, "prev_models.json")
os.makedirs(CACHE_DIR, exist_ok=True)

# ─── 汇率 ───
USD_TO_CNY = 7.25

# ─── 通用请求函数 (带重试和缓存) ───
def fj(url, tok="", to=20, retries=3):
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    if tok: h["Authorization"] = "Bearer " + tok
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=to) as r:
                data = r.read()
                # 缓存到本地
                ch = hashlib.md5(url.encode()).hexdigest()
                with open(os.path.join(CACHE_DIR, ch + ".json"), "wb") as cf:
                    cf.write(data)
                return json.loads(data)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1 * (attempt + 1))
            else:
                print("  WARN: %s (after %d retries)" % (e, retries), file=sys.stderr)
                # 尝试从缓存读取
                ch = hashlib.md5(url.encode()).hexdigest()
                cp = os.path.join(CACHE_DIR, ch + ".json")
                if os.path.exists(cp):
                    try:
                        print("  Using cache for: %s" % url, file=sys.stderr)
                        return json.load(open(cp))
                    except:
                        pass
                return None

# ─── 价格分级 ───
def PT(inp, out, cur="CNY", price_unit="per_token"):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0: return "free"
    if cur == "USD" and price_unit == "per_token":
        p = inp * 1e6
    else:
        p = inp
    if p < 0.1:   return "cheap"
    elif p < 10:   return "mid"
    elif p < 100:  return "high"
    else:           return "ultra"

# ─── HTML 转义 ───
def Te(s):
    return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

# ─── 标签 HTML ───
def th(tags):
    m = {"免费":"free","免费额度":"free","便宜":"cheap","极便宜":"cheap","性价比":"cheap",
         "旗舰":"hot","主力":"hot","最新版":"hot","2025新":"hot","2026新":"hot",
         "视觉":"vision","推理":"reason","长上下文":"long","超长上下文":"long",
         "开源":"other","代码":"other","图片生成":"other","视频生成":"other",
         "快速":"other","高性能":"hot","Pro订阅":"other","蒸馏":"other",
         "轻量":"other","已下线":"other","即将下线":"other","价格待确认":"other",
         "语音":"other","TTS":"other","ASR":"other","向量":"other","排序":"other",
         "OCR":"other","多模态":"vision","Turbo":"hot","降价后":"cheap","降价90%":"cheap",
         "超低价":"cheap","编程":"other","智能路由":"other","免费":"free",
         "满血版":"hot","价格变动":"other","涨价":"hot","降价":"cheap"}
    return "".join('<span class="tg tg-' + m.get(x,"other") + '">' + x + '</span>' for x in (tags or []))

# ─── 价格徽章 (CNY) ───
def bc(inp, out):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0:
        return '<span class="price-badge price-free">免费额度</span>'
    if inp == out:
        c = "price-cheap" if inp < 1 else "price-mid" if inp < 10 else "price-high" if inp < 100 else "price-ultra"
        return '<span class="price-badge ' + c + '">¥' + ("%.2f" % inp) + '/M</span>'
    return '<span class="price-badge price-mid">IN:¥' + ("%.2f" % inp) + ' OUT:¥' + ("%.2f" % out) + '/M</span>'

# ─── 价格徽章 (USD) ───
# price_unit: "per_token" = $/token (multiply 1e6 to display), "per_1m" = already $/1M tokens
def bo(inp, out, price_unit="per_token"):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0:
        return '<span class="price-badge price-free">$0 (免费)</span>'
    if price_unit == "per_token":
        p = inp * 1e6; q = out * 1e6
    else:
        p = inp; q = out
    if inp == out:
        c = "price-free" if p < 0.1 else "price-cheap" if p < 1 else "price-mid" if p < 10 else "price-high" if p < 100 else "price-ultra"
        return '<span class="price-badge ' + c + '">$' + ("%.2f" % p) + '/1M</span>'
    return '<span class="price-badge price-mid">IN:$' + ("%.1f" % p) + ' OUT:$' + ("%.1f" % q) + '/1M</span>'

# ─── 模型卡片生成 ───
def make_card(pid, pname, pc, mname, inp, out, ctx, tags, scen, cmd_base, cur="CNY", extra_attrs="", family="", price_unit="per_token"):
    pt = PT(inp, out, cur, price_unit)
    ts = th(tags)
    bg = bc(inp, out) if cur == "CNY" else bo(inp, out, price_unit)
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
        'data-ctx="' + ctx_num + '" data-ctx-display="' + ctx + '" ' + extra_attrs + fam_attr + ' '
        'onclick="showCodeModal(\'' + cmd_base + '\',\'' + mname + '\',\'' + pid + '\')">'
        '<div class="dot"></div><div class="prov">' + pname + '</div>'
        '<div class="mname">' + mname + '</div><div class="tags">' + ts + '</div>'
        '<div class="prow">' + bg + '</div>'
        '<div class="ctx-row"><span class="ctx">上下文: ' + ctx + '</span>'
        '<div class="ctx-bar-wrap"><div class="ctx-bar" style="width:' + str(min(100, int(ctx_num or 0) / 1000)) + '%"></div></div></div>'
        '<div class="base-url">' + cmd_base + '</div>'
        '<div class="hint">点击查看接入代码</div>'
        '<div class="card-actions">'
        '<span class="fav-btn" onclick="event.stopPropagation();toggleFav(this)" title="收藏">&#9734;</span>'
        '<div class="cb-wrap"><input type="checkbox" class="mc-cb" onclick="event.stopPropagation();toggleSel(this)"><label class="cb-lbl">对比</label></div>'
        '</div></div>'
    )

def make_or_card(pv, nn, inp, out, cc, tt, ss, mid2, family="", price_unit="per_token"):
    pp = PT(inp, out, "USD", price_unit)
    tts = th(tt)
    bg = bo(inp, out, price_unit)
    inp_s = str(inp) if inp else "0"
    out_s = str(out) if out else "0"
    or_base = "https://openrouter.ai/api/v1/chat/completions"
    cmd = or_base
    ctx_num = re.sub(r'[^\d]', '', cc) if cc else "0"
    fam_attr = ' data-family="' + family + '"' if family else ''
    return (
        '<div class="mc" style="--c:#6366f1" data-s="' + ss + '" data-p="openrouter" data-pt="' + pp + '" '
        'data-inp="' + inp_s + '" data-out="' + out_s + '" data-cur="USD" '
        'data-ctx="' + ctx_num + '" data-ctx-display="' + cc + '" ' + fam_attr + ' '
        'onclick="showCodeModal(\'' + cmd + '\',\'' + nn + '\',\'openrouter\')">'
        '<div class="dot"></div><div class="prov">OPENROUTER:' + pv + '</div>'
        '<div class="mname">' + nn + '</div><div class="tags">' + tts + '</div>'
        '<div class="prow">' + bg + '</div>'
        '<div class="ctx-row"><span class="ctx">上下文: ' + cc + '</span>'
        '<div class="ctx-bar-wrap"><div class="ctx-bar" style="width:' + str(min(100, int(ctx_num or 0) / 1000)) + '%"></div></div></div>'
        '<div class="base-url">' + or_base + '</div>'
        '<div class="hint">点击查看接入代码</div>'
        '<div class="card-actions">'
        '<span class="fav-btn" onclick="event.stopPropagation();toggleFav(this)" title="收藏">&#9734;</span>'
        '<div class="cb-wrap"><input type="checkbox" class="mc-cb" onclick="event.stopPropagation();toggleSel(this)"><label class="cb-lbl">对比</label></div>'
        '</div></div>'
    )

# ─── 模型家族识别 ───
def get_family(mid):
    """根据模型名称识别家族标签"""
    n = mid.lower()
    if any(x in n for x in ['gpt-', 'gpt4', 'gpt3', 'o1-', 'o3-', 'o4-']): return 'GPT'
    if 'claude' in n: return 'Claude'
    if 'gemini' in n: return 'Gemini'
    if 'llama' in n: return 'Llama'
    if 'mistral' in n or 'mixtral' in n or 'codestral' in n or 'pixtral' in n: return 'Mistral'
    if 'deepseek' in n: return 'DeepSeek'
    if 'qwen' in n or 'qwq' in n: return 'Qwen'
    if 'glm' in n: return 'GLM'
    if 'kimi' in n or 'moonshot' in n: return 'Kimi'
    if 'doubao' in n or 'seed' in n: return 'Doubao'
    if 'yi-' in n or 'yi ' in n: return 'Yi'
    if 'phi' in n: return 'Phi'
    if 'command' in n: return 'Command'
    if 'jamba' in n: return 'Jamba'
    if 'grok' in n: return 'Grok'
    if 'nova' in n: return 'Nova'
    if 'sonar' in n: return 'Sonar'
    if 'hunyuan' in n: return 'Hunyuan'
    if 'spark' in n or 'generalv' in n: return 'Spark'
    if 'minimax' in n or 'abab' in n: return 'MiniMax'
    if 'baichuan' in n: return 'Baichuan'
    if 'step' in n: return 'Step'
    if 'ernie' in n or 'wenxin' in n: return 'ERNIE'
    if 'solar' in n: return 'Solar'
    if 'wizardlm' in n: return 'WizardLM'
    if 'zephyr' in n: return 'Zephyr'
    if 'nous' in n: return 'Nous'
    if 'hermes' in n: return 'Hermes'
    if 'openchat' in n: return 'OpenChat'
    if 'neural' in n: return 'Neural'
    if 'mythomax' in n: return 'MythoMax'
    if 'toppy' in n: return 'Toppy'
    if 'bagel' in n: return 'Bagel'
    if 'lzlv' in n: return 'LzLv'
    if 'rwkv' in n: return 'RWKV'
    if 'falcon' in n: return 'Falcon'
    if 'starcoder' in n: return 'StarCoder'
    if 'codellama' in n: return 'CodeLlama'
    if 'wizardcoder' in n: return 'WizardCoder'
    if 'phind' in n: return 'Phind'
    if 'samantha' in n: return 'Samantha'
    if 'airoboros' in n: return 'Airoboros'
    if 'vicuna' in n: return 'Vicuna'
    if 'orca' in n: return 'Orca'
    if 'dolphin' in n: return 'Dolphin'
    if 'megamix' in n: return 'MegaMix'
    if 'cosmic' in n: return 'Cosmic'
    if 'psymed' in n: return 'PsyMed'
    if 'biomistral' in n: return 'BioMistral'
    if 'medllama' in n: return 'MedLlama'
    if 'internlm' in n: return 'InternLM'
    if 'kolors' in n: return 'Kolors'
    if 'wan' in n and 'ai' in n: return 'Wan'
    if 'cosyvoice' in n or 'sensevoice' in n: return 'FunAudio'
    if 'bge' in n: return 'BGE'
    return 'Other'

# ═══════════════════════════════════════════════════════════
# 各平台价格映射函数
# ═══════════════════════════════════════════════════════════

def sp(mid):
    """硅基流动价格映射"""
    t = ["免费额度"]; s = "日常对话"; i = o = 0.0
    n = mid.lower()
    if "deepseek-ai/" in mid:
        if "R1" in mid:
            if "Distill" in mid:
                t = ["推理","蒸馏"]
                sz = next((x for x in ["7B","14B","32B"] if x in mid), "7B")
                i = {"7B":0.1,"14B":0.4,"32B":1.0}[sz]; o = i * 4
            else:
                i, o = 4.0, 16.0; t = ["推理","旗舰"]
        elif "V3.2" in mid: i, o = 2.0, 8.0; t = ["满血版","旗舰"]
        elif "V3.1" in mid: i, o = 4.0, 12.0; t = ["深度推理"]
        elif "V3" in mid:   i, o = 2.0, 8.0; t = ["满血版","旗舰"]
        elif "OCR" in mid:  i, o = 0.3, 0; t = ["OCR"]; s = "其他"
        else: i, o = 0, 0
    elif mid.startswith("Qwen/"):
        b = mid.split("/",1)[1]; t = []
        if "Image" in b:         i, o = 0.5, 0; t = ["图片生成"]; s = "图片生成"
        elif "VL" in b:
            t = ["视觉"]; s = "视觉图片"
            i, o = (0.8,6.4) if any(x in b for x in ["235B","397B"]) else \
                    (0.6,4.8) if "32B" in b else \
                    (0.4,3.2) if "30B" in b else (0.2,2.0)
            if "Thinking" in b:   t.append("推理"); s = "深度推理"
        elif "Coder" in b:       i, o = 0.4, 3.2; t = ["代码"]; s = "编程代码"
        elif "QwQ" in b:         i, o = 0.7, 2.0; t = ["推理"]; s = "深度推理"
        elif "Embedding" in b:    i, o = 0.1, 0; t = ["向量"]; s = "其他"
        elif "Reranker" in b:    i, o = 0.1, 0; t = ["排序"]; s = "其他"
        elif "Omni" in b:        i, o = 0.4, 3.2; t = ["多模态"]
        elif "3.5" in b:
            t = ["最新版"]
            i, o = (0.2,2.0) if any(x in b for x in ["4B","9B"]) else \
                    (0.6,4.8) if "27B" in b else \
                    (0.4,3.2) if any(x in b for x in ["35B","30B"]) else \
                    (0.8,6.4) if any(x in b for x in ["122B","397B"]) else (0.2,2.0)
        elif "3-" in b or (".3" in b and "3.5" not in b):
            t = ["2025新"]
            if any(x in b for x in ["4B","8B"]): i, o = 0, 0; t = ["免费额度"]
            elif any(x in b for x in ["14B","32B"]): i, o = 0.5, 1.0
            elif "235B" in b: i, o = 0.8, 6.4
            else: i, o = 0.5, 1.0
        elif "2.5" in b:
            t = ["开源"]
            if "7B" in b:       i, o = 0, 0; t = ["免费额度"]
            elif "14B" in b:     i, o = 0.5, 0.7
            elif "32B" in b:     i, o = 0.6, 2.0
            elif "72B" in b:     i, o = 1.4, 4.13
            elif "Coder" in b:   i, o = 0.7, 1.4; t = ["代码"]; s = "编程代码"
            else:                 i, o = 0, 0; t = ["免费额度"]
        elif "2-VL" in b:        i, o = 3.0, 8.0; t = ["视觉"]
        else:                     i, o = 0, 0; t = ["免费额度"]
        if not t: t = ["免费额度"]
    elif "GLM" in mid:
        b = mid.split("/")[-1]
        if "5.1" in b:                          i, o = 8.0, 24.0; t = ["旗舰"]
        elif "GLM-5" in b and "4" not in b:      i, o = 6.0, 22.0; t = ["旗舰"]
        elif "4.7" in b:                        i, o = 2.0, 8.0; t = ["主力"]
        elif any(x in b for x in ["4.6V","4.5V"]): i, o = 2.0, 8.0; t = ["视觉"]; s = "视觉图片"
        elif "4.6" in b:                        i, o = 2.0, 8.0; t = ["主力"]
        elif "4.5-Air" in b:                   i, o = 0.5, 3.0; t = ["轻量"]
        elif "4.5" in b:                        i, o = 2.0, 8.0; t = ["主力"]
        elif "Z1-32B" in b:                    i, o = 0.5, 2.0; t = ["推理"]; s = "深度推理"
        elif "Z1-9B" in b:                     i, o = 0, 0; t = ["推理","免费额度"]
        elif "4.1V" in b:                      i, o = 0, 0; t = ["视觉","推理","免费额度"]; s = "视觉图片"
        elif "4-32B" in b:                     i, o = 2.0, 8.0; t = ["主力"]
        elif "4-9B" in b:                       i, o = 0, 0; t = ["免费额度"]
        else:                                     i, o = 2.0, 8.0; t = ["主力"]
    elif "Pro/" in mid:
        ii, oo, tt, ss = sp(mid.split("/",1)[1])
        return ii, oo, tt+["Pro订阅"], ss
    elif "moonshotai/Kimi" in mid or "Kimi-K2" in mid: i, o = 4.0, 16.0; t = ["开源","推理"]; s = "深度推理"
    elif "inclusionAI/Ling-flash" in mid:  i, o = 1.0, 4.0; t = ["长上下文"]
    elif "inclusionAI/Ling-mini" in mid:   i, o = 0.5, 2.0; t = ["快速","便宜"]
    elif "inclusionAI/Ring" in mid:        i, o = 0.5, 2.0; t = ["快速"]
    elif "FunAudioLLM/CosyVoice" in mid:   i, o = 0.2, 0; t = ["语音","TTS"]; s = "其他"
    elif "FunAudioLLM/SenseVoice" in mid:   i, o = 0.3, 0; t = ["语音","ASR"]; s = "其他"
    elif "IndexTeam/IndexTTS" in mid:      i, o = 0.5, 0; t = ["语音","TTS"]; s = "其他"
    elif "BAAI/bge" in mid or "netease-youdao" in mid: i, o = 0.1, 0; t = ["向量"]; s = "其他"
    elif "Kwai-Kolors/Kolors" in mid:       i, o = 0.5, 0; t = ["图片生成","开源"]; s = "图片生成"
    elif "Wan-AI/Wan" in mid:               i, o = 0.5, 0; t = ["视频生成","开源"]; s = "视频生成"
    elif "ByteDance-Seed" in mid:            i, o = 1.0, 4.0; t = ["开源","旗舰"]
    elif "internlm" in mid:                 i, o = 0, 0; t = ["开源","免费额度"]
    else:                                     i, o = 0, 0
    if not t: t = ["免费额度"]
    return i, o, t, s

def mp(mid):
    """月之暗面价格映射"""
    m = {
        "moonshot-v1-8k":         (2,10,"8k",["主力","降价后"],"日常对话"),
        "moonshot-v1-32k":        (12,24,"32k",["长上下文"],"日常对话"),
        "moonshot-v1-128k":       (12,24,"128k",["超长上下文","旗舰"],"深度推理"),
        "kimi-k2":                  (4,16,"262k",["旗舰","2025新"],"深度推理"),
        "kimi-k2.5":                (4,16,"262k",["旗舰","最新版"],"深度推理"),
        "kimi-k2-turbo":            (4,16,"262k",["旗舰","Turbo"],"深度推理"),
        "kimi-k2-thinking":          (4,16,"262k",["推理","旗舰"],"深度推理"),
        "kimi-k2-thinking-turbo":    (4,16,"262k",["推理","Turbo"],"深度推理"),
        "moonshot-v1-8k-vision":     (12,12,"8k",["视觉"],"视觉图片"),
        "moonshot-v1-32k-vision":   (24,24,"32k",["视觉"],"视觉图片"),
        "moonshot-v1-128k-vision":   (24,24,"128k",["视觉","超长上下文"],"视觉图片"),
    }
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in mid: return ii, oo, cc, tt, ss
    return 4, 16, "262k", ["旗舰","价格待确认"], "深度推理"

def zp(mid):
    """智谱AI价格映射"""
    m = {
        "glm-5":         (6,22,"1M",["旗舰","2026新"],"深度推理"),
        "glm-5-turbo":   (5,22,"1M",["高性能"],"深度推理"),
        "glm-5.1":       (8,24,"1M",["旗舰"],"深度推理"),
        "glm-4.7":       (2,8,"1M",["主力","2026新"],"日常对话"),
        "glm-4.7-flashx":(0.5,3,"200k",["快速","长上下文"],"日常对话"),
        "glm-4.7-flash": (0,0,"200k",["免费"],"日常对话"),
        "glm-4-plus":    (5,5,"128k",["旗舰","降价90%"],"深度推理"),
        "glm-5v-turbo":  (5,5,"1M",["视觉","旗舰"],"视觉图片"),
        "glm-z1-air":    (0.5,2,"32k",["推理","便宜"],"深度推理"),
        "glm-4.5":      (2,8,"128k",["主力"],"日常对话"),
        "glm-4.5-air":   (0.5,3,"32k",["轻量"],"日常对话"),
        "glm-4.6":      (2,8,"128k",["主力"],"日常对话"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 2, 8, "128k", ["主力"], "日常对话"

def vp(mid):
    """火山引擎价格映射"""
    m = {
        "doubao-1.6-pro-32k":    (0.8,8,"32k",["旗舰","2025新"],"日常对话"),
        "doubao-1.5-pro-32k":   (0.8,2,"32k",["主力","性价比"],"日常对话"),
        "doubao-1.5-pro-128k":  (5,5,"128k",["长上下文"],"深度推理"),
        "doubao-lite-32k":        (0.8,0.8,"32k",["极便宜","免费额度"],"日常对话"),
        "doubao-1.5-lite-32k":  (0.8,0.8,"32k",["极便宜"],"日常对话"),
        "doubao-vision":            (3,3,"64k",["视觉","超低价"],"视觉图片"),
        "doubao-coder":            (2,8,"32k",["代码","编程"],"编程代码"),
        "doubao-seed-1.6":         (0.8,8,"32k",["旗舰","2025新"],"日常对话"),
        "doubao-seed-1.6-flash":  (0.8,0.8,"32k",["快速","极便宜"],"日常对话"),
        "doubao-seed-1.6-vision": (3,3,"64k",["视觉","旗舰"],"视觉图片"),
        "doubao-seed-1.6-thinking":(4,16,"262k",["推理","旗舰"],"深度推理"),
        "doubao-seed-2.0-pro":     (1,4,"32k",["旗舰","最新版"],"日常对话"),
        "doubao-seed-2.0-mini":    (0.8,2,"32k",["轻量","性价比"],"日常对话"),
        "doubao-smart-router":      (0.8,2,"32k",["智能路由"],"日常对话"),
    }
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in mid: return ii, oo, cc, tt, ss
    return 0.8, 2, "32k", ["价格待确认"], "日常对话"

# ─── 百度文心 (从 API 拉取 + 硬编码回退) ───
BD = []
if BDK:
    # 百度千帆 V2 OpenAI兼容接口
    d = fj("https://qianfan.baidubce.com/v2/models", BDK)
    if d:
        for m in (d.get("data", []) if d else []):
            mid = m.get("id", "")
            nn = m.get("name", mid)
            # 尝试从 pricing 获取价格
            pricing = m.get("pricing", {})
            ii = float(pricing.get("input", 0) or 0)
            oo = float(pricing.get("output", 0) or 0)
            cc_r = m.get("context_length", 0) or 0
            cc = str(int(cc_r)//1000)+"k" if cc_r else "8k"
            tt = []
            ss = "日常对话"
            if ii == 0 and oo == 0: tt.append("免费额度")
            if cc_r >= 100000: tt.append("长上下文")
            n_lower = mid.lower()
            if "4.0" in n_lower or "4u" in n_lower: tt.append("旗舰"); ss = "深度推理"
            elif "3.5" in n_lower: tt.append("主力")
            elif "lite" in n_lower or "speed" in n_lower: tt.append("轻量")
            BD.append({"n": nn, "c": cc, "i": ii, "o": oo, "t": tt, "s": ss})
if not BD:
    BD = [
        {"n":"文心一言 4.0","c":"8k","i":120,"o":120,"t":["旗舰"],"s":"深度推理"},
        {"n":"文心一言 4.0-32K","c":"32k","i":120,"o":120,"t":["旗舰","长上下文"],"s":"深度推理"},
        {"n":"文心一言 3.5","c":"8k","i":20,"o":20,"t":["主力"],"s":"日常对话"},
        {"n":"文心速度 128K","c":"128k","i":12,"o":12,"t":["长上下文"],"s":"日常对话"},
        {"n":"文心 Lite","c":"8k","i":8,"o":8,"t":["轻量","免费额度"],"s":"日常对话"},
        {"n":"文心Bot 8K","c":"8k","i":20,"o":20,"t":["主力"],"s":"日常对话"},
    ]

# ─── 腾讯混元价格映射 ───
def tp(mid):
    m = {
        "hunyuan-turbos":      (0.5,1.5,"32k",["快速","便宜"],"日常对话"),
        "hunyuan-turbo":       (1,4,"32k",["主力"],"日常对话"),
        "hunyuan-pro":         (4,16,"32k",["旗舰"],"深度推理"),
        "hunyuan-large":       (4,16,"256k",["旗舰","长上下文"],"深度推理"),
        "hunyuan-lite":        (0,0,"32k",["免费额度"],"日常对话"),
        "hunyuan-standard":    (0.8,2,"32k",["性价比"],"日常对话"),
        "hunyuan-standard-vision": (2,2,"32k",["视觉"],"视觉图片"),
        "hunyuan-vision":      (4,4,"32k",["视觉","旗舰"],"视觉图片"),
        "hunyuan-coder":       (2,8,"32k",["代码"],"编程代码"),
        "hunyuan-t1":          (4,16,"256k",["推理","旗舰"],"深度推理"),
        "hunyuan-turbos-vision": (1,1,"32k",["视觉","便宜"],"视觉图片"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 1, 4, "32k", ["价格待确认"], "日常对话"

# ─── 讯飞星火价格映射 ───
def xp(mid):
    m = {
        "generalv3.5":        (2,8,"8k",["主力"],"日常对话"),
        "generalv3":          (1.5,5,"8k",["性价比"],"日常对话"),
        "4.0Ultra":           (5,20,"32k",["旗舰"],"深度推理"),
        "generalv2":          (0.5,1.5,"8k",["便宜"],"日常对话"),
        "spark-lite":         (0,0,"8k",["免费额度"],"日常对话"),
        "generalv3.5-vision": (2,8,"8k",["视觉"],"视觉图片"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 2, 8, "8k", ["价格待确认"], "日常对话"

# ─── MiniMax价格映射 ───
def mm_p(mid):
    m = {
        "abab6.5s":           (0.5,1.5,"32k",["快速","便宜"],"日常对话"),
        "abab6.5":            (2,8,"128k",["主力","长上下文"],"日常对话"),
        "abab6.5g":           (4,16,"128k",["旗舰","长上下文"],"深度推理"),
        "abab5.5":            (0.5,1.5,"32k",["便宜"],"日常对话"),
        "abab5.5s":           (0.1,0.3,"32k",["极便宜"],"日常对话"),
        "abab6.5s-vision":    (0.5,1.5,"32k",["视觉","便宜"],"视觉图片"),
        "abab6.5-vision":     (2,8,"32k",["视觉"],"视觉图片"),
        "minimax-m1":         (4,16,"1M",["推理","旗舰","长上下文"],"深度推理"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 1, 4, "32k", ["价格待确认"], "日常对话"

# ─── 零一万物价格映射 ───
def yp(mid):
    m = {
        "yi-light":           (0,0,"16k",["免费额度"],"日常对话"),
        "yi-medium":          (0.5,1.5,"16k",["便宜"],"日常对话"),
        "yi-large":           (4,16,"32k",["旗舰"],"深度推理"),
        "yi-vision":          (2,6,"16k",["视觉"],"视觉图片"),
        "yi-large-turbo":     (2,8,"32k",["主力","Turbo"],"日常对话"),
        "yi-spark":           (0.5,1.5,"16k",["便宜"],"日常对话"),
        "yi-lightning":       (0.1,0.3,"16k",["极便宜"],"日常对话"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 1, 4, "16k", ["价格待确认"], "日常对话"

# ─── 百川智能价格映射 ───
def bp(mid):
    m = {
        "baichuan2-turbo":    (0.5,1.5,"32k",["便宜"],"日常对话"),
        "baichuan2-53b":      (2,8,"32k",["主力"],"日常对话"),
        "baichuan-14b":       (0.5,1.5,"8k",["便宜"],"日常对话"),
        "baichuan4":          (4,16,"128k",["旗舰","长上下文"],"深度推理"),
        "baichuan4-vision":   (4,16,"32k",["视觉","旗舰"],"视觉图片"),
        "baichuan-m1":        (4,16,"128k",["推理","旗舰"],"深度推理"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 1, 4, "32k", ["价格待确认"], "日常对话"

# ─── 阶跃星辰价格映射 ───
def jp(mid):
    m = {
        "step-1-8k":          (2,8,"8k",["主力"],"日常对话"),
        "step-1-32k":         (4,16,"32k",["旗舰"],"深度推理"),
        "step-1-128k":        (5,20,"128k",["旗舰","长上下文"],"深度推理"),
        "step-1-flash":       (0.5,1.5,"8k",["快速","便宜"],"日常对话"),
        "step-1v-8k":         (2,8,"8k",["视觉"],"视觉图片"),
        "step-1v-32k":        (4,16,"32k",["视觉","旗舰"],"视觉图片"),
        "step-2-16k":         (4,16,"16k",["旗舰","2025新"],"深度推理"),
        "step-2-mini":        (1,4,"32k",["性价比"],"日常对话"),
        "step-r1":            (4,16,"32k",["推理","旗舰"],"深度推理"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 2, 8, "8k", ["价格待确认"], "日常对话"

# ─── DeepSeek 官方价格映射 ───
def dp(mid):
    """DeepSeek 官方（¥/M tokens，2026年4月官网定价）"""
    m = {
        "deepseek-chat":     (1,4,"64k",["主力","满血版"],"日常对话"),
        "deepseek-reasoner": (4,16,"64k",["推理","旗舰"],"深度推理"),
        "deepseek-v3":       (1,4,"64k",["主力","满血版"],"日常对话"),
        "deepseek-r1":       (4,16,"64k",["推理","旗舰"],"深度推理"),
        "deepseek-v3.1":     (1,4,"128k",["主力","满血版"],"日常对话"),
        "deepseek-prover-v2":(4,16,"64k",["推理"],"深度推理"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 1, 4, "64k", ["价格待确认"], "日常对话"

# ─── Groq 价格映射 ───
def gp(mid):
    """Groq - 超快推理（$/1M tokens，2026年4月官网定价）"""
    m = {
        "llama-3.3-70b-versatile":  (0.59,0.79,"128k",["主力","快速"],"日常对话"),
        "llama-3.3-70b-instruct":   (0.59,0.79,"128k",["主力","快速"],"日常对话"),
        "llama-3.1-8b-instant":     (0.05,0.08,"128k",["极便宜","快速"],"日常对话"),
        "llama-3.1-70b-versatile":  (0.59,0.79,"128k",["主力","快速"],"日常对话"),
        "llama-3.2-1b-preview":     (0.02,0.02,"128k",["极便宜","快速"],"日常对话"),
        "llama-3.2-3b-preview":     (0.03,0.06,"128k",["极便宜","快速"],"日常对话"),
        "llama-3.2-11b-vision-preview":(0.12,0.18,"128k",["视觉","便宜"],"视觉图片"),
        "llama-3.2-90b-vision-preview":(0.59,0.79,"128k",["视觉","主力"],"视觉图片"),
        "mixtral-8x7b-32768":       (0.24,0.24,"32k",["便宜","快速"],"日常对话"),
        "gemma2-9b-it":             (0.05,0.07,"8k",["极便宜","快速"],"日常对话"),
        "deepseek-r1-distill-llama-70b": (0.59,0.79,"128k",["推理","快速"],"深度推理"),
        "deepseek-r1-distill-qwen-32b":  (0.12,0.18,"128k",["推理","便宜"],"深度推理"),
        "qwen-qwq-32b":             (0.12,0.18,"128k",["推理","便宜"],"深度推理"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 0.24, 0.24, "32k", ["价格待确认"], "日常对话"

# ─── Together AI 价格映射 ───
def tgp(mid):
    """Together AI - 开源模型托管平台，价格极低（$/1M tokens）"""
    m = {
        "meta-llama/Llama-3.3-70B-Instruct-Turbo": (0.88,0.88,"128k",["主力","快速"],"日常对话"),
        "meta-llama/Llama-3.1-8B-Instruct-Turbo":  (0.18,0.18,"128k",["便宜","快速"],"日常对话"),
        "meta-llama/Llama-3.1-405B-Instruct-Turbo":(3.50,3.50,"128k",["旗舰"],"深度推理"),
        "meta-llama/Llama-3.2-3B-Instruct-Turbo":  (0.04,0.04,"128k",["极便宜","快速"],"日常对话"),
        "Qwen/Qwen2.5-72B-Instruct-Turbo":         (1.20,1.20,"128k",["主力","快速"],"日常对话"),
        "Qwen/Qwen2.5-Coder-32B-Instruct":         (0.80,0.80,"32k",["代码","便宜"],"编程代码"),
        "Qwen/QwQ-32B":                            (1.20,1.20,"128k",["推理","便宜"],"深度推理"),
        "deepseek-ai/DeepSeek-V3-0324":             (1.25,1.25,"64k",["主力","满血版"],"日常对话"),
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B":(2.00,2.00,"128k",["推理"],"深度推理"),
        "mistralai/Mixtral-8x7B-Instruct-v0.1":    (0.60,0.60,"32k",["便宜","快速"],"日常对话"),
        "mistralai/Mixtral-8x22B-Instruct-v0.3":   (0.60,0.60,"64k",["主力"],"日常对话"),
        "google/gemma-2-27b-it":                    (0.80,0.80,"8k",["便宜"],"日常对话"),
        "deepseek-ai/DeepSeek-R1":                  (3.00,7.00,"128k",["推理","旗舰"],"深度推理"),
        "deepseek-ai/DeepSeek-V3.1":                (0.60,1.70,"128k",["主力"],"日常对话"),
        "Qwen/Qwen3-235B-A22B-Instruct-2507-tput":  (0.20,0.60,"256k",["主力","快速"],"日常对话"),
        "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8":(0.27,0.85,"1M",["旗舰","长上下文"],"日常对话"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k.lower() in m2: return ii, oo, cc, tt, ss
    # 通用：根据模型名推断
    if "405b" in m2: return 3.50, 3.50, "128k", ["旗舰"], "深度推理"
    if "70b" in m2 or "72b" in m2: return 0.88, 0.88, "128k", ["主力"], "日常对话"
    if "32b" in m2 or "34b" in m2: return 0.80, 0.80, "32k", ["便宜"], "日常对话"
    if "8b" in m2 or "9b" in m2: return 0.18, 0.18, "128k", ["便宜"], "日常对话"
    if "3b" in m2: return 0.04, 0.04, "128k", ["极便宜"], "日常对话"
    return 0.30, 0.30, "32k", ["价格待确认"], "日常对话"

# ─── Together AI 标签推断 (API有真实价格时使用) ───
def tgp_tags(mid, inp, out, ctx):
    """根据模型名和价格推断标签和场景"""
    n = mid.lower()
    tt = []
    ss = "日常对话"
    # 价格标签
    if inp < 0.1: tt.append("极便宜")
    elif inp < 0.5: tt.append("便宜")
    elif inp < 2: pass
    elif inp < 5: tt.append("旗舰")
    else: tt.append("旗舰")
    # 上下文标签
    if ctx >= 128000: tt.append("长上下文")
    # 模型类型标签
    if "deepseek-r1" in n: tt.append("推理"); ss = "深度推理"
    elif "qwq" in n or "thinking" in n: tt.append("推理"); ss = "深度推理"
    elif "coder" in n or "code" in n: tt.append("代码"); ss = "编程代码"
    elif "vl" in n or "vision" in n: tt.append("视觉"); ss = "视觉图片"
    elif "embed" in n or "rerank" in n: ss = "其他"
    elif "405b" in n: tt.append("旗舰"); ss = "深度推理"
    elif "70b" in n or "72b" in n or "397b" in n: tt.append("主力")
    return tt, ss

# ─── Fireworks AI 价格映射 ───
def fwp(mid):
    """Fireworks AI - 快速推理平台（$/1M tokens，2026年4月官网定价）"""
    m = {
        "accounts/fireworks/models/llama-v3p3-70b-instruct":  (0.90,0.90,"128k",["主力","快速"],"日常对话"),
        "accounts/fireworks/models/llama-v3p1-8b-instruct":   (0.08,0.08,"128k",["极便宜","快速"],"日常对话"),
        "accounts/fireworks/models/llama-v3p1-70b-instruct":  (0.90,0.90,"128k",["主力","快速"],"日常对话"),
        "accounts/fireworks/models/llama-v3p2-3b-instruct":   (0.04,0.04,"128k",["极便宜","快速"],"日常对话"),
        "accounts/fireworks/models/qwen2p5-72b-instruct":     (0.90,0.90,"128k",["主力","快速"],"日常对话"),
        "accounts/fireworks/models/qwen2p5-coder-32b-instruct":(0.55,0.55,"32k",["代码","便宜"],"编程代码"),
        "accounts/fireworks/models/deepseek-v3":               (1.25,1.25,"64k",["主力","满血版"],"日常对话"),
        "accounts/fireworks/models/deepseek-r1":               (2.50,2.50,"64k",["推理","旗舰"],"深度推理"),
        "accounts/fireworks/models/mixtral-8x7b-instruct":    (0.24,0.24,"32k",["便宜","快速"],"日常对话"),
        "accounts/fireworks/models/deepseek-v3p2":             (1.25,1.25,"128k",["主力","满血版"],"日常对话"),
        "accounts/fireworks/models/deepseek-v3p1":             (1.25,1.25,"128k",["主力","满血版"],"日常对话"),
        "accounts/fireworks/models/kimi-k2p5":                 (0.50,2.80,"256k",["旗舰","长上下文"],"深度推理"),
        "accounts/fireworks/models/glm-5p1":                   (1.40,4.40,"200k",["旗舰"],"深度推理"),
        "accounts/fireworks/models/glm-5":                     (1.00,3.20,"200k",["主力"],"日常对话"),
        "accounts/fireworks/models/minimax-m2p7":              (0.30,1.20,"196k",["主力","长上下文"],"日常对话"),
        "accounts/fireworks/models/gpt-oss-120b":              (0.15,0.60,"128k",["便宜","快速"],"日常对话"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k.lower() in m2: return ii, oo, cc, tt, ss
    if "70b" in m2 or "72b" in m2: return 0.90, 0.90, "128k", ["主力","快速"], "日常对话"
    if "8b" in m2: return 0.08, 0.08, "128k", ["极便宜","快速"], "日常对话"
    if "32b" in m2: return 0.55, 0.55, "32k", ["便宜"], "日常对话"
    return 0.30, 0.30, "32k", ["价格待确认"], "日常对话"

# ─── 无问芯穹 价格映射 ───
def ip(mid):
    """无问芯穹 InfiniAI - 国内聚合平台（¥/M tokens）"""
    m = {
        "qwen2.5-72b-instruct": (4,4,"128k",["主力","长上下文"],"日常对话"),
        "qwen2.5-32b-instruct": (1.5,1.5,"32k",["便宜"],"日常对话"),
        "qwen2.5-14b-instruct": (0.8,0.8,"32k",["便宜"],"日常对话"),
        "qwen2.5-7b-instruct":  (0.4,0.4,"32k",["极便宜"],"日常对话"),
        "qwen2.5-coder-32b-instruct": (1.5,1.5,"32k",["代码","便宜"],"编程代码"),
        "qwq-32b":              (1.5,1.5,"128k",["推理","便宜"],"深度推理"),
        "deepseek-v3":          (2,8,"64k",["主力","满血版"],"日常对话"),
        "deepseek-r1":          (4,16,"64k",["推理","旗舰"],"深度推理"),
        "glm-4-plus":           (2,8,"128k",["主力"],"日常对话"),
        "glm-4-flash":          (0.5,3,"128k",["便宜","快速"],"日常对话"),
        "glm-4-9b-chat":        (0.1,0.1,"8k",["极便宜"],"日常对话"),
        "kimi-k2":              (4,16,"128k",["旗舰","长上下文"],"深度推理"),
        "yi-lightning":         (0.1,0.1,"16k",["极便宜","快速"],"日常对话"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    if "72b" in m2: return 4, 4, "128k", ["主力"], "日常对话"
    if "32b" in m2: return 1.5, 1.5, "32k", ["便宜"], "日常对话"
    if "14b" in m2: return 0.8, 0.8, "32k", ["便宜"], "日常对话"
    if "7b" in m2 or "9b" in m2: return 0.4, 0.4, "32k", ["极便宜"], "日常对话"
    return 1, 4, "32k", ["价格待确认"], "日常对话"

# ─── Novita AI 价格映射 (fallback) ───
def np(mid):
    """Novita AI - 聚合平台（¥/M tokens，API返回真实价格时不用此函数）"""
    m2 = mid.lower()
    if "glm-5.1" in m2: return 1.4, 4.4, "200k", ["旗舰"], "深度推理"
    if "glm-5" in m2: return 1.0, 3.2, "200k", ["主力"], "日常对话"
    if "glm-4.7" in m2: return 0.6, 2.2, "200k", ["主力"], "日常对话"
    if "deepseek" in m2: return 0.269, 0.4, "128k", ["主力"], "日常对话"
    if "kimi" in m2: return 0.95, 4.0, "256k", ["旗舰","长上下文"], "深度推理"
    if "qwen3.5" in m2: return 0.3, 2.4, "256k", ["主力"], "日常对话"
    if "minimax" in m2: return 0.3, 1.2, "200k", ["主力"], "日常对话"
    if "gemma" in m2: return 0.13, 0.4, "256k", ["便宜"], "日常对话"
    return 0.3, 1.2, "128k", ["价格待确认"], "日常对话"

# ─── DeepInfra 价格映射 ───
def dip(mid):
    """DeepInfra - 开源模型推理（$/1M tokens）"""
    m = {
        "Qwen/Qwen3.5-27B": (0.12,0.36,"128k",["主力","便宜"],"日常对话"),
        "Qwen/Qwen3.5-4B":  (0.02,0.06,"128k",["极便宜"],"日常对话"),
        "Qwen/QwQ-32B":     (0.12,0.36,"128k",["推理","便宜"],"深度推理"),
        "meta-llama/Llama-3.3-70B-Instruct": (0.35,0.40,"128k",["主力"],"日常对话"),
        "meta-llama/Llama-3.1-8B-Instruct":  (0.05,0.05,"128k",["极便宜"],"日常对话"),
        "deepseek-ai/DeepSeek-V3":  (0.42,0.85,"64k",["主力","满血版"],"日常对话"),
        "deepseek-ai/DeepSeek-R1":  (0.80,2.19,"64k",["推理","旗舰"],"深度推理"),
        "google/gemma-3-27b-it":    (0.10,0.10,"128k",["便宜"],"日常对话"),
        "mistralai/Mixtral-8x7B-Instruct-v0.1": (0.24,0.24,"32k",["便宜"],"日常对话"),
        "microsoft/phi-4": (0.07,0.14,"16k",["极便宜"],"日常对话"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k.lower() in m2: return ii, oo, cc, tt, ss
    if "70b" in m2 or "72b" in m2: return 0.35, 0.40, "128k", ["主力"], "日常对话"
    if "32b" in m2 or "34b" in m2: return 0.12, 0.36, "128k", ["便宜"], "日常对话"
    if "8b" in m2 or "9b" in m2: return 0.05, 0.05, "128k", ["极便宜"], "日常对话"
    if "4b" in m2: return 0.02, 0.06, "128k", ["极便宜"], "日常对话"
    return 0.12, 0.36, "32k", ["价格待确认"], "日常对话"

# ─── Novita AI 标签推断 ───
def np_tags(mid, inp, out, ctx):
    """根据模型名和价格推断标签和场景"""
    m2 = mid.lower()
    tt = []
    if inp < 0.1: tt.append("极便宜")
    elif inp < 0.5: tt.append("便宜")
    elif inp < 2: tt.append("主力")
    else: tt.append("旗舰")
    if "coder" in m2 or "code" in m2: tt.append("代码"); ss = "编程代码"
    elif "reason" in m2 or "r1" in m2 or "qwq" in m2 or "kimi-k2" in m2: tt.append("推理"); ss = "深度推理"
    elif "vision" in m2 or "vl" in m2: tt.append("视觉"); ss = "视觉图片"
    elif "ocr" in m2: tt.append("OCR"); ss = "其他"
    else: ss = "日常对话"
    if ctx >= 200000: tt.append("长上下文")
    return tt, ss

# ─── DeepInfra 标签推断 ───
def dip_tags(mid, inp, out, ctx):
    m2 = mid.lower()
    tt = []
    if inp < 0.05: tt.append("极便宜")
    elif inp < 0.2: tt.append("便宜")
    elif inp < 1: tt.append("主力")
    else: tt.append("旗舰")
    if "coder" in m2 or "code" in m2: tt.append("代码"); ss = "编程代码"
    elif "r1" in m2 or "qwq" in m2: tt.append("推理"); ss = "深度推理"
    elif "vision" in m2 or "vl" in m2: tt.append("视觉"); ss = "视觉图片"
    else: ss = "日常对话"
    if ctx >= 128000: tt.append("长上下文")
    return tt, ss

# ─── Cohere 价格映射 ───
def cop(mid):
    """Cohere - Command R+ 系列，企业级（$/1M tokens，2026年4月官网定价）"""
    m = {
        "command-r-plus":  (2.50,10.00,"128k",["旗舰","长上下文"],"深度推理"),
        "command-r":        (0.50,1.50,"128k",["主力","长上下文"],"日常对话"),
        "command-r7b":      (0.0375,0.0375,"8k",["极便宜"],"日常对话"),
        "command-a":        (0.15,0.60,"256k",["便宜","长上下文"],"日常对话"),
        "c4ai-aya-expanse-8b": (0.15,0.15,"8k",["便宜"],"日常对话"),
        "c4ai-aya-expanse-32b":(0.50,1.50,"128k",["主力"],"日常对话"),
        "embed-v3":         (0.10,0,"512",["向量"],"其他"),
        "rerank-v3":        (0.10,0,"512",["排序"],"其他"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    return 0.50, 1.50, "128k", ["价格待确认"], "日常对话"

# ═══════════════════════════════════════════════════════════
# 数据抓取
# ═══════════════════════════════════════════════════════════

print("Fetching data...")
t0 = time.time()

# ─── 阿里百炼 ───
ali = []
if ALI:
    for pg in range(1, 10):
        d = fj("https://dashscope.aliyuncs.com/api/v1/models?page_no=%d&page_size=100" % pg, ALI)
        if not d: break
        ms2 = d.get("output",{}).get("models",[]); tot = d.get("output",{}).get("total",0)
        if not ms2: break
        for m in ms2:
            p0 = (m.get("prices") or [{}])[0].get("prices", [])
            ii = oo = 0.0
            for px in p0:
                if px.get("type") == "input_token":   ii = float(px.get("price","0") or 0)
                if px.get("type") == "output_token": oo = float(px.get("price","0") or 0)
            cc = str(int(((m.get("model_info") or {}).get("context_window") or 0) // 1000)) + "k"
            ca = m.get("capabilities",[]); tt = []
            if "Reasoning" in ca: tt.append("推理")
            if "VU" in ca: tt.append("视觉")
            if "IG" in ca: tt.append("图片生成"); ss = "图片生成"
            if "VG" in ca: tt.append("视频生成"); ss = "视频生成"
            elif "VU" in ca: ss = "视觉图片"
            elif "Reasoning" in ca: ss = "深度推理"
            else: ss = "日常对话"
            nn = (m.get("name") or m.get("model") or "")
            ali.append({"n":nn,"i":ii,"o":oo,"c":cc,"t":tt,"s":ss})
        print("  Aliyun: %d/%d" % (len(ali), tot), file=sys.stderr)
        if len(ali) >= tot: break
        time.sleep(0.2)
print("  Aliyun:", len(ali), file=sys.stderr)

# ─── 硅基流动 ───
sf_ids = []
if SF:
    d = fj("https://api.siliconflow.cn/v1/models", SF)
    sf_ids = [m["id"] for m in (d.get("data",[]) if d else [])]
print("  SF:", len(sf_ids), file=sys.stderr)

# ─── 月之暗面 ───
ms_list = []
if MS:
    d = fj("https://api.moonshot.cn/v1/models", MS)
    ms_list = [{"id":m["id"],"c":str(int(m.get("context_length",0)//1000))+"k"} for m in (d.get("data",[]) if d else [])]
print("  Moonshot:", len(ms_list), file=sys.stderr)

# ─── 智谱AI ───
zh_ids = []
if ZH:
    d = fj("https://open.bigmodel.cn/api/paas/v4/models", ZH)
    zh_ids = [m["id"] for m in (d.get("data",[]) if d else [])]
print("  Zhipu:", len(zh_ids), file=sys.stderr)

# ─── 火山引擎 ───
vc_list = []
if VC:
    d = fj("https://ark.cn-beijing.volces.com/api/v3/models", VC)
    vc_list = [{"id":m["id"],"st":m.get("status","")} for m in (d.get("data",[]) if d else [])]
print("  Volcengine:", len(vc_list), file=sys.stderr)

# ─── OpenRouter (实时拉取) ───
OR = []
d = fj("https://openrouter.ai/api/v1/models", retries=3)
if d:
    OR = d.get("data", [])
    # 缓存到本地
    try:
        with open(os.path.join(CACHE_DIR, "openrouter_full.json"), "w") as cf:
            json.dump(d, cf)
    except:
        pass
else:
    # 回退到缓存
    cp = os.path.join(CACHE_DIR, "openrouter_full.json")
    if os.path.exists(cp):
        try: OR = json.load(open(cp)).get("data",[])
        except: pass
print("  OpenRouter:", len(OR), file=sys.stderr)

# ─── 腾讯混元 ───
tx_ids = []
if TX:
    d = fj("https://hunyuan.tencentcloudapi.com/v1/models", TX)
    if d:
        tx_ids = [m.get("id","") for m in (d.get("data",[]) if d else [])]
if not tx_ids:
    # 使用硬编码列表
    tx_ids = ["hunyuan-turbos","hunyuan-turbo","hunyuan-pro","hunyuan-large","hunyuan-lite",
              "hunyuan-standard","hunyuan-standard-vision","hunyuan-vision","hunyuan-coder",
              "hunyuan-t1","hunyuan-turbos-vision"]
print("  Tencent:", len(tx_ids), file=sys.stderr)

# ─── 讯飞星火 ───
xh_ids = []
if XH:
    # 讯飞没有标准模型列表API，使用硬编码
    pass
xh_ids = ["generalv3.5","generalv3","4.0Ultra","generalv2","spark-lite","generalv3.5-vision"]
print("  Spark:", len(xh_ids), file=sys.stderr)

# ─── MiniMax ───
mm_ids = []
if MM:
    d = fj("https://api.minimax.chat/v1/models", MM)
    if d:
        mm_ids = [m.get("id","") for m in (d.get("data",[]) if d else [])]
if not mm_ids:
    mm_ids = ["abab6.5s","abab6.5","abab6.5g","abab5.5","abab5.5s","abab6.5s-vision","abab6.5-vision","minimax-m1"]
print("  MiniMax:", len(mm_ids), file=sys.stderr)

# ─── 零一万物 ───
yw_ids = []
if YW:
    d = fj("https://api.lingyiwanwu.com/v1/models", YW)
    if d:
        yw_ids = [m.get("id","") for m in (d.get("data",[]) if d else [])]
if not yw_ids:
    yw_ids = ["yi-light","yi-medium","yi-large","yi-vision","yi-large-turbo","yi-spark","yi-lightning"]
print("  Yi:", len(yw_ids), file=sys.stderr)

# ─── 百川智能 ───
bc_ids = []
if BC:
    d = fj("https://api.baichuan-ai.com/v1/models", BC)
    if d:
        bc_ids = [m.get("id","") for m in (d.get("data",[]) if d else [])]
if not bc_ids:
    bc_ids = ["baichuan2-turbo","baichuan2-53b","baichuan-14b","baichuan4","baichuan4-vision","baichuan-m1"]
print("  Baichuan:", len(bc_ids), file=sys.stderr)

# ─── 阶跃星辰 ───
jc_ids = []
if JC:
    d = fj("https://api.stepfun.com/v1/models", JC)
    if d:
        jc_ids = [m.get("id","") for m in (d.get("data",[]) if d else [])]
if not jc_ids:
    jc_ids = ["step-1-8k","step-1-32k","step-1-128k","step-1-flash","step-1v-8k","step-1v-32k","step-2-16k","step-2-mini","step-r1"]
print("  Jieyue:", len(jc_ids), file=sys.stderr)

# ─── DeepSeek 官方 ───
ds_ids = []
if DS:
    d = fj("https://api.deepseek.com/v1/models", DS)
    if d:
        ds_ids = [m.get("id","") for m in (d.get("data",[]) if d else [])]
if not ds_ids:
    ds_ids = ["deepseek-chat","deepseek-reasoner","deepseek-v3","deepseek-r1","deepseek-prover-v2"]
print("  DeepSeek:", len(ds_ids), file=sys.stderr)

# ─── Groq ───
gq_ids = []
if GQ:
    d = fj("https://api.groq.com/openai/v1/models", GQ)
    if d:
        gq_ids = [m.get("id","") for m in (d.get("data",[]) if d else [])]
if not gq_ids:
    gq_ids = ["llama-3.3-70b-versatile","llama-3.1-8b-instant","llama-3.1-70b-versatile",
              "llama-3.2-1b-preview","llama-3.2-3b-preview","llama-3.2-11b-vision-preview",
              "llama-3.2-90b-vision-preview","mixtral-8x7b-32768","gemma2-9b-it",
              "deepseek-r1-distill-llama-70b","deepseek-r1-distill-qwen-32b"]
print("  Groq:", len(gq_ids), file=sys.stderr)

# ─── Together AI ───
tg_list = []
if TG:
    d = fj("https://api.together.xyz/v1/models", TG)
    if d:
        raw = d.get("data",[]) if isinstance(d, dict) else d if isinstance(d, list) else []
        for m in raw:
            mid = m.get("id","")
            pricing = m.get("pricing", {})
            inp = float(pricing.get("input", 0) or 0)
            out = float(pricing.get("output", 0) or 0)
            ctx = m.get("context_length", 0) or 0
            # 只保留有价格且有上下文的文本模型
            if inp > 0 and out > 0 and ctx > 0:
                tg_list.append({"id": mid, "i": inp, "o": out, "c": ctx})
if not tg_list:
    tg_list = [{"id":x,"i":0,"o":0,"c":0} for x in [
        "meta-llama/Llama-3.3-70B-Instruct-Turbo","meta-llama/Llama-3.1-8B-Instruct-Turbo",
        "meta-llama/Llama-3.1-405B-Instruct-Turbo","meta-llama/Llama-3.2-3B-Instruct-Turbo",
        "Qwen/Qwen2.5-72B-Instruct-Turbo","Qwen/Qwen2.5-Coder-32B-Instruct",
        "Qwen/QwQ-32B","deepseek-ai/DeepSeek-V3-0324",
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B","mistralai/Mixtral-8x7B-Instruct-v0.1",
        "mistralai/Mixtral-8x22B-Instruct-v0.3","google/gemma-2-27b-it"]]
print("  Together:", len(tg_list), file=sys.stderr)

# ─── Fireworks AI ───
fw_list = []
if FW:
    d = fj("https://api.fireworks.ai/inference/v1/models", FW)
    if d:
        for m in (d.get("data",[]) if d else []):
            mid = m.get("id","")
            ctx = m.get("context_length", 0) or 0
            fw_list.append({"id": mid, "c": ctx})
if not fw_list:
    fw_list = [{"id":x,"c":0} for x in [
        "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "accounts/fireworks/models/llama-v3p1-70b-instruct",
        "accounts/fireworks/models/llama-v3p2-3b-instruct",
        "accounts/fireworks/models/qwen2p5-72b-instruct",
        "accounts/fireworks/models/qwen2p5-coder-32b-instruct",
        "accounts/fireworks/models/deepseek-v3",
        "accounts/fireworks/models/deepseek-r1",
        "accounts/fireworks/models/mixtral-8x7b-instruct"]]
print("  Fireworks:", len(fw_list), file=sys.stderr)

# ─── Cohere ───
co_list = []
if CO:
    d = fj("https://api.cohere.com/v1/models", CO)
    if d:
        co_list = [{"id":m.get("name",m.get("id",""))} for m in (d.get("models",d.get("data",[])) if d else [])]
if not co_list:
    co_list = [{"id":x} for x in [
        "command-r-plus","command-r","command-r7b","command-a",
        "c4ai-aya-expanse-8b","c4ai-aya-expanse-32b","embed-v3","rerank-v3"]]
print("  Cohere:", len(co_list), file=sys.stderr)

# 无问芯穹 (InfiniAI)
infini_list = []
if INFINI:
    d = fj("https://cloud.infini-ai.com/maas/v1/models", INFINI)
    if d:
        raw = d.get("data",[]) if isinstance(d, dict) else d if isinstance(d, list) else []
        for m in raw:
            mid = m.get("id","")
            if mid and "embed" not in mid.lower() and "rerank" not in mid.lower():
                infini_list.append(mid)
if not infini_list:
    infini_list = ["qwen2.5-72b-instruct","qwen2.5-32b-instruct","qwen2.5-14b-instruct","qwen2.5-7b-instruct",
                   "glm-4-9b-chat","deepseek-v3","deepseek-r1","kimi-k2","yi-lightning",
                   "qwen2.5-coder-32b-instruct","qwq-32b","glm-4-plus","glm-4-flash"]
print("  InfiniAI:", len(infini_list), file=sys.stderr)

# Novita AI
novita_list = []
d = fj("https://api.novita.ai/v3/openai/models", NOVITA)
if d:
    raw = d.get("data",[]) if isinstance(d, dict) else d if isinstance(d, list) else []
    for m in raw:
        mid = m.get("id","")
        inp_p = float(m.get("input_token_price_per_m", 0) or 0)
        out_p = float(m.get("output_token_price_per_m", 0) or 0)
        ctx = int(m.get("context_size", 0) or 0)
        status = m.get("status", "")
        if mid and inp_p > 0 and out_p > 0 and status != "deprecated":
            novita_list.append({"id": mid, "i": inp_p / 10000, "o": out_p / 10000, "c": ctx})
if not novita_list:
    novita_list = [{"id":"zai-org/glm-4.7-flash","i":0.07,"o":0.4,"c":200000},
                   {"id":"deepseek/deepseek-v3.2","i":0.269,"o":0.4,"c":163840},
                   {"id":"qwen/qwen3.5-27b","i":0.3,"o":2.4,"c":262144},
                   {"id":"qwen/qwen3.5-122b-a10b","i":0.4,"o":3.2,"c":262144}]
print("  Novita:", len(novita_list), file=sys.stderr)

# DeepInfra
di_list = []
if DEEPINFRA:
    d = fj("https://api.deepinfra.com/v1/openai/models", DEEPINFRA)
    if d:
        raw = d.get("data",[]) if isinstance(d, dict) else d if isinstance(d, list) else []
        for m in raw:
            mid = m.get("id","")
            if mid and "embed" not in mid.lower() and "rerank" not in mid.lower() and "flux" not in mid.lower() and "remove" not in mid.lower() and "enhance" not in mid.lower():
                di_list.append(mid)
if not di_list:
    di_list = ["Qwen/Qwen3.5-27B","Qwen/Qwen3.5-4B","meta-llama/Llama-3.3-70B-Instruct",
               "meta-llama/Llama-3.1-8B-Instruct","deepseek-ai/DeepSeek-V3","deepseek-ai/DeepSeek-R1",
               "google/gemma-3-27b-it","mistralai/Mixtral-8x7B-Instruct-v0.1",
               "microsoft/phi-4","Qwen/QwQ-32B"]
print("  DeepInfra:", len(di_list), file=sys.stderr)

# ═══════════════════════════════════════════════════════════
# 生成模型卡片
# ═══════════════════════════════════════════════════════════

cards = []
all_models = []  # 用于价格变动检测

# 阿里百炼
for m in ali:
    fam = get_family(m["n"])
    cards.append(make_card("aliyun","阿里百炼","#ff6a00",Te(m["n"]),m["i"],m["o"],m["c"],m["t"],m["s"],
                 "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"aliyun","n":m["n"],"i":m["i"],"o":m["o"]})

# 硅基流动
for mid in sf_ids:
    ii, oo, tt, ss = sp(mid)
    fam = get_family(mid)
    cards.append(make_card("siliconflow","硅基流动","#7C3AED",Te(mid),ii,oo,"32k",tt,ss,
                 "https://api.siliconflow.cn/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"siliconflow","n":mid,"i":ii,"o":oo})

# 月之暗面
for m in ms_list:
    mid = m["id"]
    ii, oo, cc, tt, ss = mp(mid)
    fam = get_family(mid)
    cards.append(make_card("moonshot","月之暗面","#4f46e5",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.moonshot.cn/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"moonshot","n":mid,"i":ii,"o":oo})

# 智谱AI
for mid in zh_ids:
    ii, oo, cc, tt, ss = zp(mid)
    fam = get_family(mid)
    cards.append(make_card("zhipu","智谱 AI","#00c4b4",Te(mid),ii,oo,cc,tt,ss,
                 "https://open.bigmodel.cn/api/paas/v4/chat/completions","CNY",family=fam))
    all_models.append({"p":"zhipu","n":mid,"i":ii,"o":oo})

# 火山引擎
for m in vc_list:
    mid = m["id"]; st = m.get("st","")
    ii, oo, cc, tt, ss = vp(mid)
    tt = tt[:]
    if st == "Shutdown":  tt = ["已下线"] + tt
    elif st == "Retiring": tt = ["即将下线"] + tt
    fam = get_family(mid)
    cards.append(make_card("volcengine","火山引擎","#dc2626",Te(mid),ii,oo,cc,tt,ss,
                 "https://ark.cn-beijing.volces.com/api/v3/chat/completions","CNY",family=fam))
    all_models.append({"p":"volcengine","n":mid,"i":ii,"o":oo})

# 百度文心
for m in BD:
    fam = get_family(m["n"])
    cards.append(make_card("baidu","百度文心","#2932e1",Te(m["n"]),m["i"],m["o"],m["c"],m["t"],m["s"],
                 "https://qianfan.baidubce.com/v2/chat/completions","CNY",family=fam))
    all_models.append({"p":"baidu","n":m["n"],"i":m["i"],"o":m["o"]})

# OpenRouter
for m in OR[:350]:
    ii = float(m.get("pricing",{}).get("prompt",0) or 0)
    oo = float(m.get("pricing",{}).get("completion",0) or 0)
    nn = Te(m.get("name", m.get("id","")))
    cc_r = m.get("context_length") or 0
    cc = str(int(cc_r)//1000)+"k" if cc_r else "N/A"
    tt = []
    if ii == 0 and oo == 0: tt.append("免费")
    p = ii * 1e6
    if p > 0 and p < 0.1: tt.append("极便宜")
    elif p > 0 and p < 1:   tt.append("便宜")
    if cc_r >= 100000:       tt.append("长上下文")
    if m.get("vision"):       tt.append("视觉")
    if m.get("reasoning"):   tt.append("推理")
    ss = "日常对话"
    if m.get("reasoning"):   ss = "深度推理"
    elif m.get("vision"):     ss = "视觉图片"
    pv = Te(m.get("id","").split("/")[0].upper())
    mid2 = Te(m["id"])
    fam = get_family(m.get("id",""))
    cards.append(make_or_card(pv, nn, ii, oo, cc, tt, ss, mid2, family=fam))
    all_models.append({"p":"openrouter","n":m.get("id",""),"i":ii,"o":oo,"cur":"USD"})

# 腾讯混元
for mid in tx_ids:
    ii, oo, cc, tt, ss = tp(mid)
    fam = get_family(mid)
    cards.append(make_card("tencent","腾讯混元","#07c160",Te(mid),ii,oo,cc,tt,ss,
                 "https://hunyuan.tencentcloudapi.com/compatible-mode/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"tencent","n":mid,"i":ii,"o":oo})

# 讯飞星火
for mid in xh_ids:
    ii, oo, cc, tt, ss = xp(mid)
    fam = get_family(mid)
    cards.append(make_card("spark","讯飞星火","#ff6a00",Te(mid),ii,oo,cc,tt,ss,
                 "https://spark-api.xf-yun.com/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"spark","n":mid,"i":ii,"o":oo})

# MiniMax
for mid in mm_ids:
    ii, oo, cc, tt, ss = mm_p(mid)
    fam = get_family(mid)
    cards.append(make_card("minimax","MiniMax","#6366f1",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.minimax.chat/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"minimax","n":mid,"i":ii,"o":oo})

# 零一万物
for mid in yw_ids:
    ii, oo, cc, tt, ss = yp(mid)
    fam = get_family(mid)
    cards.append(make_card("yi","零一万物","#3b82f6",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.lingyiwanwu.com/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"yi","n":mid,"i":ii,"o":oo})

# 百川智能
for mid in bc_ids:
    ii, oo, cc, tt, ss = bp(mid)
    fam = get_family(mid)
    cards.append(make_card("baichuan","百川智能","#ef4444",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.baichuan-ai.com/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"baichuan","n":mid,"i":ii,"o":oo})

# 阶跃星辰
for mid in jc_ids:
    ii, oo, cc, tt, ss = jp(mid)
    fam = get_family(mid)
    cards.append(make_card("jieyue","阶跃星辰","#8b5cf6",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.stepfun.com/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"jieyue","n":mid,"i":ii,"o":oo})

# DeepSeek 官方
for mid in ds_ids:
    ii, oo, cc, tt, ss = dp(mid)
    fam = get_family(mid)
    cards.append(make_card("deepseek","DeepSeek","#4d6dff",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.deepseek.com/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"deepseek","n":mid,"i":ii,"o":oo})

# Groq
for mid in gq_ids:
    ii, oo, cc, tt, ss = gp(mid)
    fam = get_family(mid)
    cards.append(make_card("groq","Groq","#f55036",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.groq.com/openai/v1/chat/completions","USD",family=fam,price_unit="per_1m"))
    all_models.append({"p":"groq","n":mid,"i":ii,"o":oo,"cur":"USD"})

# Together AI
for m in tg_list:
    mid = m["id"]
    # 优先使用 API 返回的真实价格
    api_inp = m.get("i", 0)
    api_out = m.get("o", 0)
    api_ctx = m.get("c", 0)
    if api_inp > 0 and api_out > 0:
        ii, oo = api_inp, api_out
        cc = str(int(api_ctx)//1000)+"k" if api_ctx else "N/A"
    else:
        ii, oo, cc, tt, ss = tgp(mid)
    if api_inp == 0 and api_out == 0:
        ii, oo, cc, tt, ss = tgp(mid)
    else:
        # 从模型名推断标签
        tt, ss = tgp_tags(mid, ii, oo, api_ctx)
    fam = get_family(mid)
    cards.append(make_card("together","Together AI","#00d4ff",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.together.xyz/v1/chat/completions","USD",family=fam,price_unit="per_1m"))
    all_models.append({"p":"together","n":mid,"i":ii,"o":oo,"cur":"USD"})

# Fireworks AI
for m in fw_list:
    mid = m["id"]
    ii, oo, cc, tt, ss = fwp(mid)
    # 使用 API 返回的上下文长度
    api_ctx = m.get("c", 0)
    if api_ctx > 0:
        cc = str(int(api_ctx)//1000)+"k"
    fam = get_family(mid)
    cards.append(make_card("fireworks","Fireworks AI","#ff6b35",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.fireworks.ai/inference/v1/chat/completions","USD",family=fam,price_unit="per_1m"))
    all_models.append({"p":"fireworks","n":mid,"i":ii,"o":oo,"cur":"USD"})

# Cohere
for m in co_list:
    mid = m["id"]
    ii, oo, cc, tt, ss = cop(mid)
    fam = get_family(mid)
    cards.append(make_card("cohere","Cohere","#39d989",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.cohere.com/v2/chat/completions","USD",family=fam,price_unit="per_1m"))
    all_models.append({"p":"cohere","n":mid,"i":ii,"o":oo,"cur":"USD"})

# 无问芯穹 (InfiniAI)
for mid in infini_list:
    ii, oo, cc, tt, ss = ip(mid)
    fam = get_family(mid)
    cards.append(make_card("infini","无问芯穹","#ff6b9d",Te(mid),ii,oo,cc,tt,ss,
                 "https://cloud.infini-ai.com/maas/v1/chat/completions","CNY",family=fam))
    all_models.append({"p":"infini","n":mid,"i":ii,"o":oo})

# Novita AI
for m in novita_list:
    mid = m["id"]
    api_inp = m.get("i", 0)
    api_out = m.get("o", 0)
    api_ctx = m.get("c", 0)
    if api_inp > 0 and api_out > 0:
        ii, oo = api_inp, api_out
        cc = str(int(api_ctx)//1000)+"k" if api_ctx else "N/A"
        tt, ss = np_tags(mid, ii, oo, api_ctx)
    else:
        ii, oo, cc, tt, ss = np(mid)
    fam = get_family(mid)
    cards.append(make_card("novita","Novita AI","#6366f1",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.novita.ai/v3/openai/chat/completions","CNY",family=fam))
    all_models.append({"p":"novita","n":mid,"i":ii,"o":oo})

# DeepInfra
for mid in di_list:
    ii, oo, cc, tt, ss = dip(mid)
    fam = get_family(mid)
    cards.append(make_card("deepinfra","DeepInfra","#7c3aed",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.deepinfra.com/v1/openai/chat/completions","USD",family=fam,price_unit="per_1m"))
    all_models.append({"p":"deepinfra","n":mid,"i":ii,"o":oo,"cur":"USD"})

# ─── 价格变动检测 ───
price_changes = []
if os.path.exists(PREV_DATA):
    try:
        prev = json.load(open(PREV_DATA))
        prev_map = {(m["p"],m["n"]): m for m in prev}
        for m in all_models:
            key = (m["p"], m["n"])
            if key in prev_map:
                pm = prev_map[key]
                pi_old = pm.get("i",0); po_old = pm.get("o",0)
                pi_new = m["i"]; po_new = m["o"]
                if pi_new != pi_old or po_new != po_old:
                    price_changes.append({"p":m["p"],"n":m["n"],
                        "old_i":pi_old,"old_o":po_old,"new_i":pi_new,"new_o":po_new})
    except:
        pass
# 保存当前数据供下次对比
with open(PREV_DATA, "w") as f:
    json.dump(all_models, f)

total = len(cards)
print("Generated:", total, file=sys.stderr)
if price_changes:
    print("  Price changes detected:", len(price_changes), file=sys.stderr)

def cn(p): return sum(1 for c in cards if 'data-p="' + p + '"' in c)
ac = cn("aliyun"); sc2 = cn("siliconflow"); mc2 = cn("moonshot")
zc = cn("zhipu"); vc2 = cn("volcengine"); bc2 = cn("baidu"); oc = cn("openrouter")
tc2 = cn("tencent"); xc = cn("spark"); mmc = cn("minimax")
yc = cn("yi"); bcc = cn("baichuan"); jcc = cn("jieyue")
dc = cn("deepseek"); gc = cn("groq")
tgc = cn("together"); fwc = cn("fireworks"); coc = cn("cohere")
ic = cn("infini")
nc = cn("novita")
dic = cn("deepinfra")

def tc(p): return sum(1 for c in cards if 'data-pt="' + p + '"' in c)
print("  Tier free:%d cheap:%d mid:%d high:%d ultra:%d" % (
    tc("free"),tc("cheap"),tc("mid"),tc("high"),tc("ultra")), file=sys.stderr)

now = datetime.now().strftime("%Y-%m-%d %H:%M")

# ═══════════════════════════════════════════════════════════
# HTML 组件
# ═══════════════════════════════════════════════════════════

pt_bar = (
    '<button class="pt-filter active" data-pt="all">全部价格</button>'
    '<button class="pt-filter" data-pt="free">&#128998; 免费</button>'
    '<button class="pt-filter" data-pt="cheap">&#128308; &lt;¥0.7</button>'
    '<button class="pt-filter" data-pt="mid">&#128993; ¥0.7-10/M</button>'
    '<button class="pt-filter" data-pt="high">&#128996; ¥10+/M</button>'
    '<button class="pt-filter" data-pt="ultra">&#127745; &gt;¥100/M</button>'
)

scen_list = [("全部","all"),("日常对话","日常对话"),("深度推理","深度推理"),
             ("视觉图片","视觉图片"),("图片生成","图片生成"),("视频生成","视频生成"),
             ("编程代码","编程代码"),("其他","其他")]
scen_bar = "".join(
    '<button class="sc' + (" active" if v=="all" else "") + '" data-sc="' + v + '">' + l + '</button>'
    for l,v in scen_list
)

tabs_bar = (
    '<button class="pt active" data-p="all" style="--c:#6366f1;--bg:#eef2ff">全部 <span class="pc">' + str(total) + '</span></button>'
    '<button class="pt" data-p="openrouter" style="--c:#6366f1;--bg:#eef2ff">OpenRouter <span class="pc">' + str(oc) + '</span></button>'
    '<button class="pt" data-p="aliyun" style="--c:#ff6a00;--bg:#fff5ee">阿里百炼 <span class="pc">' + str(ac) + '</span></button>'
    '<button class="pt" data-p="siliconflow" style="--c:#7C3AED;--bg:#f5f0ff">硅基流动 <span class="pc">' + str(sc2) + '</span></button>'
    '<button class="pt" data-p="moonshot" style="--c:#4f46e5;--bg:#f0f0ff">月之暗面 <span class="pc">' + str(mc2) + '</span></button>'
    '<button class="pt" data-p="zhipu" style="--c:#00c4b4;--bg:#f0fffe">智谱 AI <span class="pc">' + str(zc) + '</span></button>'
    '<button class="pt" data-p="volcengine" style="--c:#dc2626;--bg:#fff0f0">火山引擎 <span class="pc">' + str(vc2) + '</span></button>'
    '<button class="pt" data-p="baidu" style="--c:#2932e1;--bg:#f0f2ff">百度文心 <span class="pc">' + str(bc2) + '</span></button>'
    '<button class="pt" data-p="tencent" style="--c:#07c160;--bg:#f0fff4">腾讯混元 <span class="pc">' + str(tc2) + '</span></button>'
    '<button class="pt" data-p="spark" style="--c:#ff6a00;--bg:#fff5ee">讯飞星火 <span class="pc">' + str(xc) + '</span></button>'
    '<button class="pt" data-p="minimax" style="--c:#6366f1;--bg:#eef2ff">MiniMax <span class="pc">' + str(mmc) + '</span></button>'
    '<button class="pt" data-p="yi" style="--c:#3b82f6;--bg:#eff6ff">零一万物 <span class="pc">' + str(yc) + '</span></button>'
    '<button class="pt" data-p="baichuan" style="--c:#ef4444;--bg:#fef2f2">百川智能 <span class="pc">' + str(bcc) + '</span></button>'
    '<button class="pt" data-p="jieyue" style="--c:#8b5cf6;--bg:#f5f3ff">阶跃星辰 <span class="pc">' + str(jcc) + '</span></button>'
    '<button class="pt" data-p="deepseek" style="--c:#4d6dff;--bg:#eef0ff">DeepSeek <span class="pc">' + str(dc) + '</span></button>'
    '<button class="pt" data-p="groq" style="--c:#f55036;--bg:#fff0ee">Groq <span class="pc">' + str(gc) + '</span></button>'
    '<button class="pt" data-p="together" style="--c:#00d4ff;--bg:#eef8ff">Together <span class="pc">' + str(tgc) + '</span></button>'
    '<button class="pt" data-p="fireworks" style="--c:#ff6b35;--bg:#fff5ee">Fireworks <span class="pc">' + str(fwc) + '</span></button>'
    '<button class="pt" data-p="cohere" style="--c:#39d989;--bg:#eefbf4">Cohere <span class="pc">' + str(coc) + '</span></button>'
    '<button class="pt" data-p="infini" style="--c:#ff6b9d;--bg:#fff0f6">无问芯穹 <span class="pc">' + str(ic) + '</span></button>'
    '<button class="pt" data-p="novita" style="--c:#6366f1;--bg:#eef2ff">Novita AI <span class="pc">' + str(nc) + '</span></button>'
    '<button class="pt" data-p="deepinfra" style="--c:#7c3aed;--bg:#f5f0ff">DeepInfra <span class="pc">' + str(dic) + '</span></button>'
)

snote = (
    "&#9888; <strong>数据说明：</strong>"
    "阿里百炼 <strong>" + str(ac) + "个模型</strong>从 API 实时拉取，含真实价格；"
    "硅基流动/" + str(sc2) + "个、月之暗面/" + str(mc2) + "个、智谱/" + str(zc) + "个等从 API 拉取列表，价格来自各平台官网公告（2026年4月）；"
    "OpenRouter 显示原始美元价格，国内平台显示人民币价格；"
    "标注「价格待确认」的模型请至平台控制台核实。"
    "数据更新时间：" + now
)

sort_bar = (
    '<span class="sort-lbl">排序:</span>'
    '<button class="sort-btn active" data-sort="default">默认</button>'
    '<button class="sort-btn" data-sort="inp-asc">输入价↑</button>'
    '<button class="sort-btn" data-sort="inp-desc">输入价↓</button>'
    '<button class="sort-btn" data-sort="out-asc">输出价↑</button>'
    '<button class="sort-btn" data-sort="out-desc">输出价↓</button>'
    '<button class="sort-btn" data-sort="name">名称</button>'
    '<button class="sort-btn" data-sort="combined">综合价</button>'
    '<button class="sort-btn" data-sort="ctx">上下文↓</button>'
    '<button class="sort-btn" data-sort="costperf">性价比</button>'
)

# ─── 家族筛选栏 ───
family_counts = Counter()
for c in cards:
    m = re.search(r'data-family="([^"]*)"', c)
    if m:
        family_counts[m.group(1)] += 1
# 按数量排序，取前20个家族
top_families = family_counts.most_common(20)
family_bar = '<div class="family-bar"><span class="family-lbl">家族:</span>'
family_bar += '<button class="family-btn active" data-family="all">全部</button>'
for fam, cnt in top_families:
    if fam and fam != 'Other':
        family_bar += '<button class="family-btn" data-family="' + fam + '">' + fam + ' <span class="family-cnt">' + str(cnt) + '</span></button>'
family_bar += '</div>'

# ─── 标签筛选栏 ───
tag_list = ["免费额度","便宜","极便宜","旗舰","主力","推理","视觉","长上下文","开源","代码","图片生成","视频生成","蒸馏","轻量","最新版"]
tag_bar = '<div class="tag-bar"><span class="tag-lbl">标签:</span>' + "".join(
    '<button class="tag-btn" data-tag="' + t + '">' + t + '</button>' for t in tag_list
) + '</div>'

# ─── 上下文长度筛选 ───
ctx_bar = (
    '<div class="ctx-filter-bar"><span class="ctx-lbl">上下文:</span>'
    '<button class="ctx-btn active" data-ctx="all">全部</button>'
    '<button class="ctx-btn" data-ctx="8">≥8K</button>'
    '<button class="ctx-btn" data-ctx="32">≥32K</button>'
    '<button class="ctx-btn" data-ctx="128">≥128K</button>'
    '<button class="ctx-btn" data-ctx="256">≥256K</button>'
    '<button class="ctx-btn" data-ctx="512">≥512K</button>'
    '</div>'
)

# ─── 价格区间筛选 ───
price_range_bar = (
    '<div class="price-range-bar"><span class="pr-lbl">价格区间:</span>'
    '<input type="number" id="priceMin" placeholder="最低" min="0" step="0.1">'
    '<span class="pr-sep">-</span>'
    '<input type="number" id="priceMax" placeholder="最高" min="0" step="0.1">'
    '<span class="pr-unit">元/M</span>'
    '<button class="pr-btn" onclick="applyPriceRange()">应用</button>'
    '<button class="pr-btn pr-btn-clear" onclick="clearPriceRange()">清除</button>'
    '</div>'
)

# ─── 智能推荐面板 ───
recommend_panel = (
    '<div class="rec-panel" id="recPanel">'
    '<div class="rec-title">&#127775; 智能推荐</div>'
    '<div class="rec-desc">选择你的使用场景，自动推荐最合适的模型</div>'
    '<div class="rec-options">'
    '<button class="rec-btn" data-rec="chat">💬 日常聊天</button>'
    '<button class="rec-btn" data-rec="code">💻 写代码</button>'
    '<button class="rec-btn" data-rec="translate">🌐 翻译</button>'
    '<button class="rec-btn" data-rec="write">✍️ 写文章</button>'
    '<button class="rec-btn" data-rec="reason">🧠 深度推理</button>'
    '<button class="rec-btn" data-rec="vision">📷 图片理解</button>'
    '<button class="rec-btn" data-rec="image">🎨 图片生成</button>'
    '<button class="rec-btn" data-rec="video">🎬 视频生成</button>'
    '</div>'
    '<div class="rec-result" id="recResult"></div>'
    '</div>'
)

# ─── 跨平台比价面板 ───
crossprice_panel = (
    '<div class="cross-panel" id="crossPanel" style="display:none">'
    '<div class="cross-title">&#128269; 跨平台比价 <span style="font-weight:400;font-size:12px;color:#64748b">(同一模型在不同平台的价格)</span></div>'
    '<div class="cross-list" id="crossList"></div>'
    '</div>'
)

# ─── 月费计算器 (增强版) ───
calc_panel = (
    '<div class="calc-panel" id="calcPanel">'
    '<div class="calc-title">&#128202; 月费计算器</div>'
    '<div class="calc-presets">'
    '<span class="calc-preset-lbl">预设:</span>'
    '<button class="preset-btn" data-chats="100" data-tokens="1000" data-ratio="0.5">轻度用户</button>'
    '<button class="preset-btn" data-chats="1000" data-tokens="2000" data-ratio="1">中度用户</button>'
    '<button class="preset-btn" data-chats="5000" data-tokens="4000" data-ratio="1.5">重度用户</button>'
    '<button class="preset-btn" data-chats="2000" data-tokens="3000" data-ratio="2">开发者</button>'
    '</div>'
    '<div class="calc-row">'
    '<label>每月对话次数:</label><input type="number" id="calcChats" value="1000" min="0">'
    '</div>'
    '<div class="calc-row">'
    '<label>每对话Token数:</label><input type="number" id="calcTokens" value="2000" min="0">'
    '</div>'
    '<div class="calc-row">'
    '<label>输出/输入比:</label><input type="number" id="calcRatio" value="1" min="0" step="0.1">'
    '</div>'
    '<div class="calc-row">'
    '<label>月预算(元):</label><input type="number" id="calcBudget" value="" min="0" placeholder="可选">'
    '</div>'
    '<div class="calc-btns">'
    '<button class="calc-btn" onclick="runCalc()">计算月费用</button>'
    '<button class="calc-btn calc-btn-all" onclick="runCalcAll()">计算全部模型</button>'
    '<button class="calc-btn calc-btn-rev" onclick="runCalcReverse()">预算反推</button>'
    '</div>'
    '<div class="calc-result" id="calcResult"></div>'
    '</div>'
)

# ─── 模型对比面板 ───
cmp_panel = (
    '<div class="cmp-panel" id="cmpPanel" style="display:none">'
    '<div class="cmp-title">&#128202; 模型对比 (<span id="cmpCount">0</span>/3)</div>'
    '<div class="cmp-list" id="cmpList"></div>'
    '<div class="cmp-actions">'
    '<button class="cmp-btn" onclick="showCmp()">并排对比</button>'
    '<button class="cmp-btn cmp-btn-clear" onclick="clearCmp()">清空</button>'
    '</div>'
    '</div>'
    '<div class="cmp-modal" id="cmpModal" style="display:none">'
    '<div class="cmp-modal-content">'
    '<div class="cmp-modal-header"><span>模型对比详情</span><button class="cmp-close" onclick="closeCmpModal()">&times;</button></div>'
    '<div class="cmp-modal-body" id="cmpModalBody"></div>'
    '</div></div>'
)

# ─── 价格变动提示 ───
price_change_html = ""
if price_changes:
    price_change_html = '<div class="price-change-note">&#128260; 检测到 <strong>' + str(len(price_changes)) + '</strong> 个模型价格变动</div>'

# ═══════════════════════════════════════════════════════════
# CSS (完全内联)
# ═══════════════════════════════════════════════════════════

CSS = '''
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#050506;--surface:#0a0a0b;--surface2:#111113;--border:rgba(255,255,255,.08);--border-hi:rgba(255,255,255,.15);--text:#ededf0;--text2:#8a8f98;--text3:#55585e;--accent:#6366f1;--accent2:#a855f7;--accent-glow:rgba(99,102,241,.15);--radius:10px;--radius-lg:14px}
body{font-family:"Inter",-apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC",sans-serif;background:var(--bg);color:var(--text);transition:background .4s,color .4s;letter-spacing:-.01em;-webkit-font-smoothing:antialiased}
body.light{--bg:#f8f9fb;--surface:#fff;--surface2:#f4f5f7;--border:rgba(0,0,0,.08);--border-hi:rgba(0,0,0,.14);--text:#1a1c20;--text2:#5f6368;--text3:#93979c;--accent:#4f46e5;--accent2:#7c3aed;--accent-glow:rgba(79,70,229,.1)}
a{color:var(--accent);text-decoration:none}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px 40px}
.hdr{text-align:center;padding:32px 12px 20px}
.hdr h1{font-size:clamp(22px,5vw,32px);font-weight:700;background:linear-gradient(135deg,#6366f1,#a855f7,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:6px;letter-spacing:-.03em}
.hdr p{font-size:12px;color:var(--text2);letter-spacing:.01em}
.brow{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin-top:10px}
.bd{background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:3px 10px;font-size:10px;color:var(--text2);font-weight:500}
.bd-free{background:rgba(34,197,94,.08);color:#4ade80;border-color:rgba(34,197,94,.2)}
.bd-cheap{background:rgba(59,130,246,.08);color:#60a5fa;border-color:rgba(59,130,246,.2)}
.bd-mid{background:rgba(245,158,11,.08);color:#fbbf24;border-color:rgba(245,158,11,.2)}
.bd-high{background:rgba(239,68,68,.08);color:#f87171;border-color:rgba(239,68,68,.2)}
.bd-ultra{background:rgba(168,85,247,.08);color:#c084fc;border-color:rgba(168,85,247,.2)}
.snote{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.15);border-radius:var(--radius);padding:10px 14px;margin:10px 0 16px;font-size:11px;color:#fbbf24;line-height:1.7;text-align:center;backdrop-filter:blur(8px)}
.snote strong{color:#f59e0b}
/* 平台筛选栏 */
.pbar{display:flex;gap:6px;overflow-x:auto;padding:8px 0;scrollbar-width:none;flex-wrap:wrap;margin-bottom:2px}
.pbar::-webkit-scrollbar{display:none}
.pt{flex-shrink:0;display:flex;align-items:center;gap:5px;padding:6px 12px;border-radius:20px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-weight:500;font-size:11px;cursor:pointer;transition:all .2s cubic-bezier(.4,0,.2,1);white-space:nowrap;letter-spacing:.01em}
.pt:hover{border-color:var(--border-hi);color:var(--text);background:var(--surface2)}
.pt.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 20px var(--accent-glow)}
.pc{background:rgba(255,255,255,.15);border-radius:8px;padding:1px 5px;font-size:9px;font-weight:600}
.pt:not(.active) .pc{background:rgba(255,255,255,.06)}
/* 价格分级栏 */
.ptbar{display:flex;gap:5px;overflow-x:auto;padding:6px 0;scrollbar-width:none;flex-wrap:wrap;margin-bottom:6px}
.ptbar::-webkit-scrollbar{display:none}
.pt-filter{flex-shrink:0;display:flex;align-items:center;gap:4px;padding:5px 11px;border-radius:16px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:11px;font-weight:500;cursor:pointer;transition:all .2s;white-space:nowrap}
.pt-filter:hover{border-color:var(--border-hi);color:var(--text)}
.pt-filter.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 16px var(--accent-glow)}
.pt-filter[data-pt=free].active{background:#16a34a;border-color:#16a34a;box-shadow:0 0 16px rgba(22,163,74,.2)}
.pt-filter[data-pt=cheap].active{background:#2563eb;border-color:#2563eb;box-shadow:0 0 16px rgba(37,99,235,.2)}
.pt-filter[data-pt=mid].active{background:#d97706;border-color:#d97706;box-shadow:0 0 16px rgba(217,119,6,.2)}
.pt-filter[data-pt=high].active{background:#dc2626;border-color:#dc2626;box-shadow:0 0 16px rgba(220,38,38,.2)}
.pt-filter[data-pt=ultra].active{background:#7c3aed;border-color:#7c3aed;box-shadow:0 0 16px rgba(124,58,237,.2)}
/* 场景筛选栏 */
.sbar{display:flex;gap:5px;padding:6px 0;overflow-x:auto;scrollbar-width:none;margin-bottom:10px;flex-wrap:wrap}
.sbar::-webkit-scrollbar{display:none}
.sc{flex-shrink:0;padding:4px 10px;border-radius:10px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:11px;cursor:pointer;transition:all .2s;font-weight:500}
.sc:hover{border-color:var(--border-hi);color:var(--text)}
.sc.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 16px var(--accent-glow)}
/* 搜索框 */
.srow{position:relative;margin-bottom:12px}
.srow input{width:100%;padding:10px 14px 10px 36px;border:1px solid var(--border);border-radius:var(--radius);font-size:13px;background:var(--surface);outline:none;color:var(--text);transition:all .2s;letter-spacing:-.01em}
.srow input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.srow::before{content:"\\2315";position:absolute;left:12px;top:50%;transform:translateY(-50%);font-size:16px;color:var(--text3);pointer-events:none;font-weight:300}
/* 加载动画 */
.loading{text-align:center;padding:30px;color:var(--text2);font-size:13px;display:none}
.loading.show{display:block}
.sp{width:24px;height:24px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}
/* 模型卡片网格 */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:8px}
.grid.list-view{grid-template-columns:1fr}
.grid.list-view .mc{display:flex;align-items:center;gap:12px;padding:8px 14px}
.grid.list-view .mc .dot{position:static;flex-shrink:0}
.grid.list-view .mc .prov{margin:0;padding:0;min-width:80px}
.grid.list-view .mc .mname{margin:0;min-width:150px}
.grid.list-view .mc .tags{margin:0;flex:1}
.grid.list-view .mc .prow{margin:0;min-width:120px}
.grid.list-view .mc .ctx-row{margin:0;min-width:80px}
.grid.list-view .mc .hint{display:none}
.grid.list-view .mc .card-actions{position:static;margin:0}
/* 模型卡片 - 核心设计 */
.mc{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:14px;cursor:pointer;transition:all .2s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}
.mc::before{content:"";position:absolute;inset:0;background:linear-gradient(135deg,transparent 40%,rgba(99,102,241,.03) 50%,transparent 60%);opacity:0;transition:opacity .4s;pointer-events:none}
.mc:hover{border-color:var(--border-hi);transform:translateY(-1px);box-shadow:0 4px 24px rgba(0,0,0,.3),0 0 40px var(--accent-glow)}
.mc:hover::before{opacity:1}
.mc.fav-card{border-color:rgba(245,158,11,.3);box-shadow:0 0 20px rgba(245,158,11,.08)}
/* Shimmer effect on hover */
.mc::after{content:"";position:absolute;top:0;left:-100%;width:60%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.03),transparent);transition:none;pointer-events:none}
.mc:hover::after{animation:shimmer 1.2s ease-out}
@keyframes shimmer{0%{left:-100%}100%{left:200%}}
.dot{position:absolute;top:12px;right:12px;width:6px;height:6px;border-radius:50%;background:var(--c,var(--accent));box-shadow:0 0 8px var(--c,var(--accent))}
.prov{font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:.6px;margin-bottom:3px;padding-right:16px;font-weight:500}
.mname{font-size:13px;font-weight:600;color:var(--text);margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:-.01em}
.tags{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:7px}
.tg{font-size:9px;padding:2px 6px;border-radius:6px;font-weight:500;letter-spacing:.02em}
.tg-free{background:rgba(34,197,94,.1);color:#4ade80}
.tg-cheap{background:rgba(59,130,246,.1);color:#60a5fa}
.tg-hot{background:rgba(239,68,68,.1);color:#f87171}
.tg-vision{background:rgba(168,85,247,.1);color:#c084fc}
.tg-reason{background:rgba(14,165,233,.1);color:#38bdf8}
.tg-long{background:rgba(34,197,94,.1);color:#4ade80}
.tg-other{background:var(--surface2);color:var(--text2);border:1px solid var(--border)}
.prow{display:flex;align-items:center;gap:5px;margin-bottom:3px;min-height:20px}
.price-badge{font-size:11px;font-weight:600;padding:2px 7px;border-radius:8px;white-space:nowrap;letter-spacing:.01em}
.price-free{background:rgba(34,197,94,.1);color:#4ade80}
.price-cheap{background:rgba(59,130,246,.1);color:#60a5fa}
.price-mid{background:rgba(245,158,11,.1);color:#fbbf24}
.price-high{background:rgba(239,68,68,.1);color:#f87171}
.price-ultra{background:rgba(168,85,247,.1);color:#c084fc}
.ctx-row{display:flex;align-items:center;gap:6px;margin-bottom:3px}
.ctx{font-size:10px;color:var(--text3)}
.ctx-bar-wrap{flex:1;height:3px;background:var(--surface2);border-radius:2px;overflow:hidden}
.ctx-bar{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:2px;transition:width .3s}
.hint{font-size:10px;color:var(--accent);margin-top:4px;display:none;letter-spacing:.02em}
.mc:hover .hint{display:block}
.card-actions{display:flex;align-items:center;justify-content:space-between;margin-top:4px}
.fav-btn{cursor:pointer;font-size:14px;color:var(--text3);transition:color .15s;user-select:none}
.fav-btn.active{color:#f59e0b;text-shadow:0 0 8px rgba(245,158,11,.4)}
.fav-btn:hover{color:#fbbf24}
.empty{text-align:center;padding:50px 20px;color:var(--text2);font-size:13px}
.ftr{text-align:center;padding:24px 12px;border-top:1px solid var(--border);margin-top:28px}
.ftr p{font-size:11px;color:var(--text3);line-height:2}


/* 筛选分组 */
.fg{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:10px 12px;margin-bottom:10px;backdrop-filter:blur(8px)}
.fg-title{font-size:12px;font-weight:700;color:var(--accent);margin-bottom:6px;letter-spacing:.02em;text-transform:uppercase;border-bottom:1px solid var(--border);padding-bottom:4px}
.fg .pbar,.fg .ptbar,.fg .sbar,.fg .sort-bar,.fg .tag-bar,.fg .ctx-filter-bar,.fg .price-range-bar,.fg .family-bar{margin-bottom:4px}
.fg .rec-panel{margin-bottom:0;padding:8px 10px}
.fg .toolbar{margin-bottom:0}

/* 跨平台比价 + 月费计算器 同行 */
.side-panels{display:flex;gap:10px;margin-bottom:10px}
.side-panels .cross-panel{flex:1;margin-bottom:0}
.side-panels .calc-panel{flex:1;margin-bottom:0}

/* 分页 */
.pagination{display:flex;gap:6px;align-items:center;justify-content:center;padding:12px 0;flex-wrap:wrap}
.page-btn{padding:6px 12px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:12px;cursor:pointer;transition:all .2s;font-weight:500}
.page-btn:hover{border-color:var(--border-hi);color:var(--text)}
.page-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.page-info{font-size:11px;color:var(--text3);margin:0 8px}

/* 排序栏 */
.sort-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.sort-lbl{font-size:11px;color:var(--text3);font-weight:500;letter-spacing:.03em;text-transform:uppercase}
.sort-btn{padding:4px 10px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:11px;cursor:pointer;transition:all .2s;font-weight:500}
.sort-btn:hover{border-color:var(--border-hi);color:var(--text)}
.sort-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}

/* 标签筛选 */
.tag-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.tag-lbl{font-size:11px;color:var(--text3);font-weight:500;letter-spacing:.03em;text-transform:uppercase}
.tag-btn{padding:3px 8px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:10px;cursor:pointer;transition:all .2s;font-weight:500}
.tag-btn:hover{border-color:var(--border-hi);color:var(--text)}
.tag-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}

/* 家族筛选 */
.family-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.family-lbl{font-size:11px;color:var(--text3);font-weight:500;letter-spacing:.03em;text-transform:uppercase}
.family-btn{padding:3px 8px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:10px;cursor:pointer;transition:all .2s;font-weight:500}
.family-btn:hover{border-color:var(--border-hi);color:var(--text)}
.family-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}
.family-cnt{background:rgba(255,255,255,.12);border-radius:4px;padding:0 4px;font-size:8px;font-weight:600;margin-left:2px}
.family-btn:not(.active) .family-cnt{background:rgba(255,255,255,.06)}

/* 上下文筛选 */
.ctx-filter-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.ctx-lbl{font-size:11px;color:var(--text3);font-weight:500;letter-spacing:.03em;text-transform:uppercase}
.ctx-btn{padding:3px 8px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:10px;cursor:pointer;transition:all .2s;font-weight:500}
.ctx-btn:hover{border-color:var(--border-hi);color:var(--text)}
.ctx-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}

/* 价格区间筛选 */
.price-range-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.pr-lbl{font-size:11px;color:var(--text3);font-weight:500;letter-spacing:.03em;text-transform:uppercase}
.pr-sep{color:var(--text3)}
.pr-unit{font-size:10px;color:var(--text3)}
.price-range-bar input{width:65px;padding:4px 8px;border:1px solid var(--border);border-radius:6px;font-size:11px;background:var(--surface);color:var(--text)}
.pr-btn{padding:4px 8px;border-radius:6px;border:none;background:var(--accent);color:#fff;font-size:10px;cursor:pointer;font-weight:500}
.pr-btn:hover{box-shadow:0 0 12px var(--accent-glow)}
.pr-btn-clear{background:var(--surface2);color:var(--text2);border:1px solid var(--border)}
.pr-btn-clear:hover{border-color:var(--border-hi)}

/* 月费计算器 */
.calc-panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:14px;margin-bottom:14px;backdrop-filter:blur(8px)}
.calc-title{font-size:13px;font-weight:600;color:var(--text);margin-bottom:8px;letter-spacing:-.01em}
.calc-presets{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.calc-preset-lbl{font-size:11px;color:var(--text3);font-weight:500}
.preset-btn{padding:3px 8px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:10px;cursor:pointer;transition:all .2s;font-weight:500}
.preset-btn:hover{border-color:var(--accent);color:var(--accent)}
.calc-row{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.calc-row label{font-size:11px;color:var(--text2);width:90px;font-weight:500}
.calc-row input{flex:1;padding:5px 8px;border:1px solid var(--border);border-radius:6px;font-size:12px;max-width:110px;background:var(--surface2);color:var(--text)}
.calc-btns{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.calc-btn{background:var(--accent);color:#fff;border:none;padding:6px 14px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;transition:all .2s}
.calc-btn:hover{box-shadow:0 0 20px var(--accent-glow)}
.calc-btn-all{background:#0ea5e9}
.calc-btn-all:hover{box-shadow:0 0 20px rgba(14,165,233,.2)}
.calc-btn-rev{background:var(--accent2)}
.calc-btn-rev:hover{box-shadow:0 0 20px rgba(168,85,247,.2)}
.calc-result{margin-top:10px;max-height:350px;overflow-y:auto}
.calc-table-wrap{overflow-x:auto}
.calc-table{width:100%;border-collapse:collapse;font-size:11px}
.calc-table th,.calc-table td{padding:5px 8px;border:1px solid var(--border);text-align:left}
.calc-table th{background:var(--surface2);font-weight:600;color:var(--text2)}
.calc-table tr:nth-child(even){background:rgba(255,255,255,.02)}

/* 模型对比 */
.cmp-panel{background:var(--surface);border:1px solid rgba(99,102,241,.15);border-radius:var(--radius-lg);padding:12px;margin-bottom:10px;backdrop-filter:blur(8px)}
.cmp-title{font-size:13px;font-weight:600;color:var(--accent);margin-bottom:6px}
.cmp-list{margin-bottom:8px}
.cmp-item{display:flex;align-items:center;gap:6px;padding:5px 8px;background:var(--surface2);border-radius:6px;margin-bottom:3px;border:1px solid var(--border)}
.cmp-item-name{flex:1;font-size:12px;font-weight:500;color:var(--text)}
.cmp-item-price{font-size:11px;color:var(--accent);font-weight:600}
.cmp-item-del{background:rgba(239,68,68,.1);color:#f87171;border:none;width:18px;height:18px;border-radius:50%;cursor:pointer;font-size:12px;line-height:1}
.cmp-actions{display:flex;gap:6px}
.cmp-btn{padding:5px 12px;border-radius:6px;border:none;font-size:11px;font-weight:600;cursor:pointer;background:var(--accent);color:#fff;transition:all .2s}
.cmp-btn:hover{box-shadow:0 0 16px var(--accent-glow)}
.cmp-btn-clear{background:var(--surface2);color:var(--text2);border:1px solid var(--border)}
.cmp-btn-clear:hover{border-color:var(--border-hi)}
.cmp-modal{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;z-index:9999}
.cmp-modal-content{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);max-width:800px;width:90%;max-height:80vh;overflow:auto;box-shadow:0 24px 80px rgba(0,0,0,.5)}
.cmp-modal-header{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid var(--border);font-size:14px;font-weight:600}
.cmp-close{background:none;border:none;font-size:20px;cursor:pointer;color:var(--text2)}
.cmp-close:hover{color:var(--text)}
.cmp-modal-body{padding:18px}
.cmp-table{width:100%;border-collapse:collapse;font-size:12px}
.cmp-table th,.cmp-table td{padding:8px 10px;border:1px solid var(--border);text-align:left}
.cmp-table th{background:var(--surface2);font-weight:600;color:var(--text2)}

/* 卡片操作 */
.cb-wrap{display:flex;align-items:center;gap:3px}
.cb-lbl{font-size:9px;color:var(--accent);cursor:pointer;font-weight:500}
.mc-cb{width:12px;height:12px;cursor:pointer;accent-color:var(--accent)}

/* 智能推荐 */
.rec-panel{background:var(--surface);border:1px solid rgba(99,102,241,.12);border-radius:var(--radius-lg);padding:14px;margin-bottom:14px;backdrop-filter:blur(8px)}
.rec-title{font-size:13px;font-weight:600;color:var(--accent);margin-bottom:3px}
.rec-desc{font-size:11px;color:var(--text2);margin-bottom:8px}
.rec-options{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.rec-btn{padding:6px 12px;border-radius:8px;border:1px solid rgba(99,102,241,.2);background:var(--surface);color:var(--accent);font-size:11px;cursor:pointer;transition:all .2s;font-weight:500}
.rec-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 16px var(--accent-glow)}
.rec-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 16px var(--accent-glow)}
.rec-result{margin-top:6px}
.rec-card{display:flex;align-items:center;gap:8px;padding:7px 10px;background:var(--surface2);border-radius:8px;margin-bottom:4px;border:1px solid var(--border)}
.rec-rank{width:22px;height:22px;border-radius:6px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0}
.rec-info{flex:1}
.rec-info .ri-name{font-size:12px;font-weight:600;color:var(--text)}
.rec-info .ri-reason{font-size:10px;color:var(--text2)}
.rec-price{font-size:11px;font-weight:600;color:var(--accent)}

/* 跨平台比价 */
.cross-panel{background:var(--surface);border:1px solid rgba(34,197,94,.12);border-radius:var(--radius-lg);padding:14px;margin-bottom:14px;backdrop-filter:blur(8px)}
.cross-title{font-size:13px;font-weight:600;color:#4ade80;margin-bottom:6px}
.cross-list{max-height:280px;overflow-y:auto}
.cross-group{margin-bottom:6px}
.cross-group-name{font-size:12px;font-weight:600;color:var(--text);margin-bottom:3px}
.cross-item{display:flex;align-items:center;gap:6px;padding:3px 8px;background:var(--surface2);border-radius:4px;margin-bottom:2px;font-size:11px;border:1px solid var(--border)}
.cross-platform{color:var(--text2);min-width:80px}
.cross-price{font-weight:600;color:#4ade80}
.cross-best{background:rgba(34,197,94,.1);border-radius:3px;padding:1px 5px;font-size:9px;color:#4ade80;font-weight:600}

/* 价格变动提示 */
.price-change-note{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.15);border-radius:var(--radius);padding:7px 12px;margin-bottom:10px;font-size:11px;color:#fbbf24;text-align:center;backdrop-filter:blur(8px)}
.price-change-note strong{color:#f59e0b}

/* 工具栏 */
.toolbar{display:flex;gap:6px;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap}
.toolbar-left{display:flex;gap:6px;align-items:center}
.toolbar-right{display:flex;gap:6px;align-items:center}
.tool-btn{padding:5px 10px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:11px;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:4px;font-weight:500}
.tool-btn:hover{border-color:var(--border-hi);color:var(--text)}
.tool-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}

/* 筛选结果计数 */
.filter-count{font-size:11px;color:var(--text2);padding:3px 0;margin-bottom:6px;font-weight:500}
.filter-count strong{color:var(--accent);font-weight:600}

/* 货币切换 */
.cur-switch{display:flex;align-items:center;gap:5px}
.cur-btn{padding:3px 8px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:10px;cursor:pointer;transition:all .2s;font-weight:500}
.cur-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}

/* Light mode overrides */
body.light .snote{background:#fffbeb;border-color:#fde68a;color:#92400e}
body.light .snote strong{color:#d97706}
body.light .mc:hover{box-shadow:0 4px 20px rgba(0,0,0,.08),0 0 30px var(--accent-glow)}
body.light .mc::after{background:linear-gradient(90deg,transparent,rgba(0,0,0,.02),transparent)}
body.light .calc-table tr:nth-child(even){background:rgba(0,0,0,.02)}
body.light .tg-other{border:none}
body.light .cmp-modal{background:rgba(0,0,0,.3)}
body.light .cmp-modal-content{box-shadow:0 24px 80px rgba(0,0,0,.15)}

/* Toast 提示 */
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);padding:10px 20px;border-radius:10px;font-size:12px;font-weight:500;z-index:9999;pointer-events:none;opacity:0;transition:all .3s cubic-bezier(.4,0,.2,1);white-space:nowrap;max-width:90vw;overflow:hidden;text-overflow:ellipsis;letter-spacing:.01em;backdrop-filter:blur(12px)}
.toast-show{opacity:1!important;transform:translateX(-50%) translateY(0)!important}
.toast-ok{background:rgba(34,197,94,.15);color:#4ade80;border:1px solid rgba(34,197,94,.25);box-shadow:0 4px 24px rgba(34,197,94,.1)}
.toast-err{background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.25)}
body.light .toast-ok{background:rgba(22,163,74,.1);color:#16a34a;border-color:rgba(22,163,74,.2)}
body.light .toast-err{background:rgba(220,38,38,.1);color:#dc2626;border-color:rgba(220,38,38,.2)}

/* Base URL 显示 */
.base-url{font-size:9px;color:var(--text3);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:"SF Mono",Monaco,"Cascadia Code",monospace;letter-spacing:0;opacity:.7;transition:opacity .2s}
.mc:hover .base-url{opacity:1}

/* 代码片段模态框 */
.code-modal{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;z-index:9998;opacity:0;pointer-events:none;transition:opacity .25s}
.code-modal.show{opacity:1;pointer-events:auto}
.code-modal-content{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);max-width:680px;width:92%;max-height:85vh;overflow:auto;box-shadow:0 24px 80px rgba(0,0,0,.5);transform:translateY(20px);transition:transform .25s}
.code-modal.show .code-modal-content{transform:translateY(0)}
.code-modal-header{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid var(--border)}
.code-modal-title{font-size:14px;font-weight:600;color:var(--text);display:flex;align-items:center;gap:8px}
.code-modal-title .cm-model{color:var(--accent);font-weight:700}
.code-modal-close{background:none;border:none;font-size:20px;cursor:pointer;color:var(--text2);padding:4px 8px;border-radius:6px;transition:all .15s}
.code-modal-close:hover{color:var(--text);background:var(--surface2)}
.code-modal-body{padding:16px 18px}
.code-tabs{display:flex;gap:4px;margin-bottom:12px;flex-wrap:wrap}
.code-tab{padding:6px 14px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:12px;cursor:pointer;transition:all .2s;font-weight:500;font-family:"SF Mono",Monaco,"Cascadia Code",monospace}
.code-tab:hover{border-color:var(--border-hi);color:var(--text)}
.code-tab.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}
.code-block{position:relative;background:var(--surface2);border:1px solid var(--border);border-radius:8px;overflow:hidden}
.code-block pre{margin:0;padding:14px 16px;overflow-x:auto;font-size:12px;line-height:1.6;font-family:"SF Mono",Monaco,"Cascadia Code",monospace;color:var(--text);white-space:pre;tab-size:2}
.code-copy-btn{position:absolute;top:8px;right:8px;padding:4px 10px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:10px;cursor:pointer;transition:all .15s;font-weight:500;z-index:1}
.code-copy-btn:hover{border-color:var(--accent);color:var(--accent)}
.code-copy-btn.copied{background:rgba(34,197,94,.15);color:#4ade80;border-color:rgba(34,197,94,.3)}
.code-info{margin-top:12px;padding:10px 14px;background:rgba(99,102,241,.06);border:1px solid rgba(99,102,241,.12);border-radius:8px;font-size:11px;color:var(--text2);line-height:1.6}
.code-info strong{color:var(--accent)}
.code-info code{background:var(--surface2);padding:1px 5px;border-radius:3px;font-family:"SF Mono",Monaco,"Cascadia Code",monospace;font-size:10px;color:var(--text)}

/* 导出按钮 */
.export-dropdown{position:relative;display:inline-block}
.export-menu{position:absolute;top:100%;right:0;margin-top:4px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:4px 0;min-width:120px;box-shadow:0 8px 32px rgba(0,0,0,.3);z-index:100;display:none}
.export-menu.show{display:block}
.export-menu-item{display:block;width:100%;padding:6px 14px;border:none;background:none;color:var(--text2);font-size:11px;cursor:pointer;text-align:left;transition:all .15s;font-weight:500}
.export-menu-item:hover{background:var(--surface2);color:var(--text)}

/* ═══════════════════════════════════════════════════════════
   移动端适配
   ═══════════════════════════════════════════════════════════ */
@media(max-width:768px){
/* 整体布局 */
.wrap{padding:0 10px 30px}
.hdr{padding:20px 8px 12px}
.hdr h1{font-size:20px;margin-bottom:4px}
.hdr p{font-size:10px;line-height:1.4}
.brow{gap:4px;margin-top:8px}
.bd{padding:2px 7px;font-size:9px;border-radius:16px}

/* 筛选栏 - 横向滚动，不换行 */
.pbar,.ptbar,.sbar,.sort-bar,.tag-bar,.ctx-filter-bar,.price-range-bar,.family-bar{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;padding:6px 0;gap:4px}
.side-panels{flex-direction:column}
.fg{padding:8px 10px}
.pbar::-webkit-scrollbar,.ptbar::-webkit-scrollbar,.sbar::-webkit-scrollbar{display:none}
.pt{padding:5px 10px;font-size:10px;border-radius:16px;flex-shrink:0}
.pc{font-size:8px;padding:1px 4px}
.pt-filter{padding:4px 9px;font-size:10px;border-radius:12px;flex-shrink:0}
.sc{padding:3px 8px;font-size:10px;border-radius:8px;flex-shrink:0}
.sort-btn{padding:3px 8px;font-size:10px;flex-shrink:0}
.sort-lbl,.tag-lbl,.ctx-lbl,.pr-lbl,.calc-preset-lbl{font-size:10px;flex-shrink:0}
.tag-btn{padding:2px 6px;font-size:9px;flex-shrink:0}
.ctx-btn{padding:2px 6px;font-size:9px;flex-shrink:0}
.family-btn{padding:2px 6px;font-size:9px;flex-shrink:0}
.family-lbl{font-size:10px;flex-shrink:0}

/* 搜索框 */
.srow input{padding:9px 12px 9px 32px;font-size:14px;border-radius:8px}
.srow::before{left:10px;font-size:15px}

/* 网格 - 单列 */
.grid{grid-template-columns:1fr;gap:6px}

/* 卡片 - 紧凑 */
.mc{padding:10px 12px;border-radius:10px}
.mname{font-size:12px;margin-bottom:4px}
.prov{font-size:8px;margin-bottom:2px}
.tags{gap:2px;margin-bottom:5px}
.tg{font-size:8px;padding:1px 5px;border-radius:4px}
.prow{margin-bottom:2px;min-height:18px}
.price-badge{font-size:10px;padding:1px 6px;border-radius:6px}
.ctx-row{gap:4px;margin-bottom:2px}
.ctx{font-size:9px}
.ctx-bar-wrap{height:2px}
.base-url{font-size:8px;margin-top:1px}
.hint{font-size:9px;margin-top:3px}
.dot{width:5px;height:5px;top:10px;right:10px}
.fav-btn{font-size:12px}
.cb-lbl{font-size:8px}
.mc-cb{width:10px;height:10px}
.card-actions{margin-top:2px}

/* 工具栏 */
.toolbar{gap:4px;margin-bottom:8px}
.tool-btn{padding:4px 8px;font-size:10px;gap:3px}
.cur-switch{gap:3px}
.cur-btn{padding:2px 6px;font-size:9px}
.filter-count{font-size:10px;padding:2px 0;margin-bottom:4px}

/* 面板 - 紧凑 */
.calc-panel,.cmp-panel,.rec-panel,.cross-panel{padding:10px;border-radius:10px;margin-bottom:10px}
.calc-title,.cmp-title,.rec-title,.cross-title{font-size:12px;margin-bottom:6px}
.calc-row{gap:6px;margin-bottom:5px}
.calc-row label{font-size:10px;width:70px}
.calc-row input{padding:4px 6px;font-size:11px;max-width:90px}
.calc-btns{gap:4px}
.calc-btn{padding:5px 10px;font-size:11px}
.calc-presets{gap:3px;margin-bottom:6px}
.preset-btn{padding:2px 6px;font-size:9px}
.calc-result{max-height:250px;margin-top:6px}
.calc-table{font-size:10px}
.calc-table th,.calc-table td{padding:3px 5px}
.cmp-item{padding:4px 6px;gap:4px}
.cmp-item-name{font-size:11px}
.cmp-item-price{font-size:10px}
.cmp-btn{padding:4px 10px;font-size:10px}
.cmp-btn-clear{padding:4px 10px;font-size:10px}
.rec-btn{padding:5px 10px;font-size:10px}
.rec-card{padding:5px 8px;gap:6px}
.rec-rank{width:18px;height:18px;font-size:9px;border-radius:4px}
.rec-info .ri-name{font-size:11px}
.rec-info .ri-reason{font-size:9px}
.rec-price{font-size:10px}
.cross-list{max-height:200px}
.cross-group-name{font-size:11px}
.cross-item{padding:2px 6px;font-size:10px}
.cross-platform{min-width:60px}
.cross-best{font-size:8px;padding:0 4px}

/* 价格区间 */
.price-range-bar input{width:55px;padding:3px 5px;font-size:10px}
.pr-btn{padding:3px 6px;font-size:9px}
.pr-btn-clear{padding:3px 6px;font-size:9px}

/* 弹窗 */
.cmp-modal-content{width:95%;max-height:90vh;border-radius:12px}
.cmp-modal-header{padding:10px 14px;font-size:13px}
.cmp-modal-body{padding:12px}
.cmp-table{font-size:10px}
.cmp-table th,.cmp-table td{padding:5px 6px}
.cmp-close{font-size:18px}

/* 代码片段模态框移动端 */
.code-modal-content{width:95%;max-height:90vh;border-radius:12px}
.code-modal-header{padding:10px 14px}
.code-modal-title{font-size:13px}
.code-modal-body{padding:12px 14px}
.code-tab{padding:5px 10px;font-size:11px}
.code-block pre{padding:10px 12px;font-size:11px;line-height:1.5}
.code-copy-btn{padding:3px 8px;font-size:9px}
.code-info{padding:8px 10px;font-size:10px}

/* Toast */
#toast{bottom:16px;padding:8px 14px;font-size:11px;border-radius:8px;max-width:85vw}

/* 页脚 */
.ftr{padding:16px 8px;margin-top:20px}
.ftr p{font-size:10px;line-height:1.8}

/* 数据说明 */
.snote{padding:8px 10px;margin:8px 0 12px;font-size:10px;border-radius:8px}
.price-change-note{padding:6px 10px;margin-bottom:8px;font-size:10px;border-radius:6px}
}

/* 超小屏幕 (<400px) 进一步压缩 */
@media(max-width:400px){
.hdr h1{font-size:18px}
.hdr p{font-size:9px}
.pt{padding:4px 8px;font-size:9px}
.pt-filter{padding:3px 7px;font-size:9px}
.sc{padding:2px 6px;font-size:9px}
.mc{padding:8px 10px}
.mname{font-size:11px}
.base-url{font-size:7px}
.calc-row label{width:60px;font-size:9px}
}
'''

# ═══════════════════════════════════════════════════════════
# JavaScript (完整前端逻辑)
# ═══════════════════════════════════════════════════════════

JS = r'''
var curP='all',curS='all',curPT='all',curSort='default',selModels=[];
var curTags=[],curCtx='all',curCur='CNY',priceMin=null,priceMax=null;
var curFamily='all';
var isDark=localStorage.getItem('dark')!=='0';
var isListView=localStorage.getItem('listView')==='1';
var favs=JSON.parse(localStorage.getItem('favs')||'[]');
var USD_TO_CNY=7.25;

// 初始化
document.addEventListener('DOMContentLoaded',function(){
if(!isDark)document.body.classList.add('light');
if(isListView){document.getElementById('grid').classList.add('list-view');document.getElementById('listBtn').classList.add('active');}
// 恢复收藏
favs.forEach(function(f){var c=findCardByName(f);if(c){c.classList.add('fav-card');var fb=c.querySelector('.fav-btn');if(fb)fb.classList.add('active');}});
// 加载动画
var ld=document.getElementById('ld');ld.classList.add('show');
setTimeout(function(){ld.classList.remove('show')},600);
// 平台筛选
document.querySelectorAll('.pt').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.pt').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curP=b.dataset.p;filter();saveState();});});
// 价格分级筛选
document.querySelectorAll('.pt-filter').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.pt-filter').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curPT=b.dataset.pt;filter();saveState();});});
// 场景筛选
document.querySelectorAll('.sc').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.sc').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curS=b.dataset.sc;filter();saveState();});});
// 排序
document.querySelectorAll('.sort-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.sort-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curSort=b.dataset.sort;sortCards();});});
// 标签筛选
document.querySelectorAll('.tag-btn').forEach(function(b){b.addEventListener('click',function(){
b.classList.toggle('active');
curTags=Array.from(document.querySelectorAll('.tag-btn.active')).map(function(x){return x.dataset.tag;});
filter();saveState();});});
// 上下文筛选
document.querySelectorAll('.ctx-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.ctx-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curCtx=b.dataset.ctx;filter();saveState();});});
// 家族筛选
document.querySelectorAll('.family-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.family-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curFamily=b.dataset.family;filter();saveState();});});
// 货币切换
document.querySelectorAll('.cur-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.cur-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curCur=b.dataset.cur;updatePrices();});});
// 搜索
var st;
document.getElementById('si').addEventListener('input',function(){clearTimeout(st);st=setTimeout(function(){filter();saveState();},200)});
// 预设按钮
document.querySelectorAll('.preset-btn').forEach(function(b){b.addEventListener('click',function(){
document.getElementById('calcChats').value=b.dataset.chats;
document.getElementById('calcTokens').value=b.dataset.tokens;
document.getElementById('calcRatio').value=b.dataset.ratio;});});
// 智能推荐
document.querySelectorAll('.rec-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.rec-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');runRecommend(b.dataset.rec);});});
// 键盘快捷键
document.addEventListener('keydown',function(e){
if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();document.getElementById('si').focus()}
if(e.key==='Escape'){
// 先关闭代码模态框，再清空搜索
var cm=document.getElementById('codeModal');
if(cm&&cm.classList.contains('show')){closeCodeModal();return;}
document.getElementById('si').blur();document.getElementById('si').value='';filter();
}
if(e.key==='d'&&!e.ctrlKey&&document.activeElement.tagName!=='INPUT'){toggleDark();}
if(e.key==='v'&&!e.ctrlKey&&document.activeElement.tagName!=='INPUT'){toggleView();}
// 数字键1-9快速切换平台
var platforms=['all','openrouter','aliyun','siliconflow','moonshot','zhipu','volcengine','baidu','tencent'];
var num=parseInt(e.key);
if(num>=1&&num<=9&&document.activeElement.tagName!=='INPUT'){
var pb=document.querySelector('.pt[data-p="'+platforms[num-1]+'"]');
if(pb)pb.click();
}
});
// 从URL hash恢复状态
restoreState();
// 点击其他区域关闭导出菜单
document.addEventListener('click',function(e){
if(!e.target.closest('.export-dropdown'))closeExportMenu();
});
// 初始筛选
filter();
// 生成跨平台比价
buildCrossPrice();
});

function findCardByName(name){
var cards=document.querySelectorAll('.mc');
for(var i=0;i<cards.length;i++){
var mn=(cards[i].querySelector('.mname')||{}).textContent||'';
if(mn===name)return cards[i];
}return null;
}

// ─── 高级搜索语法解析 ───
function parseAdvancedSearch(q){
var result={text:'',priceMin:null,priceMax:null,ctxMin:null,ctxMax:null,family:null,platform:null};
if(!q)return result;
var parts=q.split(/\s+/);
var textParts=[];
parts.forEach(function(p){
// price<1 或 price>5 或 price=2
var priceMatch=p.match(/^price\s*([<>=])\s*([\d.]+)$/i);
if(priceMatch){
var op=priceMatch[1],val=parseFloat(priceMatch[2]);
if(op==='<')result.priceMax=val;
else if(op==='>')result.priceMin=val;
else if(op==='='){result.priceMin=val;result.priceMax=val;}
return;
}
// ctx>128 或 ctx<32 或 ctx=64
var ctxMatch=p.match(/^ctx\s*([<>=])\s*(\d+)$/i);
if(ctxMatch){
var op=ctxMatch[1],val=parseInt(ctxMatch[2]);
if(op==='<')result.ctxMax=val;
else if(op==='>')result.ctxMin=val;
else if(op==='='){result.ctxMin=val;result.ctxMax=val;}
return;
}
// family:GPT
var famMatch=p.match(/^family[:=]\s*(\S+)$/i);
if(famMatch){result.family=famMatch[1];return;}
// platform:aliyun
var platMatch=p.match(/^platform[:=]\s*(\S+)$/i);
if(platMatch){result.platform=platMatch[1].toLowerCase();return;}
textParts.push(p);
});
result.text=textParts.join(' ');
return result;
}

// ─── 筛选 ───
function filter(){
var cs=document.querySelectorAll('.mc');
var q=(document.getElementById('si').value||'').toLowerCase().trim();
var n=0;
cs.forEach(function(c){
var sh=true;
var pn=(c.querySelector('.prov')||{}).textContent||'';
var mn=(c.querySelector('.mname')||{}).textContent||'';
if(curP!='all'&&curP!==(c.dataset.p||''))sh=false;
if(curPT!='all'&&curPT!==(c.dataset.pt||''))sh=false;
if(curS!='all'&&curS!==(c.dataset.s||''))sh=false;
// 标签筛选
if(curTags.length>0){
var cardTags=Array.from(c.querySelectorAll('.tg')).map(function(t){return t.textContent;});
var match=curTags.some(function(t){return cardTags.indexOf(t)!==-1;});
if(!match)sh=false;
}
// 上下文筛选
if(curCtx!=='all'){
var ctxVal=parseInt(c.dataset.ctx||0);
var ctxMin=parseInt(curCtx)*1000;
if(ctxVal<ctxMin)sh=false;
}
// 家族筛选
if(curFamily!=='all'){
var fam=c.dataset.family||'';
if(fam!==curFamily)sh=false;
}
// 价格区间筛选
if(priceMin!==null||priceMax!==null){
var inp=parseFloat(c.dataset.inp||0);
var cur=c.dataset.cur||'CNY';
var cnyInp=cur==='USD'?inp*1e6*USD_TO_CNY:inp;
if(priceMin!==null&&cnyInp<priceMin)sh=false;
if(priceMax!==null&&cnyInp>priceMax)sh=false;
}
// 搜索 (支持高级语法)
if(q){
var adv=parseAdvancedSearch(q);
// 文本匹配
if(adv.text&&mn.toLowerCase().indexOf(adv.text)===-1&&pn.toLowerCase().indexOf(adv.text)===-1)sh=false;
// 高级价格筛选
if(adv.priceMin!==null){
var cInp=cur==='USD'?inp*1e6*USD_TO_CNY:inp;
if(cInp<adv.priceMin)sh=false;
}
if(adv.priceMax!==null){
var cInp2=cur==='USD'?inp*1e6*USD_TO_CNY:inp;
if(cInp2>adv.priceMax)sh=false;
}
// 高级上下文筛选
if(adv.ctxMin!==null){
var ctxK=parseInt(c.dataset.ctx||0)/1000;
if(ctxK<adv.ctxMin)sh=false;
}
if(adv.ctxMax!==null){
var ctxK2=parseInt(c.dataset.ctx||0)/1000;
if(ctxK2>adv.ctxMax)sh=false;
}
// 高级家族筛选
if(adv.family){
var fam2=(c.dataset.family||'').toLowerCase();
if(fam2!==adv.family.toLowerCase())sh=false;
}
// 高级平台筛选
if(adv.platform){
if((c.dataset.p||'')!==adv.platform)sh=false;
}
}
c.setAttribute('data-visible',sh?'1':'0');
c.style.display=sh?'':'none';if(sh)n++;
});
document.getElementById('empty').style.display=n===0?'block':'none';
// 更新筛选计数
totalFiltered=n;
currentPage=1;
// Apply pagination based on data-visible
var visIdx=0;
cs.forEach(function(c){
    if(c.getAttribute('data-visible')==='1'){
        var page=Math.floor(visIdx/PAGE_SIZE)+1;
        c.style.display=(page===currentPage)?'':'none';
        visIdx++;
    }
});
var fc=document.getElementById('filterCount');
if(fc)fc.innerHTML='显示 <strong>'+n+'</strong> / '+cs.length+' 个模型';
renderPagination();
}

// ─── 分页 ───
var PAGE_SIZE=60;
var currentPage=1;
var totalFiltered=0;

function renderPagination(){
    var totalPages=Math.ceil(totalFiltered/PAGE_SIZE)||1;
    if(currentPage>totalPages)currentPage=totalPages;
    var pg=document.getElementById('pagination');
    if(!pg)return;
    if(totalPages<=1){pg.innerHTML='';return;}
    var h='';
    h+='<button class="page-btn" onclick="goPage(1)"'+(currentPage===1?' disabled':'')+'>&laquo; 首页</button>';
    h+='<button class="page-btn" onclick="goPage('+(currentPage-1)+')"'+(currentPage===1?' disabled':'')+'>&lsaquo; 上一页</button>';
    var start=Math.max(1,currentPage-3);
    var end=Math.min(totalPages,currentPage+3);
    if(start>1)h+='<span class="page-info">...</span>';
    for(var i=start;i<=end;i++){
        h+='<button class="page-btn'+(i===currentPage?' active':'')+'" onclick="goPage('+i+')">'+i+'</button>';
    }
    if(end<totalPages)h+='<span class="page-info">...</span>';
    h+='<button class="page-btn" onclick="goPage('+(currentPage+1)+')"'+(currentPage===totalPages?' disabled':'')+'>下一页 &rsaquo;</button>';
    h+='<button class="page-btn" onclick="goPage('+totalPages+')"'+(currentPage===totalPages?' disabled':'')+'>末页 &raquo;</button>';
    h+='<span class="page-info">第 '+currentPage+' / '+totalPages+' 页 (共 '+totalFiltered+' 个)</span>';
    pg.innerHTML=h;
}

function goPage(p){
    var totalPages=Math.ceil(totalFiltered/PAGE_SIZE)||1;
    if(p<1)p=1;if(p>totalPages)p=totalPages;
    currentPage=p;
    applyPage();
    renderPagination();
    document.querySelector('.grid').scrollIntoView({behavior:'smooth',block:'start'});
}

function applyPage(){
    var cards=document.querySelectorAll('.mc');
    var vis=0;
    cards.forEach(function(c){
        if(c.getAttribute('data-visible')==='1'){
            var page=Math.floor(vis/PAGE_SIZE)+1;
            var show=(page===currentPage);
            c.style.display=show?'':'none';
            vis++;
        }
    });
}

// ─── 排序 ───
function sortCards(){
var grid=document.getElementById('grid');
var cs=Array.from(grid.querySelectorAll('.mc'));
var sortFn={
'default':function(){return 0},
'inp-asc':function(a,b){return (parseFloat(a.dataset.inp)||0)-(parseFloat(b.dataset.inp)||0)},
'inp-desc':function(a,b){return (parseFloat(b.dataset.inp)||0)-(parseFloat(a.dataset.inp)||0)},
'out-asc':function(a,b){return (parseFloat(a.dataset.out)||0)-(parseFloat(b.dataset.out)||0)},
'out-desc':function(a,b){return (parseFloat(b.dataset.out)||0)-(parseFloat(b.dataset.out)||0)},
'name':function(a,b){return (a.querySelector('.mname')||{}).textContent.localeCompare((b.querySelector('.mname')||{}).textContent)},
'combined':function(a,b){
var ai=parseFloat(a.dataset.inp)||0,ao=parseFloat(a.dataset.out)||0;
var bi=parseFloat(b.dataset.inp)||0,bo=parseFloat(b.dataset.out)||0;
return (ai+ao*0.5)-(bi+bo*0.5);
},
'ctx':function(a,b){return (parseInt(b.dataset.ctx)||0)-(parseInt(a.dataset.ctx)||0)},
'costperf':function(a,b){
// 性价比 = 上下文长度 / (输入价+输出价*0.5)，越大越好
var ai=parseFloat(a.dataset.inp)||0,ao=parseFloat(a.dataset.out)||0,ac2=parseInt(a.dataset.ctx)||1;
var bi=parseFloat(b.dataset.inp)||0,bo=parseFloat(b.dataset.out)||0,bc2=parseInt(b.dataset.ctx)||1;
var pa=(ai+ao*0.5)||0.001,pb=(bi+bo*0.5)||0.001;
return (bc2/pb)-(ac2/pa);
}
};
cs.sort(sortFn[curSort]||sortFn['default']);
cs.forEach(function(c){grid.appendChild(c)});
filter();
// Re-apply pagination after sort
applyPage();
renderPagination();
}

// ─── 货币切换 ───
function updatePrices(){
document.querySelectorAll('.mc').forEach(function(c){
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var prow=c.querySelector('.prow');
if(!prow)return;
if(curCur==='CNY'){
if(cur==='USD'){
var cnyInp=inp*1e6*USD_TO_CNY;
var cnyOut=out*1e6*USD_TO_CNY;
prow.innerHTML=makeCNYBadge(cnyInp,cnyOut);
}else{
prow.innerHTML=makeCNYBadge(inp,out);
}
}else{
if(cur==='CNY'){
var usdInp=inp/USD_TO_CNY;
var usdOut=out/USD_TO_CNY;
prow.innerHTML=makeUSDBadge(usdInp,usdOut);
}else{
prow.innerHTML=makeUSDBadge(inp*1e6,out*1e6);
}
}
});
}
function makeCNYBadge(inp,out){
if(inp===0&&out===0)return '<span class="price-badge price-free">免费额度</span>';
if(Math.abs(inp-out)<0.01){
var c=inp<1?"price-cheap":inp<10?"price-mid":inp<100?"price-high":"price-ultra";
return '<span class="price-badge '+c+'">¥'+inp.toFixed(2)+'/M</span>';
}
return '<span class="price-badge price-mid">IN:¥'+inp.toFixed(2)+' OUT:¥'+out.toFixed(2)+'/M</span>';
}
function makeUSDBadge(inp,out){
if(inp===0&&out===0)return '<span class="price-badge price-free">$0 (免费)</span>';
if(Math.abs(inp-out)<0.01){
var c=inp<0.1?"price-free":inp<1?"price-cheap":inp<10?"price-mid":inp<100?"price-high":"price-ultra";
return '<span class="price-badge '+c+'">$'+inp.toFixed(2)+'/1M</span>';
}
return '<span class="price-badge price-mid">IN:$'+inp.toFixed(2)+' OUT:$'+out.toFixed(2)+'/1M</span>';
}

// ─── 收藏 ───
function toggleFav(btn){
btn.classList.toggle('active');
var c=btn.closest('.mc');
c.classList.toggle('fav-card');
var mn=(c.querySelector('.mname')||{}).textContent||'';
if(btn.classList.contains('active')){
if(favs.indexOf(mn)===-1)favs.push(mn);
}else{
var idx=favs.indexOf(mn);if(idx!==-1)favs.splice(idx,1);
}
localStorage.setItem('favs',JSON.stringify(favs));
}

// ─── 暗色模式 ───
function toggleDark(){
isDark=!isDark;
document.body.classList.toggle('light');
localStorage.setItem('dark',isDark?'1':'0');
}

// ─── 视图切换 ───
function toggleView(){
isListView=!isListView;
document.getElementById('grid').classList.toggle('list-view');
document.getElementById('listBtn').classList.toggle('active');
localStorage.setItem('listView',isListView?'1':'0');
}

// ─── 价格区间 ───
function applyPriceRange(){
priceMin=parseFloat(document.getElementById('priceMin').value)||null;
priceMax=parseFloat(document.getElementById('priceMax').value)||null;
filter();
}
function clearPriceRange(){
priceMin=null;priceMax=null;
document.getElementById('priceMin').value='';
document.getElementById('priceMax').value='';
filter();
}

// ─── 模型对比 ───
function toggleSel(cb){
var c=cb.closest('.mc');
var mName=(c.querySelector('.mname')||{}).textContent||'';
var prov=(c.querySelector('.prov')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var ctx=c.dataset.ctxDisplay||'';
var cmd=c.getAttribute('onclick')||'';
var mIdx=selModels.findIndex(function(m){return m.name===mName});
if(cb.checked){
if(selModels.length>=3){cb.checked=false;alert('最多选择3个模型对比');return}
if(mIdx===-1)selModels.push({name:mName,prov:prov,inp:inp,out:out,cur:cur,ctx:ctx,cmd:cmd});
}else{
if(mIdx!==-1)selModels.splice(mIdx,1);
}
updateCmpPanel();
}
function updateCmpPanel(){
var panel=document.getElementById('cmpPanel');
var list=document.getElementById('cmpList');
var count=document.getElementById('cmpCount');
count.textContent=selModels.length;
if(selModels.length===0){panel.style.display='none';return}
panel.style.display='block';
list.innerHTML=selModels.map(function(m,i){
var price=m.cur==='USD'?'$'+(m.inp*1e6).toFixed(2)+'/M':'¥'+m.inp.toFixed(2)+'/M';
return '<div class="cmp-item"><span class="cmp-item-name">'+m.name+'</span>'
+'<span class="cmp-item-price">'+price+'</span>'
+'<button class="cmp-item-del" onclick="delSel('+i+')">&times;</button></div>';
}).join('');
}
function delSel(i){selModels.splice(i,1);updateCmpPanel();
var cbs=document.querySelectorAll('.mc-cb');cbs.forEach(function(cb){
var c=cb.closest('.mc');var n=(c.querySelector('.mname')||{}).textContent||'';
if(!selModels.find(function(m){return m.name===n}))cb.checked=false;
});}
function clearCmp(){selModels=[];updateCmpPanel();
document.querySelectorAll('.mc-cb').forEach(function(cb){cb.checked=false});}
function showCmp(){
if(selModels.length<2){alert('请至少选择2个模型');return}
var body=document.getElementById('cmpModalBody');
body.innerHTML='<table class="cmp-table"><thead><tr><th>项目</th>'
+selModels.map(function(m){return '<th>'+m.name+'</th>'}).join('')
+'</tr></thead><tbody>'
+'<tr><td>平台</td>'+selModels.map(function(m){return '<td>'+m.prov+'</td>'}).join('')+'</tr>'
+'<tr><td>输入价格</td>'+selModels.map(function(m){
var p=m.cur==='USD'?'$'+(m.inp*1e6).toFixed(4):'¥'+m.inp.toFixed(4);
return '<td>'+p+'/M</td>';
}).join('')+'</tr>'
+'<tr><td>输出价格</td>'+selModels.map(function(m){
var p=m.cur==='USD'?'$'+(m.out*1e6).toFixed(4):'¥'+m.out.toFixed(4);
return '<td>'+p+'/M</td>';
}).join('')+'</tr>'
+'<tr><td>上下文</td>'+selModels.map(function(m){return '<td>'+m.ctx+'</td>'}).join('')+'</tr>'
+'<tr><td>货币</td>'+selModels.map(function(m){return '<td>'+m.cur+'</td>'}).join('')+'</tr>'
+'</tbody></table>';
document.getElementById('cmpModal').style.display='flex';
}
function closeCmpModal(){document.getElementById('cmpModal').style.display='none'}

// ─── 月费计算器 ───
function getCalcParams(){
return {
chats:parseInt(document.getElementById('calcChats').value)||0,
tokens:parseInt(document.getElementById('calcTokens').value)||0,
ratio:parseFloat(document.getElementById('calcRatio').value)||1
};
}
function calcModelCost(m,params){
var inTok=params.chats*params.tokens;
var outTok=inTok*params.ratio;
if(m.cur==="USD"){return (m.inp*inTok+m.out*outTok)*USD_TO_CNY;}
else{return m.inp*inTok/1e6+m.out*outTok/1e6;}
}
function runCalc(){
var params=getCalcParams();
var results=selModels.map(function(m){
return {name:m.name,cost:calcModelCost(m,params),cur:m.cur,inp:m.inp,out:m.out};
});
results.sort(function(a,b){return a.cost-b.cost});
if(results.length===0){
document.getElementById('calcResult').innerHTML='<div style="color:#94a3b8;font-size:13px;padding:10px">请先在上方勾选要计算的模型（最多3个）</div>';
return;
}
renderCalcResult(results,params);
}
function runCalcAll(){
var params=getCalcParams();
var cs=document.querySelectorAll('.mc');
var results=[];
cs.forEach(function(c){
if(c.style.display==='none')return;
var mName=(c.querySelector('.mname')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var m={name:mName,inp:inp,out:out,cur:cur};
var cost=calcModelCost(m,params);
results.push({name:mName,cost:cost,cur:cur,inp:inp,out:out});
});
results.sort(function(a,b){return a.cost-b.cost});
if(results.length===0){
document.getElementById('calcResult').innerHTML='<div style="color:#94a3b8;font-size:13px;padding:10px">没有可计算的模型</div>';
return;
}
renderCalcResult(results.slice(0,30),params);
}
function runCalcReverse(){
var budget=parseFloat(document.getElementById('calcBudget').value)||0;
if(budget<=0){alert('请输入月预算金额');return;}
var params=getCalcParams();
if(params.chats<=0||params.tokens<=0){alert('请先设置对话次数和Token数');return;}
var cs=document.querySelectorAll('.mc');
var results=[];
cs.forEach(function(c){
if(c.style.display==='none')return;
var mName=(c.querySelector('.mname')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var m={name:mName,inp:inp,out:out,cur:cur};
var cost=calcModelCost(m,params);
var maxChats=budget>0&&cost>0?Math.floor(budget/cost*params.chats):0;
results.push({name:mName,cost:cost,maxChats:maxChats,cur:cur});
});
results.sort(function(a,b){return b.maxChats-a.maxChats});
var html='<div class="calc-table-wrap"><table class="calc-table"><thead><tr><th>排名</th><th>模型</th><th>月费(¥)</th><th>预算内最多对话</th></tr></thead><tbody>';
results.slice(0,30).forEach(function(r,i){
var costStr='¥'+r.cost.toFixed(2);
html+='<tr><td>'+(i+1)+'</td><td>'+r.name+'</td><td>'+costStr+'</td><td><b>'+r.maxChats.toLocaleString()+'</b> 次</td></tr>';
});
html+='</tbody></table></div>';
document.getElementById('calcResult').innerHTML=html;
}
function renderCalcResult(results,params){
var html='<div class="calc-table-wrap"><table class="calc-table"><thead><tr><th>排名</th><th>模型</th><th>月费用(¥'+params.chats+'次×'+params.tokens+'T)</th></tr></thead><tbody>';
results.forEach(function(r,i){
var costStr='¥'+r.cost.toFixed(2);
html+='<tr><td>'+(i+1)+'</td><td>'+r.name+'</td><td><b>'+costStr+'</b></td></tr>';
});
html+='</tbody></table></div>';
document.getElementById('calcResult').innerHTML=html;
}

// ─── 智能推荐 ───
function runRecommend(scene){
var cs=document.querySelectorAll('.mc');
var results=[];
cs.forEach(function(c){
var mName=(c.querySelector('.mname')||{}).textContent||'';
var prov=(c.querySelector('.prov')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var scen=c.dataset.s||'';
var ctx=parseInt(c.dataset.ctx)||0;
var tags=Array.from(c.querySelectorAll('.tg')).map(function(t){return t.textContent;});
var score=0;
var reason='';
// 场景匹配评分
if(scene==='chat'){
if(scen==='日常对话')score+=30;
if(tags.indexOf('便宜')!==-1||tags.indexOf('极便宜')!==-1)score+=20;
if(tags.indexOf('免费额度')!==-1)score+=25;
if(inp>0&&inp<1)score+=15;
if(tags.indexOf('视觉')!==-1)score-=10; // 不需要视觉
if(inp>10)score-=20; // 太贵
reason=score>50?'性价比高，适合日常使用':'价格适中';
}else if(scene==='code'){
if(scen==='编程代码')score+=30;
if(tags.indexOf('代码')!==-1)score+=25;
if(tags.indexOf('推理')!==-1)score+=10;
if(ctx>=32000)score+=10;
if(tags.indexOf('视觉')!==-1)score-=5;
reason=tags.indexOf('代码')!==-1?'代码专用模型':'通用模型，可写代码';
}else if(scene==='translate'){
if(scen==='日常对话')score+=25;
if(inp>0&&inp<2)score+=20;
if(tags.indexOf('免费额度')!==-1)score+=25;
if(ctx>=32000)score+=10;
if(tags.indexOf('视觉')!==-1)score-=10;
reason='翻译不需要高级模型，便宜即可';
}else if(scene==='write'){
if(scen==='日常对话')score+=20;
if(scen==='深度推理')score+=15;
if(ctx>=64000)score+=15;
if(inp>0&&inp<5)score+=10;
reason=ctx>=64000?'长上下文，适合长文':'适合一般写作';
}else if(scene==='reason'){
if(scen==='深度推理')score+=30;
if(tags.indexOf('推理')!==-1)score+=25;
if(tags.indexOf('旗舰')!==-1)score+=10;
if(ctx>=128000)score+=10;
reason=tags.indexOf('推理')!==-1?'推理专用模型':'通用模型';
}else if(scene==='vision'){
if(scen==='视觉图片')score+=30;
if(tags.indexOf('视觉')!==-1)score+=25;
if(tags.indexOf('多模态')!==-1)score+=20;
reason='视觉/多模态模型';
}else if(scene==='image'){
if(scen==='图片生成')score+=30;
if(tags.indexOf('图片生成')!==-1)score+=25;
reason='图片生成专用';
}else if(scene==='video'){
if(scen==='视频生成')score+=30;
if(tags.indexOf('视频生成')!==-1)score+=25;
reason='视频生成专用';
}
// 通用加分
if(tags.indexOf('免费额度')!==-1)score+=5;
if(score>0)results.push({name:mName,prov:prov,score:score,inp:inp,out:out,cur:cur,reason:reason});
});
results.sort(function(a,b){return b.score-a.score});
var html='';
results.slice(0,5).forEach(function(r,i){
var price=r.cur==='USD'?'$'+(r.inp*1e6).toFixed(2)+'/M':'¥'+r.inp.toFixed(2)+'/M';
if(r.inp===0&&r.out===0)price='免费';
html+='<div class="rec-card"><div class="rec-rank">'+(i+1)+'</div>'
+'<div class="rec-info"><div class="ri-name">'+r.name+'</div>'
+'<div class="ri-reason">'+r.prov+' · '+r.reason+'</div></div>'
+'<div class="rec-price">'+price+'</div></div>';
});
if(!html)html='<div style="color:#94a3b8;font-size:13px;padding:10px">未找到匹配模型</div>';
document.getElementById('recResult').innerHTML=html;
}

// ─── 跨平台比价 ───
// 精确的模型名标准化：提取模型系列+参数量+版本，用于跨平台匹配
function normalizeModelName(rawName){
var n=rawName;
// 去掉 OPENROUTER: 前缀
n=n.replace(/^OPENROUTER:/i,'');
// 去掉供应商前缀 (如 deepseek-ai/, Qwen/, Pro/ 等)
n=n.split('/').pop();
// 统一大小写用于匹配
var lower=n.toLowerCase();
// 提取模型系列名 + 参数量 + 关键版本标识
// DeepSeek 系列
if(lower.indexOf('deepseek')!==-1){
var v='';
if(/r1/i.test(n))v='R1';
else if(/v3\.2/i.test(n))v='V3.2';
else if(/v3\.1/i.test(n))v='V3.1';
else if(/v3/i.test(n))v='V3';
else if(/ocr/i.test(n))v='OCR';
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var distill=/distill/i.test(n)?'-Distill':'';
var chat=/chat/i.test(n)?'-Chat':'';
return 'DeepSeek-'+v+distill+chat+(sz?'-'+sz:'');
}
// Qwen 系列
if(lower.indexOf('qwen')!==-1||lower.indexOf('qwq')!==-1){
var base=/qwq/i.test(n)?'QwQ':'Qwen';
var ver=(n.match(/(\d+\.\d+|\d+)/)||['',''])[1];
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var vl=/vl/i.test(n)?'-VL':'';
var coder=/coder/i.test(n)?'-Coder':'';
var img=/image/i.test(n)?'-Image':'';
var think=/thinking/i.test(n)?'-Thinking':'';
var omni=/omni/i.test(n)?'-Omni':'';
var emb=/embedding/i.test(n)?'-Embedding':'';
return base+(ver?'-'+ver:'')+vl+coder+img+think+omni+emb+(sz?'-'+sz:'');
}
// GLM 系列
if(lower.indexOf('glm')!==-1){
var ver=(n.match(/glm[-_]?(\d+\.?\d*)/i)||['',''])[1];
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var flash=/flash/i.test(n)?'-Flash':'';
var air=/air/i.test(n)?'-Air':'';
var turbo=/turbo/i.test(n)?'-Turbo':'';
var v=/v/i.test(n)&&/flash|air|turbo/i.test(n)===false?'-V':'';
var z=/z1/i.test(n)?'-Z1':'';
return 'GLM-'+ver+flash+air+turbo+v+z+(sz?'-'+sz:'');
}
// Kimi/Moonshot 系列
if(lower.indexOf('kimi')!==-1||lower.indexOf('moonshot')!==-1){
var v=/k2\.5/i.test(n)?'K2.5':/k2/i.test(n)?'K2':'V1';
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var ctx=(n.match(/(\d+k)/i)||['',''])[1].toLowerCase();
var think=/thinking/i.test(n)?'-Thinking':'';
var turbo=/turbo/i.test(n)?'-Turbo':'';
var vis=/vision/i.test(n)?'-Vision':'';
return 'Kimi-'+v+think+turbo+vis+(ctx?'-'+ctx:'')+(sz?'-'+sz:'');
}
// Doubao/豆包 系列
if(lower.indexOf('doubao')!==-1||lower.indexOf('seed')!==-1){
var v=(n.match(/(seed[-_]?\d+\.\d+|doubao[-_]?\d+\.\d+)/i)||['',''])[1]||'';
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var pro=/pro/i.test(n)?'-Pro':'';
var lite=/lite/i.test(n)?'-Lite':'';
var mini=/mini/i.test(n)?'-Mini':'';
var flash=/flash/i.test(n)?'-Flash':'';
var vis=/vision/i.test(n)?'-Vision':'';
var think=/thinking/i.test(n)?'-Thinking':'';
var coder=/coder/i.test(n)?'-Coder':'';
return 'Doubao-'+v+pro+lite+mini+flash+vis+think+coder+(sz?'-'+sz:'');
}
// Llama 系列
if(lower.indexOf('llama')!==-1){
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var guard=/guard/i.test(n)?'-Guard':'';
var chat=/chat/i.test(n)?'-Chat':'';
var instruct=/instruct/i.test(n)?'-Instruct':'';
return 'Llama-'+ver+guard+chat+instruct+(sz?'-'+sz:'');
}
// Mistral 系列
if(lower.indexOf('mistral')!==-1||lower.indexOf('mixtral')!==-1){
var base=/mixtral/i.test(n)?'Mixtral':'Mistral';
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var small=/small/i.test(n)?'-Small':'';
var medium=/medium/i.test(n)?'-Medium':'';
var large=/large/i.test(n)?'-Large':'';
var nemo=/nemo/i.test(n)?'-Nemo':'';
var codestral=/codestral/i.test(n)?'-Codestral':'';
var pixtral=/pixtral/i.test(n)?'-Pixtral':'';
return base+(ver?'-'+ver:'')+small+medium+large+nemo+codestral+pixtral+(sz?'-'+sz:'');
}
// Claude 系列
if(lower.indexOf('claude')!==-1){
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var haiku=/haiku/i.test(n)?'-Haiku':'';
var sonnet=/sonnet/i.test(n)?'-Sonnet':'';
var opus=/opus/i.test(n)?'-Opus':'';
return 'Claude-'+ver+haiku+sonnet+opus;
}
// GPT 系列
if(lower.indexOf('gpt')!==-1){
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var turbo=/turbo/i.test(n)?'-Turbo':'';
var mini=/mini/i.test(n)?'-Mini':'';
var omni=/omni/i.test(n)?'-Omni':'';
var vis=/vision/i.test(n)?'-Vision':'';
return 'GPT-'+ver+turbo+mini+omni+vis;
}
// Gemini 系列
if(lower.indexOf('gemini')!==-1){
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var flash=/flash/i.test(n)?'-Flash':'';
var pro=/pro/i.test(n)?'-Pro':'';
var think=/thinking/i.test(n)?'-Thinking':'';
return 'Gemini-'+ver+flash+pro+think;
}
// Yi/零一万物 系列
if(lower.indexOf('yi-')!==-1||lower.indexOf('yi ')!==-1){
var v=(n.match(/yi[-_](light|medium|large|spark|lightning|vision)/i)||['',''])[1]||'';
var turbo=/turbo/i.test(n)?'-Turbo':'';
return 'Yi-'+v.charAt(0).toUpperCase()+v.slice(1)+turbo;
}
// 通用的兜底：去掉常见后缀，保留核心名
var core=n.replace(/[-_](chat|instruct|fp\d+|latest|main|default|v\d+|it\d+|q\d+)/gi,'');
var sz2=(core.match(/(\d+b)/i)||['',''])[1].toUpperCase();
core=core.replace(/[-_]?\d+b/i,'');
return core+(sz2?'-'+sz2:'');
}

function buildCrossPrice(){
var cs=document.querySelectorAll('.mc');
var modelMap={};
var platformSet={};
cs.forEach(function(c){
var mName=(c.querySelector('.mname')||{}).textContent||'';
var prov=(c.querySelector('.prov')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var pid=c.dataset.p||'';
// 精确标准化模型名
var coreName=normalizeModelName(mName);
if(!coreName)return;
if(!modelMap[coreName])modelMap[coreName]=[];
// 去重：同一平台同一模型只保留一个
var key=pid+'_'+coreName;
if(platformSet[key])return;
platformSet[key]=true;
modelMap[coreName].push({name:mName,prov:prov,inp:inp,out:out,cur:cur,baseName:coreName,pid:pid});
});
// 只显示在2个以上不同平台出现的模型
var groups=Object.values(modelMap).filter(function(g){
var pids={};g.forEach(function(m){pids[m.pid]=1;});
return Object.keys(pids).length>=2&&g.length<=15;
});
// 按平台数排序，平台数相同按最低价排序
groups.sort(function(a,b){
var pa={};a.forEach(function(m){pa[m.pid]=1;});
var pb={};b.forEach(function(m){pb[m.pid]=1;});
var da=Object.keys(pa).length,db=Object.keys(pb).length;
if(da!==db)return db-da;
var minA=Infinity,minB=Infinity;
a.forEach(function(m){var c=m.cur==='USD'?m.inp*1e6*USD_TO_CNY:m.inp;if(c<minA)minA=c;});
b.forEach(function(m){var c=m.cur==='USD'?m.inp*1e6*USD_TO_CNY:m.inp;if(c<minB)minB=c;});
return minA-minB;
});
var html='';
groups.slice(0,30).forEach(function(g){
// 找最低价
var minCost=Infinity;
g.forEach(function(m){
var cnyInp=m.cur==='USD'?m.inp*1e6*USD_TO_CNY:m.inp;
if(cnyInp<minCost)minCost=cnyInp;
});
// 统计平台数
var pids={};g.forEach(function(m){pids[m.pid]=1;});
var pCount=Object.keys(pids).length;
html+='<div class="cross-group"><div class="cross-group-name">'+g[0].baseName+' ('+pCount+'个平台, '+g.length+'个渠道)</div>';
// 按价格排序
var sorted=g.slice().sort(function(a,b){
var ca=a.cur==='USD'?a.inp*1e6*USD_TO_CNY:a.inp;
var cb=b.cur==='USD'?b.inp*1e6*USD_TO_CNY:b.inp;
return ca-cb;
});
sorted.forEach(function(m){
var cnyInp=m.cur==='USD'?m.inp*1e6*USD_TO_CNY:m.inp;
var priceStr=m.cur==="USD"?"$"+(m.inp*1e6).toFixed(2)+"/M":"\u00a5"+m.inp.toFixed(2)+"/M";
if(m.inp===0&&m.out===0)priceStr="\u514d\u8d39";
var isBest=Math.abs(cnyInp-minCost)<0.01;
var diff=cnyInp-minCost;
var diffStr="";
if(diff>0.01&&minCost>0)diffStr=" <span style=\"color:#94a3b8;font-size:10px\">(+"+((diff/minCost)*100).toFixed(0)+"%)</span>";
html+="<div class=\"cross-item\"><span class=\"cross-platform\">"+m.prov+"</span>"
+"<span class=\"cross-price\">"+priceStr+"</span>"
+(isBest?"<span class=\"cross-best\">\u6700\u4f4e</span>":"")
+diffStr
+"</div>";
});
html+="</div>";
});
if(html){
document.getElementById("crossPanel").style.display="block";
document.getElementById("crossList").innerHTML=html;
}else{
document.getElementById("crossPanel").style.display="none";
}
}

// ─── 数据导出 ───
function toggleExportMenu(){
var menu=document.getElementById('exportMenu');
menu.classList.toggle('show');
}
function closeExportMenu(){
var menu=document.getElementById('exportMenu');
if(menu)menu.classList.remove('show');
}
function getVisibleModels(){
var cs=document.querySelectorAll('.mc');
var models=[];
cs.forEach(function(c){
if(c.style.display==='none')return;
var mName=(c.querySelector('.mname')||{}).textContent||'';
var prov=(c.querySelector('.prov')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var ctx=c.dataset.ctxDisplay||c.dataset.ctx||'';
var scen=c.dataset.s||'';
var pt=c.dataset.pt||'';
var pid=c.dataset.p||'';
var tags=Array.from(c.querySelectorAll('.tg')).map(function(t){return t.textContent;});
models.push({name:mName,provider:prov,platform:pid,inputPrice:inp,outputPrice:out,currency:cur,context:ctx,scenario:scen,priceTier:pt,tags:tags});
});
return models;
}
function exportCSV(){
var models=getVisibleModels();
if(models.length===0){alert('没有可导出的模型');return;}
var headers=['名称','平台','平台ID','输入价格','输出价格','货币','上下文','场景','价格分级','标签'];
var rows=[headers.join(',')];
models.forEach(function(m){
rows.push([
'"'+m.name.replace(/"/g,'""')+'"',
'"'+m.provider.replace(/"/g,'""')+'"',
m.platform,
m.inputPrice,
m.outputPrice,
m.currency,
'"'+m.context+'"',
'"'+m.scenario+'"',
m.priceTier,
'"'+m.tags.join(';')+'"'
].join(','));
});
var csv='\uFEFF'+rows.join('\n');
downloadFile(csv,'ai-models-'+Date.now()+'.csv','text/csv;charset=utf-8');
closeExportMenu();
showTip('已导出 '+models.length+' 个模型 (CSV)',true);
}
function exportJSON(){
var models=getVisibleModels();
if(models.length===0){alert('没有可导出的模型');return;}
var json=JSON.stringify(models,null,2);
downloadFile(json,'ai-models-'+Date.now()+'.json','application/json;charset=utf-8');
closeExportMenu();
showTip('已导出 '+models.length+' 个模型 (JSON)',true);
}
function downloadFile(content,filename,mimeType){
var blob=new Blob([content],{type:mimeType});
var url=URL.createObjectURL(blob);
var a=document.createElement('a');
a.href=url;a.download=filename;
document.body.appendChild(a);
a.click();
document.body.removeChild(a);
URL.revokeObjectURL(url);
}

// ─── 代码片段模态框 ───
var _codeModalData = null;
function showCodeModal(baseUrl, modelName, platformId){
var modal = document.getElementById('codeModal');
if(!modal) return;
// 从 base_url 提取 base_url (去掉 /chat/completions 后缀)
var apiBase = baseUrl.replace(/\/chat\/completions\/?$/,'');
_codeModalData = {baseUrl:baseUrl, apiBase:apiBase, model:modelName, platform:platformId};
// 更新标题
var titleEl = modal.querySelector('.cm-model');
if(titleEl) titleEl.textContent = modelName;
// 默认显示 Python
switchCodeTab('python');
modal.classList.add('show');
}
function closeCodeModal(){
var modal = document.getElementById('codeModal');
if(modal) modal.classList.remove('show');
}
function switchCodeTab(lang){
if(!_codeModalData) return;
var d = _codeModalData;
document.querySelectorAll('.code-tab').forEach(function(t){t.classList.remove('active');});
var tab = document.querySelector('.code-tab[data-lang="'+lang+'"]');
if(tab) tab.classList.add('active');
var code = '';
if(lang === 'python'){
code = 'from openai import OpenAI\n\nclient = OpenAI(\n    api_key="YOUR_API_KEY",\n    base_url="'+d.apiBase+'"\n)\n\nresponse = client.chat.completions.create(\n    model="'+d.model+'",\n    messages=[\n        {"role": "system", "content": "You are a helpful assistant."},\n        {"role": "user", "content": "Hello!"}\n    ]\n)\n\nprint(response.choices[0].message.content)';
}else if(lang === 'nodejs'){
code = 'import OpenAI from "openai";\n\nconst client = new OpenAI({\n    apiKey: "YOUR_API_KEY",\n    baseURL: "'+d.apiBase+'"\n});\n\nconst response = await client.chat.completions.create({\n    model: "'+d.model+'",\n    messages: [\n        { role: "system", content: "You are a helpful assistant." },\n        { role: "user", content: "Hello!" }\n    ]\n});\n\nconsole.log(response.choices[0].message.content);';
}else if(lang === 'curl'){
code = 'curl '+d.baseUrl+' \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -d \'{\n    "model": "'+d.model+'",\n    "messages": [\n      {"role": "system", "content": "You are a helpful assistant."},\n      {"role": "user", "content": "Hello!"}\n    ]\n  }\'';
}else if(lang === 'stream'){
code = 'from openai import OpenAI\n\nclient = OpenAI(\n    api_key="YOUR_API_KEY",\n    base_url="'+d.apiBase+'"\n)\n\nstream = client.chat.completions.create(\n    model="'+d.model+'",\n    messages=[\n        {"role": "user", "content": "Hello!"}\n    ],\n    stream=True\n)\n\nfor chunk in stream:\n    if chunk.choices[0].delta.content:\n        print(chunk.choices[0].delta.content, end="")';
}
var block = document.getElementById('codeBlock');
if(block){
block.querySelector('pre').textContent = code;
var copyBtn = block.querySelector('.code-copy-btn');
if(copyBtn){copyBtn.classList.remove('copied');copyBtn.textContent='复制';}
}
}
function copyCodeBlock(){
var block = document.getElementById('codeBlock');
if(!block) return;
var code = block.querySelector('pre').textContent;
var btn = block.querySelector('.code-copy-btn');
if(navigator.clipboard && navigator.clipboard.writeText){
navigator.clipboard.writeText(code).then(function(){
if(btn){btn.classList.add('copied');btn.textContent='已复制';}
setTimeout(function(){if(btn){btn.classList.remove('copied');btn.textContent='复制';}},2000);
});
}else{
fallbackCopy(code);
if(btn){btn.classList.add('copied');btn.textContent='已复制';}
setTimeout(function(){if(btn){btn.classList.remove('copied');btn.textContent='复制';}},2000);
}
}

// ─── 复制命令 ───
function copyCmd(cmd,name){
function showTip(msg,ok){
var t=document.getElementById("toast");
t.innerHTML=(ok?"<span style=\"margin-right:6px\">\u2713</span>":"")+msg;
t.className="toast-show"+(ok?" toast-ok":" toast-err");
clearTimeout(t._tid);
t._tid=setTimeout(function(){t.className="";},2800);
}
if(navigator.clipboard&&navigator.clipboard.writeText){
navigator.clipboard.writeText(cmd).then(function(){
showTip("\u5df2\u590d\u5236: "+cmd.substring(0,60),true);
}).catch(function(){
fallbackCopy(cmd);showTip("\u5df2\u590d\u5236: "+cmd.substring(0,60),true);
});
}else{
fallbackCopy(cmd);showTip("\u5df2\u590d\u5236: "+cmd.substring(0,60),true);
}
}
function fallbackCopy(text){
var ta=document.createElement("textarea");ta.value=text;ta.style.cssText="position:fixed;left:-9999px";
document.body.appendChild(ta);ta.select();
try{document.execCommand("copy");}catch(e){}
document.body.removeChild(ta);
}

// ─── 状态持久化 ───
function saveState(){
var state={p:curP,s:curS,pt:curPT,sort:curSort,tags:curTags,ctx:curCtx,family:curFamily,
q:(document.getElementById('si').value||'')};
window.location.hash=encodeURIComponent(JSON.stringify(state));
}
function restoreState(){
try{
var hash=window.location.hash.substring(1);
if(!hash)return;
var state=JSON.parse(decodeURIComponent(hash));
if(state.p){curP=state.p;var pb=document.querySelector('.pt[data-p="'+state.p+'"]');if(pb){document.querySelectorAll('.pt').forEach(function(x){x.classList.remove('active')});pb.classList.add('active');}}
if(state.s){curS=state.s;var sb=document.querySelector('.sc[data-sc="'+state.s+'"]');if(sb){document.querySelectorAll('.sc').forEach(function(x){x.classList.remove('active')});sb.classList.add('active');}}
if(state.pt){curPT=state.pt;var ptb=document.querySelector('.pt-filter[data-pt="'+state.pt+'"]');if(ptb){document.querySelectorAll('.pt-filter').forEach(function(x){x.classList.remove('active')});ptb.classList.add('active');}}
if(state.sort){curSort=state.sort;var sob=document.querySelector('.sort-btn[data-sort="'+state.sort+'"]');if(sob){document.querySelectorAll('.sort-btn').forEach(function(x){x.classList.remove('active')});sob.classList.add('active');}}
if(state.tags&&state.tags.length>0){curTags=state.tags;state.tags.forEach(function(t){var tb=document.querySelector('.tag-btn[data-tag="'+t+'"]');if(tb)tb.classList.add('active');});}
if(state.ctx){curCtx=state.ctx;var cb=document.querySelector('.ctx-btn[data-ctx="'+state.ctx+'"]');if(cb){document.querySelectorAll('.ctx-btn').forEach(function(x){x.classList.remove('active')});cb.classList.add('active');}}
if(state.family){curFamily=state.family;var fb=document.querySelector('.family-btn[data-family="'+state.family+'"]');if(fb){document.querySelectorAll('.family-btn').forEach(function(x){x.classList.remove('active')});fb.classList.add('active');}}
if(state.q){document.getElementById('si').value=state.q;}
}catch(e){}
}
'''

# ═══════════════════════════════════════════════════════════
# 组装 HTML
# ═══════════════════════════════════════════════════════════

HDR = (
    '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    '<title>AI 模型选择器 - 全网价格对比 2026</title>\n'
    '<style>\n' + CSS + '\n</style>\n'
    '</head>\n<body>\n<div class="wrap">\n'
    '<div class="hdr"><h1>AI 模型选择器</h1>'
    '<p>一键对比全网价格 &middot; 点击卡片复制切换命令 &middot; 按 / 搜索 &middot; 按 D 暗色 &middot; 按 V 切换视图</p>'
    '<div class="brow">'
    '<span class="bd">&#128202; ' + str(total) + ' 个模型</span>'
    '<span class="bd bd-free">&#128998; 免费</span>'
    '<span class="bd bd-cheap">&#128308; &lt;¥0.7</span>'
    '<span class="bd bd-mid">&#128993; ¥0.7-10/M</span>'
    '<span class="bd bd-high">&#128996; ¥10+/M</span>'
    '<span class="bd bd-ultra">&#127745; &gt;¥100/M</span>'
    '</div></div>\n'
    '<div class="snote">' + snote + '</div>\n'
    + price_change_html + '\n'
    # ─── 搜索框置顶 ───
    '<div class="srow"><input id="si" type="text" placeholder="搜索模型... 支持 price<1, ctx>128, family:GPT, platform:aliyun 等高级语法 (按 / 聚焦)"></div>\n'
    # ─── 第一大类：厂家与模型 ───
    '<div class="fg">'
    '<div class="fg-title">厂家与模型</div>'
    '<div class="pbar">' + tabs_bar + '</div>'
    + family_bar
    + tag_bar
    + ctx_bar +
    '</div>\n'
    # ─── 第二大类：用途 ───
    '<div class="fg">'
    '<div class="fg-title">用途</div>'
    '<div class="sbar">' + scen_bar + '</div>'
    + recommend_panel +
    '</div>\n'
    # ─── 第三大类：价格 ───
    '<div class="fg">'
    '<div class="fg-title">价格</div>'
    '<div class="ptbar">' + pt_bar + '</div>'
    + price_range_bar +
    '<div class="sort-bar">' + sort_bar + '</div>'
    '<div class="toolbar">'
    '<div class="toolbar-left">'
    '<div class="cur-switch"><span style="font-size:12px;color:#64748b">货币:</span>'
    '<button class="cur-btn active" data-cur="CNY">¥ CNY</button>'
    '<button class="cur-btn" data-cur="USD">$ USD</button>'
    '</div></div>'
    '<div class="toolbar-right">'
    '<div class="export-dropdown">'
    '<button class="tool-btn" onclick="toggleExportMenu()">&#128190; 导出</button>'
    '<div class="export-menu" id="exportMenu">'
    '<button class="export-menu-item" onclick="exportCSV()">&#128196; 导出 CSV</button>'
    '<button class="export-menu-item" onclick="exportJSON()">&#128203; 导出 JSON</button>'
    '</div></div>'
    '<button class="tool-btn" id="listBtn" onclick="toggleView()">&#9776; 列表</button>'
    '<button class="tool-btn" onclick="toggleDark()">&#9728; 亮色</button>'
    '</div></div>'
    '</div>\n'
    # ─── 跨平台比价 + 月费计算器 同行 ───
    '<div class="side-panels">\n'
    + crossprice_panel + '\n'
    + calc_panel + '\n'
    '</div>\n'
    + cmp_panel + '\n'
    '<div class="filter-count" id="filterCount">显示 <strong>' + str(total) + '</strong> / ' + str(total) + ' 个模型</div>\n'
        '<div class="loading" id="ld"><div class="sp"></div>加载中...</div>\n'
    '<div class="grid" id="grid">\n'
)

FTR = (
    '\n</div>\n'
    '<div class="pagination" id="pagination"></div>\n'
    '<div class="empty" id="empty" style="display:none">没有找到符合条件的模型</div>\n'
    '</div>\n'
    '<div class="ftr">'
    '<p>&#128202; 数据来源：各平台 API 实时拉取 + 官网公告（更新时间：' + now + '）</p>'
    '<p>OpenRouter 显示原始美元价格 &middot; 国内平台显示人民币价格 &middot; 点击卡片复制接入方式</p>'
    '<p>快捷键: / 搜索 | Esc 清空 | D 暗色 | V 视图 | 1-9 切换平台</p>'
    '<p><a href="https://github.com/k-goz/model-selector" target="_blank">GitHub</a></p>'
    '</div>\n'
    '<div id="toast" class=""></div>\n'
    '<div class="code-modal" id="codeModal" onclick="if(event.target===this)closeCodeModal()">'
    '<div class="code-modal-content">'
    '<div class="code-modal-header"><div class="code-modal-title"><span>&#128187;</span> 一键接入 <span class="cm-model"></span></div><button class="code-modal-close" onclick="closeCodeModal()">&times;</button></div>'
    '<div class="code-modal-body">'
    '<div class="code-tabs">'
    '<button class="code-tab active" data-lang="python" onclick="switchCodeTab(\'python\')">Python</button>'
    '<button class="code-tab" data-lang="nodejs" onclick="switchCodeTab(\'nodejs\')">Node.js</button>'
    '<button class="code-tab" data-lang="curl" onclick="switchCodeTab(\'curl\')">cURL</button>'
    '<button class="code-tab" data-lang="stream" onclick="switchCodeTab(\'stream\')">Stream</button>'
    '</div>'
    '<div class="code-block" id="codeBlock"><button class="code-copy-btn" onclick="copyCodeBlock()">复制</button><pre></pre></div>'
    '<div class="code-info"><strong>使用说明：</strong>将 <code>YOUR_API_KEY</code> 替换为你的 API 密钥即可直接运行。所有平台均兼容 <code>OpenAI SDK</code> 接入方式。</div>'
    '</div></div></div>\n'
    '<script>\n' + JS + '\n</script>\n'
    '</body>\n</html>'
)

HTML = HDR + "\n".join(cards) + FTR

with open(OUT,"w",encoding="utf-8") as f:
    f.write(HTML)
sz = os.path.getsize(OUT)
print("\nDONE:", OUT, "(%.0f KB)" % (sz/1024))
print("Stats: OR:%d Ali:%d SF:%d MS:%d ZH:%d VC:%d BD:%d TX:%d XH:%d MM:%d YW:%d BC:%d JC:%d DS:%d GQ:%d TG:%d FW:%d CO:%d IF:%d NV:%d DI:%d Total:%d" % (
    oc,ac,sc2,mc2,zc,vc2,bc2,tc2,xc,mmc,yc,bcc,jcc,dc,gc,tgc,fwc,coc,ic,nc,dic,total))
print("Time: %.1fs" % (time.time()-t0))
