#!/usr/bin/env python3
import os, time, json, sys, urllib.request
from datetime import datetime

SF  = os.environ.get("SF_KEY","sk-lvhjyumsmqidzpmwtmkcyxrhetbmaodfjklenoomnlsjbqha")
ALI = os.environ.get("ALIYUN_KEY","sk-5521c543f8f74954a027ddd41edafa08")
MS  = os.environ.get("MS_KEY","sk-ok4u4zjqFLYquLDmBwc1QOxE6PPNG0KSDOj3EnDfmR7QVxXw")
ZH  = os.environ.get("ZH_KEY","ff71a2ef7fbb431fb519d10df953b674.gMVnjHX5SgqgZy4Q")
VC  = os.environ.get("VOLC_KEY","e5786517-18a1-439d-98b3-b065e3d720e7")
OUT = os.path.expanduser("~/.qclaw/model-selector-v2.html")
ORC = "/tmp/openrouter_full.json"

def fj(url, tok="", to=20):
    h = {"User-Agent": "Mozilla/5.0"}
    if tok: h["Authorization"] = "Bearer " + tok
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=to) as r:
            return json.loads(r.read())
    except Exception as e:
        print("  WARN:", e, file=sys.stderr)
        return None

def PT(inp, out, cur="CNY"):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0: return "free"
    p = inp * 1e6 if cur == "USD" else inp
    if p < 0.1:   return "cheap"
    elif p < 10:   return "mid"
    elif p < 100:  return "high"
    else:           return "ultra"

def Te(s):
    return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def th(tags):
    m = {"免费":"free","免费额度":"free","便宜":"cheap","极便宜":"cheap","性价比":"cheap",
         "旗舰":"hot","主力":"hot","最新版":"hot","2025新":"hot","2026新":"hot",
         "视觉":"vision","推理":"reason","长上下文":"long","超长上下文":"long",
         "开源":"other","代码":"other","图片生成":"other","视频生成":"other",
         "快速":"other","高性能":"hot","Pro订阅":"other","蒸馏":"other",
         "轻量":"other","已下线":"other","即将下线":"other","价格待确认":"other"}
    return "".join('<span class="tg tg-' + m.get(x,"other") + '">' + x + '</span>' for x in (tags or []))

def bc(inp, out):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0:
        return '<span class="price-badge price-free">免费额度</span>'
    if inp == out:
        c = "price-cheap" if inp < 1 else "price-mid" if inp < 10 else "price-high" if inp < 100 else "price-ultra"
        return '<span class="price-badge ' + c + '">¥' + ("%.2f" % inp) + '/M</span>'
    return '<span class="price-badge price-mid">IN:¥' + ("%.2f" % inp) + ' OUT:¥' + ("%.2f" % out) + '/M</span>'

def bo(inp, out):
    inp = float(inp or 0); out = float(out or 0)
    if inp == 0 and out == 0:
        return '<span class="price-badge price-free">$0 (免费)</span>'
    p = inp * 1e6
    if inp == out:
        c = "price-free" if p < 0.1 else "price-cheap" if p < 1 else "price-mid" if p < 10 else "price-high" if p < 100 else "price-ultra"
        return '<span class="price-badge ' + c + '">$' + ("%.2f" % p) + '/1M</span>'
    return '<span class="price-badge price-mid">IN:$' + ("%.1f" % (inp*1e6)) + ' OUT:$' + ("%.1f" % (out*1e6)) + '/1M</span>'

def make_card(pid, pname, pc, mname, inp, out, ctx, tags, scen, cmd_base, cur="CNY"):
    pt = PT(inp, out, cur)
    ts = th(tags)
    bg = bc(inp, out) if cur == "CNY" else bo(inp, out)
    return (
        '<div class="mc" style="--c:' + pc + '" data-s="' + scen + '" data-p="' + pid + '" data-pt="' + pt + '" ' +
        'onclick="copyCmd(&apos;' + cmd_base + '&apos;,&apos;' + mname + '&apos;)">' +
        '<div class="dot"></div><div class="prov">' + pname + '</div>' +
        '<div class="mname">' + mname + '</div><div class="tags">' + ts + '</div>' +
        '<div class="prow">' + bg + '</div><div class="ctx">上下文: ' + ctx + '</div>' +
        '<div class="hint">点击复制 API 接入方式</div></div>'
    )

