# Phase 17 生成器重构保护网

基线标签：`phase17-baseline-20260830`  
基线提交：`6d10a098114a805f578d0b0c5f121b0bb4f33389`

## 目的

Phase 17 只改变代码职责边界，不允许无说明地改变模型、价格、来源、上下文、页面功能或生产入口。任何功能开发必须与生成器拆分分开提交。

## 已锁定的兼容面

- CLI：`--refresh`、`--render-only`、`--update-db`。
- 环境变量：平台 Key、输出路径、模型 JSON、缓存目录、Telegram 和延迟成功通知开关。
- 代表性语义：七种价格状态、三种来源类型、四种上下文状态、DeepSeek 时段价格区间。
- 生成产物：模型数量、平台分布、价格状态、来源分布、上下文状态和逐 offering 语义。
- Schema：Phase 17 兼容 Schema 锁定当前公开结构与枚举；Phase 18 再升级为正式版本。
- 既有门禁：Python、Ground Truth、数据、页面、Playwright、npm audit。

## 机器可读差异

```bash
python3 scripts/compare_generated_artifacts.py \
  --baseline /path/to/before/models_data.json \
  --candidate /path/to/after/models_data.json \
  --output output/phase17-artifact-diff.json \
  --fail-on-change
```

报告忽略模型数组顺序和 `collected_at`，但价格、状态、来源、上下文、标签和证据等语义变化会失败。Phase 18 引入正式稳定 ID 后，当前 `platform_id/name` 兼容键将迁移为 `provider_offering_id`。

```bash
python3 scripts/validate_catalog_schema.py models_data.json
```

CI 与真实刷新流水线都执行 Draft 2020-12 Schema 校验。

## 当前基线

- `generate.py`：2893 行。
- `assets/app.js`：1498 行。
- 模型：2301。
- 平台：23。
- 来源：API 2107、scrape 89、fallback 105。
- 价格状态：priced 1399、free 26、free_tier 653、non_token 151、unknown 4、retiring 21、unavailable 47。
- 上下文状态：known 1430、inferred 153、not_applicable 151、unknown 567。

这些数值只用于绑定本次重构起点，不作为后续真实刷新必须保持不变的业务阈值。
