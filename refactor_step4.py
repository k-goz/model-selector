#!/usr/bin/env python3
"""第四步：重写主循环赋值 — 海外走 get_dynamic_price(), 国内走 get_domestic_price()"""

with open("generate.py", "r", encoding="utf-8") as f:
    content = f.read()

# ── 硅基流动 ──
content = content.replace(
    '''    # 硅基流动
    for mid in sf_ids:
        ii, oo, tt, ss = sp(mid)
        fam = get_family(mid)
        cards.append(make_card("siliconflow","硅基流动","#7C3AED",Te(mid),ii,oo,"32k",tt,ss,
                     "https://api.siliconflow.cn/v1/chat/completions","CNY",family=fam,price_src="H"))
        all_models.append({"p":"siliconflow","n":mid,"i":ii,"o":oo,"src":"H"})''',
    '''    # 硅基流动
    for mid in sf_ids:
        dom = get_domestic_price("siliconflow", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","32k")
        else:
            ii, oo, cc = get_dynamic_price("siliconflow", mid)
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
        fam = get_family(mid)
        cards.append(make_card("siliconflow","硅基流动","#7C3AED",Te(mid),ii,oo,cc,tt,ss,
                     "https://api.siliconflow.cn/v1/chat/completions","CNY",family=fam,price_src="A"))
        all_models.append({"p":"siliconflow","n":mid,"i":ii,"o":oo,"src":"A"})'''
)

