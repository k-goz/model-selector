# AI 模型选择器

一键对比全网 AI 模型价格，快速选择、跨平台比价、月费估算。

**https://ai-model-selector-eight.vercel.app**

---

## 支持平台（25 家，3127 个模型）

### 国内官方平台

| 平台 | 模型数 | 价格来源 | 货币 |
|------|--------|----------|------|
| 阿里百炼 | 468 | API 实时获取 | CNY |
| 百度文心 | 181 | API 实时获取 | CNY |
| 火山引擎 | 115 | API 实时获取 | CNY |
| 硅基流动 | 110 | API 实时获取 | CNY |
| 月之暗面 | 9 | API 实时获取 | CNY |
| 腾讯混元 | 11 | API 实时获取 | CNY |
| 智谱 AI | 7 | API 实时获取 | CNY |
| MiniMax | 8 | API 实时获取 | CNY |
| 零一万物 | 7 | API 实时获取 | CNY |
| 阶跃星辰 | 9 | API 实时获取 | CNY |
| 讯飞星火 | 6 | API 实时获取 | CNY |
| 百川智能 | 6 | API 实时获取 | CNY |
| DeepSeek | 2 | API 实时获取 | CNY |

### 国内聚合平台

| 平台 | 模型数 | 价格来源 | 货币 | 特点 |
|------|--------|----------|------|------|
| 无问芯穹 | 51 | API 实时获取 | CNY | 国产模型聚合 |
| Novita AI | 95 | API 实时获取 | CNY | GPU云+模型聚合 |
| n1n.ai | 571 | 公开价格API | CNY | 闭源模型折扣代理 |
| AIGC2D | 571 | 公开价格API | CNY | OneAPI系统 |
| ChatAnywhere | 93 | 网页抓取 | CNY | GPT/Claude中转 |

### 国外平台

| 平台 | 模型数 | 价格来源 | 货币 |
|------|--------|----------|------|
| OpenRouter | 350 | API 实时获取 | USD |
| Together AI | 69 | API 实时获取 | USD |
| DeepInfra | 132 | API 实时获取 | USD |
| Groq | 16 | API 实时获取 | USD |
| Fireworks AI | 9 | API 实时获取 | USD |
| Cohere | 8 | API 实时获取 | USD |
| AiHubMix | 223 | API 实时获取 | USD |

---

## 功能

### 核心功能
- **多平台聚合** — 25 家平台 3127 个模型统一呈现
- **实时价格对比** — 支持 CNY / USD 双货币切换
- **一键接入** — 点击卡片弹出代码片段（Python / Node.js / cURL / Stream）
- **Base URL 显示** — 每个卡片直接展示 API 接入地址

### 筛选与排序
- **平台筛选** — 25 家平台一键切换，显示各平台模型数
- **模型家族** — DeepSeek / Qwen / GLM / GPT / Claude / Gemini 等家族标签
- **价格分级筛选** — 免费 / 便宜 / 中等 / 贵 / 极贵
- **场景筛选** — 日常对话 / 深度推理 / 视觉图片 / 图片生成 / 视频生成 / 编程代码
- **标签筛选** — 免费 / 旗舰 / 视觉 / 推理 / 长上下文 / 开源等
- **上下文长度筛选** — 按上下文窗口大小过滤
- **价格区间筛选** — 自定义输入/输出价格范围
- **多维排序** — 默认 / 输入价升序 / 输入价降序 / 输出价升序 / 输出价降序 / 名称
- **高级搜索** — 支持 `family:deepseek price:<5 ctx:>100k` 等语法
- **分页** — 每页 66 个模型，底部翻页

### 智能功能
- **智能推荐** — 日常对话 / 编程 / 推理 / 视觉场景一键推荐最优模型
- **跨平台比价** — 精确模型名匹配，同一模型在不同平台的价格对比
- **月费计算器** — 输入对话次数 / Token 数 / 输出输入比，计算各模型月费排名
- **预算反推** — 输入月预算，反推每个模型可用对话次数
- **模型对比** — 最多勾选 3 个模型并排对比
- **Rate Limits 对比** — 各平台并发限制 (TPM/RPM) 一目了然
- **真实文本计价器** — 粘贴代码/文案，自动估算 Token 数并对比各平台花费
- **接口测速 (TTFB)** — 选择模型，测各平台首字响应时间，找最快接口

