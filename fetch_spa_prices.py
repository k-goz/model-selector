#!/usr/bin/env python3
"""
SPA 定价页爬取脚本 — 用 Playwright 爬取 5 个 SPA 平台的实时定价。
需要: pip install playwright && playwright install chromium
输出: spa_prices.json（供 generate.py 使用）
"""
import asyncio, json, sys, os, time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "spa_prices.json")

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("playwright not installed, run: pip install playwright && playwright install chromium", file=sys.stderr)


# ═══════════════════════════════════════════════════════════
# 平台 1: 腾讯混元 (复用 fetch_tencent.py 的逻辑)
# ═══════════════════════════════════════════════════════════
TENCENT_COOKIES = [
    {"domain": ".cloud.tencent.com", "path": "/", "name": "ownerUin", "value": "O100048466778G"},
    {"domain": ".cloud.tencent.com", "path": "/", "name": "skey", "value": "g0tGvib8odzJYbSU0W7WLAeLn1OHmJAy-FiGgfg0mvc_"},
    {"domain": ".cloud.tencent.com", "path": "/", "name": "uin", "value": "o100048466778"},
    {"domain": ".cloud.tencent.com", "path": "/", "name": "loginType", "value": "wx"},
    {"domain": ".tencent.com", "path": "/", "name": "hunyuan_token", "value": "EQD42D4+6H50mSpBkxUCWnhdGgDFAAqZBJm0pV91Amr/qok7ChgqVtAg5i3VclkToeNczngr79hnL9M8PAzm1g=="},
]

async def scrape_tencent(browser):
    """腾讯混元 TokenHub — 通过内部 API 获取"""
    context = await browser.new_context()
    await context.add_cookies(TENCENT_COOKIES)
    page = await context.new_page()
    prices = {}
    try:
        await page.goto("https://console.cloud.tencent.com/tokenhub/models?regionId=1", wait_until="load", timeout=60000)
        await page.wait_for_timeout(5000)
        data = await page.evaluate("""
            async () => {
                const params = new URLSearchParams({
                    cmd: 'DescribeModelList', action: 'delegate', serviceType: 'tokenhub',
                    version: '3', json: '1', dictId: '3216', sts: '1',
                    t: Date.now(), uin: '100048466778', ownerUin: '100048466778',
                    Offset: '0', Limit: '100', Region: '1',
                });
                const resp = await fetch('https://console.cloud.tencent.com/cgi/capi?' + params.toString(), {
                    credentials: 'include',
                    headers: { 'Referer': 'https://console.cloud.tencent.com/tokenhub/models?regionId=1' }
                });
                return await resp.json();
            }
        """)
        if data.get("code") != 0:
            print("  Tencent: API failed, cookie may have expired", file=sys.stderr)
            return {}
        inner = data.get("data", {})
        if isinstance(inner.get("data"), str):
            inner = json.loads(inner["data"])
        models = inner["data"]["Response"]["ModelSet"]
        for m in models:
            name = m.get("ModelId", m.get("DisplayName", "")).lower()
            tiers = m.get("ModelChargingInfo", [])
            if tiers:
                inp = float(tiers[0].get("InputPrice", 0) or 0)
                out = float(tiers[0].get("OutputPrice", 0) or 0)
                ctx = m.get("ModelSpec", {}).get("ContextLength", "")
                if inp > 0 or out > 0:
                    prices[name] = {"input": inp, "output": out, "context": str(ctx) if ctx else "N/A",
                                    "source": "https://cloud.tencent.com/product/hunyuan"}
        print("  Tencent: %d models" % len(prices), file=sys.stderr)
    except Exception as e:
        print("  Tencent error:", str(e)[:80], file=sys.stderr)
    finally:
        await page.close()
    return prices


