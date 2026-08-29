# Phase 16 数据刷新中断事件报告

更新时间：2026-08-29（Asia/Shanghai）

## 结论

生产站可访问，但每日模型数据刷新已经中断。仓库和生产 `models_data.json` 的最后采集时间均为 `2026-08-13 00:52`，数据产品不能再被描述为实时。

本次取证只能确认“旧刷新入口停止产生定时运行，且存在四条 GitHub 状态异常的 queued runs”。没有足够证据把唯一根因写死为 concurrency、Secrets 或 GitHub schedule 服务。

## 事件基线

- 默认分支：`main`
- 事件基线提交：`c55fcfa8b009205d38a7363c9685c70b1d69bc7a`
- 远程回退标签：`phase16-baseline-20260829`
- 本地与 `origin/main`：取证时一致，工作区干净
- 生产域名：`https://model.ai-selector.top`
- 生产托管：Vercel，响应头包含 `server: Vercel`
- 数据记录：2279 个模型，23 个有数据的平台
- 最后采集：`2026-08-13 00:52`
- 最近健康检查：持续因数据超过 48 小时新鲜度门禁而失败

## GitHub Actions 证据

取证时工作流均为 active：`CI`、`Deploy to Aliyun`、`Deployment Health`、`Refresh Model Data on Main`、`Update Model Data`。

四条手工刷新从 2026-08-12 起长期显示 queued：

| Run ID | 触发方式 | 原始 HEAD | 状态 |
|---|---|---|---|
| 31616940314 | workflow_dispatch | 829b9aa | queued |
| 31617426392 | workflow_dispatch | 829b9aa | queued |
| 31618066335 | workflow_dispatch | 6bd7d16 | queued |
| 31618365140 | workflow_dispatch | 76222bc | queued |

调用取消 API 时 GitHub 返回 `Cannot cancel a workflow run that is completed`，但运行列表仍返回 queued。这些记录不能被正常取消，应视为 GitHub 状态不一致的幽灵队列，并通过全新的入口工作流身份和 concurrency 组绕开。

旧 `Update Model Data` 最近可见的 schedule 运行停在 2026-07-09；8 月 13 日的数据恢复来自单独的 main push 调用链，之后没有新的每日 schedule 运行。

仓库 Actions 已启用，允许全部 Actions；默认 `GITHUB_TOKEN` 权限为 read。生产刷新入口必须显式声明最小的 `contents: write` 权限。

## Secrets 核验边界

GitHub 只允许核验 Secret 名称，不能读取或证明其值仍有效。取证时 25 个数据平台/通知 Secret 名称存在，包括 `SF_KEY`、`ALIYUN_KEY`、`MS_KEY`、`ZH_KEY`、`VOLC_KEY`、`TENCENT_KEY`、`TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID` 等。

工作流声明的 `YI_KEY` 不在仓库 Secret 名称列表中，因此零一万物采集会明确降级为 fallback；它不应拖垮其他平台刷新。

历史腾讯 Cookie/凭据是否已在供应商侧轮换，无法通过当前仓库证明。当前树只从环境变量或被 Git 忽略的 `tencent_cookie.json` 读取凭据；安全责任人仍需在腾讯控制台确认旧凭据失效并记录轮换日期，不能把新值写入仓库或本报告。

## Vercel Git 连接纠偏

首次合并后的现场验证发现，GitHub 状态检查部署到重复项目 `model-selector`，而自定义域名实际绑定在 `ai-model-selector`。这说明“Vercel check 成功”此前不能证明正式域名已经更新。

2026-08-29 已完成：

- 将 `k-goz/model-selector` GitHub 仓库连接到正式 Vercel 项目 `ai-model-selector`；
- 从重复项目 `model-selector` 断开 Git 自动部署；
- 保留重复项目本身，不执行不可逆删除；
- 删除本地临时链接目录及其中的短期 OIDC 环境文件。

后续必须以 `model.ai-selector.top` 的响应、部署 commit 和线上 JSON 为验收依据，不能只看 GitHub 的 Vercel 状态为绿色。