### 体验
- **暗色模式** — 默认 Linear Aesthetic 暗色精度美学，可切换亮色
- **收藏功能** — 收藏常用模型，本地持久化
- **列表/网格视图** — 两种浏览模式切换
- **筛选持久化** — 筛选条件通过 URL hash 持久化，可分享
- **筛选栏默认折叠** — 左侧筛选栏默认全部折叠，按需展开
- **移动端适配** — 768px / 400px 两级响应式
- **键盘快捷键** — `/` 搜索 / `Esc` 清空 / `D` 暗色 / `V` 视图 / `1-9` 切换平台
- **微信二维码** — 页脚扫码加微信获取最新资讯

## 价格说明

- **国外平台**（OpenRouter / Together / Groq / Fireworks / Cohere / DeepInfra / AiHubMix）：显示美元价格（$/1M tokens）
- **国内平台**：显示人民币价格（¥/M tokens）
- 阿里百炼、百度文心、火山引擎等价格从 API 实时获取
- n1n.ai / AIGC2D 价格从公开价格 API 获取
- ChatAnywhere 价格从官方文档网页抓取
- 标注「价格待确认」的模型请至平台控制台核实

## 数据同步机制

本项目已全面重构为 **"Single Source of Truth (SSOT)"** 三层定价真理库架构，彻底摒弃了不稳定的爬虫猜测和硬编码兜底。

```
┌─────────────────────────────────────────────────────────┐
│  第1层: 官方 API 直接拉取 (优先级最高)                    │
│  - 适用于提供明确价格字段的 API (如 OpenRouter/阿里百炼)   │
│  - 获取到的必定是最新精准价格                             │
├─────────────────────────────────────────────────────────┤
│  第2层: 官方平台网页抓取                                  │
│  - 适用于提供官方价格清单网页但无接口的平台 (如硅基流动)   │
│  - 脚本自动执行并解析网页 DOM，确保与官网一致             │
├─────────────────────────────────────────────────────────┤
│  第3层: official_prices_db.json 真理库                    │
│  - 全局统一的定价字典，支持精确/前缀匹配                  │
│  - 若前两层未命中，强制查表。若仍未找到，直接返回 0 + 警告  │
│  - 彻底阻断不可控的“盲猜”和硬编码，实现 100% 精确          │
└─────────────────────────────────────────────────────────┘
```

**关键保证**：所有平台都有明确来源（URL及货币单位），若模型价格未录入 `official_prices_db.json`，控制台将明确抛出 `⚠️ PRICE_MISSING` 警告，严禁系统瞎猜，确保展示价格的绝对可靠性。

### 本地操作流程

1. **首次运行 / 更新数据**：`rm models_data.json && python3 generate.py`
   - 删除旧 JSON → 强制从 API 拉取最新数据及价格体系 → 生成 HTML + 更新 JSON

2. **只改页面样式/功能**：`python3 generate.py`
   - 从 JSON 加载（0.1s）→ 生成 HTML + 更新 JSON → 数据不丢

3. **添加新平台/模型**：修改 `generate.py` 或在 `official_prices_db.json` 补充记录 → `rm models_data.json && python3 generate.py`

### CI/CD 自动更新

- GitHub Actions 每天北京时间 06:00 自动运行
- 从 GitHub Secrets 读取 API Key，调用各平台 API
- 自动 commit `index.html` + `models_data.json` + `ping_analysis.json`
- 部署到 Vercel（静态站点）

## 技术架构

### 核心架构
- **前端**：纯 HTML + CSS + JS，零依赖，单文件可离线使用
- **后端**：Python 数据抓取脚本（`generate.py`），从各平台 API 拉取模型数据生成静态 HTML
- **数据层**：`models_data.json` 作为数据中间层，保证页面修改不丢数据
- **设计**：CSS 变量体系 + Linear Aesthetic 设计风格（shimmer / glow / micro-border / glassmorphism）
- **部署**：GitHub Actions 每日自动更新（北京时间 08:00）→ Vercel 静态站点

