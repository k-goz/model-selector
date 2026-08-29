"""Official pricing-source collection kept outside the generator entrypoint."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request

from .sources import parse_deepseek_pricing_html, parse_moonshot_pricing_markdown


def fetch_official_prices(script_dir: str | Path):
    """从官方定价页爬取价格，返回 {model_name: {"input": float, "output": float, "currency": str, "source": str}}"""
    prices = {}

    def _fh(url, timeout=20):
        h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers=h)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.read().decode("utf-8", errors="ignore")
            except Exception as e:
                if attempt == 0:
                    time.sleep(1)
                else:
                    print("  fetch_official_prices fetch error: %s [%s]" % (str(e)[:60], url), file=sys.stderr)
                    return None

    # 1. DeepSeek - 官方表格含空闲/高峰双价；发布高峰价并保留区间。
    try:
        src = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing"
        h = _fh(src)
        if h:
            for model_name, price in parse_deepseek_pricing_html(h).items():
                prices[model_name] = {**price, "source": src}
            print("  fetch_official_prices: DeepSeek %d models" % sum(1 for k in prices if k.startswith("deepseek")), file=sys.stderr)
    except Exception as e:
        print("  fetch_official_prices: DeepSeek error:", str(e)[:80], file=sys.stderr)

    # 2. 月之暗面 - 使用官方机器可读 Markdown，避免 SSR 混入其他表格。
    try:
        source_url = "https://platform.kimi.com/docs/pricing/chat-v1.md"
        h = _fh(source_url)
        if h:
            for model_name, price in parse_moonshot_pricing_markdown(h).items():
                prices[model_name] = {**price, "source": source_url}
            print("  fetch_official_prices: Moonshot %d models" % sum(1 for k in prices if k.startswith("moonshot")), file=sys.stderr)
    except Exception as e:
        print("  fetch_official_prices: Moonshot error:", str(e)[:80], file=sys.stderr)

    # 3. 腾讯混元 - 通过 Jina Reader 提取 SPA 页面
    try:
        jina_url = "https://r.jina.ai/https://cloud.tencent.com/document/product/1729"
        jina_h = {"User-Agent": "Mozilla/5.0", "Accept": "text/plain"}
        jina_req = urllib.request.Request(jina_url, headers=jina_h)
        with urllib.request.urlopen(jina_req, timeout=20) as jina_r:
            jina_text = jina_r.read().decode("utf-8", errors="ignore")
        # 在 markdown 文本中寻找价格表格行 (如 "hunyuan-turbos 0.8 2")
        for line in jina_text.split("\n"):
            if "hunyuan" in line.lower() and "|" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    _mn = parts[0].strip().lower()
                    _iv = re.search(r'([\d.]+)', parts[1])
                    _ov = re.search(r'([\d.]+)', parts[2]) if len(parts) > 2 else None
                    if _iv and _ov:
                        prices[_mn] = {"input": float(_iv.group(1)), "output": float(_ov.group(1)), "currency": "CNY", "source": "jina:腾讯混元"}
        if any("hunyuan" in k for k in prices):
            print("  fetch_official_prices: Tencent (Jina) %d models" % sum(1 for k in prices if "hunyuan" in k), file=sys.stderr)
    except Exception as e:
        print("  fetch_official_prices: Tencent Jina error:", str(e)[:60], file=sys.stderr)
    # 如需爬取，需使用 headless browser（selenium/playwright）
    # try:
    #     h = _fh("https://cloud.tencent.com/document/product/1729/97731")
    #     ...
    # except Exception as e:
    #     print("  fetch_official_prices: Tencent error:", str(e)[:80], file=sys.stderr)

    # 4. MiniMax - Mintlify SSR，表格含 model / input / output / cache_read / cache_write
    try:
        h = _fh("https://platform.minimaxi.com/docs/guides/pricing-paygo")
        if h:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', h, re.DOTALL)
            for i in range(len(tds) - 2):
                model_txt = re.sub(r'<[^>]+>', '', tds[i]).strip()
                ml = model_txt.lower()
                if not model_txt or not ('minimax' in ml or 'abab' in ml or 'm2' in ml):
                    continue
                mn = ml.replace(' ', '-').strip()
                if mn in prices:
                    continue
                for j in range(i + 1, min(i + 3, len(tds))):
                    inp_txt = re.sub(r'<[^>]+>', '', tds[j]).strip()
                    inp_m = re.search(r'^([\d.]+)', inp_txt)
                    if inp_m and float(inp_m.group(1)) > 0:
                        iv = float(inp_m.group(1))
                        for k in range(j + 1, min(j + 3, len(tds))):
                            out_txt = re.sub(r'<[^>]+>', '', tds[k]).strip()
                            out_m = re.search(r'^([\d.]+)', out_txt)
                            if out_m and float(out_m.group(1)) > 0:
                                ov = float(out_m.group(1))
                                if ov >= iv:
                                    prices[mn] = {"input": iv, "output": ov, "currency": "CNY",
                                                 "source": "https://platform.minimaxi.com/docs/guides/pricing-paygo"}
                                    break
                        break
            print("  fetch_official_prices: MiniMax %d models" % sum(1 for k in prices if "minimax" in k or "abab" in k or "m2" in k), file=sys.stderr)
    except Exception as e:
        print("  fetch_official_prices: MiniMax error:", str(e)[:80], file=sys.stderr)

    # 5. 阿里百炼 - 阿里云帮助文档
    try:
        h = _fh("https://help.aliyun.com/zh/model-studio/getting-started/models")
        if h:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', h, re.DOTALL)
            for i in range(len(tds) - 2):
                model_txt = re.sub(r'<[^>]+>', '', tds[i]).strip().lower()
                if not model_txt or not ('qwen' in model_txt or 'qwq' in model_txt):
                    continue
                mn = model_txt.strip()
                if mn in prices:
                    continue
                for j in range(i + 1, min(i + 4, len(tds))):
                    inp_txt = re.sub(r'<[^>]+>', '', tds[j]).strip()
                    inp_m = re.search(r'^([\d.]+)', inp_txt)
                    if inp_m and float(inp_m.group(1)) > 0:
                        iv = float(inp_m.group(1))
                        for k in range(j + 1, min(j + 3, len(tds))):
                            out_txt = re.sub(r'<[^>]+>', '', tds[k]).strip()
                            out_m = re.search(r'^([\d.]+)', out_txt)
                            if out_m and float(out_m.group(1)) > 0:
                                ov = float(out_m.group(1))
                                if ov >= iv:
                                    prices[mn] = {"input": iv, "output": ov, "currency": "CNY",
                                                 "source": "https://help.aliyun.com/zh/model-studio/getting-started/models"}
                                    break
                        break
            print("  fetch_official_prices: Aliyun %d models" % sum(1 for k in prices if "qwen" in k or "qwq" in k), file=sys.stderr)
    except Exception as e:
        print("  fetch_official_prices: Aliyun error:", str(e)[:80], file=sys.stderr)

    # 6. 硅基流动 - Next.js RSC 接口，无需 API Key，无需 Playwright
    try:
        rsc_url = "https://siliconflow.cn/models?_rsc=1wtp7"
        rsc_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "RSC": "1",
            "Next-Router-State-Tree": "%5B%22%22%2C%7B%22children%22%3A%5B%22models%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%5D%7D%5D%7D%2Cnull%2Cnull%2Ctrue%5D",
        }
        req = urllib.request.Request(rsc_url, headers=rsc_headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        lines = raw.split("\n")
        # 数据在第5行(0-indexed)，包含 "data":[ 数组
        for line in lines:
            data_start = line.find('"data":[')
            if data_start == -1:
                continue
            arr_start = line.find("[", data_start + 6)
            # 用栈匹配括号
            depth = 0
            arr_end = arr_start
            for ci in range(arr_start, min(arr_start + 300000, len(line))):
                if line[ci] == "[":
                    depth += 1
                elif line[ci] == "]":
                    depth -= 1
                    if depth == 0:
                        arr_end = ci + 1
                        break
            json_str = line[arr_start:arr_end]
            models_arr = json.loads(json_str)
            sf_count = 0
            for m in models_arr:
                if m.get("type") not in ("text",):
                    continue
                if m.get("subType") not in ("chat",):
                    continue
                mn_raw = m.get("modelName", "")
                mn = mn_raw.lower().strip()
                if not mn:
                    continue
                ip = float(m.get("inputPrice", 0) or 0)
                op = float(m.get("outputPrice", 0) or 0)
                # 存储多个键以覆盖不同命名格式
                keys = ["sf:" + mn]
                # 去掉 Pro/ 前缀
                if mn.startswith("pro/"):
                    keys.append("sf:" + mn[4:])
                # 去掉 provider 前缀
                for pfx in ["deepseek-ai/", "thudm/", "qwen/", "minimaxai/", "moonshotai/", "stepfun-ai/", "inclusionai/", "zai-org/", "bytedance-seed/", "tencent/", "internlm/", "paddlepaddle/", "kwaipilot/"]:
                    if mn.startswith(pfx):
                        keys.append("sf:" + mn[len(pfx):])
                    if mn.startswith("pro/" + pfx):
                        keys.append("sf:" + mn[4 + len(pfx):])
                entry = {
                    "input": ip,
                    "output": op,
                    "currency": "CNY",
                    "source": "https://siliconflow.cn/models",
                    "platform": "siliconflow",
                    "raw_name": mn_raw,
                }
            for key in keys:
                if key not in prices:
                    prices[key] = entry
            sf_count += 1
        print("  fetch_official_prices: SiliconFlow RSC %d models" % sf_count, file=sys.stderr)
    except Exception as e:
        print("  fetch_official_prices: SiliconFlow RSC error:", str(e)[:80], file=sys.stderr)

    # 7. 百度文心 - 百度智能云文档
    try:
        h = _fh("https://cloud.baidu.com/doc/WENXINWORKSHOP/s/hlxqvkx82")
        if h:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', h, re.DOTALL)
            for i in range(len(tds) - 3):
                model_txt = re.sub(r'<[^>]+>', '', tds[i]).strip().lower()
                if not model_txt or 'ernie' not in model_txt:
                    continue
                mn = model_txt.replace(' ', '-').strip()
                if mn in prices:
                    continue
                for j in range(i + 1, min(i + 4, len(tds))):
                    inp_txt = re.sub(r'<[^>]+>', '', tds[j]).strip()
                    inp_m = re.search(r'([\d.]+)\s*(?:元|/)', inp_txt)
                    if inp_m and float(inp_m.group(1)) > 0:
                        iv = float(inp_m.group(1))
                        # 通常按千 tokens 计费，我们需要转为百万 tokens
                        if "千" in inp_txt or "1000" in inp_txt:
                            iv *= 1000
                        for k in range(j + 1, min(j + 3, len(tds))):
                            out_txt = re.sub(r'<[^>]+>', '', tds[k]).strip()
                            out_m = re.search(r'([\d.]+)\s*(?:元|/)', out_txt)
                            if out_m and float(out_m.group(1)) > 0:
                                ov = float(out_m.group(1))
                                if "千" in out_txt or "1000" in out_txt:
                                    ov *= 1000
                                prices[mn] = {"input": iv, "output": ov, "currency": "CNY",
                                             "source": "https://cloud.baidu.com/doc/WENXINWORKSHOP/s/hlxqvkx82"}
                                break
                        break
            print("  fetch_official_prices: Baidu %d models" % sum(1 for k in prices if "ernie" in k), file=sys.stderr)
    except Exception as e:
        print("  fetch_official_prices: Baidu error:", str(e)[:80], file=sys.stderr)

    # 8. 火山引擎 (Doubao)
    try:
        h = _fh("https://www.volcengine.com/docs/82379/1099320")
        if h:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', h, re.DOTALL)
            for i in range(len(tds) - 3):
                model_txt = re.sub(r'<[^>]+>', '', tds[i]).strip().lower()
                if not model_txt or 'doubao' not in model_txt:
                    continue
                mn = model_txt.replace(' ', '-').strip()
                if mn in prices:
                    continue
                for j in range(i + 1, min(i + 4, len(tds))):
                    inp_txt = re.sub(r'<[^>]+>', '', tds[j]).strip()
                    inp_m = re.search(r'([\d.]+)\s*(?:元|/)', inp_txt)
                    if inp_m and float(inp_m.group(1)) > 0:
                        iv = float(inp_m.group(1))
                        if "千" in inp_txt or "1000" in inp_txt:
                            iv *= 1000
                        for k in range(j + 1, min(j + 3, len(tds))):
                            out_txt = re.sub(r'<[^>]+>', '', tds[k]).strip()
                            out_m = re.search(r'([\d.]+)\s*(?:元|/)', out_txt)
                            if out_m and float(out_m.group(1)) > 0:
                                ov = float(out_m.group(1))
                                if "千" in out_txt or "1000" in out_txt:
                                    ov *= 1000
                                prices[mn] = {"input": iv, "output": ov, "currency": "CNY",
                                             "source": "https://www.volcengine.com/docs/82379/1099320"}
                                break
                        break
            print("  fetch_official_prices: Volcengine %d models" % sum(1 for k in prices if "doubao" in k), file=sys.stderr)
    except Exception as e:
        print("  fetch_official_prices: Volcengine error:", str(e)[:80], file=sys.stderr)

    # 9. 加载本地 tencent_prices.json 兜底
    try:
        tencent_file = os.path.join(str(script_dir), "tencent_prices.json")
        if os.path.exists(tencent_file):
            with open(tencent_file, 'r', encoding='utf-8') as f:
                t_data = json.load(f)
            t_count = 0
            for k, v in t_data.items():
                mn = v.get("model_id", "").lower().strip()
                if mn and mn not in prices and float(v.get("input_price", 0)) > 0:
                    prices[mn] = {"input": float(v.get("input_price")), "output": float(v.get("output_price")), "currency": "CNY", "source": "tencent_prices.json"}
                    t_count += 1
            print("  fetch_official_prices: Tencent JSON %d models" % t_count, file=sys.stderr)
    except Exception as e:
        print("  fetch_official_prices: Tencent JSON error:", str(e)[:80], file=sys.stderr)

    print("  fetch_official_prices: total %d models" % len(prices), file=sys.stderr)
    return prices

