"""模型目录刷新与静态站点生成流水线。"""

from __future__ import annotations

from collections.abc import Sequence


def run(entrypoint_file: str, argv: Sequence[str] | None = None) -> None:
    #!/usr/bin/env python3
    """AI 模型选择器 - 数据抓取与页面生成脚本
    支持平台: 阿里百炼, 硅基流动, 月之暗面, 智谱AI, 火山引擎, 百度文心, OpenRouter,
               腾讯混元, 讯飞星火, MiniMax, 零一万物, 百川智能, 阶跃星辰, DeepSeek, Groq,
               Together AI, Fireworks AI, Cohere, 无问芯穹, Novita AI, DeepInfra, AiHubMix, n1n.ai, ChatAnywhere
    
    架构: SSOT (Single Source of Truth) 四层价格解析系统
    - T1: API 直接返回的价格（最高优先级）
    - T2: 官方定价页爬取
    - T3: official_prices_db.json 价格数据库
    - T4: LiteLLM 社区价格数据（海外平台兜底）
    """
    import os
    import time
    import json
    import sys
    import urllib.request
    import re
    import logging
    from datetime import datetime
    from collections import Counter
    from typing import Dict, List, Tuple, Optional, Any
    
    from src.pricing import (
        PriceDatabase,
        SSOTPriceResolver,
        classify_price,
        fetch_official_prices,
        get_model_family,
        get_price_tier,
        infer_tags_and_scene as infer_model_metadata,
        normalize_for_match as normalize_model_name,
    )
    from src.collection import CachedHttpClient, collect_platform_catalog
    from src.config import RuntimeConfig
    from src.monitoring import update_ping_history
    from src.notifications import send_telegram_refresh
    from src.history import write_history_artifacts, write_lifecycle_archive
    from src.quality import assess_catalog_risk, load_policy, write_quality_report
    from src.publication import build_catalog, write_catalog
    from src.rendering import (
        compose_page,
        load_asset,
        make_card,
        make_or_card,
        render_template,
        set_official_prices,
        Te,
        write_english_version,
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 日志配置
    # ═══════════════════════════════════════════════════════════════════════════
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )
    logger = logging.getLogger(__name__)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 运行配置（仅从环境变量读取，无硬编码密钥默认值）
    # ═══════════════════════════════════════════════════════════════════════════
    CONFIG = RuntimeConfig.from_environment(entrypoint_file, list(sys.argv if argv is None else argv))
    
    # ─── 输出路径 (支持 OUTPUT_FILE 环境变量覆盖，适配 CI 环境) ───
    SCRIPT_DIR = str(CONFIG.project_dir)
    OUT = str(CONFIG.output_file)
    CACHE_DIR = str(CONFIG.cache_dir)
    PREV_DATA = str(CONFIG.previous_data_file)
    HTTP_CLIENT = CachedHttpClient(CONFIG.cache_dir)
    
    # ─── 解析参数 ───
    UPDATE_DB = CONFIG.update_db
    FORCE_REFRESH = CONFIG.force_refresh
    RENDER_ONLY = CONFIG.render_only
    
    # ─── 汇率 ───
    USD_TO_CNY = 7.25
    
    # ─── 从官方定价页爬取价格 ───
    
    OFFICIAL_PRICES = {}
    
    # ─── 模型名标准化（用于跨平台匹配） ───
    def normalize_for_match(model_name):
        return normalize_model_name(model_name)
    
    # ─── 官方价格数据库（SSOT: Single Source of Truth） ───
    OFFICIAL_PRICES_DB = {}
    _opdb_path = os.path.join(SCRIPT_DIR, "official_prices_db.json")
    if os.path.exists(_opdb_path):
        try:
            with open(_opdb_path, "r", encoding="utf-8") as _f:
                OFFICIAL_PRICES_DB = json.load(_f)
            _opdb_count = sum(len([k for k in v if not k.startswith("_")]) for k in OFFICIAL_PRICES_DB if k != "_meta" for v in [OFFICIAL_PRICES_DB[k]])
            print("  official_prices_db.json: %d platforms, %d entries" % (len([k for k in OFFICIAL_PRICES_DB if k != "_meta"]), _opdb_count), file=sys.stderr)
        except Exception as e:
            print("  official_prices_db.json load error:", e, file=sys.stderr)
    
    PRICE_DATABASE = PriceDatabase(_opdb_path)
    
    TENCENT_PRICES = {}
    _tp_path = os.path.join(SCRIPT_DIR, "tencent_prices.json")
    if os.path.exists(_tp_path):
        try:
            with open(_tp_path, "r", encoding="utf-8") as _f:
                _tp_raw = json.load(_f)
            for _k, _v in _tp_raw.items():
                _mid = _v.get("model_id", _k).lower()
                TENCENT_PRICES[_mid] = _v
            print("  tencent_prices.json: %d models" % len(TENCENT_PRICES), file=sys.stderr)
        except Exception as _e:
            print("  tencent_prices.json load error:", _e, file=sys.stderr)
    
    def get_tencent_price(model_id):
        mid = model_id.lower()
        norm = normalize_for_match(model_id)
        for k in (mid, norm):
            if k in TENCENT_PRICES:
                e = TENCENT_PRICES[k]
                return e["input_price"], e["output_price"], e.get("max_context", "32k")
        return 0, 0, "N/A"
    
    def get_db_price(platform_key, raw_model_id):
        return PRICE_DATABASE.get_price(platform_key, raw_model_id)
    
    
    # ─── 价格漂移检测（已移除：不再依赖第三方数据源交叉验证） ───
    
    # ─── 通用请求函数 (带重试和缓存) ───
    def fj(url: str, tok: str = "", to: int = 20, retries: int = 3, platform: str = "") -> Optional[Dict]:
        """Legacy-compatible wrapper around the collection HTTP boundary."""
        return HTTP_CLIENT.fetch_json(url, tok, timeout=to, retries=retries, platform=platform)
    
    # ─── 价格分级 ───
    def PT(inp: float, out: float, cur: str = "CNY", price_unit: str = "per_token") -> str:
        return get_price_tier(inp, out, cur, price_unit)
    
    # ─── HTML 转义 ───
    
    # ─── 模型家族识别 ───
    def get_family(mid):
        return get_model_family(mid)
    
    # ═══════════════════════════════════════════════════════════
    # 双轨制价格获取：海外走 LiteLLM，国内走 official_prices_db.json
    # ═══════════════════════════════════════════════════════════
    
    # LiteLLM 社区价格数据（第4层兜底）
    LITELLM_DB = {}
    LITELLM_KEY_MAP = {
        "together": "together_ai", "fireworks": "fireworks_ai",
        "cohere": "cohere", "groq": "groq", "novita": "novita", "deepinfra": "deepinfra",
    }
    try:
        if RENDER_ONLY:
            raise RuntimeError("render-only mode")
        _llm_url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
        _llm_req = urllib.request.Request(_llm_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(_llm_req, timeout=30) as _r:
            _llm_data = json.loads(_r.read().decode("utf-8", errors="ignore"))
        for _rn, _info in _llm_data.items():
            if not isinstance(_info, dict): continue
            _prov = _info.get("litellm_provider", "")
            if not _prov: continue
            _li = float(_info.get("input_cost_per_token", 0) or 0) * 1e6
            _lo = float(_info.get("output_cost_per_token", 0) or 0) * 1e6
            if _li == 0: _li = float(_info.get("input_cost_per_million_tokens", 0) or 0)
            if _lo == 0: _lo = float(_info.get("output_cost_per_million_tokens", 0) or 0)
            if _li > 0 or _lo > 0:
                if _prov not in LITELLM_DB: LITELLM_DB[_prov] = {}
                _mk = _rn.replace(_prov + "/", "").lower()
                _ctx = _info.get("max_input_tokens", 0)
                LITELLM_DB[_prov][_mk] = {"input": _li, "output": _lo, "context": ("%dk" % (_ctx // 1000)) if _ctx else "N/A"}
        _llm_total = sum(len(v) for v in LITELLM_DB.values())
        print("  LiteLLM: %d providers, %d entries" % (len(LITELLM_DB), _llm_total), file=sys.stderr)
    except Exception as _e:
        print("  LiteLLM fetch skipped:", str(_e)[:60], file=sys.stderr)
    
    PRICE_RESOLVER = SSOTPriceResolver(db_path=_opdb_path, price_db=PRICE_DATABASE)
    
    def infer_tags_and_scene(mid, inp, out, ctx):
        return infer_model_metadata(mid, inp, out, ctx)
    
    def n1np(mid):
        """n1n.ai - 国内聚合平台（¥/M tokens，仅使用API获取的真实价格）"""
        if mid in n1n_prices:
            ii, oo = n1n_prices[mid]
            return ii, oo
        # 无API价格 → 尝试 official_prices_db.json
        db_i, db_o, _ = get_db_price("n1n", mid)
        if db_i > 0 or db_o > 0:
            return db_i, db_o
        print("  ⚠️ PRICE_MISSING: [n1n] %s → 价格为0" % mid, file=sys.stderr)
        return 0, 0
    
    
    def cap(mid):
        """ChatAnywhere - 国内中转平台（¥/M tokens，优先使用官方文档自营价）"""
        if mid in ca_prices:
            ii, oo = ca_prices[mid]
            return ii, oo, "P"
        # 无API价格 → 尝试 official_prices_db.json
        db_i, db_o, _ = get_db_price("ca", mid)
        if db_i > 0 or db_o > 0:
            return db_i, db_o, "DB"
        print("  ⚠️ PRICE_MISSING: [ca] %s → 价格为0" % mid, file=sys.stderr)
        return 0, 0, ""
    
    
    
    def get_absolute_price(platform, model_name, api_price=None):
        PRICE_RESOLVER.official_prices = OFFICIAL_PRICES
        PRICE_RESOLVER.litellm_prices = LITELLM_DB
        result = PRICE_RESOLVER.get_absolute_price(platform, model_name, api_price)
        return result.input_price, result.output_price, result.context, result.source_tag
    
    
    
    # ═══════════════════════════════════════════════════════════
    
    
    # ═══════════════════════════════════════════════════════════
    # 数据抓取
    # ═══════════════════════════════════════════════════════════
    
    # ─── 始终从官方源抓取最新价格（无论是否使用 JSON 缓存） ───
    print("Fetching official prices..." if not RENDER_ONLY else "Render-only: skipping official price fetch", file=sys.stderr)
    OFFICIAL_PRICES = {} if RENDER_ONLY else fetch_official_prices(CONFIG.project_dir)
    set_official_prices(OFFICIAL_PRICES)
    print("  Official prices: %d models loaded" % len(OFFICIAL_PRICES), file=sys.stderr)
    
    if UPDATE_DB:
        print("Updating official_prices_db.json...", file=sys.stderr)
        db_path = os.path.join(SCRIPT_DIR, "official_prices_db.json")
        try:
            db_data = {}
            if os.path.exists(db_path):
                with open(db_path, "r", encoding="utf-8") as f:
                    db_data = json.load(f)
            def _scraped_platform(model_key, price_info):
                source = str(price_info.get("source", "")).lower()
                if model_key.startswith("sf:"): return "siliconflow", model_key[3:]
                source_map = [
                    ("deepseek", "deepseek"), ("moonshot", "moonshot"),
                    ("minimaxi", "minimax"), ("minimax", "minimax"),
                    ("aliyun", "aliyun"), ("dashscope", "aliyun"),
                    ("baidu", "baidu"), ("volcengine", "volcengine"),
                    ("tencent", "tencent"),
                ]
                for marker, platform_key in source_map:
                    if marker in source:
                        return platform_key, model_key
                return "", model_key
    
            added_count = 0
            skipped_count = 0
            for model_key, pinfo in OFFICIAL_PRICES.items():
                platform_key, normalized_key = _scraped_platform(model_key, pinfo)
                if not platform_key:
                    skipped_count += 1
                    logger.warning("跳过无法确认平台的价格记录: %s", model_key)
                    continue
                platform_data = db_data.setdefault(platform_key, {})
                platform_data.setdefault("_source", pinfo.get("source", "scraped"))
                platform_data.setdefault("_currency", pinfo.get("currency", "CNY"))
                existing = platform_data.get(normalized_key, {})
                platform_data[normalized_key] = {
                    "input": pinfo.get("input", existing.get("input", 0)),
                    "output": pinfo.get("output", existing.get("output", 0)),
                    "context": pinfo.get("context", existing.get("context", "N/A")),
                }
                added_count += 1
            db_data.setdefault("_meta", {})["updated_at"] = datetime.now().strftime("%Y-%m-%d")
            with open(db_path, "w", encoding="utf-8") as f:
                json.dump(db_data, f, indent=2, ensure_ascii=False)
            print("  Updated %d prices inside platform namespaces; skipped %d ambiguous records" % (added_count, skipped_count), file=sys.stderr)
        except Exception as e:
            print("  Error updating DB:", e, file=sys.stderr)
        sys.exit(0)
    
    
    # ─── 检查 models_data.json（伪动态方案：优先从静态 JSON 加载） ───
    MODELS_JSON = str(CONFIG.models_file)
    USE_JSON_DATA = False
    t0 = time.time()
    cards = []
    all_models = []
    price_changes = []
    source_runs = {}
    existing_catalog = {}
    if os.path.exists(MODELS_JSON):
        try:
            with open(MODELS_JSON, "r", encoding="utf-8") as existing_file:
                existing_catalog = json.load(existing_file)
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("无法读取既有目录作为历史基线: %s", error)
    prior_context_models = list(existing_catalog.get("models", []))
    data_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    or_prices = {}  # OpenRouter 价格查找表（始终可用）
    OR = []         # OpenRouter 原始数据
    
    if os.path.exists(MODELS_JSON) and not FORCE_REFRESH:
        _json_age_hours = (time.time() - os.path.getmtime(MODELS_JSON)) / 3600
        print("Loading models from JSON:", MODELS_JSON, "(age: %.1fh)" % _json_age_hours, file=sys.stderr)
        if _json_age_hours > 24 and not RENDER_ONLY:
            print("  ⚠️ models_data.json 已超过24小时，将重新生成", file=sys.stderr)
        try:
            jdata = existing_catalog
            jmodels = jdata.get("models", [])
            prior_context_models = jmodels
            jmeta = jdata.get("meta", {})
            source_runs = jmeta.get("source_runs", {}) if isinstance(jmeta.get("source_runs", {}), dict) else {}
            data_updated_at = jmeta.get("updated_at", data_updated_at)
            for m in jmodels:
                pid = m["platform_id"]
                pname = m["platform_name"]
                pc = m["platform_color"]
                mname = m["name"]
                if not str(pid).strip() or not str(mname).strip():
                    logger.warning("跳过无效缓存模型: platform=%r name=%r", pid, mname)
                    continue
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
                    _or_src = m.get("price_src","") or ("A" if (inp_orig > 0 or out_orig > 0) else "")
                    cards.append(make_or_card(pv, Te(mname), inp_orig, out_orig, ctx, tags, scen, Te(mname), family=fam, price_unit=pu, price_src=_or_src))
                else:
                    # ─── 用官方价格覆盖 JSON 缓存中的旧价格 ───
                    if OFFICIAL_PRICES and pid in ("siliconflow",):
                        # 硅基流动：尝试用 RSC 接口获取的真实价格覆盖
                        # 尝试多种键格式匹配（RSC modelName 可能带 Pro/ 前缀或不带）
                        mname_lower = mname.lower()
                        lookup_key = None
                        op_data = None
                        # 去掉已知前缀的组合
                        prefixes_to_strip = ["pro/", "deepseek-ai/", "thudm/", "qwen/", "minimaxai/", "moonshotai/", "stepfun-ai/", "inclusionai/", "zai-org/", "bytedance-seed/", "tencent/", "internlm/", "paddlepaddle/", "kwaipilot/"]
                        # 尝试1: 直接用 mname_lower 作为键
                        candidates = ["sf:" + mname_lower]
                        # 尝试2: 去掉所有前缀组合
                        temp = mname_lower
                        for pfx in prefixes_to_strip:
                            if temp.startswith(pfx):
                                temp = temp[len(pfx):]
                        candidates.append("sf:" + temp)
                        # 尝试3: Pro/ + 其他前缀
                        if mname_lower.startswith("pro/"):
                            temp2 = mname_lower[4:]  # 去掉 pro/
                            candidates.append("sf:" + temp2)
                            for pfx in prefixes_to_strip:
                                if temp2.startswith(pfx):
                                    temp2 = temp2[len(pfx):]
                                    candidates.append("sf:" + temp2)
                        for c in candidates:
                            if c in OFFICIAL_PRICES:
                                lookup_key = c
                                op_data = OFFICIAL_PRICES[c]
                                break
                        if op_data and (op_data.get("input", 0) > 0 or op_data.get("output", 0) > 0):
                            old_i, old_o = inp_orig, out_orig
                            new_i = op_data["input"]
                            new_o = op_data["output"]
                            if old_i != new_i or old_o != new_o:
                                price_changes.append({
                                    "p": pid, "n": mname,
                                    "old_i": old_i, "old_o": old_o,
                                    "new_i": new_i, "new_o": new_o,
                                })
                            inp_orig = new_i
                            out_orig = new_o
                    # 渲染模式严格沿用快照来源；刷新模式才重新解析价格来源。
                    if RENDER_ONLY:
                        _src_tag = m.get("price_src", "") or "H"
                    else:
                        _, _, _, _src_tag = get_absolute_price(pid, mname)
                    _effective_src = _src_tag or m.get("price_src", "") or "H"
                    cards.append(make_card(pid, pname, pc, Te(mname), inp_orig, out_orig, ctx, tags, scen, base_url, cur, family=fam, price_unit=pu, price_src=_effective_src))
                all_models.append({"p": pid, "n": mname, "i": inp_orig, "o": out_orig, "cur": cur, "src": m.get("price_src","") or _src_tag})
            price_changes = jmeta.get("price_changes", [])
            USE_JSON_DATA = _json_age_hours <= 24 or RENDER_ONLY
            if not USE_JSON_DATA:
                print("  缓存过期，将重新从API生成", file=sys.stderr)
            print("  Loaded %d models from JSON" % len(jmodels), file=sys.stderr)
            # 加载 OpenRouter 缓存用于交叉验证
            _or_cache = os.path.join(CACHE_DIR, "openrouter_full.json")
            if os.path.exists(_or_cache):
                try:
                    _or_data = json.load(open(_or_cache))
                    OR = _or_data.get("data", [])
                    for _m in OR:
                        _mid = _m.get("id", "")
                        _ii = float(_m.get("pricing", {}).get("prompt", 0) or 0)
                        _oo = float(_m.get("pricing", {}).get("completion", 0) or 0)
                        if _ii <= 0 and _oo <= 0: continue
                        _norm = normalize_for_match(_mid)
                        if _norm not in or_prices:
                            or_prices[_norm] = {"input_per_1m": _ii * 1e6, "output_per_1m": _oo * 1e6, "raw_name": _mid}
                    print("  OpenRouter prices (cache): %d models" % len(or_prices), file=sys.stderr)
                except: pass
        except Exception as e:
            print("  JSON load error:", str(e)[:100], file=sys.stderr)
            USE_JSON_DATA = False
    
    if not USE_JSON_DATA:
        print("Fetching data...")
        t0 = time.time()
        data_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        catalog_collection = collect_platform_catalog(CONFIG.api_keys, CONFIG.cache_dir, HTTP_CLIENT)
        source_runs.update(catalog_collection.source_runs)
    
        # ─── 已迁移平台：统一抓取结果 + 数据血缘 ───
        ali_result = catalog_collection["aliyun"]
        ali = [{
            "n": model["id"],
            "i": float(model.get("input_price") or 0),
            "o": float(model.get("output_price") or 0),
            "c": model.get("context", "N/A"),
            "t": model.get("tags", []),
            "s": model.get("scene", "日常对话"),
            "from_api": ali_result.metadata.source_type == "api",
        } for model in ali_result.models]
        print("  Aliyun:", len(ali), file=sys.stderr)
    
        siliconflow_result = catalog_collection["siliconflow"]
        sf_ids = [model["id"] for model in siliconflow_result.models]
        print("  SF:", len(sf_ids), file=sys.stderr)
    
        # ─── 月之暗面 ───
        moonshot_result = catalog_collection["moonshot"]
        ms_list = moonshot_result.models
        print("  Moonshot:", len(ms_list), file=sys.stderr)
    
        # ─── 智谱AI ───
        zhipu_result = catalog_collection["zhipu"]
        zh_ids = [model["id"] for model in zhipu_result.models]
        print("  Zhipu:", len(zh_ids), file=sys.stderr)
    
        # ─── 火山引擎 ───
        volcengine_result = catalog_collection["volcengine"]
        vc_list = volcengine_result.models
        print("  Volcengine:", len(vc_list), file=sys.stderr)
    
        # ─── OpenRouter（公开目录，失败时使用本地缓存） ───
        openrouter_result = catalog_collection["openrouter"]
        OR = openrouter_result.models
        print("  OpenRouter:", len(OR), file=sys.stderr)
    
        # 构建 OpenRouter 价格查找表
        or_prices = {}
        for _m in OR:
            _mid = _m.get("id", "")
            _ii = float(_m.get("input_price", 0) or 0)
            _oo = float(_m.get("output_price", 0) or 0)
            if _ii <= 0 and _oo <= 0:
                continue
            _norm = normalize_for_match(_mid)
            if _norm not in or_prices:
                or_prices[_norm] = {"input_per_1m": _ii * 1e6, "output_per_1m": _oo * 1e6, "raw_name": _mid}
        print("  OpenRouter prices lookup: %d models" % len(or_prices), file=sys.stderr)
    
        # ─── 腾讯混元 ───
        tencent_result = catalog_collection["tencent"]
        tx_ids = [model["id"] for model in tencent_result.models]
        print("  Tencent:", len(tx_ids), file=sys.stderr)
    
        # ─── 讯飞星火 ───
        spark_result = catalog_collection["spark"]
        xh_ids = [model["id"] for model in spark_result.models]
        print("  Spark:", len(xh_ids), file=sys.stderr)
    
        # ─── MiniMax ───
        minimax_result = catalog_collection["minimax"]
        mm_ids = [model["id"] for model in minimax_result.models]
        print("  MiniMax:", len(mm_ids), file=sys.stderr)
    
        # ─── 零一万物 ───
        yi_result = catalog_collection["yi"]
        yw_ids = [model["id"] for model in yi_result.models]
        print("  Yi:", len(yw_ids), file=sys.stderr)
    
        # ─── 百度文心（已弃用API，用 domestic_prices.json 兜底） ───
        BD = []
    
        # ─── 百川智能 ───
        baichuan_result = catalog_collection["baichuan"]
        bc_ids = [model["id"] for model in baichuan_result.models]
        print("  Baichuan:", len(bc_ids), file=sys.stderr)
    
        # ─── 阶跃星辰 ───
        jieyue_result = catalog_collection["jieyue"]
        jc_ids = [model["id"] for model in jieyue_result.models]
        print("  Jieyue:", len(jc_ids), file=sys.stderr)
    
        # ─── DeepSeek 官方 ───
        deepseek_result = catalog_collection["deepseek"]
        ds_ids = [model["id"] for model in deepseek_result.models]
        print("  DeepSeek:", len(ds_ids), file=sys.stderr)
    
        # ─── Groq ───
        groq_result = catalog_collection["groq"]
        gq_ids = [model["id"] for model in groq_result.models]
        print("  Groq:", len(gq_ids), file=sys.stderr)
    
        # ─── Together AI ───
        together_result = catalog_collection["together"]
        tg_list = together_result.models
        print("  Together:", len(tg_list), file=sys.stderr)
    
        # ─── Fireworks AI ───
        fireworks_result = catalog_collection["fireworks"]
        fw_list = fireworks_result.models
        print("  Fireworks:", len(fw_list), file=sys.stderr)
    
        # ─── Cohere ───
        cohere_result = catalog_collection["cohere"]
        co_list = cohere_result.models
        print("  Cohere:", len(co_list), file=sys.stderr)
    
        # 无问芯穹 (InfiniAI)
        infini_result = catalog_collection["infini"]
        infini_list = [model["id"] for model in infini_result.models]
        print("  InfiniAI:", len(infini_list), file=sys.stderr)
    
        # Novita AI
        novita_result = catalog_collection["novita"]
        novita_list = novita_result.models
        print("  Novita:", len(novita_list), file=sys.stderr)
    
        # DeepInfra（公开目录，包含真实定价）
        deepinfra_result = catalog_collection["deepinfra"]
        di_list = deepinfra_result.models
        print("  DeepInfra:", len(di_list), file=sys.stderr)
    
    
        # AiHubMix
        aihubmix_result = catalog_collection["aihubmix"]
        ahm_list = [model["id"] for model in aihubmix_result.models]
        print("  AiHubMix:", len(ahm_list), file=sys.stderr)
    
        # n1n.ai
        n1n_result = catalog_collection["n1n"]
        n1n_list = [model["id"] for model in n1n_result.models]
        n1n_prices = {
            model["id"]: (float(model.get("input_price") or 0), float(model.get("output_price") or 0))
            for model in n1n_result.models
            if model.get("input_price") or model.get("output_price")
        }
        print("  n1n.ai:", len(n1n_list), file=sys.stderr)
    
        # ChatAnywhere
        chatanywhere_result = catalog_collection["ca"]
        ca_list = [model["id"] for model in chatanywhere_result.models]
        ca_prices = {
            model["id"]: (float(model.get("input_price") or 0), float(model.get("output_price") or 0))
            for model in chatanywhere_result.models
            if model.get("input_price") or model.get("output_price")
        }
        print("  ChatAnywhere:", len(ca_list), file=sys.stderr)
    
        # ═══════════════════════════════════════════════════════════
        # 从官方定价页爬取价格
        # ═══════════════════════════════════════════════════════════
        # OFFICIAL_PRICES 已在进入数据抓取前加载，避免重复访问官方站点。
    
        # ═══════════════════════════════════════════════════════════
        # 生成模型卡片
        # ═══════════════════════════════════════════════════════════
    
        cards = []
        all_models = []  # 用于价格变动检测
    
        # 阿里百炼
        for m in ali:
            fam = get_family(m["n"])
            api_price = (m["i"], m["o"], m["c"]) if m.get("from_api") and (m["i"] > 0 or m["o"] > 0) else None
            ii, oo, cc, src = get_absolute_price("aliyun", m["n"], api_price=api_price)
            tt, ss = m["t"], m["s"]
            if src != "A":
                tt2, ss2 = infer_tags_and_scene(m["n"], ii, oo, cc)
                if not tt: tt = tt2
                if ss in ("日常对话",""): ss = ss2
            cards.append(make_card("aliyun","阿里百炼","#ff6a00",Te(m["n"]),ii,oo,cc,tt,ss,
                         "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"aliyun","n":m["n"],"i":ii,"o":oo,"src":src})
    
        # 硅基流动
        for mid in sf_ids:
            ii, oo, cc, src = get_absolute_price("siliconflow", mid)
            if not cc or cc == "N/A":
                cc = "32k"
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("siliconflow","硅基流动","#7C3AED",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.siliconflow.cn/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"siliconflow","n":mid,"i":ii,"o":oo,"src":src})
    
        # 月之暗面
        for m in ms_list:
            mid = m["id"]
            ii, oo, cc, src = get_absolute_price("moonshot", mid)
            if not cc or cc == "N/A":
                cc = m.get("context") or "N/A"
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("moonshot","月之暗面","#4f46e5",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.moonshot.cn/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"moonshot","n":mid,"i":ii,"o":oo,"src":src})
    
        # 智谱AI
        for mid in zh_ids:
            ii, oo, cc, src = get_absolute_price("zhipu", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("zhipu","智谱 AI","#00c4b4",Te(mid),ii,oo,cc,tt,ss,
                         "https://open.bigmodel.cn/api/paas/v4/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"zhipu","n":mid,"i":ii,"o":oo,"src":src})
    
        # 火山引擎
        for m in vc_list:
            mid = m["id"]; st = m.get("status","")
            ii, oo, cc, src = get_absolute_price("volcengine", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            tt = tt[:]
            if st == "Shutdown":  tt = ["已下线"] + tt
            elif st == "Retiring": tt = ["即将下线"] + tt
            fam = get_family(mid)
            cards.append(make_card("volcengine","火山引擎","#dc2626",Te(mid),ii,oo,cc,tt,ss,
                         "https://ark.cn-beijing.volces.com/api/v3/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"volcengine","n":mid,"i":ii,"o":oo,"src":src})
    
        # 百度文心
        for m in BD:
            mid = m["n"]
            fam = get_family(mid)
            api_price = (m["i"], m["o"], m["c"]) if (m["i"] > 0 and m["o"] > 0) else None
            ii, oo, cc, src = get_absolute_price("baidu", mid, api_price=api_price)
            if not cc or cc == "N/A":
                cc = m["c"]
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            cards.append(make_card("baidu","百度文心","#2932e1",Te(mid),ii,oo,cc,tt,ss,
                         "https://qianfan.baidubce.com/v2/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"baidu","n":mid,"i":ii,"o":oo,"src":src})
    
        # OpenRouter
        for m in OR:
            ii = float(m.get("input_price", 0) or 0)
            oo = float(m.get("output_price", 0) or 0)
            nn = Te(m.get("name", m.get("id", "")))
            cc_r = m.get("context_tokens") or 0
            cc = m.get("context") or "N/A"
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
            src = "A" if openrouter_result.metadata.source_type == "api" else "H"
            cards.append(make_or_card(pv, nn, ii, oo, cc, tt, ss, mid2, family=fam, price_src=src))
            all_models.append({"p":"openrouter","n":m.get("id",""),"i":ii,"o":oo,"cur":"USD","src":src})
    
        # 腾讯混元
        for mid in tx_ids:
            t_i, t_o, t_c = get_tencent_price(mid)
            if t_i > 0:
                ii, oo, cc, src = t_i, t_o, t_c, "T"
            else:
                ii, oo, cc, src = get_absolute_price("tencent", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("tencent","腾讯混元","#07c160",Te(mid),ii,oo,cc,tt,ss,
                         "https://hunyuan.tencentcloudapi.com/compatible-mode/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"tencent","n":mid,"i":ii,"o":oo,"src":src})
    
        # 讯飞星火
        for mid in xh_ids:
            ii, oo, cc, src = get_absolute_price("spark", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("spark","讯飞星火","#ff6a00",Te(mid),ii,oo,cc,tt,ss,
                         "https://spark-api.xf-yun.com/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"spark","n":mid,"i":ii,"o":oo,"src":src})
    
        # MiniMax
        for mid in mm_ids:
            ii, oo, cc, src = get_absolute_price("minimax", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("minimax","MiniMax","#6366f1",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.minimax.chat/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"minimax","n":mid,"i":ii,"o":oo,"src":src})
    
        # 零一万物
        for mid in yw_ids:
            ii, oo, cc, src = get_absolute_price("yi", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("yi","零一万物","#3b82f6",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.lingyiwanwu.com/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"yi","n":mid,"i":ii,"o":oo,"src":src})
    
        # 百川智能
        for mid in bc_ids:
            ii, oo, cc, src = get_absolute_price("baichuan", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("baichuan","百川智能","#ef4444",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.baichuan-ai.com/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"baichuan","n":mid,"i":ii,"o":oo,"src":src})
    
        # 阶跃星辰
        for mid in jc_ids:
            ii, oo, cc, src = get_absolute_price("jieyue", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("jieyue","阶跃星辰","#8b5cf6",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.stepfun.com/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"jieyue","n":mid,"i":ii,"o":oo,"src":src})
    
        # DeepSeek 官方
        for mid in ds_ids:
            ii, oo, cc, src = get_absolute_price("deepseek", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("deepseek","DeepSeek","#4d6dff",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.deepseek.com/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"deepseek","n":mid,"i":ii,"o":oo,"src":src})
    
        # Groq
        for mid in gq_ids:
            ii, oo, cc, src = get_absolute_price("groq", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("groq","Groq","#f55036",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.groq.com/openai/v1/chat/completions","USD",family=fam,price_unit="per_1m",price_src=src))
            all_models.append({"p":"groq","n":mid,"i":ii,"o":oo,"cur":"USD","src":src})
    
        # Together AI
        for m in tg_list:
            mid = m["id"]
            api_inp = m.get("input_price", 0)
            api_out = m.get("output_price", 0)
            api_ctx = m.get("context_tokens", 0)
            ii, oo, cc = get_db_price("together", mid)
            src = "DB" if (ii > 0 or oo > 0) else ""
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            if api_inp > 0 and api_out > 0:
                ii, oo = api_inp, api_out
                cc = m.get("context") or cc
                tt, ss = infer_tags_and_scene(mid, ii, oo, api_ctx)
                src = "A" if together_result.metadata.source_type == "api" else "H"
            fam = get_family(mid)
            cards.append(make_card("together","Together AI","#00d4ff",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.together.xyz/v1/chat/completions","USD",family=fam,price_unit="per_1m",price_src=src))
            all_models.append({"p":"together","n":mid,"i":ii,"o":oo,"cur":"USD","src":src})
    
        # Fireworks AI
        for m in fw_list:
            mid = m["id"]
            ii, oo, cc, src = get_absolute_price("fireworks", mid)
            api_ctx = m.get("context_tokens", 0)
            if api_ctx > 0:
                cc = m.get("context") or cc
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("fireworks","Fireworks AI","#ff6b35",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.fireworks.ai/inference/v1/chat/completions","USD",family=fam,price_unit="per_1m",price_src=src))
            all_models.append({"p":"fireworks","n":mid,"i":ii,"o":oo,"cur":"USD","src":src})
    
        # Cohere
        for m in co_list:
            mid = m["id"]
            ii, oo, cc, src = get_absolute_price("cohere", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("cohere","Cohere","#39d989",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.cohere.com/v2/chat/completions","USD",family=fam,price_unit="per_1m",price_src=src))
            all_models.append({"p":"cohere","n":mid,"i":ii,"o":oo,"cur":"USD","src":src})
    
        # 无问芯穹 (InfiniAI)
        for mid in infini_list:
            ii, oo, cc, src = get_absolute_price("infini", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("infini","无问芯穹","#ff6b9d",Te(mid),ii,oo,cc,tt,ss,
                         "https://cloud.infini-ai.com/maas/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"infini","n":mid,"i":ii,"o":oo,"src":src})
    
        # Novita AI
        for m in novita_list:
            mid = m["id"]
            api_inp = m.get("input_price", 0)
            api_out = m.get("output_price", 0)
            api_ctx = m.get("context_tokens", 0)
            if api_inp > 0 and api_out > 0:
                ii, oo = api_inp, api_out
                cc = m.get("context") or "N/A"
                tt, ss = infer_tags_and_scene(mid, ii, oo, api_ctx)
                src = "A" if novita_result.metadata.source_type == "api" else "H"
            else:
                ii, oo, cc = get_db_price("novita", mid)
                tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
                src = "DB" if (ii > 0 or oo > 0) else ""
            fam = get_family(mid)
            cards.append(make_card("novita","Novita AI","#6366f1",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.novita.ai/v3/openai/chat/completions","USD",family=fam,price_unit="per_1m",price_src=src))
            all_models.append({"p":"novita","n":mid,"i":ii,"o":oo,"cur":"USD","src":src})
    
        # DeepInfra
        for m in di_list:
            mid = m["id"]
            if m.get("input_price", 0) > 0 or m.get("output_price", 0) > 0:
                ii = m.get("input_price", 0)
                oo = m.get("output_price", 0)
                cc = m.get("context") or "N/A"
                tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
                src = "A" if deepinfra_result.metadata.source_type == "api" else "H"
            else:
                ii, oo, cc = get_db_price("deepinfra", mid)
                tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
                src = "DB" if (ii > 0 or oo > 0) else ""
                if src == "":
                    print("  ⚠️ PRICE_MISSING: [deepinfra] %s → 价格为0" % mid, file=sys.stderr)
            fam = get_family(mid)
            cards.append(make_card("deepinfra","DeepInfra","#7c3aed",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.deepinfra.com/v1/openai/chat/completions","USD",family=fam,price_unit="per_1m",price_src=src))
            all_models.append({"p":"deepinfra","n":mid,"i":ii,"o":oo,"cur":"USD","src":src})
    
        # AiHubMix
        for mid in ahm_list:
            ii, oo, cc, src = get_absolute_price("aihubmix", mid)
            tt, ss = infer_tags_and_scene(mid, ii, oo, cc)
            fam = get_family(mid)
            cards.append(make_card("aihubmix","AiHubMix","#10b981",Te(mid),ii,oo,cc,tt,ss,
                         "https://api.aihubmix.com/v1/chat/completions","USD",family=fam,price_unit="per_1m",price_src=src))
            all_models.append({"p":"aihubmix","n":mid,"i":ii,"o":oo,"cur":"USD","src":src})
    
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
                         "https://api.n1n.ai/v1/chat/completions","CNY",family=fam,price_src="P"))
            all_models.append({"p":"n1n","n":mid,"i":ii,"o":oo,"cur":"CNY","src":"P"})
    
        # ChatAnywhere
        for mid in ca_list:
            ii, oo, src = cap(mid)
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
                         "https://api.chatanywhere.org/v1/chat/completions","CNY",family=fam,price_src=src))
            all_models.append({"p":"ca","n":mid,"i":ii,"o":oo,"cur":"CNY","src":src})
    
        # ─── 多源交叉验证已移除（不再依赖多源交叉验证）───
    
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
    
    # ─── 价格漂移检测已移除（不再依赖第三方数据源交叉验证）───
    drift_list = []
    
    # 每次运行都发送通知
    if not RENDER_ONLY and not CONFIG.defer_success_notification:
        send_telegram_refresh(
            CONFIG.telegram_bot_token,
            CONFIG.telegram_chat_id,
            total,
            price_changes,
        )
    
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
    cac = cn("ca")
    
    def tc(p): return sum(1 for c in cards if 'data-pt="' + p + '"' in c)
    print("  Tier free:%d cheap:%d mid:%d high:%d ultra:%d unknown:%d" % (
        tc("free"),tc("cheap"),tc("mid"),tc("high"),tc("ultra"),tc("unknown")), file=sys.stderr)
    
    now = data_updated_at
    
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
        '<button class="pt-filter" data-pt="unknown">&#9898; 价格待确认</button>'
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
        '<button class="pt" data-p="aihubmix" style="--c:#10b981;--bg:#ecfdf5">AiHubMix <span class="pc">' + str(ahmc) + '</span></button>'
        '<button class="pt" data-p="n1n" style="--c:#f59e0b;--bg:#fffbeb">n1n.ai <span class="pc">' + str(n1nc) + '</span></button>'
        '<button class="pt" data-p="ca" style="--c:#06b6d4;--bg:#ecfeff">ChatAnywhere <span class="pc">' + str(cac) + '</span></button>'
    )
    
    snote = (
        "&#9888; <strong>数据说明：</strong>"
        "阿里百炼 <strong>" + str(ac) + "个模型</strong>从 API 直接采集；"
        "硅基流动/" + str(sc2) + "个、月之暗面/" + str(mc2) + "个、智谱/" + str(zc) + "个等从 API 采集列表，价格来自各平台官网公告；"
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
        '<div class="cross-panel" id="crossPanel" style="display:block">'
        '<div class="cross-title">&#128269; 跨平台比价 <span style="font-weight:400;font-size:12px;color:var(--text2)">(同一模型在不同平台的价格)</span></div>'
        '<div class="cross-search"><input type="search" id="crossSearchInput" aria-label="跨平台模型搜索" placeholder="输入模型名搜索比价..." oninput="buildCrossPrice()"><button class="cross-search-clear" aria-label="清空比价搜索" onclick="document.getElementById(\'crossSearchInput\').value=\'\';buildCrossPrice()">✕</button></div>'
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
        '<label for="calcChats">每月对话次数:</label><input type="number" id="calcChats" value="1000" min="0">'
        '</div>'
        '<div class="calc-row">'
        '<label for="calcTokens">每对话Token数:</label><input type="number" id="calcTokens" value="2000" min="0">'
        '</div>'
        '<div class="calc-row">'
        '<label for="calcRatio">输出/输入比:</label><input type="number" id="calcRatio" value="1" min="0" step="0.1">'
        '</div>'
        '<div class="calc-row">'
        '<label for="calcBudget">月预算(元):</label><input type="number" id="calcBudget" value="" min="0" placeholder="可选">'
        '</div>'
        '<div class="calc-btns">'
        '<button class="calc-btn" onclick="runCalc()">计算月费用</button>'
        '<button class="calc-btn calc-btn-all" onclick="runCalcAll()">计算全部模型</button>'
        '<button class="calc-btn calc-btn-rev" onclick="runCalcReverse()">预算反推</button>'
        '</div>'
        '<div class="calc-result" id="calcResult"></div>'
        '</div>'
    )
    
    # ─── 价格漂移报告面板 ───
    drift_panel = ""
    if drift_list:
        drift_rows = ""
        for d in drift_list:
            pct = d["drift_pct"]
            if pct > 20:
                cls = "drift-red"
            elif pct >= 5:
                cls = "drift-yellow"
            else:
                cls = "drift-green"
            drift_rows += (
                '<div class="drift-item ' + cls + '">'
                '<span class="drift-model">' + Te(d["model_name"]) + '</span>'
                '<span class="drift-platform">' + Te(d["platform"]) + '</span>'
                '<span class="drift-our">¥' + ("%.4f" % d["our_price"]) + '/M</span>'
                '<span class="drift-ref">¥' + ("%.4f" % d["ref_price"]) + '/M</span>'
                '<span class="drift-src">' + Te(d["ref_source"]) + '</span>'
                '<span class="drift-pct">' + ("%.1f" % pct) + '%</span>'
                '</div>'
            )
        drift_panel = (
            '<div class="drift-panel" id="driftPanel">'
            '<div class="drift-title">&#128270; 价格漂移检测</div>'
            '<div class="drift-desc">硬编码价格与 OpenRouter/LiteLLM 参考价格偏差 ≥5% 的模型（共 ' + str(len(drift_list)) + ' 个）</div>'
            '<div class="drift-legend"><span class="drift-green">&#9679;</span> &lt;5% <span class="drift-yellow">&#9679;</span> 5-20% <span class="drift-red">&#9679;</span> &gt;20%</div>'
            '<div class="drift-header-row">'
            '<span class="drift-model">模型</span>'
            '<span class="drift-platform">平台</span>'
            '<span class="drift-our">我方价格</span>'
            '<span class="drift-ref">参考价格</span>'
            '<span class="drift-src">参考源</span>'
            '<span class="drift-pct">偏差</span>'
            '</div>'
            '<div class="drift-list">' + drift_rows + '</div>'
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
        '<div class="cmp-modal" id="cmpModal" style="display:none" role="dialog" aria-modal="true" aria-labelledby="cmpModalTitle">'
        '<div class="cmp-modal-content">'
        '<div class="cmp-modal-header"><span id="cmpModalTitle">模型对比详情</span><button class="cmp-close" aria-label="关闭模型对比" onclick="closeCmpModal()">&times;</button></div>'
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
    
    
    # CSS (完整样式)
    # ═══════════════════════════════════════════════════════════
    
    CSS = load_asset("assets/styles.css")
    
    
    # ═══════════════════════════════════════════════════════════
    # JavaScript (完整前端逻辑)
    # ═══════════════════════════════════════════════════════════
    
    frontend_scripts = [
        "assets/js/i18n.js",
        "assets/js/routing.js",
        "assets/js/analytics.js",
        "assets/js/core.js",
        "assets/js/alerts.js",
        "assets/js/reports.js",
    ]
    for script_path in frontend_scripts:
        load_asset(script_path)
    script_tags = "\n".join(
        f'<script src="/{script_path}" defer></script>' for script_path in frontend_scripts
    )
    
    
    # ═══════════════════════════════════════════════════════════
    # 组装 HTML
    # ═══════════════════════════════════════════════════════════
    
    HDR = render_template("templates/document_head.html", {
        "STYLES": CSS,
        "TOTAL": total,
        "DATA_NOTE": snote,
        "UPDATED_AT": now,
        "PRICE_CHANGE_HTML": price_change_html,
    }) + (
        # ─── 左侧筛选栏 + 右侧内容 布局 ───
        '<button class="sidebar-toggle" aria-label="打开筛选器" aria-controls="sidebar" aria-expanded="false" onclick="toggleSidebar()">&#9776;</button>\n'
        '<div class="main-layout">\n'
        # ─── 左侧 Sidebar ───
        '<div class="sidebar" id="sidebar" role="region" aria-label="模型筛选器">\n'
        # 清除筛选按钮
        '<button class="clear-filter-btn" onclick="clearAllFilters()">✕ 清除筛选</button>\n'
        '<div class="srow"><input id="si" type="search" aria-label="搜索模型" placeholder="搜索模型..." oninput="filter()" onkeydown="if(event.key===\'Escape\'){this.value=\'\';filter()}" style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface2);color:var(--text);font-size:12px" onfocus="this.style.borderColor=\'var(--accent)\'" onblur="this.style.borderColor=\'var(--border)\'"></div>\n'
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
        # 跨平台比价（默认展开）
        '<div class="fg fg-collapsible">\n'
        '<div class="fg-title" onclick="toggleFg(this)">跨平台比价 <span class="fg-arrow">▾</span></div>\n'
        '<div class="fg-body">' + crossprice_panel.replace('id="crossList"', 'id="crossList" tabindex="0" aria-label="跨平台比价结果"') + '</div>\n'
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
        '<button class="tool-btn" id="shareBtn" onclick="copyShareLink()">&#128279; 分享</button>\n'
        '</div></div>\n'
        '</div>\n'
        # 侧面板（默认折叠）
        '<div class="fg fg-collapsible fg-collapsed">\n'
        '<div class="fg-title" onclick="toggleFg(this)">月费计算器 <span class="fg-arrow">▸</span></div>\n'
        '<div class="fg-body">' + calc_panel + '</div>\n'
        '</div>\n'
        '<div class="fg fg-collapsible fg-collapsed">\n'
        '<div class="fg-title" onclick="toggleFg(this)">⚠ Rate Limits <span class="fg-arrow">▸</span></div>\n'
        '<div class="fg-body">' + rl_panel + '</div>\n'
        '</div>\n'
        + ('<div class="fg fg-collapsible fg-collapsed">\n'
           '<div class="fg-title" onclick="toggleFg(this)">&#128270; 价格漂移 <span class="fg-arrow">▸</span></div>\n'
           '<div class="fg-body">' + drift_panel + '</div>\n'
           '</div>\n' if drift_panel else '')
        + '</div>\n'  # /sidebar
        # ─── 右侧内容区 ───
        '<div class="content-area" id="catalog" tabindex="-1">\n'
        + cmp_panel + '\n'
    
        '<div class="filter-count" id="filterCount">显示 <strong>' + str(total) + '</strong> / ' + str(total) + ' 个模型 <span style="font-weight:400;color:#94a3b8;font-size:10px;margin-left:8px">价格来源: <span class="price-src" title="API实时返回">A</span>=API <span class="price-src" title="官方定价页爬取">S</span>=爬取 <span class="price-src" title="官方价格数据库">DB</span>=数据库 <span class="price-src" title="LiteLLM社区数据">L</span>=LiteLLM <span class="price-src price-src-proxy" title="代理平台自营价,非官方价">P</span>=代理自营</span></div>\n'
            '<div class="loading" id="ld"><div class="sp"></div>加载中...</div>\n'
        '<div class="grid" id="grid" aria-live="polite" aria-busy="true">\n'
    )
    
    FTR = (
        '</div>\n'
        '</div>\n'
        '</div>\n'
        '\n</div>\n'
        '<div class="pagination" id="pagination" role="region" aria-label="模型分页"></div>\n'
        '<div class="empty" id="empty" style="display:none">没有找到符合条件的模型</div>\n'
        '</div>\n'
        '<footer class="ftr">'
        '<div class="wechat-qr">'
        '<img src="/assets/wechat-qr.jpg" alt="微信二维码" class="qr-img" width="908" height="908" loading="lazy" decoding="async">'
        '<p class="qr-text">扫码加微信 &middot; 获取最新AI模型资讯</p>'
        '</div>'
        '<p>&#128202; 数据来源：各平台 API 直接采集 + 官网公告（更新时间：' + now + '）</p>'
        '<p>OpenRouter 显示原始美元价格 &middot; 国内平台显示人民币价格 &middot; 点击卡片复制接入方式</p>'
        '<p>快捷键: / 搜索 | Esc 清空 | D 暗色 | V 视图 | 1-9 切换平台</p>'
        '<p><a href="https://github.com/k-goz/model-selector" target="_blank">GitHub</a> &middot; <a href="https://cloud.siliconflow.cn/i/exbVXMa4" target="_blank" class="invite-link">&#9734; 支持开发者 — 注册硅基流动领代金券</a></p>'
        '</footer>\n'
        # My Insights 板块（小红书同步内容）
        + load_asset("templates/insights.html")
        # AdSense 底部广告位
        + '<aside class="ad-container ad-bottom" aria-label="底部广告"><ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-XXXXXXXXXXXXXXXX" data-ad-slot="XXXXXXXXXX" data-ad-format="auto" data-full-width-responsive="true"></ins><script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></aside>\n'
        '<div id="toast" class=""></div>\n'
        # Token 计价器模态框
        '<div class="tk-modal" id="tkModal" role="dialog" aria-modal="true" aria-labelledby="tkModalTitle" onclick="if(event.target===this)closeTokenCalc()">'
        '<div class="tk-modal-content">'
        '<div class="tk-modal-header"><div class="tk-modal-title" id="tkModalTitle">&#128270; 真实文本计价器</div><button class="tk-modal-close" aria-label="关闭计价器" onclick="closeTokenCalc()">&times;</button></div>'
        '<div class="tk-modal-body">'
        '<div style="margin-bottom:8px;font-size:11px;color:var(--text2)">粘贴你的代码或文案，自动计算 Token 数并对比各平台花费</div>'
        '<textarea class="tk-textarea" id="tkText" aria-label="待计价文本" placeholder="在此粘贴文本...\n\n支持中文、英文、代码混合内容"></textarea>'
        '<div class="tk-stats" id="tkStats"></div>'
        '<div style="margin-bottom:8px">'
        '<button class="tk-btn" onclick="calcTokens()">计算 Token</button>'
        '<button class="tk-btn tk-btn-sec" onclick="clearTokenCalc()">清空</button>'
        '<span style="font-size:10px;color:var(--text3);margin-left:8px">分词器: GPT-4 Cl100k (近似)</span>'
        '</div>'
        '<div id="tkResult"></div>'
        '</div></div></div>\n'
        # TTFB 测速模态框
        '<div class="ping-modal" id="pingModal" role="dialog" aria-modal="true" aria-labelledby="pingModalTitle" onclick="if(event.target===this)closePingModal()">'
        '<div class="ping-modal-content">'
        '<div class="ping-modal-header"><div class="ping-modal-title" id="pingModalTitle">&#9889; 接口测速 (TTFB)</div><button class="ping-modal-close" aria-label="关闭测速" onclick="closePingModal()">&times;</button></div>'
        '<div class="ping-modal-body">'
        '<div style="margin-bottom:8px;font-size:11px;color:var(--text2)">输入模型名，自动测所有平台该模型的 TTFB，按延迟从低到高排序</div>'
        '<input class="tk-model-input" id="pingModelInput" aria-label="测速模型名" placeholder="输入模型名搜索，如: deepseek-v3" oninput="updatePingSuggestions()">'
        '<div id="pingSuggestions" style="margin-bottom:8px"></div>'
        '<div style="margin-bottom:8px">'
        '<button class="ping-btn" id="pingStartBtn" onclick="startPing()">测速所有平台</button>'
        '<button class="ping-btn" style="background:var(--surface2);color:var(--text2);border:1px solid var(--border)" onclick="clearPingResult()">清除结果</button>'
        '<span style="font-size:10px;color:var(--text3);margin-left:8px">仅测 API 连接速度，不消耗 Token</span>'
        '</div>'
        '<div class="ping-result-list" id="pingResultList"></div>'
        '</div></div></div>\n'
        '<div class="code-modal" id="codeModal" role="dialog" aria-modal="true" aria-labelledby="codeModalTitle" onclick="if(event.target===this)closeCodeModal()">'
        '<div class="code-modal-content">'
        '<div class="code-modal-header"><div class="code-modal-title" id="codeModalTitle"><span>&#128187;</span> 一键接入 <span class="cm-model"></span></div><button class="code-modal-close" aria-label="关闭接入代码" onclick="closeCodeModal()">&times;</button></div>'
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
        + script_tags + '\n'
        '</body>\n</html>'
    )
    
    shell_content = [
        '<noscript><p class="no-js-message">请启用 JavaScript 以加载模型目录；原始数据可直接访问 models_data.json。</p></noscript>'
    ]
    HTML = compose_page(HDR, shell_content, FTR)
    
    with open(OUT,"w",encoding="utf-8") as f:
        f.write(HTML)
    sz = os.path.getsize(OUT)
    
    # ─── 自动更新 models_data.json（保持数据同步） ───
    if RENDER_ONLY:
        print("  Render-only: models_data.json preserved", file=sys.stderr)
    else:
        try:
            catalog = build_catalog(
                cards=cards,
                updated_at=data_updated_at,
                source_runs=source_runs,
                price_changes=price_changes,
                use_json_data=USE_JSON_DATA,
                official_prices=OFFICIAL_PRICES,
                official_prices_db=OFFICIAL_PRICES_DB,
                prior_context_models=prior_context_models,
            )
            history_root = CONFIG.models_file.parent / "data"
            history_before = existing_catalog if existing_catalog.get("models") else catalog
            history_diff = write_history_artifacts(
                history_before,
                catalog,
                history_path=history_root / "history" / "price-history.json",
                diff_path=history_root / "diffs" / "latest.json",
                summary_path=history_root / "history" / "summary.json",
            )
            write_lifecycle_archive(
                history_root / "history" / "lifecycle-archive.json",
                history_before,
                catalog,
                history_diff,
            )
            quality_report = assess_catalog_risk(
                history_before,
                catalog,
                history_diff,
                policy=load_policy(history_root / "quality" / "baseline.json"),
            )
            write_quality_report(history_root / "quality" / "latest-report.json", quality_report)
            if quality_report["status"] == "blocked":
                raise RuntimeError("高风险目录差异阻止发布: %s" % quality_report["high_risk"])
            write_catalog(CONFIG.models_file, catalog)
            print("  models_data.json updated (%d models)" % total, file=sys.stderr)
            print("  Catalog diff: %s" % history_diff["summary"], file=sys.stderr)
        except Exception as error:
            print("  models_data.json update failed:", str(error)[:80], file=sys.stderr)
            raise
    # ─── 每日测速并保存历史数据 ───
    try:
        if RENDER_ONLY:
            raise RuntimeError("render-only mode: skip ping probes")
        with open(MODELS_JSON, "r", encoding="utf-8") as _pf:
            _ping_models = json.load(_pf).get("models", [])
        _ok_count, _target_count = update_ping_history(
            _ping_models,
            os.path.join(CACHE_DIR, "ping_history.json"),
            os.path.join(SCRIPT_DIR, "ping_analysis.json"),
        )
        print("  Ping: %d/%d platforms tested" % (_ok_count, _target_count), file=sys.stderr)
    except Exception as _e:
        if RENDER_ONLY:
            print("  Render-only: ping probes skipped", file=sys.stderr)
        else:
            print("  Ping skipped:", str(_e)[:60], file=sys.stderr)
    
    
    print("Stats: OR:%d Ali:%d SF:%d MS:%d ZH:%d VC:%d BD:%d TX:%d XH:%d MM:%d YW:%d BC:%d JC:%d DS:%d GQ:%d TG:%d FW:%d CO:%d IF:%d NV:%d DI:%d AH:%d N1:%d CA:%d Total:%d" % (
        oc,ac,sc2,mc2,zc,vc2,bc2,tc2,xc,mmc,yc,bcc,jcc,dc,gc,tgc,fwc,coc,ic,nc,dic,ahmc,n1nc,cac,total))
    print("Time: %.1fs" % (time.time()-t0))
    
    # ─── 自动生成英文版 en/index.html ───
    try:
        write_english_version(HTML, CONFIG.project_dir / "en" / "index.html")
    except Exception as error:
        logger.error("英文版生成失败: %s", error)
    
