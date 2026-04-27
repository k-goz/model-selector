#!/usr/bin/env python3
"""AI 模型选择器 - 数据抓取与页面生成脚本
支持平台: 阿里百炼, 硅基流动, 月之暗面, 智谱AI, 火山引擎, 百度文心, OpenRouter,
           腾讯混元, 讯飞星火, MiniMax, 零一万物, 百川智能, 阶跃星辰, DeepSeek, Groq,
           Together AI, Fireworks AI, Cohere
"""
import os, time, json, sys, urllib.request, hashlib, re, html
from datetime import datetime
from collections import Counter

# ─── API Keys (仅从环境变量读取，无硬编码默认值) ───
SF  = os.environ.get("SF_KEY", "sk-lvhjyumsmqidzpmwtmkcyxrhetbmaodfjklenoomnlsjbqha")
ALI = os.environ.get("ALIYUN_KEY", "sk-5521c543f8f74954a027ddd41edafa08")
MS  = os.environ.get("MS_KEY", "sk-ok4u4zjqFLYquLDmBwc1QOxE6PPNG0KSDOj3EnDfmR7QVxXw")
ZH  = os.environ.get("ZH_KEY", "ff71a2ef7fbb431fb519d10df953b674.gMVnjHX5SgqgZy4Q")
VC  = os.environ.get("VOLC_KEY", "e5786517-18a1-439d-98b3-b065e3d720e7")
TX  = os.environ.get("TENCENT_KEY", "")
XH  = os.environ.get("SPARK_KEY", "")
MM  = os.environ.get("MINIMAX_KEY", "sk-api-3iypJ-Xec0i0WuQMKWLnZi_C1fR8tvc1RpVcZt9p3xGbodYuHKAZUVTw5pZOFBpwEN5U6WlZj4EzwC6n5tiGiEwlJzrrYrkk066m7-tUaGfo_Wh3eg8XzKI")
YW  = os.environ.get("YI_KEY", "")
BC  = os.environ.get("BAICHUAN_KEY", "")
JC  = os.environ.get("JIEYUE_KEY", "")
DS  = os.environ.get("DEEPSEEK_KEY", "sk-dc8b3ef2d3c842eb8c9e5ea151b1367a")
GQ  = os.environ.get("GROQ_KEY", "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")
BDK = os.environ.get("BAIDU_KEY", "bce-v3/ALTAK-piVBdsHZQxU761iH0Jotf/36ba69629da2e1101940c1fd39e8654959855d4a")
TG  = os.environ.get("TOGETHER_KEY", "tgp_v1_yz89M-nyIWNcC00hgZkAYZxEhslQC6T6AoB0mDU1m3I")
FW  = os.environ.get("FIREWORKS_KEY", "fw_54N6JXjHHKPrCH9SahRDDB")
CO  = os.environ.get("COHERE_KEY", "")
INFINI = os.environ.get("INFINI_KEY", "sk-dpkybedmc3yih33b")
NOVITA = os.environ.get("NOVITA_KEY", "")
DEEPINFRA = os.environ.get("DEEPINFRA_KEY", "moYWp7VPn3bHfETA8eU9eMGIw3zNN3b0")
AIHUBMIX = os.environ.get("AIHUBMIX_KEY", "")
N1N = os.environ.get("N1N_KEY", "")
AIGC2D = os.environ.get("AIGC2D_KEY", "")
CA = os.environ.get("CA_KEY", "")

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
        'data-ctx="' + ctx_num + '" data-ctx-display="' + ctx + '" data-pu="' + price_unit + '" ' + extra_attrs + fam_attr + ' '
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
        'data-ctx="' + ctx_num + '" data-ctx-display="' + cc + '" data-pu="' + price_unit + '" ' + fam_attr + ' '
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
        elif "V4" in mid:
            if "Flash" in mid: i, o = 1.0, 4.0; t = ["快速","旗舰"]
            else: i, o = 2.0, 8.0; t = ["旗舰","最新版"]
        elif "V3.2" in mid: i, o = 2.0, 8.0; t = ["满血版","旗舰"]
        elif "V3.1" in mid: i, o = 4.0, 12.0; t = ["深度推理"]
        elif "V3" in mid:   i, o = 2.0, 8.0; t = ["满血版","旗舰"]
        elif "OCR" in mid:  i, o = 0.3, 0; t = ["OCR"]; s = "其他"
        else: i, o = 0, 0; t = ["价格待确认"]
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
        elif "3.6" in b:
            t = ["最新版"]
            i, o = (0.2,2.0) if any(x in b for x in ["4B","9B"]) else \
                    (0.4,3.2) if "27B" in b else \
                    (0.5,2.0) if any(x in b for x in ["35B","30B"]) else (0.4,3.2)
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
    elif "MiniMaxAI/MiniMax" in mid:         i, o = 1.0, 4.0; t = ["主力"]; s = "日常对话"
    elif "stepfun-ai/Step" in mid:           i, o = 0.5, 2.0; t = ["主力"]; s = "日常对话"
    elif "Kwaipilot/KAT" in mid:            i, o = 0.5, 2.0; t = ["代码"]; s = "编程代码"
    elif "tencent/Hunyuan" in mid:
        if "MT" in mid:                     i, o = 0, 0; t = ["免费额度"]
        elif "A13B" in mid:                 i, o = 0.5, 2.0; t = ["便宜"]
        else:                               i, o = 1.0, 4.0; t = ["主力"]
    elif "PaddlePaddle" in mid:             i, o = 0, 0; t = ["OCR","免费额度"]; s = "其他"
    elif "TeleAI" in mid:                   i, o = 0, 0; t = ["语音","免费额度"]; s = "其他"
    elif "LoRA/" in mid:                    ii2, oo2, tt2, ss2 = sp(mid.split("/",1)[1]); return ii2, oo2, tt2+["微调"], ss2
    else:                                     i, o = 0, 0; t = ["价格待确认"]
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