# SF price rules
def sp(mid):
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
    elif "ByteDance-Seed" in mid:           i, o = 1.0, 4.0; t = ["开源","旗舰"]
    elif "internlm" in mid:                 i, o = 0, 0; t = ["开源","免费额度"]
    else:                                     i, o = 0, 0
    if not t: t = ["免费额度"]
    return i, o, t, s

def mp(mid):
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
        "doubao-seedream-4":       (3,0,"-",["图片生成","旗舰"],"图片生成"),
        "doubao-seedream-5":       (3,0,"-",["图片生成","最新版"],"图片生成"),
        "doubao-seedance-1":       (0.5,0,"-",["视频生成","旗舰"],"视频生成"),
        "doubao-seedance-2":       (0.5,0,"-",["视频生成"],"视频生成"),
        "doubao-seed-2.0-pro":     (1,4,"32k",["旗舰","最新版"],"日常对话"),
        "doubao-seed-2.0-mini":    (0.8,2,"32k",["轻量","性价比"],"日常对话"),
        "doubao-smart-router":      (0.8,2,"32k",["智能路由"],"日常对话"),
    }
    for k,(ii,oo,cc,tt,ss) in m.items():
        if k in mid: return ii, oo, cc, tt, ss
    return 0.8, 2, "32k", ["价格待确认"], "日常对话"

BD = [
    {"n":"文心一言 4.0","c":"8k","i":120,"o":120,"t":["旗舰"],"s":"深度推理"},
    {"n":"文心一言 4.0-32K","c":"32k","i":120,"o":120,"t":["旗舰","长上下文"],"s":"深度推理"},
    {"n":"文心一言 3.5","c":"8k","i":20,"o":20,"t":["主力"],"s":"日常对话"},
    {"n":"文心速度 128K","c":"128k","i":12,"o":12,"t":["长上下文"],"s":"日常对话"},
    {"n":"文心 Lite","c":"8k","i":8,"o":8,"t":["轻量","免费额度"],"s":"日常对话"},
    {"n":"文心Bot 8K","c":"8k","i":20,"o":20,"t":["主力"],"s":"日常对话"},
]

# ── Fetch ──────────────────────────────────
print("Fetching data...")
t0 = time.time()

ali = []
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

d = fj("https://api.siliconflow.cn/v1/models", SF)
sf_ids = [m["id"] for m in (d.get("data",[]) if d else [])]
print("  SF:", len(sf_ids), file=sys.stderr)

