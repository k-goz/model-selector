# AI 模型选择器

面向 AI API 使用者的静态模型目录：统一查看模型、上下文、输入/输出价格、接入地址，并完成筛选、比价和用量估算。

线上地址：[model.ai-selector.top](https://model.ai-selector.top)（[Vercel 备用域名](https://ai-model-selector-eight.vercel.app)）

## 当前状态

- 当前模型数、平台数和采集时间以 `models_data.json.meta` 为唯一事实来源，README 不再维护容易漂移的固定数字。
- 前端是生成后的纯 HTML/CSS/JavaScript，中文页与英文页均可独立部署。
- `generate.py` 仍是生产编排入口；所有当前有模型数据的平台目录均已迁入 `src/platforms/`，生产生成不再依赖未审计的内联平台目录。
- 数据缓存的采集时间与页面生成时间分开记录，缓存重建页面不会伪装成一次新采集。
- 每日刷新由 `.github/workflows/refresh-model-data.yml` 唯一触发，执行体依次完成测试、采集、数据校验、价格基准校验、静态页面门禁、桌面/移动端浏览器回归和静态产物提交。
- 页面根据 `models_data.json.meta.updated_at` 动态显示数据年龄，并区分新鲜、延迟、过期和未知状态。

生产刷新、告警和部署事实来源见 [`docs/PHASE16_REFRESH_INCIDENT.md`](docs/PHASE16_REFRESH_INCIDENT.md) 与 [`docs/PRODUCTION_DEPLOYMENT_SOURCE_OF_TRUTH.md`](docs/PRODUCTION_DEPLOYMENT_SOURCE_OF_TRUTH.md)。

## 价格语义

价格不能简单地用 `0` 判断为免费。每条模型数据现在包含 `price_status` 和 `billing_unit`：

| `price_status` | 含义 | 是否进入 Token 费用计算 |
|---|---|---|
| `priced` | 已知 Token 价格 | 是 |
| `free` | 明确永久免费 | 是，费用为 0 |
| `free_tier` | 只有免费额度，超额价格未确认 | 否 |
| `non_token` | 按次、图片、视频或其他单位计费 | 否 |
| `unknown` | 价格待确认 | 否 |
| `retiring` | 即将下线 | 否 |
| `unavailable` | 已下线或不可用 | 否 |

这样可避免把按张计费、按次计费、免费额度或缺失价格的模型误标为“免费”。页面上的价格排序、推荐、月费计算和预算反推均遵循该状态。

## 数据血缘

每条模型记录包含：

- `model_source`：`api`、`scrape`、`fallback`、`legacy_generator` 或 `legacy_snapshot`。
- `source_url`：模型目录来源 URL。
- `collected_at`：该目录的实际采集时间。
- `price_source_url`：价格来源 URL；尚未迁移的平台允许为空，但会产生校验警告。

`meta.source_runs` 保存每个平台本次抓取的来源类型、模型数量和失败原因；`meta.lineage_counts` 汇总不同来源类型覆盖的模型数。API 请求失败时会明确记录为 `fallback`，官方文档抓取记录为 `scrape`，不会把缓存或静态回退伪装成当前 API 数据。

## 数据链路

```text
平台 API / 公开数据
        │
        ▼
generate.py --refresh
        │
        ├── official_prices_db.json  官方价格补充库
        ├── models_data.json         可审计的数据快照
        ├── ping_analysis.json       延迟分析数据
        └── index.html + en/index.html
                    │
                    ▼
              Vercel 静态部署
```

`official_prices_db.json` 的根节点只能是平台命名空间。可用以下命令检查并清理误写到根节点的模型记录：

```bash
python3 scripts/normalize_official_prices_db.py
python3 scripts/normalize_official_prices_db.py --write
```

## 本地开发

项目运行时只依赖 Python 标准库；单元测试使用 `pytest`，浏览器回归使用 Playwright。

```bash
python3 -m pip install pytest
npm ci
npx playwright install chromium

# 使用现有 models_data.json 快速重建页面，不刷新采集时间
python3 generate.py --render-only

# 强制从各平台刷新；密钥缺失的平台会使用脚本内已有的安全回退
python3 generate.py --refresh

# 本地预览
python3 -m http.server 8080
```

密钥通过环境变量读取，常用项包括 `ALIYUN_KEY`、`SF_KEY`、`MS_KEY`、`ZH_KEY`、`VOLC_KEY`、`TENCENT_KEY`、`MINIMAX_KEY`、`DEEPSEEK_KEY`、`GROQ_KEY`、`TOGETHER_KEY` 等。仓库不保存真实密钥。

腾讯控制台视觉抓取仅从本地 `tencent_cookie.json` 读取 Cookie，可从 `tencent_cookie.json.example` 复制结构。该文件已被 Git 忽略，不得提交。

## 验证

```bash
# 单元测试
python3 -m pytest tests/ -q

# 校验数据结构、状态语义、重复项和采集时间
python3 validate_data.py --max-age-hours 48

# 核心价格样本与官网基准对照；缺失模型和价格偏差都会失败
python3 verify_ground_truth.py

# 检查中英文页面 DOM、模型数量、URL 和脚本结构
python3 validate_site.py

# 桌面 Chromium 与 Pixel 7 移动视口真实交互回归
npm run test:browser

# 检查唯一生产域名、中英文页面和数据新鲜度
python3 check_deployment.py --max-age-hours 48

# 使用指定快照校验
python3 verify_ground_truth.py --json /path/to/models_data.json
```

`ground_truth.json` 只放少量、可从官方来源复核的关键模型，不把大规模第三方聚合数据冒充为价格真值。

## 目录

```text
.
├── generate.py                       # 当前生产生成器与平台抓取主流程
├── validate_data.py                  # 发布前数据契约校验
├── validate_site.py                  # 生成页面静态质量门禁
├── verify_ground_truth.py            # 核心模型价格基准校验
├── ground_truth.json                 # 小规模官方价格样本
├── official_prices_db.json           # 按平台分区的价格补充库
├── models_data.json                  # 当前发布数据快照
├── index.html                        # 中文静态站
├── en/index.html                     # 英文静态站
├── src/models/                       # 领域模型
├── src/pricing/                      # 价格解析与价格状态分类
├── src/platforms/base.py             # 统一抓取结果、来源元数据和 OpenAI 兼容基类
├── src/platforms/catalog.py          # 已接入生产的关键平台抓取器
├── src/rendering/                     # 前端资源读取与页面组合
├── assets/styles.css                  # 页面样式源码，生成时内联
├── assets/app.js                      # 浏览器交互源码，生成时内联
├── templates/page.html                # 页面组合骨架
├── templates/document_head.html       # 文档头、导航与概览区块
├── templates/insights.html            # Insights 内容区块
├── playwright.config.js               # 桌面/移动端浏览器回归配置
├── scripts/normalize_official_prices_db.py
├── tests/browser/                     # Playwright 真实交互回归
├── tests/                             # Python 单元与静态页面测试
├── .github/workflows/refresh-model-data.yml # 定时/手工生产刷新入口
└── .github/workflows/update-models.yml       # 可复用刷新执行体
```

## 现阶段开发原则

1. 先保证价格语义正确和来源可追溯，再增加平台数量。
2. 未知价格必须展示为未知，不能用 `0` 代替。
3. 新抓取器先输出标准化模型记录，再接入页面生成。
4. 每次数据更新必须通过结构校验和核心价格样本校验。
5. 逐步将 `generate.py` 中的平台抓取、归一化、渲染拆分，但在拆分完成前保持单一生产入口，避免形成两套失真的架构。

## 下一阶段

- 补齐旧平台的 `price_source_url` 和币种转换证据，逐步消除血缘警告。
- 连续观察三次真实每日 schedule，确认刷新、提交、Vercel 发布、告警恢复闭环稳定。
- 将页面区块继续拆成更小模板，并为筛选状态、计算器和复制命令补充更细粒度测试。

价格数据仅供选型参考，最终以平台控制台和正式账单为准。