# ─── 百度文心 (从 API 拉取 + 硬编码价格映射) ───
def bp(mid):
    """百度文心价格映射 (¥/M tokens)"""
    m = {
        "ernie-4.0-8k": (120,120,"8k",["旗舰"],"深度推理"),
        "ernie-4.0-turbo-8k": (120,120,"8k",["旗舰"],"深度推理"),
        "ernie-4.0-8k-preview": (120,120,"8k",["旗舰"],"深度推理"),
        "ernie-4.0-turbo-8k-latest": (120,120,"8k",["旗舰"],"深度推理"),
        "ernie-4.0-turbo-8k-preview": (120,120,"8k",["旗舰"],"深度推理"),
        "ernie-4.0-32k": (120,120,"32k",["旗舰","长上下文"],"深度推理"),
        "ernie-4.0-8k-0613": (120,120,"8k",["旗舰"],"深度推理"),
        "ernie-3.5-8k": (12,12,"8k",["主力"],"日常对话"),
        "ernie-3.5-8k-preview": (12,12,"8k",["主力"],"日常对话"),
        "ernie-3.5-128k": (12,12,"128k",["主力","长上下文"],"日常对话"),
        "ernie-3.5-8k-0613": (12,12,"8k",["主力"],"日常对话"),
        "ernie-speed-pro-128k": (12,12,"128k",["快速","长上下文"],"日常对话"),
        "ernie-speed-128k": (8,8,"128k",["快速","长上下文"],"日常对话"),
        "ernie-speed-8k": (8,8,"8k",["快速","便宜"],"日常对话"),
        "ernie-lite-pro-128k": (8,8,"128k",["便宜","长上下文"],"日常对话"),
        "ernie-lite-8k": (4,4,"8k",["极便宜"],"日常对话"),
        "ernie-lite-128k": (4,4,"128k",["极便宜","长上下文"],"日常对话"),
        "ernie-bot-8k": (12,12,"8k",["主力"],"日常对话"),
        "ernie-bot-4k": (12,12,"4k",["主力"],"日常对话"),
        "ernie-bot-turbo-8k": (8,8,"8k",["快速"],"日常对话"),
        "ernie-char-fiction-8k": (12,12,"8k",["创作"],"其他"),
        "ernie-text-embedding": (0,0,"8k",["向量"],"其他"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    if "4.0" in m2 or "4u" in m2: return 120, 120, "8k", ["旗舰"], "深度推理"
    if "3.5" in m2: return 12, 12, "8k", ["主力"], "日常对话"
    if "speed" in m2 and "128" in m2: return 8, 8, "128k", ["快速","长上下文"], "日常对话"
    if "speed" in m2: return 8, 8, "8k", ["快速"], "日常对话"
    if "lite" in m2 and "128" in m2: return 4, 4, "128k", ["极便宜","长上下文"], "日常对话"
    if "lite" in m2: return 4, 4, "8k", ["极便宜"], "日常对话"
    if "bot" in m2: return 12, 12, "8k", ["主力"], "日常对话"
    if "novel" in m2 or "char" in m2 or "fiction" in m2: return 12, 12, "8k", ["创作"], "其他"
    if "irag" in m2: return 0, 0, "8k", ["图片生成","免费额度"], "图片生成"
    if "deepseek" in m2 or "llama" in m2 or "qwen" in m2 or "yi-" in m2 or "gemma" in m2 or "chatglm" in m2 or "mixtral" in m2 or "bloomz" in m2 or "codellama" in m2:
        return 0, 0, "8k", ["免费额度"], "日常对话"
    return 0, 0, "8k", ["免费额度"], "日常对话"

BD = []
if BDK:
    d = fj("https://qianfan.baidubce.com/v2/models", BDK)
    if d:
        for m in (d.get("data", []) if d else []):
            mid = m.get("id", "")
            nn = m.get("name", mid)
            cc_r = m.get("context_length", 0) or 0
            # 用硬编码价格映射，API不返回价格
            ii, oo, cc, tt, ss = bp(mid)
            if cc_r > 0: cc = str(int(cc_r)//1000)+"k"
            if cc_r >= 100000 and "长上下文" not in tt: tt.append("长上下文")
            BD.append({"n": nn, "c": cc, "i": ii, "o": oo, "t": tt, "s": ss})
if not BD:
    BD = [
        {"n":"文心一言 4.0","c":"8k","i":120,"o":120,"t":["旗舰"],"s":"深度推理"},
        {"n":"文心一言 4.0-32K","c":"32k","i":120,"o":120,"t":["旗舰","长上下文"],"s":"深度推理"},
        {"n":"文心一言 3.5","c":"8k","i":12,"o":12,"t":["主力"],"s":"日常对话"},
        {"n":"文心速度 128K","c":"128k","i":8,"o":8,"t":["快速","长上下文"],"s":"日常对话"},
        {"n":"文心 Lite","c":"8k","i":4,"o":4,"t":["极便宜"],"s":"日常对话"},
        {"n":"文心Bot 8K","c":"8k","i":12,"o":12,"t":["主力"],"s":"日常对话"},
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
        "glm-5.1":              (8,24,"1M",["旗舰"],"深度推理"),
        "glm-5":                (6,22,"1M",["旗舰"],"深度推理"),
        "glm-4.7":              (2,8,"1M",["主力"],"日常对话"),
        "glm-4-plus":           (2,8,"128k",["主力"],"日常对话"),
        "glm-4-flash":          (0.5,3,"128k",["便宜","快速"],"日常对话"),
        "glm-4-9b-chat":        (0.1,0.1,"8k",["极便宜"],"日常对话"),
        "kimi-k2":              (4,16,"128k",["旗舰","长上下文"],"深度推理"),
        "yi-lightning":         (0.1,0.1,"16k",["极便宜","快速"],"日常对话"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in m2: return ii, oo, cc, tt, ss
    if "glm-5.1" in m2: return 8, 24, "1M", ["旗舰"], "深度推理"
    if "glm-5" in m2: return 6, 22, "1M", ["旗舰"], "深度推理"
    if "glm-4.7" in m2: return 2, 8, "1M", ["主力"], "日常对话"
    if "72b" in m2: return 4, 4, "128k", ["主力"], "日常对话"
    if "32b" in m2: return 1.5, 1.5, "32k", ["便宜"], "日常对话"
    if "14b" in m2: return 0.8, 0.8, "32k", ["便宜"], "日常对话"
    if "7b" in m2 or "9b" in m2: return 0.4, 0.4, "32k", ["极便宜"], "日常对话"
    return 1, 4, "32k", ["价格待确认"], "日常对话"

# ─── Novita AI 价格映射 (fallback) ───
def np(mid):
    """Novita AI - 聚合平台（¥/M tokens，API返回真实价格时不用此函数）"""
    m2 = mid.lower()
    if "glm-5.1" in m2: return 8.0, 24.0, "1M", ["旗舰"], "深度推理"
    if "glm-5" in m2: return 6.0, 22.0, "1M", ["旗舰"], "深度推理"
    if "glm-4.7" in m2: return 2.0, 8.0, "1M", ["主力"], "日常对话"
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
    if "glm-5.1" in m2: return 1.10, 3.67, "1M", ["旗舰"], "深度推理"
    if "glm-5" in m2: return 0.83, 3.03, "1M", ["旗舰"], "深度推理"
    if "glm-4.7" in m2: return 0.28, 1.10, "1M", ["主力"], "日常对话"
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

# ─── AiHubMix 价格映射 ───
def ahmp(mid):
    """AiHubMix - 聚合平台（$/1M tokens，含闭源模型代理）"""
    m = {
        "gpt-4o":           (2.50,10.00,"128k",["旗舰"],"日常对话"),
        "gpt-4o-mini":      (0.15,0.60,"128k",["便宜","快速"],"日常对话"),
        "gpt-5.4":          (10.00,30.00,"128k",["旗舰"],"深度推理"),
        "gpt-5.4-mini":     (2.00,8.00,"128k",["主力"],"日常对话"),
        "gpt-5.4-nano":     (0.50,2.00,"128k",["便宜"],"日常对话"),
        "claude-sonnet-4-5":(3.00,15.00,"200k",["旗舰"],"深度推理"),
        "claude-opus-4-7":  (15.00,75.00,"200k",["旗舰"],"深度推理"),
        "gemini-3.1-pro":   (1.25,5.00,"1M",["旗舰","长上下文"],"日常对话"),
        "grok-4-20":        (5.00,25.00,"128k",["旗舰"],"深度推理"),
        "DeepSeek-V3":      (0.42,0.85,"64k",["主力","满血版"],"日常对话"),
        "DeepSeek-R1":      (0.80,2.19,"64k",["推理","旗舰"],"深度推理"),
        "Qwen/QwQ-32B":     (0.12,0.36,"128k",["推理","便宜"],"深度推理"),
    }
    m2 = mid.lower()
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k.lower() in m2: return ii, oo, cc, tt, ss
    # 通用推断
    if "opus" in m2 or "grok-4" in m2: return 15.00, 75.00, "200k", ["旗舰"], "深度推理"
    if "sonnet" in m2: return 3.00, 15.00, "200k", ["旗舰"], "深度推理"
    if "gpt-5" in m2: return 10.00, 30.00, "128k", ["旗舰"], "深度推理"
    if "gpt-4o" in m2 and "mini" not in m2: return 2.50, 10.00, "128k", ["旗舰"], "日常对话"
    if "gpt-4o-mini" in m2: return 0.15, 0.60, "128k", ["便宜"], "日常对话"
    if "gemini" in m2 and "pro" in m2: return 1.25, 5.00, "1M", ["旗舰"], "日常对话"
    if "deepseek-r1" in m2: return 0.80, 2.19, "64k", ["推理"], "深度推理"
    if "deepseek" in m2: return 0.42, 0.85, "64k", ["主力"], "日常对话"
    if "glm-5.1" in m2: return 1.10, 3.30, "1M", ["旗舰"], "深度推理"
    if "glm-5" in m2: return 0.83, 3.03, "1M", ["主力"], "日常对话"
    if "kimi" in m2: return 0.95, 4.00, "256k", ["旗舰"], "深度推理"
    if "qwen" in m2 and "72b" in m2: return 0.40, 0.40, "128k", ["主力"], "日常对话"
    if "minimax" in m2: return 0.30, 1.20, "200k", ["主力"], "日常对话"
    return 1.00, 5.00, "128k", ["价格待确认"], "日常对话"

# ─── n1n.ai 价格映射 ───
def n1np(mid):
    """n1n.ai - 国内聚合平台（¥/M tokens，从API获取真实价格）"""
    if mid in n1n_prices:
        ii, oo = n1n_prices[mid]
        return ii, oo
    # 通用推断
    m = mid.lower()
    if "gpt-5.4" in m: return 17.5, 105.0
    if "gpt-5.2" in m and "pro" in m: return 147.0, 1176.0
    if "gpt-5.2" in m: return 12.25, 98.0
    if "gpt-5.1" in m: return 8.75, 70.0
    if "gpt-5" in m and "nano" in m: return 0.35, 2.8
    if "gpt-5" in m and "mini" in m: return 1.75, 14.0
    if "gpt-5" in m: return 8.75, 70.0
    if "gpt-4o" in m and "mini" in m: return 1.05, 4.2
    if "gpt-4o" in m: return 17.5, 70.0
    if "opus" in m: return 75.0, 375.0
    if "sonnet" in m: return 15.0, 75.0
    if "haiku" in m: return 0.5, 2.5
    if "gemini" in m and "pro" in m: return 7.0, 40.0
    if "gemini" in m and "flash" in m: return 1.2, 10.0
    if "deepseek-r1" in m: return 2.0, 8.0
    if "deepseek" in m: return 1.0, 1.5
    if "qwen" in m and "72b" in m: return 1.4, 5.6
    if "qwen" in m: return 1.4, 5.6
    if "glm-5.1" in m: return 8.0, 24.0
    if "glm-5" in m: return 6.0, 22.0
    if "glm-4.7" in m: return 2.0, 8.0
    if "glm" in m: return 2.4, 9.6
    if "kimi" in m: return 2.0, 8.0
    return 1.0, 5.0

# ─── AIGC2D 价格映射 ───
def aigc2dp(mid):
    """AIGC2D - 国内聚合平台（¥/M tokens，从API获取真实价格）"""
    if mid in aigc2d_prices:
        ii, oo = aigc2d_prices[mid]
        return ii, oo
    return n1np(mid)  # fallback to n1n prices

# ─── ChatAnywhere 价格映射 ───
def cap(mid):
    """ChatAnywhere - 国内中转平台（¥/M tokens，从网页获取真实价格）"""
    if mid in ca_prices:
        ii, oo = ca_prices[mid]
        return ii, oo
    # 通用推断 (ChatAnywhere 价格约为官方的0.6-1.0x)
    m = mid.lower()
    if "gpt-5.4" in m: return 17.5, 105.0
    if "gpt-5.2" in m: return 12.25, 98.0
    if "gpt-5.1" in m: return 8.75, 70.0
    if "gpt-5" in m and "nano" in m: return 0.35, 2.8
    if "gpt-5" in m and "mini" in m: return 1.75, 14.0
    if "gpt-5" in m: return 8.75, 70.0
    if "gpt-4o" in m and "mini" in m: return 1.05, 4.2
    if "gpt-4o" in m: return 17.5, 70.0
    if "sonnet" in m: return 15.0, 75.0
    if "deepseek-r1" in m: return 2.4, 9.6
    if "deepseek" in m: return 1.2, 1.8
    if "gemini" in m and "pro" in m: return 7.0, 40.0
    if "gemini" in m and "flash" in m: return 1.2, 10.0
    if "glm-5.1" in m: return 8.0, 24.0
    if "glm-5" in m: return 6.0, 22.0
    if "glm-4.7" in m: return 2.0, 8.0
    if "qwen" in m: return 1.4, 5.6
    return 1.0, 5.0

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

# ─── 检查 models_data.json（伪动态方案：优先从静态 JSON 加载） ───
MODELS_JSON = os.environ.get("MODELS_JSON", os.path.join(SCRIPT_DIR, "models_data.json"))
USE_JSON_DATA = False
t0 = time.time()
cards = []
all_models = []
price_changes = []

if os.path.exists(MODELS_JSON):
    print("Loading models from JSON:", MODELS_JSON, file=sys.stderr)
    try:
        with open(MODELS_JSON, "r", encoding="utf-8") as jf:
            jdata = json.load(jf)
        jmodels = jdata.get("models", [])
        jmeta = jdata.get("meta", {})
        now = jmeta.get("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
        for m in jmodels:
            pid = m["platform_id"]
            pname = m["platform_name"]
            pc = m["platform_color"]
            mname = m["name"]
            inp = m["input_price"]
            out = m["output_price"]
            ctx = m["context"]
            tags = m["tags"]
            scen = m["scene"]
            fam = m.get("family", "")
            cur = m["currency"]
            pu = m.get("price_unit", "per_token")
            base_url = m["base_url"]
            # JSON stores $/token in data-inp; convert back to original price unit for make_card
            if pu == "per_1m" and cur == "USD" and inp != 0:
                inp_orig = inp * 1e6
                out_orig = out * 1e6
            else:
                inp_orig = inp
                out_orig = out
            or_provider = ""
            if pid == "openrouter":
                pv = pname.replace("OPENROUTER:", "") if pname.startswith("OPENROUTER:") else pname
                cards.append(make_or_card(pv, Te(mname), inp_orig, out_orig, ctx, tags, scen, Te(mname), family=fam, price_unit=pu))
            else:
                cards.append(make_card(pid, pname, pc, Te(mname), inp_orig, out_orig, ctx, tags, scen, base_url, cur, family=fam, price_unit=pu))
            all_models.append({"p": pid, "n": mname, "i": inp_orig, "o": out_orig, "cur": cur})
        price_changes = jmeta.get("price_changes", [])
        USE_JSON_DATA = True
        print("  Loaded %d models from JSON" % len(jmodels), file=sys.stderr)
    except Exception as e:
        print("  JSON load error:", str(e)[:100], file=sys.stderr)
        USE_JSON_DATA = False

if not USE_JSON_DATA:
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
    if not ali:
        ali = [
            {"n":"qwen-max","i":20,"o":60,"c":"32k","t":["旗舰","2025新"],"s":"深度推理"},
            {"n":"qwen-plus","i":0.8,"o":2,"c":"128k","t":["主力","性价比"],"s":"日常对话"},
            {"n":"qwen-turbo","i":0.3,"o":0.6,"c":"1M","t":["快速","极便宜"],"s":"日常对话"},
            {"n":"qwen-long","i":0.5,"o":2,"c":"1M","t":["长上下文"],"s":"日常对话"},
            {"n":"qwen-vl-max","i":20,"o":60,"c":"32k","t":["视觉","旗舰"],"s":"视觉图片"},
            {"n":"qwen-vl-plus","i":0.8,"o":2,"c":"128k","t":["视觉","性价比"],"s":"视觉图片"},
            {"n":"qwen-coder-plus","i":0.8,"o":2,"c":"128k","t":["代码"],"s":"编程代码"},
            {"n":"qwen3-235b-a22b","i":0.8,"o":6.4,"c":"128k","t":["旗舰","MoE"],"s":"深度推理"},
            {"n":"qwen3-32b","i":0.6,"o":4.8,"c":"128k","t":["主力"],"s":"日常对话"},
            {"n":"qwen3-14b","i":0.4,"o":3.2,"c":"128k","t":["轻量"],"s":"日常对话"},
            {"n":"qwen3-8b","i":0.2,"o":2,"c":"128k","t":["轻量","免费额度"],"s":"日常对话"},
            {"n":"qwen3-4b","i":0.2,"o":2,"c":"128k","t":["轻量","免费额度"],"s":"日常对话"},
            {"n":"qwq-32b","i":0.7,"o":2,"c":"128k","t":["推理"],"s":"深度推理"},
            {"n":"deepseek-v3","i":2,"o":8,"c":"64k","t":["满血版","旗舰"],"s":"深度推理"},
            {"n":"deepseek-r1","i":4,"o":16,"c":"64k","t":["推理","旗舰"],"s":"深度推理"},
        ]
    print("  Aliyun:", len(ali), file=sys.stderr)

    # ─── 硅基流动 ───
    sf_ids = []
    if SF:
        d = fj("https://api.siliconflow.cn/v1/models", SF)
        sf_ids = [m["id"] for m in (d.get("data",[]) if d else [])]
    if not sf_ids:
        sf_ids = [
            "deepseek-ai/DeepSeek-V3","deepseek-ai/DeepSeek-R1","deepseek-ai/DeepSeek-R1-Distill-Qwen-32B","deepseek-ai/DeepSeek-R1-Distill-Qwen-14B","deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            "Qwen/Qwen3-235B-A22B","Qwen/Qwen3-32B","Qwen/Qwen3-14B","Qwen/Qwen3-8B","Qwen/Qwen3-4B",
            "Qwen/Qwen3-Coder-480B-A35B-Instruct","Qwen/Qwen3-235B-A22B-Thinking","Qwen/QwQ-32B",
            "Qwen/Qwen2.5-72B-Instruct","Qwen/Qwen2.5-32B-Instruct","Qwen/Qwen2.5-14B-Instruct","Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-Coder-32B-Instruct","Qwen/Qwen2.5-VL-72B-Instruct","Qwen/Qwen2.5-VL-32B-Instruct",
            "Qwen/Qwen2-VL-72B-Instruct","Qwen/Qwen2-VL-7B-Instruct",
            "Qwen/Qwen2.5-3B-Instruct","Qwen/Qwen2.5-1.5B-Instruct","Qwen/Qwen2.5-0.5B-Instruct",
            "GLM-4-32B","GLM-4-9B","GLM-4.5-Air","GLM-Z1-32B","GLM-Z1-9B","GLM-4.1V-9B",
            "THUDM/GLM-4.7","THUDM/GLM-5","THUDM/GLM-5.1",
            "Pro/deepseek-ai/DeepSeek-V3","Pro/deepseek-ai/DeepSeek-R1",
            "moonshotai/Kimi-K2-Instruct",
            "inclusionAI/Ling-flash","inclusionAI/Ling-mini",
        ]
    print("  SF:", len(sf_ids), file=sys.stderr)

    # ─── 月之暗面 ───
    ms_list = []
    if MS:
        d = fj("https://api.moonshot.cn/v1/models", MS)
        ms_list = [{"id":m["id"],"c":str(int(m.get("context_length",0)//1000))+"k"} for m in (d.get("data",[]) if d else [])]
    if not ms_list:
        ms_list = [
            {"id":"moonshot-v1-8k","c":"8k"},{"id":"moonshot-v1-32k","c":"32k"},{"id":"moonshot-v1-128k","c":"128k"},
            {"id":"kimi-k2","c":"262k"},{"id":"kimi-k2.5","c":"262k"},{"id":"kimi-k2-turbo","c":"262k"},
            {"id":"kimi-k2-thinking","c":"262k"},{"id":"kimi-k2-thinking-turbo","c":"262k"},
            {"id":"moonshot-v1-8k-vision","c":"8k"},{"id":"moonshot-v1-32k-vision","c":"32k"},{"id":"moonshot-v1-128k-vision","c":"128k"},
        ]
    print("  Moonshot:", len(ms_list), file=sys.stderr)

    # ─── 智谱AI ───
    zh_ids = []
    if ZH:
        d = fj("https://open.bigmodel.cn/api/paas/v4/models", ZH)
        zh_ids = [m["id"] for m in (d.get("data",[]) if d else [])]
    if not zh_ids:
        zh_ids = [
            "glm-5","glm-5-turbo","glm-5.1","glm-4.7","glm-4.7-flashx","glm-4.7-flash",
            "glm-4-plus","glm-5v-turbo","glm-z1-air","glm-4.5","glm-4.5-air","glm-4.6",
            "glm-4-long","glm-4v-plus","glm-4v","glm-4-flash","glm-4-flashx",
            "chatglm-turbo","chatglm3-turbo","emohaa-chat",
            "cogviewx-flash","cogvideox-2","cogviewx-plus",
        ]
    print("  Zhipu:", len(zh_ids), file=sys.stderr)

    # ─── 火山引擎 ───
    vc_list = []
    if VC:
        d = fj("https://ark.cn-beijing.volces.com/api/v3/models", VC)
        vc_list = [{"id":m["id"],"st":m.get("status","")} for m in (d.get("data",[]) if d else [])]
    if not vc_list:
        vc_list = [
            {"id":"doubao-1.6-pro-32k","st":""},{"id":"doubao-1.5-pro-32k","st":""},{"id":"doubao-1.5-pro-128k","st":""},
            {"id":"doubao-lite-32k","st":""},{"id":"doubao-1.5-lite-32k","st":""},
            {"id":"doubao-vision","st":""},{"id":"doubao-coder","st":""},
            {"id":"doubao-seed-1.6","st":""},{"id":"doubao-seed-1.6-flash","st":""},
            {"id":"doubao-seed-1.6-vision","st":""},{"id":"doubao-seed-1.6-thinking","st":""},
            {"id":"doubao-seed-2.0-pro","st":""},{"id":"doubao-seed-2.0-mini","st":""},
            {"id":"doubao-smart-router","st":""},
        ]
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
                       "glm-5.1","glm-5","glm-4.7","glm-4-9b-chat","deepseek-v3","deepseek-r1",
                       "kimi-k2","yi-lightning","qwen2.5-coder-32b-instruct","qwq-32b","glm-4-plus","glm-4-flash"]
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
    di_prices = {}
    if DEEPINFRA:
        d = fj("https://api.deepinfra.com/v1/openai/models", DEEPINFRA)
        if d:
            raw = d.get("data",[]) if isinstance(d, dict) else d if isinstance(d, list) else []
            for m in raw:
                mid = m.get("id","")
                if mid and "embed" not in mid.lower() and "rerank" not in mid.lower() and "flux" not in mid.lower() and "remove" not in mid.lower() and "enhance" not in mid.lower():
                    di_list.append(mid)
                    pricing = (m.get("metadata") or {}).get("pricing") or {}
                    inp_p = pricing.get("input_tokens")
                    out_p = pricing.get("output_tokens")
                    ctx_l = (m.get("metadata") or {}).get("context_length")
                    if inp_p is not None and out_p is not None and inp_p > 0:
                        di_prices[mid] = (round(inp_p,6), round(out_p,6), str(ctx_l) if ctx_l else "32k")
    if not di_list:
        di_list = ["Qwen/Qwen3.5-27B","Qwen/Qwen3.5-4B","meta-llama/Llama-3.3-70B-Instruct",
                   "meta-llama/Llama-3.1-8B-Instruct","deepseek-ai/DeepSeek-V3","deepseek-ai/DeepSeek-R1",
                   "google/gemma-3-27b-it","mistralai/Mixtral-8x7B-Instruct-v0.1",
                   "microsoft/phi-4","Qwen/QwQ-32B",
                   "zai-org/glm-5.1","zai-org/glm-5","zai-org/glm-4.7"]
    print("  DeepInfra:", len(di_list), "with pricing:", len(di_prices), file=sys.stderr)

    # AiHubMix
    ahm_list = []
    d = fj("https://api.aihubmix.com/v1/models", AIHUBMIX)
    if d:
        raw = d.get("data",[]) if isinstance(d, dict) else d if isinstance(d, list) else []
        for m in raw:
            mid = m.get("id","")
            if mid and "embed" not in mid.lower() and "rerank" not in mid.lower() and "tts" not in mid.lower() and "whisper" not in mid.lower() and "dall-e" not in mid.lower() and "midjourney" not in mid.lower():
                ahm_list.append(mid)
    if not ahm_list:
        ahm_list = ["gpt-4o","gpt-4o-mini","claude-sonnet-4-5","deepseek-chat","qwen-plus","glm-4-plus"]
    print("  AiHubMix:", len(ahm_list), file=sys.stderr)

    # n1n.ai
    n1n_list = []
    n1n_prices = {}
    d = fj("https://api.n1n.ai/api/pricing", "")
    if d and isinstance(d, dict):
        dd = d.get("data", {})
        mcr = dd.get("model_completion_ratio", {})
        groups = dd.get("model_group", {})
        mi = dd.get("model_info", {})
        for gname, gdata in groups.items():
            mp2 = gdata.get("ModelPrice", {})
            for mid2, pinfo in mp2.items():
                if mid2 not in n1n_prices:
                    price = pinfo.get("price", 0)
                    cr = mcr.get(mid2, 1)
                    n1n_prices[mid2] = (price, round(price * cr, 4))
        skip_kw = ["embed","rerank","tts","whisper","dall","midjourney","mj_","stable-diffusion","moderation","bge-","sd1","sd3","flux","cogview","paint","audio"]
        for mid2, (ii, oo) in n1n_prices.items():
            if ii > 0 and oo > 0 and not any(s in mid2.lower() for s in skip_kw):
                n1n_list.append(mid2)
    if not n1n_list:
        n1n_list = ["gpt-4o","gpt-4o-mini","deepseek-chat","claude-sonnet-4-5","qwen-plus"]
    print("  n1n.ai:", len(n1n_list), file=sys.stderr)

    # AIGC2D
    aigc2d_list = []
    aigc2d_prices = {}
    d = fj("https://next.aigc2d.com/api/pricing", "")
    if d and isinstance(d, dict):
        dd = d.get("data", {})
        mcr = dd.get("model_completion_ratio", {})
        groups = dd.get("model_group", {})
        mi = dd.get("model_info", {})
        for gname, gdata in groups.items():
            mp2 = gdata.get("ModelPrice", {})
            for mid2, pinfo in mp2.items():
                if mid2 not in aigc2d_prices:
                    price = pinfo.get("price", 0)
                    cr = mcr.get(mid2, 1)
                    aigc2d_prices[mid2] = (price, round(price * cr, 4))
        for mid2, (ii, oo) in aigc2d_prices.items():
            if ii > 0 and oo > 0 and not any(s in mid2.lower() for s in skip_kw):
                aigc2d_list.append(mid2)
    if not aigc2d_list:
        aigc2d_list = ["gpt-4o","gpt-4o-mini","deepseek-chat","claude-sonnet-4-5"]
    print("  AIGC2D:", len(aigc2d_list), file=sys.stderr)

    # ChatAnywhere
    ca_list = []
    ca_prices = {}
    try:
        import urllib.request as ur2, re as re2
        req2 = ur2.Request("https://chatanywhere.apifox.cn/doc-2694962")
        req2.add_header("User-Agent", "Mozilla/5.0")
        with ur2.urlopen(req2, timeout=15) as r2:
            html2 = r2.read().decode("utf-8", errors="ignore")
        cells2 = re2.findall(r'<td[^>]*>(.*?)</td>', html2, re2.DOTALL)
        for i2 in range(0, len(cells2) - 2, 5):
            model2 = re2.sub(r'<[^>]+>', '', cells2[i2]).strip()
            inp_t = re2.sub(r'<[^>]+>', '', cells2[i2+1]).strip()
            out_t = re2.sub(r'<[^>]+>', '', cells2[i2+2]).strip()
            inp_m = re2.search(r'^([\d.]+)', inp_t.strip())
            out_m = re2.search(r'^([\d.]+)', out_t.strip())
            if inp_m and out_m and model2 and len(model2) > 1:
                inp2 = float(inp_m.group(1))
                out2 = float(out_m.group(1))
                if inp2 > 0 and out2 > 0 and inp2 < 100 and out2 < 1000:
                    if model2 not in ca_prices:
                        ca_prices[model2] = (round(inp2 * 1000, 4), round(out2 * 1000, 4))
        skip_ca = ["-ca","-search","-image","-audio","-realtime","moderation","embed","bge-","rerank","tts","whisper","dall","instruct-0","codex-ca","chat-latest-ca"]
        for mid2, (ii, oo) in ca_prices.items():
            if not any(s in mid2.lower() for s in skip_ca):
                ca_list.append(mid2)
    except Exception as e2:
        print("  ChatAnywhere fetch error:", str(e2)[:80], file=sys.stderr)
    if not ca_list:
        ca_list = ["gpt-4o","gpt-4o-mini","deepseek-chat","claude-sonnet-4-5","gemini-2.5-flash"]
    print("  ChatAnywhere:", len(ca_list), file=sys.stderr)

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
        if mid in di_prices:
            ii, oo, cc = di_prices[mid]
            _, _, _, tt, ss = dip(mid)
        else:
            ii, oo, cc, tt, ss = dip(mid)
        fam = get_family(mid)
        cards.append(make_card("deepinfra","DeepInfra","#7c3aed",Te(mid),ii,oo,cc,tt,ss,
                     "https://api.deepinfra.com/v1/openai/chat/completions","USD",family=fam,price_unit="per_1m"))
        all_models.append({"p":"deepinfra","n":mid,"i":ii,"o":oo,"cur":"USD"})

    # AiHubMix
    for mid in ahm_list:
        ii, oo, cc, tt, ss = ahmp(mid)
        fam = get_family(mid)
        cards.append(make_card("aihubmix","AiHubMix","#10b981",Te(mid),ii,oo,cc,tt,ss,
                     "https://api.aihubmix.com/v1/chat/completions","USD",family=fam,price_unit="per_1m"))
        all_models.append({"p":"aihubmix","n":mid,"i":ii,"o":oo,"cur":"USD"})

    # n1n.ai
    for mid in n1n_list:
        ii, oo = n1np(mid)
        fam = get_family(mid)
        cc = "128k"
        m = mid.lower()
        if "1m" in m or "1000k" in m: cc = "1M"
        elif "200k" in m: cc = "200k"
        elif "128k" in m: cc = "128k"
        elif "32k" in m: cc = "32k"
        elif "8k" in m: cc = "8k"
        tt = []
        if ii < 1: tt.append("便宜")
        elif ii < 10: tt.append("主力")
        else: tt.append("旗舰")
        if "r1" in m or "think" in m or "reason" in m: tt.append("推理")
        ss = "深度推理" if "推理" in tt else "日常对话"
        cards.append(make_card("n1n","n1n.ai","#f59e0b",Te(mid),ii,oo,cc,tt,ss,
                     "https://api.n1n.ai/v1/chat/completions","CNY",family=fam))
        all_models.append({"p":"n1n","n":mid,"i":ii,"o":oo,"cur":"CNY"})

    # AIGC2D
    for mid in aigc2d_list:
        ii, oo = aigc2dp(mid)
        fam = get_family(mid)
        cc = "128k"
        m = mid.lower()
        if "1m" in m or "1000k" in m: cc = "1M"
        elif "200k" in m: cc = "200k"
        elif "128k" in m: cc = "128k"
        elif "32k" in m: cc = "32k"
        elif "8k" in m: cc = "8k"
        tt = []
        if ii < 1: tt.append("便宜")
        elif ii < 10: tt.append("主力")
        else: tt.append("旗舰")
        if "r1" in m or "think" in m or "reason" in m: tt.append("推理")
        ss = "深度推理" if "推理" in tt else "日常对话"
        cards.append(make_card("aigc2d","AIGC2D","#8b5cf6",Te(mid),ii,oo,cc,tt,ss,
                     "https://api.aigc2d.com/v1/chat/completions","CNY",family=fam))
        all_models.append({"p":"aigc2d","n":mid,"i":ii,"o":oo,"cur":"CNY"})

    # ChatAnywhere
    for mid in ca_list:
        ii, oo = cap(mid)
        fam = get_family(mid)
        cc = "128k"
        m = mid.lower()
        if "1m" in m or "1000k" in m: cc = "1M"
        elif "200k" in m: cc = "200k"
        elif "128k" in m: cc = "128k"
        elif "32k" in m: cc = "32k"
        elif "8k" in m: cc = "8k"
        tt = []
        if ii < 1: tt.append("便宜")
        elif ii < 10: tt.append("主力")
        else: tt.append("旗舰")
        if "r1" in m or "think" in m or "reason" in m: tt.append("推理")
        ss = "深度推理" if "推理" in tt else "日常对话"
        cards.append(make_card("ca","ChatAnywhere","#06b6d4",Te(mid),ii,oo,cc,tt,ss,
                     "https://api.chatanywhere.org/v1/chat/completions","CNY",family=fam))
        all_models.append({"p":"ca","n":mid,"i":ii,"o":oo,"cur":"CNY"})

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

# ─── Telegram 通知（每次运行都发送）───
def send_telegram_notification(total_models, changes):
    """发送每日更新通知到 Telegram（无论是否有价格变动）"""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 构建纯文本消息（不用MarkdownV2，避免转义问题）
    lines = []
    lines.append("✅ 模型数据每日更新")
    lines.append(f"⏰ {now_str}")
    lines.append(f"📊 模型总数: {total_models}")
    lines.append("")
    
    if changes:
        lines.append(f"🔔 价格变动: {len(changes)} 个模型")
        for c in changes[:5]:  # 最多显示5个
            platform = c["p"]
            model = c["n"]
            old_i = c.get("old_i", 0); new_i = c.get("new_i", 0)
            
            if old_i == 0:
                trend_str = "🆕 新增"
            else:
                change_pct = ((new_i - old_i) / old_i) * 100
                if change_pct > 0:
                    trend_str = f"📈 +{change_pct:.1f}%"
                else:
                    trend_str = f"📉 {change_pct:.1f}%"
            
            lines.append(f"  • {model} ({platform})")
            lines.append(f"    ¥{old_i:.4f} → ¥{new_i:.4f} {trend_str}")
        
        if len(changes) > 5:
            lines.append(f"  ... 还有 {len(changes) - 5} 个")
    else:
        lines.append("✨ 价格无变动")
    
    lines.append("")
    lines.append("🌐 https://model.ai-selector.top")
    
    message = "\n".join(lines)
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True
        }).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        print("  Telegram notification sent", file=sys.stderr)
    except Exception as e:
        print("  Telegram notification failed:", e, file=sys.stderr)

# 每次运行都发送通知
send_telegram_notification(total, price_changes)

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
ahmc = cn("aihubmix")
n1nc = cn("n1n")
a2c = cn("aigc2d")
cac = cn("ca")

def tc(p): return sum(1 for c in cards if 'data-pt="' + p + '"' in c)
print("  Tier free:%d cheap:%d mid:%d high:%d ultra:%d" % (
    tc("free"),tc("cheap"),tc("mid"),tc("high"),tc("ultra")), file=sys.stderr)

now = datetime.now().strftime("%Y-%m-%d %H:%M")
WECHAT_QR = """/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgFBgcGBQgHBgcJCAgJDBMMDAsLDBgREg4THBgdHRsYGxofIywlHyEqIRobJjQnKi4vMTIxHiU2OjYwOiwwMTD/2wBDAQgJCQwKDBcMDBcwIBsgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDD/wAARCAOMA4wDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKA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FFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFAH/9n53zuAAAAAABzI7JahZd0RyLEJsyCkp7w="""

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
    '<button class="pt" data-p="deepinfra" style="--c:#7!c3aed;--bg:#f5f0ff">DeepInfra <span class="pc">' + str(dic) + '</span></button>'
    '<button class="pt" data-p="aihubmix" style="--c:#10b981;--bg:#ecfdf5">AiHubMix <span class="pc">' + str(ahmc) + '</span></button>'
    '<button class="pt" data-p="n1n" style="--c:#f59e0b;--bg:#fffbeb">n1n.ai <span class="pc">' + str(n1nc) + '</span></button>'
    '<button class="pt" data-p="aigc2d" style="--c:#8b5cf6;--bg:#f5f3ff">AIGC2D <span class="pc">' + str(a2c) + '</span></button>'
    '<button class="pt" data-p="ca" style="--c:#06b6d4;--bg:#ecfeff">ChatAnywhere <span class="pc">' + str(cac) + '</span></button>'
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
family_bar = '<div class="family-bar"><span class="family-lbl"></span>'
family_bar += '<button class="family-btn active" data-family="all">全部</button>'
for fam, cnt in top_families:
    if fam and fam != 'Other':
        family_bar += '<button class="family-btn" data-family="' + fam + '">' + fam + ' <span class="family-cnt">' + str(cnt) + '</span></button>'
family_bar += '</div>'

# ─── 标签筛选栏 ───
tag_list = ["免费额度","便宜","极便宜","旗舰","主力","推理","视觉","长上下文","开源","代码","图片生成","视频生成","蒸馏","轻量","最新版"]
tag_bar = '<div class="tag-bar"><span class="tag-lbl"></span>' + "".join(
    '<button class="tag-btn" data-tag="' + t + '">' + t + '</button>' for t in tag_list
) + '</div>'

# ─── 上下文长度筛选 ───
ctx_bar = (
    '<div class="ctx-filter-bar"><span class="ctx-lbl"></span>'
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
    '<div class="cross-search"><input type="text" id="crossSearchInput" placeholder="输入模型名搜索比价..." oninput="buildCrossPrice()"><button class="cross-search-clear" onclick="document.getElementById(\'crossSearchInput\').value=\'\';buildCrossPrice()">✕</button></div>'
    '<div class="cross-list" id="crossList"></div>'
    '</div>'
)

# ─── 月费计算器 (增强版) ───
# ─── Rate Limits 对比面板 ───
rl_panel = (
    '<div class="rl-panel" id="rlPanel">'
    '<div class="rl-title">&#9888; Rate Limits 对比</div>'
    '<div class="rl-note">各平台并发限制 (TPM/RPM)，避开上线后频繁报错的坑</div>'
    '<table class="rl-table"><tr><th>平台</th><th>TPM (tokens/min)</th><th>RPM (req/min)</th><th>并发限制</th></tr>'
    '<tr><td>阿里百炼</td><td>500,000</td><td>500</td><td><span class="rl-tag rl-tag-high">高</span></td></tr>'
    '<tr><td>硅基流动</td><td>200,000</td><td>100</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>月之暗面</td><td>320,000</td><td>30</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>智谱 AI</td><td>500,000</td><td>200</td><td><span class="rl-tag rl-tag-high">高</span></td></tr>'
    '<tr><td>火山引擎</td><td>500,000</td><td>500</td><td><span class="rl-tag rl-tag-high">高</span></td></tr>'
    '<tr><td>百度文心</td><td>300,000</td><td>300</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>腾讯混元</td><td>300,000</td><td>60</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>DeepSeek</td><td>1,000,000</td><td>30</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>OpenRouter</td><td>无限制</td><td>无限制</td><td><span class="rl-tag rl-tag-high">高</span></td></tr>'
    '<tr><td>Groq</td><td>6,000</td><td>30</td><td><span class="rl-tag rl-tag-low">低</span></td></tr>'
    '<tr><td>Together AI</td><td>200,000</td><td>60</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>Fireworks AI</td><td>200,000</td><td>100</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>Cohere</td><td>100,000</td><td>100</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>无问芯穹</td><td>100,000</td><td>60</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>Novita AI</td><td>100,000</td><td>60</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>DeepInfra</td><td>200,000</td><td>100</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>AiHubMix</td><td>200,000</td><td>60</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>n1n.ai</td><td>100,000</td><td>60</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>AIGC2D</td><td>100,000</td><td>60</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '<tr><td>ChatAnywhere</td><td>100,000</td><td>60</td><td><span class="rl-tag rl-tag-mid">中</span></td></tr>'
    '</table>'
    '<div class="rl-note">数据来源: 各平台官网文档 (2026年4月)。TPM=每分钟Token数, RPM=每分钟请求数。标注"低"的平台在生产环境需特别注意限流。</div>'
    '</div>'
)

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
.grid.list-view .mc{display:grid;align-items:center;grid-template-columns:12px 90px 200px 1fr 110px 70px 60px;gap:0 10px;padding:8px 14px}
.grid.list-view .mc .dot{position:static;grid-column:1}
.grid.list-view .mc .prov{margin:0;padding:0;grid-column:2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.grid.list-view .mc .mname{margin:0;grid-column:3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.grid.list-view .mc .tags{margin:0;grid-column:4;overflow:hidden;white-space:nowrap}
.grid.list-view .mc .prow{margin:0;grid-column:5}
.grid.list-view .mc .ctx-row{margin:0;grid-column:6}
.grid.list-view .mc .base-url{display:none}
.grid.list-view .mc .hint{display:none}
.grid.list-view .mc .card-actions{position:static;margin:0;grid-column:7}
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
.wechat-qr{margin-bottom:16px;padding:16px;background:var(--surface);border:1px solid var(--border);border-radius:12px;display:inline-block}
.qr-img{width:140px;height:140px;border-radius:8px;image-rendering:pixelated}
.qr-text{font-size:12px;color:var(--text2);margin-top:8px;font-weight:500}


/* 筛选分组 */
.fg{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:10px 12px;margin-bottom:10px;backdrop-filter:blur(8px)}
.fg-title{font-size:12px;font-weight:700;color:var(--accent);margin-bottom:6px;letter-spacing:.02em;text-transform:uppercase;border-bottom:1px solid var(--border);padding-bottom:4px}
.fg .pbar,.fg .ptbar,.fg .sbar,.fg .sort-bar,.fg .tag-bar,.fg .ctx-filter-bar,.fg .price-range-bar,.fg .family-bar{margin-bottom:4px}
.fg .rec-panel{margin-bottom:0;padding:8px 10px}
.fg .toolbar{margin-bottom:0}

/* 跨平台比价 + 月费计算器 同行 */
.side-panels{display:grid;grid-template-columns:1fr 1fr 1.2fr;gap:10px;margin-bottom:10px;align-items:stretch}
.side-panels .cross-panel{margin-bottom:0}.cross-search{display:flex;gap:4px;margin-bottom:8px}
.cross-search input{flex:1;padding:5px 8px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface2);color:var(--text);font-size:11px}
.cross-search input:focus{border-color:var(--accent);outline:none}
.cross-search-clear{padding:2px 6px;border:1px solid var(--border);border-radius:var(--radius);background:transparent;color:var(--text2);cursor:pointer;font-size:11px}
.cross-search-clear:hover{border-color:var(--accent);color:var(--accent)}
.side-panels .calc-panel{margin-bottom:0}
.side-panels .rl-panel{margin-bottom:0}

/* 分页 */
.pagination{display:flex;gap:6px;align-items:center;justify-content:center;padding:12px 0;flex-wrap:wrap}
.page-btn{padding:6px 12px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:12px;cursor:pointer;transition:all .2s;font-weight:500}
.page-btn:hover{border-color:var(--border-hi);color:var(--text)}
.page-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.page-info{font-size:11px;color:var(--text3);margin:0 8px}

/* 排序栏 */
.sort-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.sort-lbl{font-size:11px;color:var(--accent);font-weight:700;letter-spacing:.03em;text-transform:uppercase}
.sort-btn{padding:4px 10px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:11px;cursor:pointer;transition:all .2s;font-weight:500}
.sort-btn:hover{border-color:var(--border-hi);color:var(--text)}
.sort-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}

/* 标签筛选 */
.tag-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.tag-lbl{font-size:11px;color:var(--accent);font-weight:700;letter-spacing:.03em;text-transform:uppercase}
.tag-btn{padding:3px 8px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:10px;cursor:pointer;transition:all .2s;font-weight:500}
.tag-btn:hover{border-color:var(--border-hi);color:var(--text)}
.tag-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}

/* 家族筛选 */
.family-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.family-lbl{font-size:11px;color:var(--accent);font-weight:700;letter-spacing:.03em;text-transform:uppercase}
.family-btn{padding:3px 8px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:10px;cursor:pointer;transition:all .2s;font-weight:500}
.family-btn:hover{border-color:var(--border-hi);color:var(--text)}
.family-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}
.family-cnt{background:rgba(255,255,255,.12);border-radius:4px;padding:0 4px;font-size:8px;font-weight:600;margin-left:2px}
.family-btn:not(.active) .family-cnt{background:rgba(255,255,255,.06)}

/* 上下文筛选 */
.ctx-filter-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.ctx-lbl{font-size:11px;color:var(--accent);font-weight:700;letter-spacing:.03em;text-transform:uppercase}
.ctx-btn{padding:3px 8px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);font-size:10px;cursor:pointer;transition:all .2s;font-weight:500}
.ctx-btn:hover{border-color:var(--border-hi);color:var(--text)}
.ctx-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 0 12px var(--accent-glow)}

/* 价格区间筛选 */
.price-range-bar{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.pr-lbl{font-size:11px;color:var(--accent);font-weight:700;letter-spacing:.03em;text-transform:uppercase}
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
.cross-list{max-height:420px;overflow-y:auto}
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



/* ═══════════════════════════════════════════════════════════
   移动端适配
   ═══════════════════════════════════════════════════════════ */
@media(max-width:768px){
.main-layout{flex-direction:column}
.sidebar{width:100%;max-height:none;position:static;border-right:none;border-bottom:1px solid var(--border);padding:10px;display:none}
.sidebar.open{display:block}
.sidebar-toggle{display:flex}
.content-area{padding:10px}
/* 整体布局 */
.wrap{padding:0 10px 30px}
.hdr{padding:20px 8px 12px}
.hdr h1{font-size:20px;margin-bottom:4px}
.hdr p{font-size:10px;line-height:1.4}
.brow{gap:4px;margin-top:8px}
.bd{padding:2px 7px;font-size:9px;border-radius:16px}

/* 筛选栏 - 横向滚动，不换行 */
.pbar,.ptbar,.sbar,.sort-bar,.tag-bar,.ctx-filter-bar,.price-range-bar,.family-bar{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;padding:6px 0;gap:4px}
.side-panels{grid-template-columns:1fr}
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
.cross-list{max-height:300px}
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
.wechat-qr{padding:12px}
.qr-img{width:120px;height:120px}

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
/* ─── 左侧筛选栏 + 右侧内容 布局 ─── */
.main-layout{display:flex;gap:0;align-items:flex-start;width:100%}
.sidebar{width:220px;min-width:220px;max-width:220px;flex-shrink:0;position:sticky;top:0;max-height:100vh;overflow-y:auto;overflow-x:hidden;padding:12px 10px;background:var(--surface);border-right:1px solid var(--border);scrollbar-width:thin;scrollbar-color:var(--border) transparent}
.sidebar::-webkit-scrollbar{width:4px}
.sidebar::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.sidebar .fg{background:none;border:none;padding:0;margin-bottom:10px;border-radius:0}
.sidebar .fg-title{font-size:11px;font-weight:700;color:var(--accent);margin-bottom:5px;letter-spacing:.03em;text-transform:uppercase;padding-bottom:4px;border-bottom:1px solid var(--border)}
.sidebar .pbar,.sidebar .sbar,.sidebar .ptbar,.sidebar .tag-bar,.sidebar .ctx-filter-bar,.sidebar .family-bar{flex-wrap:wrap;overflow-x:visible;padding:4px 0;margin-bottom:2px}
.sidebar .sort-bar{flex-wrap:wrap;margin-bottom:2px}
.sidebar .toolbar{flex-wrap:wrap;gap:4px}
.sidebar .toolbar-left,.sidebar .toolbar-right{flex-wrap:wrap;gap:3px}
.sidebar .price-range-bar{flex-wrap:wrap;gap:4px}
.sidebar .price-range-bar input{width:60px}
.sidebar .rec-panel{padding:8px;margin-bottom:8px}
.sidebar .rec-options{flex-wrap:wrap;gap:3px}
.sidebar .rec-btn{font-size:9px;padding:3px 6px}
.sidebar table,.sidebar .rl-table,.sidebar .calc-table,.sidebar .cross-list{max-width:100%}
.sidebar .rl-note,.sidebar .calc-note{font-size:9px}
/* ─── 折叠分组 ─── */
.fg-collapsible .fg-title{cursor:pointer;user-select:none;display:flex;align-items:center;justify-content:space-between}
.fg-collapsible .fg-title:hover{opacity:.8}
.fg-arrow{font-size:10px;transition:transform .2s}
.fg-collapsed .fg-body{display:none}
.fg-collapsed .fg-arrow{transform:rotate(0deg)}
.fg-collapsible:not(.fg-collapsed) .fg-arrow{transform:rotate(90deg)}
.clear-filter-btn{width:100%;padding:6px 0;margin-bottom:8px;border:1px solid var(--border);border-radius:var(--radius);background:transparent;color:var(--text2);font-size:11px;cursor:pointer;transition:all .15s}
.clear-filter-btn:hover{border-color:var(--accent);color:var(--accent);background:rgba(99,102,241,.06)}

.sidebar .side-panels{display:flex;flex-direction:column;gap:8px;grid-template-columns:none}
.sidebar .cross-panel,.sidebar .calc-panel,.sidebar .rl-panel{flex:none;width:100%}
.sidebar .cross-list{max-height:200px}
.content-area{flex:1;min-width:0;padding:12px 14px}
.content-area .srow{margin-bottom:10px}
.content-area .side-panels{margin-bottom:10px}
.content-area .filter-count{margin-bottom:6px}
.sidebar-toggle{display:none;position:fixed;top:10px;left:10px;z-index:100;width:36px;height:36px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:18px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.2);align-items:center;justify-content:center}

/* ─── Rate Limits 面板 ─── */
.rl-panel{background:var(--surface);border:1px solid rgba(251,146,60,.12);border-radius:var(--radius-lg);padding:14px;margin-bottom:14px;backdrop-filter:blur(8px)}
.rl-title{font-size:13px;font-weight:600;color:#fb923c;margin-bottom:6px}
.rl-table{width:100%;border-collapse:collapse;font-size:10px;margin-top:8px}
.rl-table th{background:var(--surface2);padding:5px 6px;text-align:left;font-weight:600;color:var(--text2);border-bottom:1px solid var(--border)}
.rl-table td{padding:4px 6px;border-bottom:1px solid var(--border);color:var(--text2)}
.rl-table tr:hover td{background:var(--surface2)}
.rl-tag{display:inline-block;padding:1px 5px;border-radius:4px;font-size:9px;font-weight:600}
.rl-tag-low{background:#fef3c7;color:#92400e}
.rl-tag-mid{background:#dbeafe;color:#1e40af}
.rl-tag-high{background:#dcfce7;color:#166534}
.rl-note{font-size:10px;color:var(--text3);margin-top:6px;line-height:1.4}

/* ─── Token 计价器模态框 ─── */
.tk-modal{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;z-index:9997;opacity:0;pointer-events:none;transition:opacity .25s}
.tk-modal.show{opacity:1;pointer-events:auto}
.tk-modal-content{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);max-width:720px;width:92%;max-height:85vh;overflow:auto;box-shadow:0 24px 80px rgba(0,0,0,.5);transform:translateY(20px);transition:transform .25s}
.tk-modal.show .tk-modal-content{transform:translateY(0)}
.tk-modal-header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--border)}
.tk-modal-title{font-size:14px;font-weight:600;color:var(--accent)}
.tk-modal-close{background:none;border:none;font-size:20px;cursor:pointer;color:var(--text2);padding:4px 8px}
.tk-modal-close:hover{color:var(--text)}
.tk-modal-body{padding:16px}
.tk-textarea{width:100%;min-height:120px;max-height:300px;padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--surface2);color:var(--text);font-size:12px;font-family:monospace;resize:vertical;margin-bottom:10px}
.tk-textarea:focus{outline:none;border-color:var(--accent)}
.tk-stats{display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap}
.tk-stat{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:8px 12px;flex:1;min-width:100px}
.tk-stat-label{font-size:10px;color:var(--text3);margin-bottom:2px}
.tk-stat-value{font-size:18px;font-weight:700;color:var(--accent)}
.tk-btn{padding:6px 14px;border-radius:8px;border:none;font-size:11px;font-weight:600;cursor:pointer;background:var(--accent);color:#fff;transition:all .2s;margin-right:6px}
.tk-btn:hover{box-shadow:0 0 16px var(--accent-glow)}
.tk-btn-sec{background:var(--surface2);color:var(--text2);border:1px solid var(--border)}
.tk-result-table{width:100%;border-collapse:collapse;font-size:10px;margin-top:10px}
.tk-result-table th{background:var(--surface2);padding:5px 6px;text-align:left;font-weight:600;color:var(--text2);border-bottom:1px solid var(--border)}
.tk-result-table td{padding:4px 6px;border-bottom:1px solid var(--border)}
.tk-result-table tr:hover td{background:var(--surface2)}
.tk-cheapest{color:#22c55e;font-weight:700}
.tk-model-row{display:flex;gap:6px;align-items:center;margin-bottom:6px;flex-wrap:wrap}
.tk-model-input{flex:1;min-width:200px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--surface2);color:var(--text);font-size:11px}
.tk-model-input:focus{outline:none;border-color:var(--accent)}

/* ─── TTFB 测速面板 ─── */
.ping-modal{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;z-index:9996;opacity:0;pointer-events:none;transition:opacity .25s}
.ping-modal.show{opacity:1;pointer-events:auto}
.ping-modal-content{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);max-width:680px;width:92%;max-height:85vh;overflow:auto;box-shadow:0 24px 80px rgba(0,0,0,.5);transform:translateY(20px);transition:transform .25s}
.ping-modal.show .ping-modal-content{transform:translateY(0)}
.ping-modal-header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--border)}
.ping-modal-title{font-size:14px;font-weight:600;color:#22d3ee}
.ping-modal-close{background:none;border:none;font-size:20px;cursor:pointer;color:var(--text2);padding:4px 8px}
.ping-modal-close:hover{color:var(--text)}
.ping-modal-body{padding:16px}
.ping-model-select{width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:8px;background:var(--surface2);color:var(--text);font-size:12px;margin-bottom:10px}
.ping-btn{padding:6px 14px;border-radius:8px;border:none;font-size:11px;font-weight:600;cursor:pointer;background:#22d3ee;color:#000;transition:all .2s;margin-right:6px}
.ping-btn:hover{box-shadow:0 0 16px rgba(34,211,238,.4)}
.ping-btn:disabled{opacity:.5;cursor:not-allowed}
.ping-result-list{margin-top:10px}
.ping-result-item{display:flex;align-items:center;gap:8px;padding:6px 8px;border-bottom:1px solid var(--border);font-size:11px}
.ping-platform{min-width:80px;font-weight:500;color:var(--text)}
.ping-ms{min-width:60px;font-weight:700}
.ping-ms-fast{color:#22c55e}
.ping-ms-mid{color:#eab308}
.ping-ms-slow{color:#ef4444}
.ping-ms-timeout{color:var(--text3);font-style:italic}
.ping-bar-wrap{flex:1;height:6px;background:var(--surface2);border-radius:3px;overflow:hidden}
.ping-bar{height:100%;border-radius:3px;transition:width .3s}
.ping-status{font-size:9px;color:var(--text3);min-width:50px;text-align:right}
.ping-spinner{display:inline-block;width:12px;height:12px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite;margin-right:4px;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}

/* ─── 工具栏新按钮 ─── */
.tool-btn-extended{margin-left:4px}

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

// ─── 从 models_data.json 动态加载模型数据 ───
var modelsDataLoaded = false;
function renderModelsFromJSON(data) {
    var grid = document.getElementById('grid');
    if (!grid || !data || !data.models) return false;
    // 清空现有卡片
    grid.innerHTML = '';
    var models = data.models;
    var meta = data.meta || {};
    // 更新汇率
    if (meta.usd_to_cny) USD_TO_CNY = meta.usd_to_cny;
    // 更新数据说明中的时间
    var timeEls = document.querySelectorAll('.ftr p, .snote');
    // 动态生成卡片
    for (var i = 0; i < models.length; i++) {
        var m = models[i];
        var pid = m.platform_id;
        var pname = m.platform_name;
        var pc = m.platform_color;
        if(!pc && data.platforms && data.platforms[pid]) pc = data.platforms[pid].color;
        if(!pc) pc = '#6366f1';
        var mname = m.name;
        var inp = m.input_price;
        var out = m.output_price;
        var ctx = m.context;
        var tags = m.tags || [];
        var scen = m.scene || '日常对话';
        var fam = m.family || '';
        var cur = m.currency || 'CNY';
        var pu = m.price_unit || 'per_token';
        var baseUrl = m.base_url || '';

        // 价格分级
        var pt = 'mid';
        var inpF = parseFloat(inp) || 0, outF = parseFloat(out) || 0;
        if (inpF === 0 && outF === 0) pt = 'free';
        else if (cur === 'USD' && pu === 'per_token') { var p = inpF * 1e6; pt = p < 0.1 ? 'cheap' : p < 10 ? 'mid' : p < 100 ? 'high' : 'ultra'; }
        else { pt = inpF < 0.1 ? 'cheap' : inpF < 10 ? 'mid' : inpF < 100 ? 'high' : 'ultra'; }

        // data-inp/data-out
        var inpS, outS;
        if (pu === 'per_1m' && cur === 'USD') { inpS = inpF / 1e6; outS = outF / 1e6; }
        else { inpS = inpF; outS = outF; }

        // 上下文数值
        var ctxNum = ctx.replace(/[^\d]/g, '') || '0';

        // 标签 HTML
        var tagMap = {'免费':'free','免费额度':'free','便宜':'cheap','极便宜':'cheap','性价比':'cheap',
            '旗舰':'hot','主力':'hot','最新版':'hot','2025新':'hot','2026新':'hot',
            '视觉':'vision','推理':'reason','长上下文':'long','超长上下文':'long',
            '开源':'other','代码':'other','图片生成':'other','视频生成':'other',
            '快速':'other','高性能':'hot','Pro订阅':'other','蒸馏':'other',
            '轻量':'other','已下线':'other','即将下线':'other','价格待确认':'other',
            '语音':'other','TTS':'other','ASR':'other','向量':'other','排序':'other',
            'OCR':'other','多模态':'vision','Turbo':'hot','降价后':'cheap','降价90%':'cheap',
            '超低价':'cheap','超便宜':'cheap','编程':'other','智能路由':'other',
            '满血版':'hot','价格变动':'other','涨价':'hot','降价':'cheap','免费':'free'};
        var tagsHtml = '';
        for (var ti = 0; ti < tags.length; ti++) {
            var tc = tagMap[tags[ti]] || 'other';
            tagsHtml += '<span class="tg tg-' + tc + '">' + tags[ti] + '</span>';
        }

        // 价格徽章
        var priceHtml = '';
        if (cur === 'CNY') {
            if (inpF === 0 && outF === 0) priceHtml = '<span class="price-badge price-free">免费额度</span>';
            else if (inpF === outF) { var cc2 = inpF < 1 ? 'price-cheap' : inpF < 10 ? 'price-mid' : inpF < 100 ? 'price-high' : 'price-ultra'; priceHtml = '<span class="price-badge ' + cc2 + '">¥' + inpF.toFixed(2) + '/M</span>'; }
            else priceHtml = '<span class="price-badge price-mid">IN:¥' + inpF.toFixed(2) + ' OUT:¥' + outF.toFixed(2) + '/M</span>';
        } else {
            var pI = pu === 'per_token' ? inpF * 1e6 : inpF;
            var pO = pu === 'per_token' ? outF * 1e6 : outF;
            if (inpF === 0 && outF === 0) priceHtml = '<span class="price-badge price-free">$0 (免费)</span>';
            else if (inpF === outF) { var cc3 = pI < 0.1 ? 'price-free' : pI < 1 ? 'price-cheap' : pI < 10 ? 'price-mid' : pI < 100 ? 'price-high' : 'price-ultra'; priceHtml = '<span class="price-badge ' + cc3 + '">$' + pI.toFixed(2) + '/1M</span>'; }
            else priceHtml = '<span class="price-badge price-mid">IN:$' + pI.toFixed(1) + ' OUT:$' + pO.toFixed(1) + '/1M</span>';
        }

        // 上下文条
        var ctxBarW = Math.min(100, (parseInt(ctxNum) || 0) / 1000);

        // 家族属性
        var famAttr = fam ? ' data-family="' + fam + '"' : '';

        // 构建卡片 HTML
        var cardHtml = '<div class="mc" style="--c:' + pc + '" data-s="' + scen + '" data-p="' + pid + '" data-pt="' + pt + '" '
            + 'data-inp="' + inpS + '" data-out="' + outS + '" data-cur="' + cur + '" data-pu="' + pu + '" '
            + 'data-ctx="' + ctxNum + '" data-ctx-display="' + ctx + '" ' + famAttr + ' '
            + 'onclick="showCodeModal(\'' + baseUrl + '\',\'' + mname.replace(/'/g, "\\'") + '\',\'' + pid + '\')">'
            + '<div class="dot"></div><div class="prov">' + pname + '</div>'
            + '<div class="mname">' + mname + '</div><div class="tags">' + tagsHtml + '</div>'
            + '<div class="prow">' + priceHtml + '</div>'
            + '<div class="ctx-row"><span class="ctx">上下文: ' + ctx + '</span>'
            + '<div class="ctx-bar-wrap"><div class="ctx-bar" style="width:' + ctxBarW + '%"></div></div></div>'
            + '<div class="base-url">' + baseUrl + '</div>'
            + '<div class="hint">点击查看接入代码</div>'
            + '<div class="card-actions">'
            + '<span class="fav-btn" onclick="event.stopPropagation();toggleFav(this)" title="收藏">&#9734;</span>'
            + '<div class="cb-wrap"><input type="checkbox" class="mc-cb" onclick="event.stopPropagation();toggleSel(this)"><label class="cb-lbl">对比</label></div>'
            + '</div></div>';

        grid.insertAdjacentHTML('beforeend', cardHtml);
    }

    // 更新模型计数
    var bdEls = document.querySelectorAll('.bd');
    if (bdEls.length > 0) bdEls[0].innerHTML = '&#128202; ' + models.length + ' 个模型';
    var fcEl = document.querySelector('.filter-count');
    if (fcEl) fcEl.innerHTML = '显示 <strong>' + models.length + '</strong> / ' + models.length + ' 个模型';

    // 更新平台筛选栏计数
    if (meta.platform_counts) {
        var pc2 = meta.platform_counts;
        document.querySelectorAll('.pt').forEach(function(b) {
            var p = b.dataset.p;
            var span = b.querySelector('.pc');
            if (span && pc2[p]) span.textContent = pc2[p];
        });
    }

    modelsDataLoaded = true;
    return true;
}

// 初始化
document.addEventListener('DOMContentLoaded',function(){
// ─── 尝试从 models_data.json 动态加载 ───
fetch('models_data.json').then(function(r){return r.json();}).then(function(data){
    if(data && data.models && data.models.length>0){
        renderModelsFromJSON(data);
        filter();
    }
}).catch(function(){
    // JSON 加载失败，使用 HTML 中已有的硬编码卡片
});

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
var pu2=c.dataset.pu||'per_token';
var mul=cur==='USD'?(pu2==='per_1m'?1:1e6):1;
var cnyInp=cur==='USD'?inp*mul*USD_TO_CNY:inp;
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
var cInp=cur==='USD'?inp*mul*USD_TO_CNY:inp;
if(cInp<adv.priceMin)sh=false;
}
if(adv.priceMax!==null){
var cInp2=cur==='USD'?inp*mul*USD_TO_CNY:inp;
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
var PAGE_SIZE=66;
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
var pu=c.dataset.pu||'per_token';
if(curCur==='CNY'){
if(cur==='USD'){
var mul=pu==='per_1m'?1:1e6;
var cnyInp=inp*mul*USD_TO_CNY;
var cnyOut=out*mul*USD_TO_CNY;
prow.innerHTML=makeCNYBadge(cnyInp,cnyOut);
}else{
prow.innerHTML=makeCNYBadge(inp,out);
}
}else{
if(cur==='CNY'){
var usdInp=inp/USD_TO_CNY/1e6;
var usdOut=out/USD_TO_CNY/1e6;
prow.innerHTML=makeUSDBadge(usdInp,usdOut);
}else{
var mul2=pu==='per_1m'?1:1e6;
prow.innerHTML=makeUSDBadge(inp*mul2,out*mul2);
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
// 搜索过滤
var crossQ=(document.getElementById('crossSearchInput')||{}).value||'';
crossQ=crossQ.trim().toLowerCase();
// 只显示在2个以上不同平台出现的模型
var groups=Object.values(modelMap).filter(function(g){
var pids={};g.forEach(function(m){pids[m.pid]=1;});
var ok=Object.keys(pids).length>=2&&g.length<=15;
if(ok&&crossQ){ok=g[0].baseName.toLowerCase().indexOf(crossQ)!==-1;}
return ok;
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
groups.forEach(function(g){
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
document.getElementById("crossPanel").style.display="block";
document.getElementById("crossList").innerHTML='<div style="padding:8px;font-size:12px;color:var(--text3)">未找到匹配的跨平台模型</div>';
}
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


// ═══════════════════════════════════════════════════════════
// 真实文本计价器
// ═══════════════════════════════════════════════════════════
function showTokenCalc(){
    var m=document.getElementById('tkModal');
    if(m)m.classList.add('show');
}
function closeTokenCalc(){
    var m=document.getElementById('tkModal');
    if(m)m.classList.remove('show');
}

// GPT-4 Cl100k 近似分词器
function estimateTokens(text){
    if(!text)return 0;
    var len=text.length;
    var cjk=0;
    for(var i=0;i<len;i++){
        var c=text.charCodeAt(i);
        if((c>=0x4E00&&c<=0x9FFF)||(c>=0x3400&&c<=0x4DBF)||(c>=0x3000&&c<=0x303F)||(c>=0xFF00&&c<=0xFFEF))cjk++;
    }
    var nonCjk=len-cjk;
    return Math.ceil(nonCjk/4+cjk/1.5);
}

function calcTokens(){
    var text=document.getElementById('tkText').value;
    if(!text.trim()){showTip('请先输入文本',false);return;}
    var tokens=estimateTokens(text);
    var chars=text.length;
    var lines=text.split('\n').length;
    var estOutTokens=Math.round(tokens*0.4);

    var statsHtml='<div class="tk-stat"><div class="tk-stat-label">字符数</div><div class="tk-stat-value">'+chars.toLocaleString()+'</div></div>'
        +'<div class="tk-stat"><div class="tk-stat-label">行数</div><div class="tk-stat-value">'+lines.toLocaleString()+'</div></div>'
        +'<div class="tk-stat"><div class="tk-stat-label">输入 Token</div><div class="tk-stat-value">~'+tokens.toLocaleString()+'</div></div>'
        +'<div class="tk-stat"><div class="tk-stat-label">预估输出 Token</div><div class="tk-stat-value">~'+estOutTokens.toLocaleString()+'</div></div>';
    document.getElementById('tkStats').innerHTML=statsHtml;

    var cs=document.querySelectorAll('.mc');
    var results=[];
    cs.forEach(function(c){
        var inp=parseFloat(c.dataset.inp)||0;
        var out=parseFloat(c.dataset.out)||0;
        var cur=c.dataset.cur||'CNY';
        var pid=c.dataset.p||'';
        var mname=(c.querySelector('.mname')||{}).textContent||'';
        var pname=(c.querySelector('.prov')||{}).textContent||'';
        if(inp===0&&out===0)return;
        var pu=c.dataset.pu||'per_token';
        var cost;
        if(cur==='CNY'){
            cost=(inp*tokens+out*estOutTokens)/1e6;
        }else{
            var mul=pu==='per_1m'?1e-6:1;
            cost=(inp*tokens+out*estOutTokens)*mul;
        }
        results.push({pid:pid,mname:mname,pname:pname,cost:cost,cur:cur});
    });

    results.sort(function(a,b){return a.cost-b.cost;});
    var minCost=results.length>0?results[0].cost:0;

    var html='<table class="tk-result-table"><tr><th>#</th><th>平台</th><th>模型</th><th>预估花费</th></tr>';
    var shown=0;
    for(var i=0;i<results.length&&shown<30;i++){
        var r=results[i];
        var costStr;
        if(r.cur==='CNY')costStr='¥'+r.cost.toFixed(4);
        else costStr='$'+r.cost.toFixed(4);
        var cheapest=r.cost===minCost?'tk-cheapest':'';
        html+='<tr><td>'+(i+1)+'</td><td>'+r.pname+'</td><td class="'+cheapest+'">'+r.mname+'</td><td class="'+cheapest+'">'+costStr+'</td></tr>';
        shown++;
    }
    html+='</table>';
    if(results.length>30)html+='<div style="font-size:10px;color:var(--text3);margin-top:4px">显示前30个最便宜的，共'+results.length+'个模型</div>';
    document.getElementById('tkResult').innerHTML=html;
}

function clearTokenCalc(){
    document.getElementById('tkText').value='';
    document.getElementById('tkStats').innerHTML='';
    document.getElementById('tkResult').innerHTML='';
}

// ═══════════════════════════════════════════════════════════
// TTFB 测速（搜索模型名 → 自动测所有平台）
// ═══════════════════════════════════════════════════════════
var pingSelectedModel='';

function showPingModal(){
    var m=document.getElementById('pingModal');
    if(m)m.classList.add('show');
}
function closePingModal(){
    var m=document.getElementById('pingModal');
    if(m)m.classList.remove('show');
}

function updatePingSuggestions(){
    var q=(document.getElementById('pingModelInput').value||'').toLowerCase().trim();
    var div=document.getElementById('pingSuggestions');
    if(!q||q.length<2){div.innerHTML='';return;}
    // 收集所有匹配的模型名（去重）
    var cs=document.querySelectorAll('.mc');
    var modelNames=[];
    var seenName={};
    cs.forEach(function(c){
        var mname=(c.querySelector('.mname')||{}).textContent||'';
        var key=mname.toLowerCase();
        if(seenName[key])return;
        if(key.indexOf(q)===-1)return;
        seenName[key]=1;
        // 统计该模型在多少个平台可用
        var platformCount=0;
        cs.forEach(function(c2){
            var n2=(c2.querySelector('.mname')||{}).textContent||'';
            if(n2===mname)platformCount++;
        });
        modelNames.push({name:mname,count:platformCount});
    });
    modelNames.sort(function(a,b){return b.count-a.count;});
    var html='';
    var count=0;
    modelNames.forEach(function(item){
        if(count>=10)return;
        html+='<div style="display:inline-block;padding:3px 8px;margin:2px;border-radius:6px;border:1px solid var(--border);font-size:10px;cursor:pointer;background:var(--surface2);color:var(--text)" onclick="selectPingModel(\''+item.name.replace(/'/g,"\\'")+'\')">'+item.name+' <span style="color:var(--text3)">('+item.count+'平台)</span></div>';
        count++;
    });
    div.innerHTML=html||'<span style="font-size:10px;color:var(--text3)">未找到匹配模型</span>';
}

function selectPingModel(name){
    pingSelectedModel=name;
    document.getElementById('pingModelInput').value=name;
    document.getElementById('pingSuggestions').innerHTML='';
}

function startPing(){
    if(!pingSelectedModel){showTip('请先输入模型名',false);return;}
    // 收集所有平台中该模型的接口
    var cs=document.querySelectorAll('.mc');
    var endpoints=[];
    var seen={};
    cs.forEach(function(c){
        var mname=(c.querySelector('.mname')||{}).textContent||'';
        if(mname!==pingSelectedModel)return;
        var pname=(c.querySelector('.prov')||{}).textContent||'';
        var baseUrl=(c.querySelector('.base-url')||{}).textContent||'';
        var key=pname+baseUrl;
        if(seen[key])return;
        seen[key]=1;
        endpoints.push({pname:pname,baseUrl:baseUrl});
    });

    if(endpoints.length===0){showTip('未找到该模型的接口',false);return;}

    var btn=document.getElementById('pingStartBtn');
    btn.disabled=true;
    btn.innerHTML='<span class="ping-spinner"></span>测速中...';

    var listDiv=document.getElementById('pingResultList');
    listDiv.innerHTML='<div style="font-size:11px;color:var(--text3)">正在测试 '+endpoints.length+' 个平台的 '+pingSelectedModel+'...</div>';

    var results=[];
    var done=0;
    var total=endpoints.length;

    endpoints.forEach(function(ep,idx){
        var url=ep.baseUrl;
        var body=JSON.stringify({model:pingSelectedModel,messages:[{role:"user",content:"hi"}],max_tokens:1});
        var start=performance.now();
        var timeoutId;

        var controller=new AbortController();
        timeoutId=setTimeout(function(){controller.abort();},8000);

        fetch(url,{
            method:'POST',
            headers:{'Content-Type':'application/json','Authorization':'Bearer pk-test'},
            body:body,
            signal:controller.signal
        }).then(function(resp){
            clearTimeout(timeoutId);
            var ttfb=Math.round(performance.now()-start);
            // 401/403/429: TTFB仍然有效（网络通了，只是认证失败）
            var st=(resp.status>=200&&resp.status<300)||resp.status===401||resp.status===403||resp.status===429||resp.status===400?'ok':'error';
            results.push({pname:ep.pname,ms:ttfb,status:st});
        }).catch(function(err){
            clearTimeout(timeoutId);
            var ttfb=Math.round(performance.now()-start);
            if(err.name==='AbortError'){
                results.push({pname:ep.pname,ms:-1,status:'timeout'});
            }else{
                results.push({pname:ep.pname,ms:ttfb,status:'error'});
            }
        }).finally(function(){
            done++;
            if(done===total){
                renderPingResults(results);
                btn.disabled=false;
                btn.innerHTML='开始测速';
            }else{
                listDiv.innerHTML='<div style="font-size:11px;color:var(--text3)">已测试 '+done+'/'+total+'...</div>';
            }
        });
    });
}

function renderPingResults(results){
    results.sort(function(a,b){
        if(a.status!=='ok'&&b.status==='ok')return 1;
        if(a.status==='ok'&&b.status!=='ok')return -1;
        return a.ms-b.ms;
    });

    var maxMs=0;
    results.forEach(function(r){if(r.ms>0&&r.ms>maxMs)maxMs=r.ms;});
    if(maxMs===0)maxMs=1000;

    var html='';
    results.forEach(function(r,i){
        var msClass='ping-ms-mid';
        var barColor='#eab308';
        var barW=0;
        if(r.status==='ok'){
            if(r.ms<500){msClass='ping-ms-fast';barColor='#22c55e';}
            else if(r.ms>2000){msClass='ping-ms-slow';barColor='#ef4444';}
            barW=Math.min(100,(r.ms/maxMs)*100);
        }
        html+='<div class="ping-result-item">'
            +'<span class="ping-platform">'+r.pname+'</span>';
        if(r.status==='ok'){
            html+='<span class="ping-ms '+msClass+'">'+r.ms+'ms</span>';
        }else if(r.status==='timeout'){
            html+='<span class="ping-ms ping-ms-timeout">超时</span>';
        }else{
            html+='<span class="ping-ms ping-ms-timeout">错误</span>';
        }
        html+='<div class="ping-bar-wrap"><div class="ping-bar" style="width:'+barW+'%;background:'+barColor+'"></div></div>';
        if(i===0&&r.status==='ok')html+='<span style="font-size:9px;color:#22c55e;font-weight:700">最快</span>';
        else html+='<span style="font-size:9px;color:var(--text3)">'+(i+1)+'</span>';
        html+='</div>';
    });

    document.getElementById('pingResultList').innerHTML=html;
}

function clearPingResult(){
    document.getElementById('pingResultList').innerHTML='';
    pingSelectedModel='';
    pingBaseUrl='';
    document.getElementById('pingModelInput').value='';
    document.getElementById('pingSuggestions').innerHTML='';
}


function toggleFg(el){
    var fg=el.parentElement;
    fg.classList.toggle('fg-collapsed');
    var arrow=el.querySelector('.fg-arrow');
    if(fg.classList.contains('fg-collapsed')){arrow.textContent='▸';}
    else{arrow.textContent='▾';}
}
function clearAllFilters(){
    document.getElementById('si').value='';
    document.querySelectorAll('.pt.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.pt')[0].classList.add('active');
    document.querySelectorAll('.pt-filter.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.pt-filter')[0].classList.add('active');
    document.querySelectorAll('.sc.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.sc')[0].classList.add('active');
    document.querySelectorAll('.family-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.family-btn')[0].classList.add('active');
    document.querySelectorAll('.tag-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.ctx-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.ctx-btn')[0].classList.add('active');
    document.querySelectorAll('.sort-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.sort-btn')[0].classList.add('active');
    document.querySelectorAll('.cur-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.cur-btn')[0].classList.add('active');
    curP='all';curPT='all';curS='all';curFamily='all';curCtx='all';curSort='default';curTags=[];curCur='CNY';
    var pm=document.getElementById('priceMin');if(pm)pm.value='';
    var px=document.getElementById('priceMax');if(px)px.value='';
    filter();updatePrices();
}
function toggleSidebar(){
    var sb=document.getElementById('sidebar');
    if(sb)sb.classList.toggle('open');
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

    # ─── 左侧筛选栏 + 右侧内容 布局 ───
    '<button class="sidebar-toggle" onclick="toggleSidebar()">&#9776;</button>\n'
    '<div class="main-layout">\n'
    # ─── 左侧 Sidebar ───
    '<div class="sidebar" id="sidebar">\n'
    # 清除筛选按钮
    '<button class="clear-filter-btn" onclick="clearAllFilters()">✕ 清除筛选</button>\n'
    '<div class="srow"><input id="si" type="text" placeholder="搜索模型..." oninput="filter()" onkeydown="if(event.key===\'Escape\'){this.value=\'\';filter()}" style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface2);color:var(--text);font-size:12px" onfocus="this.style.borderColor=\'var(--accent)\'" onblur="this.style.borderColor=\'var(--border)\'"></div>\n'
    # 平台（默认折叠）
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">算力供应商 <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body"><div class="pbar">' + tabs_bar + '</div></div>\n'
    '</div>\n'
    # 家族（默认折叠）
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">模型家族 <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body">' + family_bar + '</div>\n'
    '</div>\n'
    # 标签（默认折叠）
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">标签 <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body">' + tag_bar + '</div>\n'
    '</div>\n'
    # 上下文（默认折叠）
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">上下文 <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body">' + ctx_bar + '</div>\n'
    '</div>\n'
    # 用途（默认折叠）
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">用途 <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body"><div class="sbar">' + scen_bar + '</div>' + recommend_panel + '</div>\n'
    '</div>\n'
    # 价格（默认折叠）
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">价格 <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body"><div class="ptbar">' + pt_bar + '</div>' + price_range_bar + '<div class="sort-bar">' + sort_bar + '</div></div>\n'
    '</div>\n'
    # 工具（默认折叠）
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">工具 <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body"><div class="toolbar" style="flex-wrap:wrap;gap:4px">\n'
    '<div class="cur-switch"><span style="font-size:11px;color:#64748b">货币</span>\n'
    '<button class="cur-btn active" data-cur="CNY">¥</button>\n'
    '<button class="cur-btn" data-cur="USD">$</button>\n'
    '</div>\n'
    '<button class="tool-btn" id="listBtn" onclick="toggleView()">&#9776; 列表</button>\n'
    '<button class="tool-btn" onclick="toggleDark()">&#9728; 亮色</button>\n'
    '<button class="tool-btn" onclick="showTokenCalc()">&#128270; 计价</button>\n'
    '<button class="tool-btn" onclick="showPingModal()">&#9889; 测速</button>\n'
    '</div></div>\n'
    '</div>\n'
    # 侧面板（默认折叠）
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">跨平台比价 <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body">' + crossprice_panel + '</div>\n'
    '</div>\n'
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">月费计算器 <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body">' + calc_panel + '</div>\n'
    '</div>\n'
    '<div class="fg fg-collapsible fg-collapsed">\n'
    '<div class="fg-title" onclick="toggleFg(this)">⚠ Rate Limits <span class="fg-arrow">▸</span></div>\n'
    '<div class="fg-body">' + rl_panel + '</div>\n'
    '</div>\n'
    '</div>\n'  # /sidebar
    # ─── 右侧内容区 ───
    '<div class="content-area">\n'
    + cmp_panel + '\n'

    '<div class="filter-count" id="filterCount">显示 <strong>' + str(total) + '</strong> / ' + str(total) + ' 个模型</div>\n'
        '<div class="loading" id="ld"><div class="sp"></div>加载中...</div>\n'
    '<div class="grid" id="grid">\n'
)

FTR = (
    '</div>\n'
    '</div>\n'
    '</div>\n'
    '\n</div>\n'
    '<div class="pagination" id="pagination"></div>\n'
    '<div class="empty" id="empty" style="display:none">没有找到符合条件的模型</div>\n'
    '</div>\n'
    '<div class="ftr">'
    '<div class="wechat-qr">'
    '<img src="data:image/jpeg;base64,' + WECHAT_QR + '" alt="微信二维码" class="qr-img">'
    '<p class="qr-text">扫码加微信 &middot; 获取最新AI模型资讯</p>'
    '</div>'
    '<p>&#128202; 数据来源：各平台 API 实时拉取 + 官网公告（更新时间：' + now + '）</p>'
    '<p>OpenRouter 显示原始美元价格 &middot; 国内平台显示人民币价格 &middot; 点击卡片复制接入方式</p>'
    '<p>快捷键: / 搜索 | Esc 清空 | D 暗色 | V 视图 | 1-9 切换平台</p>'
    '<p><a href="https://github.com/k-goz/model-selector" target="_blank">GitHub</a></p>'
    '</div>\n'
    '<div id="toast" class=""></div>\n'
    # Token 计价器模态框
    '<div class="tk-modal" id="tkModal" onclick="if(event.target===this)closeTokenCalc()">'
    '<div class="tk-modal-content">'
    '<div class="tk-modal-header"><div class="tk-modal-title">&#128270; 真实文本计价器</div><button class="tk-modal-close" onclick="closeTokenCalc()">&times;</button></div>'
    '<div class="tk-modal-body">'
    '<div style="margin-bottom:8px;font-size:11px;color:var(--text2)">粘贴你的代码或文案，自动计算 Token 数并对比各平台花费</div>'
    '<textarea class="tk-textarea" id="tkText" placeholder="在此粘贴文本...\n\n支持中文、英文、代码混合内容"></textarea>'
    '<div class="tk-stats" id="tkStats"></div>'
    '<div style="margin-bottom:8px">'
    '<button class="tk-btn" onclick="calcTokens()">计算 Token</button>'
    '<button class="tk-btn tk-btn-sec" onclick="clearTokenCalc()">清空</button>'
    '<span style="font-size:10px;color:var(--text3);margin-left:8px">分词器: GPT-4 Cl100k (近似)</span>'
    '</div>'
    '<div id="tkResult"></div>'
    '</div></div></div>\n'
    # TTFB 测速模态框
    '<div class="ping-modal" id="pingModal" onclick="if(event.target===this)closePingModal()">'
    '<div class="ping-modal-content">'
    '<div class="ping-modal-header"><div class="ping-modal-title">&#9889; 接口测速 (TTFB)</div><button class="ping-modal-close" onclick="closePingModal()">&times;</button></div>'
    '<div class="ping-modal-body">'
    '<div style="margin-bottom:8px;font-size:11px;color:var(--text2)">输入模型名，自动测所有平台该模型的 TTFB，按延迟从低到高排序</div>'
    '<input class="tk-model-input" id="pingModelInput" placeholder="输入模型名搜索，如: deepseek-v3" oninput="updatePingSuggestions()">'
    '<div id="pingSuggestions" style="margin-bottom:8px"></div>'
    '<div style="margin-bottom:8px">'
    '<button class="ping-btn" id="pingStartBtn" onclick="startPing()">测速所有平台</button>'
    '<button class="ping-btn" style="background:var(--surface2);color:var(--text2);border:1px solid var(--border)" onclick="clearPingResult()">清除结果</button>'
    '<span style="font-size:10px;color:var(--text3);margin-left:8px">仅测 API 连接速度，不消耗 Token</span>'
    '</div>'
    '<div class="ping-result-list" id="pingResultList"></div>'
    '</div></div></div>\n'
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

# ─── 自动更新 models_data.json（保持数据同步） ───
try:
    _pinfo = {
        "aliyun":{"name":"阿里百炼","color":"#ff6a00"},
        "siliconflow":{"name":"硅基流动","color":"#7C3AED"},
        "moonshot":{"name":"月之暗面","color":"#4f46e5"},
        "zhipu":{"name":"智谱 AI","color":"#00c4b4"},
        "volcengine":{"name":"火山引擎","color":"#dc2626"},
        "baidu":{"name":"百度文心","color":"#2932e1"},
        "tencent":{"name":"腾讯混元","color":"#07c160"},
        "spark":{"name":"讯飞星火","color":"#ff6347"},
        "minimax":{"name":"MiniMax","color":"#2563eb"},
        "yi":{"name":"零一万物","color":"#8b5cf6"},
        "baichuan":{"name":"百川智能","color":"#16a34a"},
        "jieyue":{"name":"阶跃星辰","color":"#ea580c"},
        "deepseek":{"name":"DeepSeek","color":"#0ea5e9"},
        "openrouter":{"name":"OpenRouter","color":"#6366f1"},
        "groq":{"name":"Groq","color":"#f97316"},
        "together":{"name":"Together AI","color":"#06b6d4"},
        "fireworks":{"name":"Fireworks AI","color":"#ef4444"},
        "cohere":{"name":"Cohere","color":"#d946ef"},
        "infini":{"name":"无问芯穹","color":"#84cc16"},
        "novita":{"name":"Novita AI","color":"#f472b6"},
        "deepinfra":{"name":"DeepInfra","color":"#a78bfa"},
        "aihubmix":{"name":"AiHubMix","color":"#fb923c"},
        "n1n":{"name":"n1n.ai","color":"#22d3ee"},
        "aigc2d":{"name":"AIGC2D","color":"#34d399"},
        "ca":{"name":"ChatAnywhere","color":"#fbbf24"},
    }
    _mj = {"meta":{"updated_at":datetime.now().strftime("%Y-%m-%d %H:%M"),"total_models":total,
        "platform_counts":{},"price_tiers":{},"price_changes":price_changes},
        "platforms":_pinfo,"models":[]}
    _pc = {}; _ptc = {}
    for c in cards:
        # 从卡片 HTML 提取 data 属性
        _dp = re.search(r'data-p="([^"]*)"', c)
        _dn = re.search(r'data-ctx-display="([^"]*)"', c)
        _di = re.search(r'data-inp="([^"]*)"', c)
        _do = re.search(r'data-out="([^"]*)"', c)
        _dc = re.search(r'data-cur="([^"]*)"', c)
        _ds = re.search(r'data-s="([^"]*)"', c)
        _df = re.search(r'data-family="([^"]*)"', c)
        _pu = re.search(r'data-pu="([^"]*)"', c)
        _dpt = re.search(r'data-pt="([^"]*)"', c)
        _mn = re.search(r'class="mname">([^<]*)', c)
        _pn = re.search(r'class="prov">([^<]*)', c)
        _bu = re.search(r'class="base-url">([^<]*)', c)
        _tg = re.findall(r'class="tg[^"]*">([^<]*)', c)
        if not _dp: continue
        pid = _dp.group(1)
        _pc[pid] = _pc.get(pid, 0) + 1
        if _dpt: _ptc[_dpt.group(1)] = _ptc.get(_dpt.group(1), 0) + 1
        _mj["models"].append({
            "platform_id":pid,
            "platform_name":html.unescape(_pn.group(1)) if _pn else "",
            "platform_color":_pinfo.get(pid,{}).get("color",""),
            "name":html.unescape(_mn.group(1)) if _mn else "",
            "input_price":float(_di.group(1)) if _di else 0,
            "output_price":float(_do.group(1)) if _do else 0,
            "input_price_display":"","output_price_display":"",
            "currency":_dc.group(1) if _dc else "CNY",
            "price_unit":_pu.group(1) if _pu else "per_token",
            "context":_dn.group(1) if _dn else "",
            "tags":_tg,
            "scene":_ds.group(1) if _ds else "",
            "family":_df.group(1) if _df else "",
            "base_url":html.unescape(_bu.group(1)) if _bu else ""
        })
    _mj["meta"]["platform_counts"] = _pc
    _mj["meta"]["price_tiers"] = _ptc
    with open(MODELS_JSON, "w", encoding="utf-8") as _jf:
        json.dump(_mj, _jf, ensure_ascii=False, separators=(',',':'))
    print("  models_data.json updated (%d models)" % total, file=sys.stderr)
except Exception as _e:
    print("  models_data.json update failed:", str(_e)[:80], file=sys.stderr)

# ─── 每日测速并保存历史数据 ───
PING_DATA_FILE = os.path.join(CACHE_DIR, "ping_history.json")
try:
    import urllib.request as _ureq
    import concurrent.futures
    
    # 从 models_data.json 读取模型数据
    with open(MODELS_JSON, "r", encoding="utf-8") as _pf:
        _pdata = json.load(_pf)
    
    # 收集需要测速的接口：每个平台的 base_url + 代表性模型
    _ping_targets = []
    _seen_base = {}
    for _pm in _pdata.get("models", []):
        _burl = _pm.get("base_url", "")
        _pid = _pm.get("platform_id", "")
        _mname = _pm.get("name", "")
        if not _burl or not _mname: continue
        # 每个平台只测一个代表性模型（避免太多请求）
        if _pid in _seen_base: continue
        _seen_base[_pid] = 1
        _ping_targets.append({
            "platform_id": _pid,
            "platform_name": _pm.get("platform_name", ""),
            "model": _mname,
            "base_url": _burl
        })
    
    def _ping_one(target, timeout=8):
        """测单个接口的 TTFB（即使返回 401/403，TTFB 仍然有效）"""
        url = target["base_url"]
        body = json.dumps({"model": target["model"], "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}).encode()
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        try:
            req = _ureq.Request(url, data=body, headers=headers, method="POST")
            t0 = time.time()
            try:
                with _ureq.urlopen(req, timeout=timeout) as resp:
                    resp.read(1)
                ttfb = int((time.time() - t0) * 1000)
                return {"platform_id": target["platform_id"], "model": target["model"], "ms": ttfb, "status": "ok"}
            except _ureq.HTTPError as e:
                # 401/403/429 等：TTFB 仍然有效（网络通了，只是认证失败）
                ttfb = int((time.time() - t0) * 1000)
                if e.code in (401, 403, 429, 402, 400):
                    return {"platform_id": target["platform_id"], "model": target["model"], "ms": ttfb, "status": "ok"}
                return {"platform_id": target["platform_id"], "model": target["model"], "ms": ttfb, "status": "error"}
        except Exception as e:
            ttfb = int((time.time() - t0) * 1000) if 't0' in dir() else -1
            if "timed out" in str(e).lower():
                return {"platform_id": target["platform_id"], "model": target["model"], "ms": -1, "status": "timeout"}
            return {"platform_id": target["platform_id"], "model": target["model"], "ms": ttfb, "status": "error"}
    
    # 并发测速
    _ping_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_ping_one, t): t for t in _ping_targets}
        for future in concurrent.futures.as_completed(futures, timeout=30):
            try:
                result = future.result()
                _ping_results.append(result)
            except:
                pass
    
    # 保存历史数据
    _history = []
    if os.path.exists(PING_DATA_FILE):
        try:
            with open(PING_DATA_FILE, "r") as hf:
                _history = json.load(hf)
        except:
            _history = []
    
    _today_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M"),
        "results": sorted(_ping_results, key=lambda x: x.get("ms", 99999) if x.get("ms", -1) > 0 else 99999)
    }
    _history.append(_today_entry)
    # 只保留最近30天的数据
    if len(_history) > 30:
        _history = _history[-30:]
    
    with open(PING_DATA_FILE, "w", encoding="utf-8") as hf:
        json.dump(_history, hf, ensure_ascii=False, separators=(',', ':'))
    
    # 同时保存一份完整的历史数据到项目目录（用于综合分析）
    _analysis_file = os.path.join(SCRIPT_DIR, "ping_analysis.json")
    with open(_analysis_file, "w", encoding="utf-8") as af:
        json.dump({
            "meta": {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "days": len(_history)},
            "daily": _history
        }, af, ensure_ascii=False, indent=2)
    
    _ok_count = sum(1 for r in _ping_results if r.get("status") == "ok")
    print("  Ping: %d/%d platforms tested" % (_ok_count, len(_ping_targets)), file=sys.stderr)
except Exception as _e:
    print("  Ping skipped:", str(_e)[:60], file=sys.stderr)


print("Stats: OR:%d Ali:%d SF:%d MS:%d ZH:%d VC:%d BD:%d TX:%d XH:%d MM:%d YW:%d BC:%d JC:%d DS:%d GQ:%d TG:%d FW:%d CO:%d IF:%d NV:%d DI:%d AH:%d N1:%d A2:%d CA:%d Total:%d" % (
    oc,ac,sc2,mc2,zc,vc2,bc2,tc2,xc,mmc,yc,bcc,jcc,dc,gc,tgc,fwc,coc,ic,nc,dic,ahmc,n1nc,a2c,cac,total))
print("Time: %.1fs" % (time.time()-t0))