d = fj("https://api.moonshot.cn/v1/models", MS)
ms_list = [{"id":m["id"],"c":str(int(m.get("context_length",0)//1000))+"k"} for m in (d.get("data",[]) if d else [])]
print("  Moonshot:", len(ms_list), file=sys.stderr)

d = fj("https://open.bigmodel.cn/api/paas/v4/models", ZH)
zh_ids = [m["id"] for m in (d.get("data",[]) if d else [])]
print("  Zhipu:", len(zh_ids), file=sys.stderr)

d = fj("https://ark.cn-beijing.volces.com/api/v3/models", VC)
vc_list = [{"id":m["id"],"st":m.get("status","")} for m in (d.get("data",[]) if d else [])]
print("  Volcengine:", len(vc_list), file=sys.stderr)

OR = []
if os.path.exists(ORC):
    try: OR = json.load(open(ORC)).get("data",[])
    except: pass
print("  OpenRouter:", len(OR), file=sys.stderr)

# ── Cards ──────────────────────────────────
cards = []

for m in ali:
    cards.append(make_card("aliyun","阿里百炼","#ff6a00",Te(m["n"]),m["i"],m["o"],m["c"],m["t"],m["s"],
                 "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions","CNY"))

for mid in sf_ids:
    ii, oo, tt, ss = sp(mid)
    cards.append(make_card("siliconflow","硅基流动","#7C3AED",Te(mid.split("/")[-1]),ii,oo,"32k",tt,ss,
                 "https://api.siliconflow.cn/v1/chat/completions","CNY"))

for m in ms_list:
    mid = m["id"]
    ii, oo, cc, tt, ss = mp(mid)
    cards.append(make_card("moonshot","月之暗面","#4f46e5",Te(mid),ii,oo,cc,tt,ss,
                 "https://api.moonshot.cn/v1/chat/completions","CNY"))

for mid in zh_ids:
    ii, oo, cc, tt, ss = zp(mid)
    cards.append(make_card("zhipu","智谱 AI","#00c4b4",Te(mid),ii,oo,cc,tt,ss,
                 "https://open.bigmodel.cn/api/paas/v4/chat/completions","CNY"))

for m in vc_list:
    mid = m["id"]; st = m.get("st","")
    ii, oo, cc, tt, ss = vp(mid)
    tt = tt[:]
    if st == "Shutdown":  tt = ["已下线"] + tt
    elif st == "Retiring": tt = ["即将下线"] + tt
    cards.append(make_card("volcengine","火山引擎","#dc2626",Te(mid),ii,oo,cc,tt,ss,
                 "https://ark.cn-beijing.volces.com/api/v3/chat/completions","CNY"))

for m in BD:
    cards.append(make_card("baidu","百度文心","#2932e1",Te(m["n"]),m["i"],m["o"],m["c"],m["t"],m["s"],
                 "https://qianfan.baidubce.com/v2/chat/completions","CNY"))

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
    pp = PT(ii, oo, "USD")
    tts = th(tt)
    bg = bo(ii, oo)
    mid2 = Te(m["id"])
    cmd = "/model " + mid2
    cards.append(
        '<div class="mc" style="--c:#6366f1" data-s="' + ss + '" data-p="openrouter" data-pt="' + pp + '" ' +
        'onclick="copyCmd(&apos;/model ' + mid2 + '&apos;, &apos;' + nn + '&apos;)">' +
        '<div class="dot"></div><div class="prov">OPENROUTER:' + pv + '</div>' +
        '<div class="mname">' + nn + '</div><div class="tags">' + tts + '</div>' +
        '<div class="prow">' + bg + '</div><div class="ctx">上下文: ' + cc + '</div>' +
        '<div class="hint">点击复制 /model ' + mid2 + '</div></div>'
    )

total = len(cards)
print("Generated:", total, file=sys.stderr)

def cn(p): return sum(1 for c in cards if '" data-p="' + p + '"' in c)
ac = cn("aliyun"); sc2 = cn("siliconflow"); mc2 = cn("moonshot")
zc = cn("zhipu"); vc2 = cn("volcengine"); bc2 = cn("baidu"); oc = cn("openrouter")

def tc(p): return sum(1 for c in cards if '" data-pt="' + p + '"' in c)
print("  Tier free:%d cheap:%d mid:%d high:%d ultra:%d" % (
    tc("free"),tc("cheap"),tc("mid"),tc("high"),tc("ultra")), file=sys.stderr)

now = datetime.now().strftime("%Y-%m-%d %H:%M")

# ── UI bars ──────────────────────────────────
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
)

snote = (
    "&#9888; <strong>数据说明：</strong>"
    "阿里百炼 <strong>" + str(ac) + "个模型</strong>从 API 实时拉取，含真实价格；"
    "硅基流动/" + str(sc2) + "个月之暗面/" + str(mc2) + "个从 API 拉取列表，价格来自各平台官网公告（2026年4月）；"
    "OpenRouter 显示原始美元价格，国内平台显示人民币价格；"
    "标注「价格待确认」的模型请至平台控制台核实。"
)

JS = (
    "var curP='all',curS='all',curPT='all';"
    "document.addEventListener('DOMContentLoaded',function(){"
    "var ld=document.getElementById('ld');ld.classList.add('show');"
    "setTimeout(function(){ld.classList.remove('show')},600);"
    "document.querySelectorAll('.pt').forEach(function(b){b.addEventListener('click',function(){"
    "document.querySelectorAll('.pt').forEach(function(x){x.classList.remove('active')});"
    "b.classList.add('active');curP=b.dataset.p;filter()});});"
    "document.querySelectorAll('.pt-filter').forEach(function(b){b.addEventListener('click',function(){"
    "document.querySelectorAll('.pt-filter').forEach(function(x){x.classList.remove('active')});"
    "b.classList.add('active');curPT=b.dataset.pt;filter()});});"
    "document.querySelectorAll('.sc').forEach(function(b){b.addEventListener('click',function(){"
    "document.querySelectorAll('.sc').forEach(function(x){x.classList.remove('active')});"
    "b.classList.add('active');curS=b.dataset.sc;filter()});});"
    "var st;"
    "document.getElementById('si').addEventListener('input',function(){clearTimeout(st);st=setTimeout(filter,200)});"
    "document.addEventListener('keydown',function(e){"
    "if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();document.getElementById('si').focus()}"
    "if(e.key==='Escape'){document.getElementById('si').blur()}});"
    "});"
    "function filter(){"
    "var cs=document.querySelectorAll('.mc');"
    "var q=(document.getElementById('si').value||'').toLowerCase().trim();"
    "var n=0;"
    "cs.forEach(function(c){"
    "var sh=true;"
    "var pn=(c.querySelector('.prov')||{}).textContent||'';"
    "var mn=(c.querySelector('.mname')||{}).textContent||'';"
    "if(curP!='all'&&curP!==(c.dataset.p||'')){sh=false}"
    "if(curPT!='all'&&curPT!==(c.dataset.pt||'')){sh=false}"
    "if(q&&mn.toLowerCase().indexOf(q)===-1&&pn.toLowerCase().indexOf(q)===-1){sh=false}"
    "c.style.display=sh?'block':'none';if(sh)n++});"
    "document.getElementById('empty').style.display=n===0?'block':'none'}"
    "function copyCmd(cmd,name){"
    "navigator.clipboard.writeText(cmd).then(function(){"
    "var t=document.getElementById('toast');t.textContent='OK '+cmd.substring(0,80);t.classList.add('show');"
    "setTimeout(function(){t.classList.remove('show')},2500)"
    "}).catch(function(){"
    "var t=document.getElementById('toast');t.textContent=cmd.substring(0,60);t.classList.add('show');"
    "setTimeout(function(){t.classList.remove('show')},2500)});}"
)

CSS = open("/tmp/css.txt").read()

# ── HTML ──────────────────────────────────
HDR = (
    '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    '<title>AI 模型选择器 - 全网价格对比 2026</title>\n'
    '<style>\n' + CSS + '\n</style>\n'
    '</head>\n<body>\n<div class="wrap">\n'
    '<div class="hdr"><h1>AI 模型选择器</h1>'
    '<p>一键对比全网价格 &middot; 点击卡片复制切换命令 &middot; 按 / 快速搜索</p>'
    '<div class="brow">'
    '<span class="bd">&#128202; ' + str(total) + ' 个模型</span>'
    '<span class="bd bd-free">&#128998; 免费</span>'
    '<span class="bd bd-cheap">&#128308; &lt;¥0.7</span>'
    '<span class="bd bd-mid">&#128993; ¥0.7-10/M</span>'
    '<span class="bd bd-high">&#128996; ¥10+/M</span>'
    '<span class="bd bd-ultra">&#127745; &gt;¥100/M</span>'
    '</div></div>\n'
    '<div class="snote">' + snote + '</div>\n'
    '<div class="pbar">' + tabs_bar + '</div>\n'
    '<div class="ptbar">' + pt_bar + '</div>\n'
    '<div class="sbar">' + scen_bar + '</div>\n'
    '<div class="srow"><input id="si" type="text" placeholder="搜索模型...  (按 / 快速聚焦)"></div>\n'
    '<div class="loading" id="ld"><div class="sp"></div>加载中...</div>\n'
    '<div class="grid" id="grid">\n'
)
FTR = (
    '\n</div>\n'
    '<div class="empty" id="empty" style="display:none">没有找到符合条件的模型</div>\n'
    '</div>\n'
    '<div class="ftr">'
    '<p>&#128202; 数据来源：各平台 API 实时拉取 + 官网公告（更新时间：' + now + '）</p>'
    '<p>OpenRouter 显示原始美元价格 &middot; 国内平台显示人民币价格 &middot; 点击卡片复制接入方式</p>'
    '<p><a href="https://github.com/k-goz/model-selector" target="_blank">GitHub</a></p>'
    '</div>\n'
    '<div id="toast" style="position:fixed;bottom:20px;left:50%;transform:translateX(-50%);'
    'background:#1e293b;color:#fff;padding:8px 16px;border-radius:8px;'
    'font-size:13px;display:none;z-index:9999"></div>\n'
    '<script>\n' + JS + '\n</script>\n'
    '</body>\n</html>'
)

HTML = HDR + "\n".join(cards) + FTR

with open(OUT,"w",encoding="utf-8") as f:
    f.write(HTML)
sz = os.path.getsize(OUT)
print("\nDONE:", OUT, "(%.0f KB)" % (sz/1024))
print("Stats: OR:%d Ali:%d SF:%d MS:%d ZH:%d VC:%d BD:%d Total:%d" % (oc,ac,sc2,mc2,zc,vc2,bc2,total))
print("Time: %.1fs" % (time.time()-t0))
