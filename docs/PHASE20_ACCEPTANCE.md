# Phase 20 与整体计划验收记录

验收时间：2026-08-30（Asia/Shanghai）

## 交付范围

- Phase 16–20 的工程项均已进入 `main`；Phase 20-3 实现提交为 `69fa5f2`。
- 生产入口：`https://model.ai-selector.top`。
- 生产 API：`/api/v1/models`，API `1.0.0`，数据 Schema `2.0.0`。
- `MODEL_API_KEYS` 已在 Vercel Production、Preview、Development 作为 Secret 配置；文档和仓库不保存 Key。

## 当前数据快照

- 更新时间：`2026-08-31 08:02`；
- 模型总数：2,302；平台数：23；
- 来源血缘：API 2,108、官方页面抓取 89、fallback 105；
- 价格状态：priced 1,400、free_tier 653、non_token 151、unavailable 47、free 26、retiring 21、unknown 4；
- 已知质量提示：567 条缺少上下文长度，4 条价格待确认，均保留不确定性语义，没有被填造成已知值。

## 工程与生产证据

- Python：141 passed；Node API：6 passed；
- Playwright：29 passed，1 个重复的移动端重型用例有意跳过；
- Ground Truth：17/17；Schema、站点和前端预算门禁通过；
- Lighthouse：Performance 99、Accessibility 100、Best Practices 100、SEO 100；
- `npm audit`：0 vulnerabilities；
- GitHub PR #23 回归：https://github.com/k-goz/model-selector/actions/runs/33271310033；
- 生产首页、英文页、JSON 健康检查 0 errors，6 个前端脚本均 HTTP 200，浏览器控制台 0 errors；
- 本地与生产数据一致：2,302 条、Schema `2.0.0`、更新时间 `2026-08-31 08:02`；
- 生产 API 验收：未认证 401、认证 200、ETag 重验证 304，缓存和限流响应头存在；
- 生产有界面 Chromium 直接调用 Service Worker 通知，结果为 `permission=granted`、`status=sent`、`channel=browser`。

这些证据证明工程闭环与受控生产通道可用，不代表已有真实企业客户付费、留存或规模化通知送达。

2026-08-30 将官方 Actions 升级到 Node.js 24+ 的当前主版本（提交 `bb1bb57`），完整 CI [33287604485](https://github.com/k-goz/model-selector/actions/runs/33287604485) 通过且不再出现 Node.js 20 弃用警告。手工验证的部署健康 [33287719823](https://github.com/k-goz/model-selector/actions/runs/33287719823) 与数据刷新 [33287721632](https://github.com/k-goz/model-selector/actions/runs/33287721632) 均成功；两者用于验证新版 checkout、setup、cache 和 artifact 链路，`workflow_dispatch` 不计入三次 schedule 验收。

## 尚待时间观察的唯一门禁

附件要求“连续三次每日 schedule 成功”必须来自真实定时运行。当前连续成功为 **2/3**，因此整体计划的工程开发完成，但时间型运营验收仍标记为待观察，不能虚报完成。

| 序号 | schedule run | 结果 | 数据提交 | 数据时间 | 数据门禁 | Vercel Git Production | 生产一致性 |
|---|---|---|---|---|---|---|---|
| 1 | [33281599414](https://github.com/k-goz/model-selector/actions/runs/33281599414) | success | `871493c` | `2026-08-30 07:43` | passed，high-risk 0 | `dpl_2bbDtyt2RkB7sMcq5GJYP9cJd3Fj` Ready | 2,301 条、Schema `2.0.0`、时间一致 |
| 2 | [33343334350](https://github.com/k-goz/model-selector/actions/runs/33343334350) | success | `160d2ab` | `2026-08-31 08:02` | passed，high-risk 0 | `dpl_B9QKnpJ8srBnGpcpQcBggBRXhrpb` Ready | 2,302 条、Schema `2.0.0`、时间一致 |

第一次定时刷新产生 6 条报价字段变化、0 新增、0 移除；模型数、平台数、fallback 比例、上下文未知和价格未知均未恶化。变化来源 `https://openrouter.ai/api/v1/models` 验收时 HTTP 200。

第二次定时刷新新增 Together `Qwen/Qwen3.8-Flash`，产生 7 条报价字段变化、0 移除；模型数增至 2,302，fallback 比例略降，上下文未知和价格未知未增加。质量门禁通过，高风险变化为 0，抽样报价来源验收时 HTTP 200。

判定标准：默认分支 `Refresh Model Data` 工作流出现连续 3 次 `event=schedule`、`conclusion=success`，每次生成数据通过门禁并自动提交，随后 Vercel Git 部署成功，生产数据时间与该提交一致。任何一次失败都会中断连续计数并进入事件处理。
