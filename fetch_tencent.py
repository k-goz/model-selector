"""腾讯混元 TokenHub 价格数据抓取脚本（完整版）

用法:
    python3 fetch_tencent.py
    python3 fetch_tencent.py --cookie-file /path/to/cookies.json
    python3 fetch_tencent.py --output /path/to/output.json
"""
import argparse
import asyncio
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_cookies(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
    except FileNotFoundError:
        print(f"Error: Cookie file not found: {path}", file=sys.stderr)
        print("Please export cookies from browser and save to tencent_cookie.json", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in cookie file: {path} ({e})", file=sys.stderr)
        sys.exit(1)
    if not isinstance(cookies, list):
        print("Error: Cookie file must contain a JSON array", file=sys.stderr)
        sys.exit(1)
    print(f"Loaded {len(cookies)} cookies from {path}", file=sys.stderr)
    return cookies


def price_tuple(tiers):
    if not tiers:
        return None, None
    try:
        return float(tiers[0]["InputPrice"]), float(tiers[0]["OutputPrice"])
    except (ValueError, TypeError, KeyError):
        return None, None


def normalize_tencent_output(raw_data):
    results = {}
    for key, info in raw_data.items():
        model_id = info.get("model_id", key).lower()
        inp = info.get("input_price")
        out = info.get("output_price")
        ctx = info.get("max_context", "")
        if ctx and isinstance(ctx, (int, float)):
            ctx = "%dk" % (int(ctx) // 1000) if ctx >= 1000 else str(ctx)
        results[model_id] = {
            "model_id": info.get("model_id", key),
            "name": info.get("name", ""),
            "brand": info.get("brand", "混元"),
            "type": info.get("type", "Text"),
            "input_price": float(inp) if inp is not None else 0,
            "output_price": float(out) if out is not None else 0,
            "currency": "CNY",
            "max_context": ctx or "N/A",
        }
    return results


async def fetch_tencent(cookie_path, output_path):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Error: playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
        sys.exit(1)

    cookies = load_cookies(cookie_path)

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:
            print(f"Error: Failed to launch browser: {e}", file=sys.stderr)
            print("Try running: playwright install chromium", file=sys.stderr)
            sys.exit(1)

        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()

        await page.goto(
            "https://console.cloud.tencent.com/tokenhub/models?regionId=1",
            wait_until="load",
            timeout=60000,
        )
        await page.wait_for_timeout(5000)

        api_url = await page.evaluate("""
            async () => {
                const url = 'https://console.cloud.tencent.com/cgi/capi';
                const ts = Date.now();
                const cookieMap = {};
                document.cookie.split('; ').forEach(c => {
                    const [k,...v] = c.split('=');
                    cookieMap[k] = decodeURIComponent(v.join('='));
                });
                const params = new URLSearchParams({
                    cmd: 'DescribeModelList',
                    action: 'delegate',
                    serviceType: 'tokenhub',
                    version: '3',
                    json: '1',
                    dictId: '3216',
                    sts: '1',
                    t: ts,
                    uin: '100048466778',
                    ownerUin: '100048466778',
                    Offset: '0',
                    Limit: '100',
                    Region: '1',
                });
                const resp = await fetch(url + '?' + params.toString(), {
                    credentials: 'include',
                    headers: {
                        'Referer': 'https://console.cloud.tencent.com/tokenhub/models?regionId=1',
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                    }
                });
                return await resp.json();
            }
        """)

        data = api_url
        api_code = data.get("code", -1)

        if api_code in (401, 403) or (api_code != 0 and "login" in str(data.get("msg", "")).lower()):
            print("Error: Cookie expired (got %s). Please re-export cookies from browser." % api_code, file=sys.stderr)
            await browser.close()
            sys.exit(1)

        if api_code != 0:
            print("Error: API call failed (code=%s, msg=%s)" % (api_code, data.get("msg", "")), file=sys.stderr)
            await browser.close()
            sys.exit(1)

        try:
            inner = data["data"]
            if isinstance(inner.get("data"), str):
                inner = json.loads(inner["data"])
            resp = inner["data"]["Response"]
            models = resp["ModelSet"]
        except (KeyError, json.JSONDecodeError) as e:
            print("Error: Page structure changed, failed to parse response: %s" % e, file=sys.stderr)
            await browser.close()
            sys.exit(1)

        total = resp.get("TotalCount", len(models))
        print("Fetched %d models (TotalCount=%d)" % (len(models), total), file=sys.stderr)

        raw_results = {}
        for m in models:
            name = m.get("DisplayName", m.get("ModelName", ""))
            brand = m.get("Brand", "混元")
            mtype = m.get("ModelType", "Text")
            model_id = m.get("ModelId", "")
            tags = m.get("Tags", [])
            tiers = m.get("ModelChargingInfo", [])
            spec = m.get("ModelSpec", {})

            inp, out = price_tuple(tiers)
            key = name.lower()
            raw_results[key] = {
                "name": name,
                "brand": brand,
                "model_id": model_id,
                "type": mtype,
                "tags": tags,
                "input_price": inp,
                "output_price": out,
                "unit": "百万tokens",
                "max_context": spec.get("ContextLength", ""),
            }

            print("  %s | %s (%s) input=%.4f output=%.4f" % (brand, name, mtype, inp or 0, out or 0), file=sys.stderr)

        results = normalize_tencent_output(raw_results)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("Saved: %s (%d models)" % (output_path, len(results)), file=sys.stderr)

        await browser.close()


def main():
    parser = argparse.ArgumentParser(description="Fetch Tencent Hunyuan model prices from TokenHub")
    parser.add_argument("--cookie-file", default=os.path.join(SCRIPT_DIR, "tencent_cookie.json"),
                        help="Path to cookie JSON file (default: tencent_cookie.json)")
    parser.add_argument("--output", default=os.path.join(SCRIPT_DIR, "tencent_prices.json"),
                        help="Output JSON file path (default: tencent_prices.json)")
    args = parser.parse_args()

    asyncio.run(fetch_tencent(args.cookie_file, args.output))


if __name__ == "__main__":
    main()