### 模块化结构 (v6.5+)
```
/src/
├── models/          # 数据模型定义 (Model, PriceInfo, PlatformInfo)
├── pricing/         # SSOT 四层价格解析系统
│   ├── normalize_for_match()  # 模型名称标准化
│   ├── PriceDatabase          # 价格数据库管理
│   └── SSOTPriceResolver      # 四层价格解析
└── platforms/       # 平台数据获取基类
    ├── BasePlatform           # 平台基类
    └── OpenAICompatiblePlatform # OpenAI 兼容平台基类

/tests/              # 单元测试
├── test_pricing.py  # 价格解析测试
└── test_models.py   # 数据模型测试
```

### 安全配置
- API Key 仅从环境变量读取，无硬编码默认值
- 支持 `.env` 文件本地开发
- GitHub Actions 通过 Secrets 注入

## 开发指南

### 本地开发

```bash
# 1. 克隆仓库
git clone https://github.com/your-repo/ai-model-selector.git
cd ai-model-selector

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 3. 运行数据抓取
python3 generate.py

# 4. 本地预览
# 直接用浏览器打开 index.html
# 或使用 Python HTTP 服务器
python3 -m http.server 8080
```

### 运行测试

```bash
# 安装测试依赖
pip install pytest

# 运行所有测试
python3 -m pytest tests/ -v

# 运行特定测试
python3 -m pytest tests/test_pricing.py -v
```

### 添加新平台

1. 在 `src/platforms/` 创建新平台类，继承 `BasePlatform`
2. 实现 `fetch_models()` 方法
3. 在 `official_prices_db.json` 添加价格数据
4. 在 `generate.py` 中注册新平台

## 更新日志

- **v6.5** (2026-05-09): 
  - 🏗️ 模块化重构：拆分 `src/models/`、`src/pricing/`、`src/platforms/` 模块
  - 🔒 安全加固：移除所有硬编码 API Key，改为纯环境变量
  - 📝 添加类型注解和文档字符串
  - 🧪 添加单元测试（34 个测试用例全部通过）
  - 📊 改进日志系统（logging 模块）
  - ⚠️ 改进错误处理（自定义异常类）
- **v6.4** (2026-04-30): 彻底重构定价架构，引入 SSOT (单一真实来源) 四层解析系统。移除所有猜测性爬虫和硬编码兜底；建立统一 `official_prices_db.json`；修复样式兼容性 bug。
- **v6.3** (2026-04-27): 全平台价格检查修复 — 百度文心添加bp()映射；硅基流动补充新模型价格；DeepInfra从API提取真实价格；修复JSON加载双重除法bug；修复OpenRouter负价格；修复上下文格式；价格待确认从358降至279
- **v6.2** (2026-04-26): 修复分页bug(JSON加载后未重新filter导致每页显示全部模型)；每页66个模型；左侧筛选栏默认全部折叠
- **v6.1** (2026-04-25): 修复6个 bug — clearAllFilters 场景筛选器类名(.sc-btn→.sc) + 缺少重置价格分级/货币切换；updatePrices/calcTokens/价格筛选正确处理 per_1m price_unit；JS 动态卡片添加 data-pu 属性；GitHub Actions 密钥名拼写修正(TOGATHER→TOGETHER)
- **v6.0** (2026-04-24): 修复数据同步链路 — models_data.json 自动更新；5个国内平台硬编码回退；添加 Rate Limits 对比 / 真实文本计价器 / TTFB 接口测速；修复 price_unit/platform_color 同步 bug；25 平台 3127 模型
- **v5.0** (2026-04-23): 添加 n1n.ai / AIGC2D / ChatAnywhere 国内聚合平台；添加微信二维码；移除导出功能；25 平台 3113 模型
- **v4.0** (2026-04-22): 添加 AiHubMix / 无问芯穹 / DeepInfra / Novita AI；API Key 实时抓取；22 平台 1895 模型
- **v3.5** (2026-04-20): 添加 Together AI / Fireworks AI / Cohere；修复 USD 价格显示；分页功能；筛选区重构
- **v3.0** (2026-04-18): 全面升级 — Linear Aesthetic 设计 / 13 平台 / 跨平台比价 / 智能推荐 / 月费计算器
- **v2.5** (2026-04-14): 接入全部平台 API；OpenRouter 价格保持美元
- **v2** (2026-04-13): 初始版本

---

*价格数据仅供参考，以各平台实际定价为准*
