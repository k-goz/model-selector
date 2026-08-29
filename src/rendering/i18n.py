"""中英文静态页面转换与写入。"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ZH_EN_MAP = [
    # === HTML meta ===
    ("lang=\"zh-CN\"", "lang=\"en\""),
    ("AI 模型选择器 - 全网价格对比 2026 | DeepSeek vs GPT-4o vs Claude",
     "AI Model Selector - Cross-Platform Pricing 2026 | DeepSeek vs GPT-4o vs Claude"),
    ("持续更新25+平台AI模型价格：DeepSeek、GPT-4o、Claude、Qwen等，一键复制API接入命令，支持跨平台比价、Token计价器、接口测速",
     "Compare AI model prices across 25+ platforms: DeepSeek, GPT-4o, Claude, Qwen & more. One-click API integration, cross-platform pricing, token calculator & speed test."),
    ("AI模型价格对比,DeepSeek价格,GPT-4o价格,Claude价格,大模型选择器,AI API定价,2026最佳AI模型,免费AI模型,廉价AI模型",
     "AI model pricing, DeepSeek price, GPT-4o price, Claude price, LLM selector, AI API pricing, best AI models 2026, free AI models, cheap AI models"),
    ("AI 模型选择器 - 全网价格对比 2026", "AI Model Selector - Cross-Platform Pricing 2026"),
    ("持续更新25+平台AI模型价格，支持跨平台比价、Token计价",
     "Compare AI model prices across 25+ platforms with cross-platform pricing & token calculator"),

    # === 导航 ===
    ("\">首页</a>", "\">Home</a>"),
    ("\">评测</a>", "\">Reviews</a>"),
    ("\">关于</a>", "\">About</a>"),
    ("\">隐私</a>", "\">Privacy</a>"),
    ("class=\"topnav-lang\" title=\"English\">EN</a>",
     "class=\"topnav-lang\" title=\"中文\">中文</a>"),

    # === 页面标题 ===
    (">AI 模型选择器</h1>", ">AI Model Selector</h1>"),
    ("一键对比全网价格 · 点击卡片复制切换命令 · 按 / 搜索 · 按 D 暗色 · 按 V 切换视图",
     "Compare prices across platforms · Click card to copy API command · Press / to search · D for dark · V for view"),
    ("个模型", " models"),

    # === 侧边栏 ===
    ("清除筛选", "Clear All"),
    ("搜索模型...", "Search models..."),
    ("算力供应商", "Providers"),
    ("模型家族", "Model Family"),
    ("跨平台比价", "Cross-Platform Pricing"),
    ("标签", "Tags"),
    ("上下文", "Context"),
    ("用途", "Use Case"),
    ("价格", "Price"),
    ("工具", "Tools"),
    ("货币", "Currency"),
    ("列表", "List"),
    ("亮色", "Light"),
    ("计价", "Pricing"),
    ("测速", "Speed Test"),

    # === 价格分级 ===
    ("全部价格", "All Prices"),
    ("免费", "Free"),
    ("&lt;¥0.7", "<¥0.7"),
    ("¥0.7-10/M", "¥0.7-10/M"),
    ("¥10+/M", "¥10+/M"),
    (">¥100/M", ">¥100/M"),

    # === 场景 ===
    ("全部\">全部<", "All\">All<"),
    ("日常对话", "Chat"),
    ("深度推理", "Deep Reasoning"),
    ("视觉图片", "Vision & Image"),
    ("图片生成", "Image Gen"),
    ("视频生成", "Video Gen"),
    ("编程代码", "Coding"),
    ("其他\">其他<", "Other\">Other<"),

    # === 标签 ===
    ("免费额度", "Free Tier"),
    ("便宜", "Cheap"),
    ("极便宜", "Very Cheap"),
    ("性价比", "Cost-Effective"),
    ("旗舰", "Flagship"),
    ("主力", "Mainstream"),
    ("最新版", "Latest"),
    ("2025新", "New 2025"),
    ("2026新", "New 2026"),
    ("视觉", "Vision"),
    ("推理", "Reasoning"),
    ("长上下文", "Long Context"),
    ("超长上下文", "Ultra Long Context"),
    ("开源", "Open Source"),
    ("代码", "Code"),
    ("快速", "Fast"),
    ("高性能", "High Performance"),
    ("Pro订阅", "Pro Subscription"),
    ("蒸馏", "Distilled"),
    ("轻量", "Lightweight"),
    ("已下线", "Offline"),
    ("即将下线", "Retiring"),
    ("价格待确认", "Price TBD"),
    ("语音", "Voice"),
    ("多模态", "Multimodal"),
    ("降价后", "Price Cut"),
    ("降价90%", "90% Off"),
    ("超低价", "Ultra Cheap"),
    ("编程", "Coding"),
    ("智能路由", "Smart Router"),
    ("满血版", "Full Version"),
    ("价格变动", "Price Changed"),
    ("涨价", "Price Up"),
    ("降价", "Price Down"),
    ("按次计费", "Per-use billing"),
    ("MoE", "MoE"),

    # === 平台名称 ===
    ("阿里百炼", "Alibaba Cloud"),
    ("硅基流动", "SiliconFlow"),
    ("月之暗面", "Moonshot"),
    ("智谱 AI", "Zhipu AI"),
    ("火山引擎", "Volcengine"),
    ("百度文心", "Baidu ERNIE"),
    ("腾讯混元", "Tencent Hunyuan"),
    ("讯飞星火", "iFlytek Spark"),
    ("MiniMax", "MiniMax"),
    ("零一万物", "01.AI"),
    ("百川智能", "Baichuan"),
    ("阶跃星辰", "StepFun"),
    ("无问芯穹", "Infini-AI"),
    ("Novita AI", "Novita AI"),
    ("DeepInfra", "DeepInfra"),
    ("AiHubMix", "AiHubMix"),
    ("n1n.ai", "n1n.ai"),
    ("ChatAnywhere", "ChatAnywhere"),

    # === 卡片文本 ===
    ("价格来源: API实时", "Price source: API real-time"),
    ("价格来源: 硬编码(可能过时)", "Price source: Hardcoded (may be outdated)"),
    ("价格来源: 代理平台自营价(非官方)", "Price source: Reseller (unofficial)"),
    ("价格来源: 官方定价页爬取", "Price source: Official pricing page"),
    ("价格来源: SPA页面爬取", "Price source: SPA page scrape"),
    ("价格来源: OpenRouter回填", "Price source: OpenRouter"),
    ("价格来源: LiteLLM社区数据", "Price source: LiteLLM community"),
    ("价格来源: 国内官方价格库", "Price source: CN official price DB"),
    ("价格来源: 官方价格数据库", "Price source: Official price DB"),
    ("价格来源: 交叉验证修正", "Price source: Cross-validated"),
    ("价格来源: 硬编码", "Price source: Hardcoded"),
    ("硬编码(可能过时)", "Hardcoded (may be outdated)"),
    ("代理平台自营价(非官方)", "Reseller (unofficial)"),
    ("官方定价页爬取", "Official pricing page"),
    ("SPA页面爬取", "SPA page scrape"),
    ("OpenRouter回填", "OpenRouter"),
    ("LiteLLM社区数据", "LiteLLM community"),
    ("国内官方价格库", "CN official price DB"),
    ("官方价格数据库", "Official price DB"),
    ("交叉验证修正", "Cross-validated"),
    ("API实时", "API real-time"),
    ("上下文: ", "Context: "),
    ("点击查看接入代码", "Click to view integration code"),
    ("收藏", "Favorite"),
    ("对比", "Compare"),
    ("免费额度</span>", "Free Tier</span>"),
    ("$0 (免费)", "$0 (Free)"),

    # === 月费计算器 ===
    ("月费计算器", "Monthly Cost Calculator"),
    ("预设:", "Presets:"),
    ("轻度用户", "Light User"),
    ("中度用户", "Medium User"),
    ("重度用户", "Heavy User"),
    ("开发者", "Developer"),
    ("每月对话次数:", "Monthly chats:"),
    ("每对话Token数:", "Tokens per chat:"),
    ("输出/输入比:", "Output/Input ratio:"),
    ("月预算(元):", "Monthly budget(¥):"),
    ("可选", "Optional"),
    ("计算月费用", "Calculate"),
    ("计算全部模型", "Calc All Models"),
    ("预算反推", "Budget Reverse"),

    # === 智能推荐 ===
    ("智能推荐", "Smart Recommend"),
    ("选择你的使用场景，自动推荐最合适的模型", "Select your use case, auto-recommend the best model"),
    ("日常聊天", "Chat"),
    ("写代码", "Write Code"),
    ("翻译", "Translate"),
    ("写文章", "Write"),
    ("图片理解", "Image Understanding"),

    # === 跨平台比价 ===
    ("同一模型在不同平台的价格", "Same model, different platform prices"),
    ("输入模型名搜索比价...", "Search model for cross-platform pricing..."),

    # === Rate Limits ===
    ("Rate Limits 对比", "Rate Limits Comparison"),
    ("各平台并发限制 (TPM/RPM)，避开上线后频繁报错的坑", "Platform concurrency limits (TPM/RPM)"),
    ("请以各平台控制台和正式账单为准。", "Verify against provider consoles and final invoices."),
    ("平台", "Platform"),
    ("TPM (tokens/min)", "TPM (tokens/min)"),
    ("RPM (req/min)", "RPM (req/min)"),
    ("并发限制", "Concurrency"),
    ("无限制", "Unlimited"),
    ("高", "High"),
    ("中", "Medium"),
    ("低", "Low"),
    ("数据来源: 各平台官网文档 (2026年4月)。TPM=每分钟Token数, RPM=每分钟请求数。标注\"低\"的平台在生产环境需特别注意限流。",
     "Source: Official platform docs (Apr 2026). TPM=Tokens per minute, RPM=Requests per minute. Platforms marked \"Low\" may have strict rate limits."),

    # === 价格漂移 ===
    ("价格漂移检测", "Price Drift Detection"),
    ("硬编码价格与 OpenRouter/LiteLLM 参考价格偏差 ≥5% 的模型", "Models with ≥5% price deviation from OpenRouter/LiteLLM reference"),
    ("模型", "Model"),
    ("我方价格", "Our Price"),
    ("参考价格", "Reference Price"),
    ("参考源", "Reference Source"),
    ("偏差", "Deviation"),

    # === 模型对比 ===
    ("模型对比", "Model Comparison"),
    ("并排对比", "Side by Side"),
    ("清空", "Clear"),
    ("模型对比详情", "Model Comparison Details"),
    ("最多选择3个模型对比", "Select up to 3 models to compare"),
    ("请至少选择2个模型", "Please select at least 2 models"),
    ("项目", "Item"),
    ("输入价格", "Input Price"),
    ("输出价格", "Output Price"),
    ("货币", "Currency"),

    # === 价格变动 ===
    ("检测到", "Detected"),
    ("个模型价格变动", "models with price changes"),

    # === 数据说明 ===
    ("数据说明：", "Data Notes:"),
    ("个模型从 API 直接采集；", " models collected directly from provider APIs; "),
    ("OpenRouter 显示原始美元价格，国内平台显示人民币价格；",
     "OpenRouter shows USD prices, Chinese platforms show CNY prices; "),
    ("标注「价格待确认」的模型请至平台控制台核实。",
     "Models marked \"Price TBD\" should be verified on the platform console."),
    ("数据更新时间：", "Last updated: "),
    ("正在核验数据时间", "Verifying data timestamp"),
    ("最后采集：", "Last collected: "),

    # === 排序 ===
    ("排序:", "Sort:"),
    ("默认", "Default"),
    ("输入价↑", "Input↑"),
    ("输入价↓", "Input↓"),
    ("输出价↑", "Output↑"),
    ("输出价↓", "Output↓"),
    ("名称", "Name"),
    ("综合价", "Combined"),
    ("上下文↓", "Context↓"),

    # === 价格区间 ===
    ("价格区间:", "Price Range:"),
    ("最低", "Min"),
    ("最高", "Max"),
    ("元/M", "/M tokens"),
    ("应用", "Apply"),
    ("清除", "Clear"),

    # === 筛选计数 ===
    ("显示", "Showing"),
    ("价格来源", "Price Source"),
    ("加载中...", "Loading..."),

    # === 页脚 ===
    ("没有找到符合条件的模型", "No models match your criteria"),
    ("微信二维码", "WeChat QR Code"),
    ("扫码加微信 · 获取最新AI模型资讯", "Scan to add WeChat · Latest AI model news"),
    ("数据来源：各平台 API 直接采集 + 官网公告（更新时间：",
     "Data source: Platform APIs + official announcements (Updated: "),
    ("OpenRouter 显示原始美元价格 · 国内平台显示人民币价格 · 点击卡片复制接入方式",
     "OpenRouter shows USD · Chinese platforms show CNY · Click card to copy API integration"),
    ("快捷键: / 搜索 | Esc 清空 | D 暗色 | V 视图 | 1-9 切换平台",
     "Shortcuts: / Search | Esc Clear | D Dark | V View | 1-9 Switch platform"),
    ("支持开发者 — 注册硅基流动领代金券",
     "Support developers — Sign up on SiliconFlow for credits"),

    # === Insights ===
    ("从小红书同步的 AI 模型使用心得与技巧",
     "AI model tips and insights synced from Xiaohongshu"),
    ("DeepSeek R1 实测：推理能力接近 o1，价格仅1/30",
     "DeepSeek R1 Review: Reasoning near o1, 1/30 the price"),
    ("在实际编码任务中测试了 DeepSeek-R1 的推理链，发现其代码生成质量与 GPT-4o 相当，但价格仅为 $1/M vs $30/M，性价比极高...",
     "Tested DeepSeek-R1 reasoning chains on coding tasks — code quality rivals GPT-4o at $1/M vs $30/M..."),
    ("Qwen3-Coder-480B 体验：国产代码模型的新天花板",
     "Qwen3-Coder-480B: New ceiling for Chinese code models"),
    ("Qwen3-Coder 在 HumanEval 和 SWE-Bench 上表现亮眼，480B 参数的代码补全能力已逼近 Claude Sonnet 4...",
     "Qwen3-Coder excels on HumanEval and SWE-Bench, 480B param code completion approaches Claude Sonnet 4..."),
    ("5个免费AI API推荐：零成本玩转大模型",
     "5 Free AI APIs: Start with zero cost"),
    ("SiliconFlow、Groq、Together AI 均提供免费额度，本文对比了各平台的免费模型列表和限制条件，帮你零成本开始 AI 开发...",
     "SiliconFlow, Groq, Together AI all offer free tiers. This article compares free model lists and limits..."),
    ("硅基流动 vs 火山引擎：国内推理服务横评",
     "SiliconFlow vs Volcengine: CN inference service comparison"),
    ("同为国内热门推理平台，硅基流动的 RSC 接口响应更快，火山引擎的 Doubao 系列价格更低，不同场景选择不同...",
     "Both popular CN inference platforms — SiliconFlow's RSC is faster, Volcengine's Doubao is cheaper..."),

    # === Token 计价器 ===
    ("真实文本计价器", "Token Pricing Calculator"),
    ("粘贴你的代码或文案，自动计算 Token 数并对比各平台花费",
     "Paste your code or text to calculate token count and compare costs across platforms"),
    ("在此粘贴文本...\n\n支持中文、英文、代码混合内容",
     "Paste your text here...\n\nSupports Chinese, English, and code mixed content"),
    ("计算 Token", "Calculate Tokens"),
    ("分词器: GPT-4 Cl100k (近似)", "Tokenizer: GPT-4 Cl100k (approximate)"),

    # === TTFB 测速 ===
    ("接口测速 (TTFB)", "Speed Test (TTFB)"),
    ("输入模型名，自动测所有平台该模型的 TTFB，按延迟从低到高排序",
     "Enter model name to test TTFB across all platforms, sorted by latency"),
    ("输入模型名搜索，如: deepseek-v3", "Search model name, e.g.: deepseek-v3"),
    ("测速所有平台", "Test All Platforms"),
    ("清除结果", "Clear Results"),
    ("仅测 API 连接速度，不消耗 Token", "Only tests API connection speed, no tokens consumed"),

    # === 代码模态框 ===
    ("一键接入", "Quick Integration"),
    ("复制", "Copy"),
    ("已复制", "Copied"),
    ("使用说明：", "Usage: "),
    ("将 <code>YOUR_API_KEY</code> 替换为你的 API 密钥即可直接运行。所有平台均兼容 <code>OpenAI SDK</code> 接入方式。",
     "Replace <code>YOUR_API_KEY</code> with your API key. All platforms are compatible with <code>OpenAI SDK</code>."),

    # === JS 中的中文（在 <script> 标签内） ===
    ("日常对话", "Chat"),  # JS scene default
    ("请先在上方勾选要计算的模型（最多3个）", "Please select models above (up to 3)"),
    ("没有可计算的模型", "No models to calculate"),
    ("请输入月预算金额", "Please enter monthly budget"),
    ("请先设置对话次数和Token数", "Please set chat count and token count"),
    ("排名", "Rank"),
    ("月费(¥)", "Monthly Cost(¥)"),
    ("预算内最多对话", "Max chats in budget"),
    ("次", " times"),
    ("月费用(¥", "Monthly Cost(¥"),
    ("性价比高，适合日常使用", "Cost-effective, great for daily use"),
    ("价格适中", "Moderate price"),
    ("代码专用模型", "Code-specialized model"),
    ("通用模型，可写代码", "General model, can write code"),
    ("翻译不需要高级模型，便宜即可", "Translation doesn't need advanced models, cheap is fine"),
    ("长上下文，适合长文", "Long context, good for long texts"),
    ("适合一般写作", "Good for general writing"),
    ("推理专用模型", "Reasoning-specialized model"),
    ("通用模型", "General model"),
    ("视觉/多模态模型", "Vision/Multimodal model"),
    ("图片生成专用", "Image generation specialized"),
    ("视频生成专用", "Video generation specialized"),
    ("未找到匹配模型", "No matching models found"),
    ("个平台,", " platforms, "),
    ("个渠道)", " channels)"),
    ("最低", "Lowest"),
    ("代理平台自营价,非官方价", "Reseller price, unofficial"),
    ("未找到匹配的跨平台模型", "No matching cross-platform models found"),
    ("请先输入文本", "Please enter text first"),
    ("字符数", "Characters"),
    ("行数", "Lines"),
    ("输入 Token", "Input Tokens"),
    ("预估输出 Token", "Est. Output Tokens"),
    ("预估花费", "Est. Cost"),
    ("显示前30个最便宜的，共", "Showing top 30 cheapest of "),
    ("平台)", " platforms)"),
    ("未找到该模型的接口", "No API endpoint found for this model"),
    ("测速中...", "Testing..."),
    ("正在测试", "Testing "),
    ("个平台的", " platforms' "),
    ("开始测速", "Start Test"),
    ("已测试", "Tested"),
    ("超时", "Timeout"),
    ("错误", "Error"),
    ("最快", "Fastest"),

    # === 分页 ===
    ("首页", "First"),
    ("上一页", "Prev"),
    ("下一页", "Next"),
    ("末页", "Last"),
    ("第", "Page "),
    ("页 (共", " of "),
    ("个)", " pages)"),

    # === Telegram 通知（非页面输出，但保持一致） ===
    ("模型数据每日更新", "Daily Model Data Update"),
    ("模型总数:", "Total models: "),
    ("价格变动:", "Price changes: "),
    ("个模型", " models"),
    ("新增", "New"),
    ("还有", " + "),
    ("个", ""),
    ("价格无变动", "No price changes"),
]

def generate_english_version(html_content: str) -> str:
    """
    将中文 HTML 转换为英文版
    
    Args:
        html_content: 中文 HTML 内容
    
    Returns:
        英文 HTML 内容
    """
    result = html_content
    for zh, en in ZH_EN_MAP:
        result = result.replace(zh, en)
    return result


def write_english_version(html_content: str, output_path: Path) -> None:
    """写入英文静态页面。"""
    logger.info("开始生成英文版 %s ...", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    english_html = generate_english_version(html_content)
    output_path.write_text(english_html, encoding="utf-8")
    logger.info("英文版生成成功: %s (%s bytes)", output_path, output_path.stat().st_size)