## 修复设计

1. 新建 `refresh-model-data.yml`，独立承载 `schedule` 和 `workflow_dispatch`。
2. `update-models.yml` 只保留 `workflow_call`，作为唯一执行体。
3. 新入口使用 `production-model-data-refresh-v2` concurrency 组，绕开旧工作流幽灵队列，同时保证生产刷新串行。
4. 删除用于临时恢复的 `refresh-on-main.yml`，避免任意 main push 都触发全量刷新。
5. 部署健康检查只验证正式域名，数据过期时至多每 24 小时通知和触发一次恢复刷新。
6. 告警状态通过 GitHub Actions cache 跨运行保存；状态恢复时发送一次恢复通知。
7. 刷新失败保留数据、价格基准和 Playwright 诊断产物。
8. 本地页面 dry run 使用 `python3 generate.py --render-only`；即使快照过期也不联网、不覆盖 JSON、不伪造采集时间。

## 验收与待观察项

一次手工全量刷新、自动提交、Vercel 部署和 2 小时新鲜度门禁必须在合并后现场验证。

连续三次每日 schedule 成功属于时间型验收，当前开发会话不能提前宣称完成。判定标准：三个相邻自然日均由 `schedule` 触发，刷新工作流成功，提交/无变化结论合理，生产健康检查通过，且没有重复故障告警。

# 2026-08-29 真实刷新补充记录

- 手动运行 `33261466626` 成功完成采集，但被 Ground Truth 门禁阻断，未提交陈旧或错误数据。
- 根因是 DeepSeek 官方定价表新增空闲/高峰时段与第三个模型列，旧解析器发生列错位；同时旧基准价格已经失效。
- 修复口径：解析逐行时段表，数据排序和预算采用高峰价，页面及 JSON 同时展示空闲至高峰区间。
- CI 生成阶段延迟成功通知，只有所有门禁通过后才允许状态恢复通知，避免“先报成功、后验收失败”。

## 2026-08-30 恢复验收

- 生产刷新运行：[`33262016571`](https://github.com/k-goz/model-selector/actions/runs/33262016571)，`workflow_dispatch`，结论 `success`。
- 自动数据提交：`7d71db3`（`auto: update model data 2026-08-30`）。
- 产物：2301 个模型；数据时间 `2026-08-30 00:06`；23 个平台中 22 个探测可达。
- 门禁：115 项 Python 测试、17/17 Ground Truth、16 项最终浏览器回归、数据与站点校验全部通过；数据校验保留 567 个上下文未知和 4 个价格待确认警告，没有将其伪装成已知或免费。
- 生产部署：Vercel `ai-model-selector` deployment `dpl_9R5DVWVn72dJD2hNceDq3fat7SH5`，状态 `Ready`，正式域名 `https://model.ai-selector.top`。
- 一致性：生产与 Git 的 `models_data.json` SHA-256 均为 `04260600df496ec1bfdd4077884b814fde1e523cc08ad4a7389b35a0d2e9cf95`。
- 线上验收：2 小时新鲜度门禁通过；页面显示“数据新鲜”和相同时间；客户端重绘后仍显示 DeepSeek 空闲至高峰价格区间，浏览器控制台 0 错误。
- 部署健康运行：[`33262478682`](https://github.com/k-goz/model-selector/actions/runs/33262478682)，结论 `success`，未触发恢复刷新。
- 刷新告警状态已从失败恢复并发送一次恢复通知；成功消息不再提前于质量门禁发送。

下一次计划任务预计在北京时间 `2026-08-31 06:00` 触发。连续三个自然日的 `schedule` 验收仍是时间型待确认项；只有三次均成功且生产健康检查无重复告警后，才能关闭该观察项。

人工责任项仍未伪装成技术完成：GitHub 无法证明历史凭据是否已由负责人完成轮换；仓库 Secret 名称中 `YI_KEY` 仍未配置，因此零一万物当前明确使用 fallback 数据。
