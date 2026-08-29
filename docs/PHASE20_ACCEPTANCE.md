# Phase 20 与整体计划验收记录

验收时间：2026-08-30（Asia/Shanghai）

## 交付范围

- Phase 16–20 的工程项均已进入 `main`；Phase 20-3 实现提交为 `69fa5f2`。
- 生产入口：`https://model.ai-selector.top`。
- 生产 API：`/api/v1/models`，API `1.0.0`，数据 Schema `2.0.0`。
- `MODEL_API_KEYS` 已在 Vercel Production、Preview、Development 作为 Secret 配置；文档和仓库不保存 Key。

## 当前数据快照

- 更新时间：`2026-08-30 00:06`；
- 模型总数：2,301；平台数：23；
- 来源血缘：API 2,107、官方页面抓取 89、fallback 105；
- 价格状态：priced 1,399、free_tier 653、non_token 151、unavailable 47、free 26、retiring 21、unknown 4；
- 已知质量提示：567 条缺少上下文长度，4 条价格待确认，均保留不确定性语义，没有被填造成已知值。

## 工程与生产证据

- Python：141 passed；Node API：6 passed；
- Playwright：29 passed，1 个重复的移动端重型用例有意跳过；
- Ground Truth：17/17；Schema、站点和前端预算门禁通过；
- Lighthouse：Performance 99、Accessibility 100、Best Practices 100、SEO 100；
- `npm audit`：0 vulnerabilities；
- GitHub PR #23 回归：https://github.com/k-goz/model-selector/actions/runs/33271310033；
- 生产首页、英文页、JSON 健康检查 0 errors，6 个前端脚本均 HTTP 200，浏览器控制台 0 errors；
- 本地与生产数据一致：2,301 条、Schema `2.0.0`、更新时间 `2026-08-30 00:06`；
- 生产 API 验收：未认证 401、认证 200、ETag 重验证 304，缓存和限流响应头存在；
- 生产有界面 Chromium 直接调用 Service Worker 通知，结果为 `permission=granted`、`status=sent`、`channel=browser`。

这些证据证明工程闭环与受控生产通道可用，不代表已有真实企业客户付费、留存或规模化通知送达。

## 尚待时间观察的唯一门禁

附件要求“连续三次每日 schedule 成功”必须来自真实定时运行。当前 `Refresh Model Data` 只有 2026-08-30 的一次成功手工运行（run `33262016571`），尚无连续三次 `schedule` 证据，因此整体计划的工程开发完成，但时间型运营验收仍标记为待观察，不能虚报完成。

判定标准：默认分支 `Refresh Model Data` 工作流出现连续 3 次 `event=schedule`、`conclusion=success`，每次生成数据通过门禁并自动提交，随后 Vercel Git 部署成功，生产数据时间与该提交一致。任何一次失败都会中断连续计数并进入事件处理。