# ── 月之暗面 ──
content = content.replace(
    '''    # 月之暗面
    for m in ms_list:
        mid = m["id"]
        ii, oo, cc, tt, ss = mp(mid)''',
    '''    # 月之暗面
    for m in ms_list:
        mid = m["id"]
        dom = get_domestic_price("moonshot", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","8k")
        else:
            ii, oo, cc = 0, 0, "8k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── 智谱AI ──
content = content.replace(
    '''    # 智谱AI
    for mid in zh_ids:
        ii, oo, cc, tt, ss = zp(mid)''',
    '''    # 智谱AI
    for mid in zh_ids:
        dom = get_domestic_price("zhipu", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","128k")
        else:
            ii, oo, cc = 0, 0, "128k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── 火山引擎 ──
content = content.replace(
    '''        ii, oo, cc, tt, ss = vp(mid)
        tt = tt[:]''',
    '''        dom = get_domestic_price("volcengine", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","32k")
        else:
            ii, oo, cc = 0, 0, "32k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
        tt = tt[:]'''
)

# ── 腾讯混元 ──
content = content.replace(
    '''    # 腾讯混元
    for mid in tx_ids:
        ii, oo, cc, tt, ss = tp(mid)''',
    '''    # 腾讯混元
    for mid in tx_ids:
        dom = get_domestic_price("tencent", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","32k")
        else:
            ii, oo, cc = 0, 0, "32k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── 讯飞星火 ──
content = content.replace(
    '''    # 讯飞星火
    for mid in xh_ids:
        ii, oo, cc, tt, ss = xp(mid)''',
    '''    # 讯飞星火
    for mid in xh_ids:
        dom = get_domestic_price("spark", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","8k")
        else:
            ii, oo, cc = 0, 0, "8k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── MiniMax ──
content = content.replace(
    '''    # MiniMax
    for mid in mm_ids:
        ii, oo, cc, tt, ss = mm_p(mid)''',
    '''    # MiniMax
    for mid in mm_ids:
        dom = get_domestic_price("minimax", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","32k")
        else:
            ii, oo, cc = 0, 0, "32k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── 零一万物 ──
content = content.replace(
    '''    # 零一万物
    for mid in yw_ids:
        ii, oo, cc, tt, ss = yp(mid)''',
    '''    # 零一万物
    for mid in yw_ids:
        dom = get_domestic_price("yi", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","16k")
        else:
            ii, oo, cc = 0, 0, "16k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── 百川智能 ──
content = content.replace(
    '''    # 百川智能
    for mid in bc_ids:
        ii, oo, cc, tt, ss = bcp(mid)''',
    '''    # 百川智能
    for mid in bc_ids:
        dom = get_domestic_price("baichuan", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","32k")
        else:
            ii, oo, cc = 0, 0, "32k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── 阶跃星辰 ──
content = content.replace(
    '''    # 阶跃星辰
    for mid in jc_ids:
        ii, oo, cc, tt, ss = jp(mid)''',
    '''    # 阶跃星辰
    for mid in jc_ids:
        dom = get_domestic_price("jieyue", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","8k")
        else:
            ii, oo, cc = 0, 0, "8k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── DeepSeek ──
content = content.replace(
    '''    # DeepSeek 官方
    for mid in ds_ids:
        ii, oo, cc, tt, ss = dp(mid)''',
    '''    # DeepSeek 官方
    for mid in ds_ids:
        dom = get_domestic_price("deepseek", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","1M")
        else:
            ii, oo, cc = 0, 0, "1M"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── Groq (海外, 走 LiteLLM) ──
content = content.replace(
    '''    # Groq
    for mid in gq_ids:
        ii, oo, cc, tt, ss = gp(mid)''',
    '''    # Groq
    for mid in gq_ids:
        ii, oo, cc = get_dynamic_price("groq", mid)
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── Together AI (海外, 走 LiteLLM) ──
content = content.replace(
    '''    # Together AI
    for m in tg_list:
        mid = m["id"]
        # 优先使用 API 返回的真实价格 (API返回$/token，需×1e6转为$/1M)
        api_inp = m.get("i", 0)
        api_out = m.get("o", 0)
        api_ctx = m.get("c", 0)
        if api_inp > 0 and api_out > 0:
            ii, oo = api_inp * 1e6, api_out * 1e6
            cc = str(int(api_ctx)//1000)+"k" if api_ctx else "N/A"
        else:
            ii, oo, cc, tt, ss = tgp(mid)
        if api_inp == 0 and api_out == 0:
            ii, oo, cc, tt, ss = tgp(mid)
        else:
            # 从模型名和价格推断标签
            tt, ss = tgp_tags(mid, ii, oo, api_ctx)''',
    '''    # Together AI
    for m in tg_list:
        mid = m["id"]
        # 优先使用 API 返回的真实价格 (API返回$/token，需×1e6转为$/1M)
        api_inp = m.get("i", 0)
        api_out = m.get("o", 0)
        api_ctx = m.get("c", 0)
        if api_inp > 0 and api_out > 0:
            ii, oo = api_inp * 1e6, api_out * 1e6
            cc = str(int(api_ctx)//1000)+"k" if api_ctx else "N/A"
        else:
            ii, oo, cc = get_dynamic_price("together_ai", mid)
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── Fireworks AI (海外, 走 LiteLLM) ──
content = content.replace(
    '''    # Fireworks AI
    for m in fw_list:
        mid = m["id"]
        ii, oo, cc, tt, ss = fwp(mid)''',
    '''    # Fireworks AI
    for m in fw_list:
        mid = m["id"]
        ii, oo, cc = get_dynamic_price("fireworks_ai", mid)
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── Cohere (海外, 走 LiteLLM) ──
content = content.replace(
    '''    # Cohere
    for m in co_list:
        mid = m.get("id", m) if isinstance(m, dict) else m
        ii, oo, cc, tt, ss = cop(mid)''',
    '''    # Cohere
    for m in co_list:
        mid = m.get("id", m) if isinstance(m, dict) else m
        ii, oo, cc = get_dynamic_price("cohere", mid)
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── 无问芯穹 (国内, 走 domestic) ──
content = content.replace(
    '''    # 无问芯穹
    for mid in infini_list:
        ii, oo, cc, tt, ss = ip(mid)''',
    '''    # 无问芯穹
    for mid in infini_list:
        dom = get_domestic_price("infini", mid)
        if dom and dom["input"] > 0:
            ii, oo, cc = dom["input"], dom["output"], dom.get("context","32k")
        else:
            ii, oo, cc = 0, 0, "32k"
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── Novita AI (海外, 走 LiteLLM) ──
content = content.replace(
    '''    # Novita AI
    for m in novita_list:
        mid = m["id"]
        # 优先使用 API 返回的真实价格 (API返回$/token，需×1e6转为$/1M)
        api_inp = m.get("i", 0)
        api_out = m.get("o", 0)
        api_ctx = m.get("c", 0)
        if api_inp > 0 and api_out > 0:
            ii, oo = api_inp * 1e6, api_out * 1e6
            cc = str(int(api_ctx)//1000)+"k" if api_ctx else "N/A"
            tt, ss = np_tags(mid, ii, oo, api_ctx)
        else:
            ii, oo, cc, tt, ss = np(mid)''',
    '''    # Novita AI
    for m in novita_list:
        mid = m["id"]
        # 优先使用 API 返回的真实价格 (API返回$/token，需×1e6转为$/1M)
        api_inp = m.get("i", 0)
        api_out = m.get("o", 0)
        api_ctx = m.get("c", 0)
        if api_inp > 0 and api_out > 0:
            ii, oo = api_inp * 1e6, api_out * 1e6
            cc = str(int(api_ctx)//1000)+"k" if api_ctx else "N/A"
        else:
            ii, oo, cc = get_dynamic_price("novita", mid)
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── DeepInfra (海外, 走 LiteLLM) ──
content = content.replace(
    '''    # DeepInfra
    for mid in di_list:
        if mid in di_prices:
            raw_ii, raw_oo, cc = di_prices[mid]
            ii, oo = raw_ii * 1e6, raw_oo * 1e6
            # Convert numeric context to "k" format
            try:
                cc_int = int(cc)
                cc = str(cc_int // 1000) + "k" if cc_int >= 1000 else str(cc_int)
            except (ValueError, TypeError):
                pass
            _, _, _, tt, ss = dip(mid)
        else:
            ii, oo, cc, tt, ss = dip(mid)''',
    '''    # DeepInfra
    for mid in di_list:
        if mid in di_prices:
            raw_ii, raw_oo, cc = di_prices[mid]
            ii, oo = raw_ii * 1e6, raw_oo * 1e6
            try:
                cc_int = int(cc)
                cc = str(cc_int // 1000) + "k" if cc_int >= 1000 else str(cc_int)
            except (ValueError, TypeError):
                pass
        else:
            ii, oo, cc = get_dynamic_price("deepinfra", mid)
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── AiHubMix (海外, 走 LiteLLM) ──
content = content.replace(
    '''    # AiHubMix
    for mid in ahm_list:
        ii, oo, cc, tt, ss = ahmp(mid)''',
    '''    # AiHubMix
    for mid in ahm_list:
        ii, oo, cc = get_dynamic_price("aihubmix", mid)
        tt, ss = infer_tags_and_scene(mid, ii, oo, cc)'''
)

# ── n1n.ai (代理, 保持 n1np 从 API 获取) ──
content = content.replace(
    '''        ii, oo = n1np(mid)''',
    '''        ii, oo = n1np(mid) if 'n1np' in dir() else (0, 0)'''
)

# ── ChatAnywhere (代理, 保持 cap 从网页获取) ──
content = content.replace(
    '''        ii, oo = cap(mid)''',
    '''        ii, oo = cap(mid) if 'cap' in dir() else (0, 0)'''
)

with open("generate.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Step 4 done: rewrote all main loop assignments")