# ═══════════════════════════════════════════════════════════
# 平台 2: 智谱 AI (bigmodel.cn/pricing)
# ═══════════════════════════════════════════════════════════
async def scrape_zhipu(browser):
    """智谱 AI — 从定价页 DOM 提取价格表格"""
    page = await browser.new_page()
    prices = {}
    try:
        await page.goto("https://bigmodel.cn/pricing", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # 尝试从 DOM 提取表格数据
        data = await page.evaluate("""
            () => {
                const results = {};
                // 策略1: 查找 table 中的价格行
                const tables = document.querySelectorAll('table');
                for (const table of tables) {
                    const rows = table.querySelectorAll('tbody tr');
                    for (const row of rows) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 3) {
                            const modelName = (cells[0]?.innerText || '').trim().toLowerCase();
                            const inputPrice = (cells[1]?.innerText || '').trim();
                            const outputPrice = (cells[2]?.innerText || '').trim();
                            if (modelName && (modelName.includes('glm') || modelName.includes('cogview'))) {
                                const ii = parseFloat(inputPrice.replace(/[^\\d.]/g, '')) || 0;
                                const oo = parseFloat(outputPrice.replace(/[^\\d.]/g, '')) || 0;
                                if (ii > 0 || oo > 0) {
                                    results[modelName] = {input: ii, output: oo};
                                }
                            }
                        }
                    }
                }
                // 策略2: 如果 table 没数据，尝试从 div/card 中提取
                if (Object.keys(results).length === 0) {
                    const cards = document.querySelectorAll('[class*="price"], [class*="model"], [class*="card"]');
                    for (const card of cards) {
                        const text = card.innerText || '';
                        const modelMatch = text.match(/(glm[-\\w.]+)/i);
                        if (modelMatch) {
                            const mn = modelMatch[1].toLowerCase();
                            const prices = text.match(/(\\d+\\.?\\d*)/g);
                            if (prices && prices.length >= 2) {
                                results[mn] = {input: parseFloat(prices[0]), output: parseFloat(prices[1])};
                            }
                        }
                    }
                }
                return results;
            }
        """)
        for k, v in data.items():
            if v.get("input", 0) > 0 or v.get("output", 0) > 0:
                prices[k] = {"input": v["input"], "output": v["output"], "context": "N/A",
                             "source": "https://bigmodel.cn/pricing"}
        print("  Zhipu: %d models" % len(prices), file=sys.stderr)
    except Exception as e:
        print("  Zhipu error:", str(e)[:80], file=sys.stderr)
    finally:
        await page.close()
    return prices


# ═══════════════════════════════════════════════════════════
# 平台 3: 火山引擎 (volcengine.com/product/doubao)
# ═══════════════════════════════════════════════════════════
async def scrape_volcengine(browser):
    """火山引擎/豆包 — 拦截 XHR 获取定价数据"""
    page = await browser.new_page()
    prices = {}
    api_responses = []

    async def intercept_response(response):
        url = response.url
        if any(kw in url for kw in ["pricing", "model", "list", "charge", "billing"]):
            try:
                body = await response.json()
                api_responses.append({"url": url, "data": body})
            except:
                pass

    page.on("response", intercept_response)

    try:
        await page.goto("https://www.volcengine.com/product/doubao", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # 从拦截的 API 响应中提取价格
        for resp in api_responses:
            data = resp["data"]
            # 尝试多种数据结构
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ["data", "models", "items", "result", "list"]:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
            for item in items:
                if not isinstance(item, dict):
                    continue
                mn = (item.get("model_name") or item.get("name") or item.get("model_id") or "").lower()
                inp = float(item.get("input_price", 0) or item.get("input_token_price", 0) or 0)
                out = float(item.get("output_price", 0) or item.get("output_token_price", 0) or 0)
                if mn and (inp > 0 or out > 0):
                    prices[mn] = {"input": inp, "output": out, "context": "N/A",
                                  "source": "https://www.volcengine.com/product/doubao"}

        # Fallback: 从 DOM 提取
        if not prices:
            data = await page.evaluate("""
                () => {
                    const results = {};
                    const tables = document.querySelectorAll('table');
                    for (const table of tables) {
                        const rows = table.querySelectorAll('tbody tr, tr');
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 3) {
                                const mn = (cells[0]?.innerText || '').trim().toLowerCase();
                                const ii = parseFloat((cells[1]?.innerText || '').replace(/[^\\d.]/g, '')) || 0;
                                const oo = parseFloat((cells[2]?.innerText || '').replace(/[^\\d.]/g, '')) || 0;
                                if (mn && (mn.includes('doubao') || mn.includes('豆包')) && (ii > 0 || oo > 0)) {
                                    results[mn] = {input: ii, output: oo};
                                }
                            }
                        }
                    }
                    return results;
                }
            """)
            for k, v in data.items():
                prices[k] = {"input": v["input"], "output": v["output"], "context": "N/A",
                             "source": "https://www.volcengine.com/product/doubao"}

        print("  Volcengine: %d models" % len(prices), file=sys.stderr)
    except Exception as e:
        print("  Volcengine error:", str(e)[:80], file=sys.stderr)
    finally:
        await page.close()
    return prices


# ═══════════════════════════════════════════════════════════
# 平台 4: 讯飞星火 (xinghuo.xfyun.cn/sparkapi)
# ═══════════════════════════════════════════════════════════
async def scrape_spark(browser):
    """讯飞星火 — 从定价页 DOM 提取"""
    page = await browser.new_page()
    prices = {}
    api_responses = []

    async def intercept_response(response):
        url = response.url
        if any(kw in url for kw in ["price", "model", "list", "billing"]):
            try:
                body = await response.json()
                api_responses.append({"url": url, "data": body})
            except:
                pass

    page.on("response", intercept_response)

    try:
        await page.goto("https://xinghuo.xfyun.cn/sparkapi", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # 从拦截的 API 响应中提取
        for resp in api_responses:
            data = resp["data"]
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ["data", "models", "items", "result", "list"]:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
            for item in items:
                if not isinstance(item, dict):
                    continue
                mn = (item.get("model_name") or item.get("name") or item.get("model_id") or "").lower()
                inp = float(item.get("input_price", 0) or 0)
                out = float(item.get("output_price", 0) or 0)
                if mn and (inp > 0 or out > 0):
                    prices[mn] = {"input": inp, "output": out, "context": "N/A",
                                  "source": "https://xinghuo.xfyun.cn/sparkapi"}

        # Fallback: DOM 提取
        if not prices:
            data = await page.evaluate("""
                () => {
                    const results = {};
                    const tables = document.querySelectorAll('table');
                    for (const table of tables) {
                        const rows = table.querySelectorAll('tbody tr, tr');
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 3) {
                                const mn = (cells[0]?.innerText || '').trim().toLowerCase();
                                const ii = parseFloat((cells[1]?.innerText || '').replace(/[^\\d.]/g, '')) || 0;
                                const oo = parseFloat((cells[2]?.innerText || '').replace(/[^\\d.]/g, '')) || 0;
                                if (mn && (ii > 0 || oo > 0)) {
                                    results[mn] = {input: ii, output: oo};
                                }
                            }
                        }
                    }
                    return results;
                }
            """)
            for k, v in data.items():
                prices[k] = {"input": v["input"], "output": v["output"], "context": "N/A",
                             "source": "https://xinghuo.xfyun.cn/sparkapi"}

        print("  Spark: %d models" % len(prices), file=sys.stderr)
    except Exception as e:
        print("  Spark error:", str(e)[:80], file=sys.stderr)
    finally:
        await page.close()
    return prices


# ═══════════════════════════════════════════════════════════
# 平台 5: 百度文心 (qianfan.baidubce.com/pricing)
# ═══════════════════════════════════════════════════════════
async def scrape_baidu(browser):
    """百度文心/千帆 — 从定价页 DOM 提取"""
    page = await browser.new_page()
    prices = {}
    api_responses = []

    async def intercept_response(response):
        url = response.url
        if any(kw in url for kw in ["price", "model", "billing", "list"]):
            try:
                body = await response.json()
                api_responses.append({"url": url, "data": body})
            except:
                pass

    page.on("response", intercept_response)

    try:
        await page.goto("https://qianfan.baidubce.com/pricing", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # 从拦截的 API 响应中提取
        for resp in api_responses:
            data = resp["data"]
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ["data", "models", "items", "result", "list"]:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
            for item in items:
                if not isinstance(item, dict):
                    continue
                mn = (item.get("model_name") or item.get("name") or item.get("model") or "").lower()
                inp = float(item.get("input_price", 0) or item.get("input_token_price", 0) or 0)
                out = float(item.get("output_price", 0) or item.get("output_token_price", 0) or 0)
                if mn and (inp > 0 or out > 0):
                    prices[mn] = {"input": inp, "output": out, "context": "N/A",
                                  "source": "https://qianfan.baidubce.com/pricing"}

        # Fallback: DOM 提取
        if not prices:
            data = await page.evaluate("""
                () => {
                    const results = {};
                    const tables = document.querySelectorAll('table');
                    for (const table of tables) {
                        const rows = table.querySelectorAll('tbody tr, tr');
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 3) {
                                const mn = (cells[0]?.innerText || '').trim().toLowerCase();
                                const ii = parseFloat((cells[1]?.innerText || '').replace(/[^\\d.]/g, '')) || 0;
                                const oo = parseFloat((cells[2]?.innerText || '').replace(/[^\\d.]/g, '')) || 0;
                                if (mn && (mn.includes('ernie') || mn.includes('文心')) && (ii > 0 || oo > 0)) {
                                    results[mn] = {input: ii, output: oo};
                                }
                            }
                        }
                    }
                    return results;
                }
            """)
            for k, v in data.items():
                prices[k] = {"input": v["input"], "output": v["output"], "context": "N/A",
                             "source": "https://qianfan.baidubce.com/pricing"}

        print("  Baidu: %d models" % len(prices), file=sys.stderr)
    except Exception as e:
        print("  Baidu error:", str(e)[:80], file=sys.stderr)
    finally:
        await page.close()
    return prices


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════
async def main():
    if not HAS_PLAYWRIGHT:
        print("Playwright not available, cannot scrape SPA pages", file=sys.stderr)
        sys.exit(1)

    print("Starting SPA price scraping...", file=sys.stderr)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # 并发爬取所有平台（但为避免被限流，串行执行）
        results = {}
        scrapers = [
            ("tencent", scrape_tencent),
            ("zhipu", scrape_zhipu),
            ("volcengine", scrape_volcengine),
            ("spark", scrape_spark),
            ("baidu", scrape_baidu),
        ]
        failed = []
        for name, scraper in scrapers:
            try:
                data = await scraper(browser)
                if data:
                    results[name] = data
                else:
                    failed.append(name)
                    print("  %s: no data returned" % name, file=sys.stderr)
            except Exception as e:
                failed.append(name)
                print("  %s scraper error: %s" % (name, str(e)[:80]), file=sys.stderr)

        await browser.close()

    # 输出结果
    output = {
        "meta": {
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "platforms_scraped": list(results.keys()),
            "platforms_failed": failed,
            "total_prices": sum(len(v) for v in results.values()),
        },
        "prices": results,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    total = output["meta"]["total_prices"]
    print("\nSaved %s: %d platforms, %d models" % (OUTPUT_PATH, len(results), total), file=sys.stderr)
    if failed:
        print("Failed platforms: %s" % ", ".join(failed), file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
