"""纯页面视觉爬取测试 - 腾讯混元 TokenHub"""
import argparse
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

from src.tencent_auth import load_tencent_cookies

SCRIPT_DIR = Path(__file__).resolve().parent


async def main(cookie_file: Path):
    cookies = load_tencent_cookies(cookie_file)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        await context.add_cookies(cookies)
        page = await context.new_page()

        print("正在访问腾讯混元 TokenHub...")
        await page.goto(
            "https://console.cloud.tencent.com/tokenhub/models?regionId=1",
            wait_until="networkidle",
            timeout=60000,
        )
        
        # 等待模型列表加载
        await page.wait_for_selector(".model-item, [class*='model'], [class*='card']", timeout=15000)
        print("✅ 页面加载完成，开始滚动加载全部模型...")
        
        # 滚动加载全部内容（模拟用户滚动）
        previous_height = 0
        same_count = 0
        for _ in range(20):  # 最多滚动20次
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                same_count += 1
                if same_count >= 3:  # 连续3次高度不变，说明到底了
                    break
            else:
                same_count = 0
                previous_height = current_height
        
        print("✅ 滚动完成，开始提取页面数据...")
        
        # 提取页面所有文本内容（用于分析）
        page_text = await page.inner_text("body")
        
        # 尝试提取模型卡片数据（通过 JS 获取 DOM 结构）
        models_data = await page.evaluate("""
            () => {
                const results = [];
                
                // 尝试多种选择器匹配模型卡片
                const selectors = [
                    '[class*="modelItem"]',
                    '[class*="ModelCard"]', 
                    '[class*="model-card"]',
                    '.model-item',
                    '[class*="card-item"]'
                ];
                
                let modelElements = [];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 0) {
                        modelElements = Array.from(els);
                        console.log(`找到 ${els.length} 个模型元素，选择器: ${sel}`);
                        break;
                    }
                }
                
                // 如果没找到，尝试从页面文本中提取模型名
                if (modelElements.length === 0) {
                    return { method: 'text', text: document.body.innerText };
                }
                
                // 提取每个模型的信息
                modelElements.forEach(el => {
                    const text = el.innerText;
                    const name = el.querySelector('[class*="name"], [class*="title"]')?.innerText || '';
                    const price = el.querySelector('[class*="price"], [class*="cost"]')?.innerText || '';
                    results.push({ name, price, text: text.substring(0, 200) });
                });
                
                return { method: 'dom', count: results.length, models: results };
            }
        """)
        
        print(f"\n📊 爬取结果:")
        if models_data.get("method") == "text":
            # 从文本中提取模型名（关键词匹配）
            import re
            text = models_data["text"]
            # 匹配常见模型名模式
            patterns = [
                r'(混元\s*\S+?\s*(?:preview|Pro|Flash|Turbo)?)',
                r'(HY\s*\d+\.?\d*\s*(?:Instruct|Think)?)',
                r'(DeepSeek\S+)',
                r'(腾讯\S+?)模型'
            ]
            found = set()
            for pat in patterns:
                for m in re.finditer(pat, text):
                    found.add(m.group(1).strip())
            print(f"从页面文本提取到 {len(found)} 个模型名:")
            for name in sorted(found):
                print(f"  - {name}")
            
            # 保存完整页面文本供分析
            with (SCRIPT_DIR / "page_text.txt").open("w", encoding="utf-8") as f:
                f.write(text)
            print(f"\n💾 完整页面文本已保存: page_text.txt")
        else:
            print(f"从 DOM 提取到 {models_data['count']} 个模型:")
            for m in models_data["models"]:
                print(f"  - {m['name']} | 价格: {m['price']}")
        
        # 截图保存
        await page.screenshot(path=str(SCRIPT_DIR / "tokenhub_visual.png"), full_page=True)
        print(f"\n📸 全页截图已保存: tokenhub_visual.png")
        
        await browser.close()
        print("\n✅ 视觉爬取测试完成")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie-file", type=Path, default=SCRIPT_DIR / "tencent_cookie.json")
    args = parser.parse_args()
    asyncio.run(main(args.cookie_file))
