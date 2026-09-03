# Phase 20 与整体计划验收记录

验收更新时间：2026-09-01（Asia/Shanghai）

## 交付范围

- Phase 16–20 的工程项均已进入 `main`；Phase 20-3 实现提交为 `69fa5f2`。
- 生产入口：`https://model.ai-selector.top`。
- 生产 API：`/api/v1/models`，API `1.0.0`，数据 Schema `2.0.0`。
- `MODEL_API_KEYS` 已在 Vercel Production、Preview、Development 作为 Secret 配置；文档和仓库不保存 Key。

## 当前数据快照

- 更新时间：`2026-09-03 07:41`；
- 模型总数：2,328；平台数：23；
- 来源血缘：API 2,134、官方页面抓取 89、fallback 105；
- 价格状态：priced 1,422、free_tier 657、non_token 151、unavailable 47、free 26、retiring 21、unknown 4；
- 已知质量提示：567 条缺少上下文长度，4 条价格待确认，均保留不确定性语义，没有被填造成已知值。

## 工程与生产证据

- Python：143 passed；Node API：6 passed；
- Playwright：29 passed，1 个重复的移动端重型用例有意跳过；
- Ground Truth：17/17；Schema、站点和前端预算门禁通过；
- Lighthouse：Performance 99、Accessibility 100、Best Practices 100、SEO 100；
- `npm audit`：0 vulnerabilities；
- GitHub PR #23 回归：https://github.com/k-goz/model-selector/actions/runs/33271310033；
- 生产首页、英文页、JSON 健康检查 0 errors，6 个前端脚本均 HTTP 200，浏览器控制台 0 errors；
- 本地与生产数据一致：2,328 条、Schema `2.0.0`、更新时间 `2026-09-03 07:41`；
- 生产 API 验收：未认证 401、认证 200、ETag 重验证 304，缓存和限流响应头存在；
- 生产有界面 Chromium 直接调用 Service Worker 通知，结果为 `permission=granted`、`status=sent`、`channel=browser`。

这些证据证明工程闭环与受控生产通道可用，不代表已有真实企业客户付费、留存或规模化通知送达。

2026-08-30 将官方 Actions 升级到 Node.js 24+ 的当前主版本（提交 `bb1bb57`），完整 CI [33287604485](https://github.com/k-goz/model-selector/actions/runs/33287604485) 通过且不再出现 Node.js 20 弃用警告。手工验证的部署健康 [33287719823](https://github.com/k-goz/model-selector/actions/runs/33287719823) 与数据刷新 [33287721632](https://github.com/k-goz/model-selector/actions/runs/33287721632) 均成功；两者用于验证新版 checkout、setup、cache 和 artifact 链路，`workflow_dispatch` 不计入三次 schedule 验收。

## 尚待时间观察的唯一门禁

附件要求“连续三次每日 schedule 成功”必须来自真实定时运行。2026-09-01 的第三次定时运行失败，中断了此前连续两次成功；修复后已有两个相邻自然日的真实定时运行成功，当前连续成功为 **2/3**。整体计划的工程开发完成，但时间型运营验收仍标记为待观察，不能虚报完成。

| 序号 | schedule run | 结果 | 数据提交 | 数据时间 | 数据门禁 | Vercel Git Production | 生产一致性 |
|---|---|---|---|---|---|---|---|
| 1 | [33281599414](https://github.com/k-goz/model-selector/actions/runs/33281599414) | success | `871493c` | `2026-08-30 07:43` | passed，high-risk 0 | `dpl_2bbDtyt2RkB7sMcq5GJYP9cJd3Fj` Ready | 2,301 条、Schema `2.0.0`、时间一致 |
| 2 | [33343334350](https://github.com/k-goz/model-selector/actions/runs/33343334350) | success | `160d2ab` | `2026-08-31 08:02` | passed，high-risk 0 | `dpl_B9QKnpJ8srBnGpcpQcBggBRXhrpb` Ready | 2,302 条、Schema `2.0.0`、时间一致 |
| 3 | [33456632457](https://github.com/k-goz/model-selector/actions/runs/33456632457) | **failure** | 无 | 无 | Schema/质量通过；过期 Ground Truth 将已下线模型误判为缺失 | 无新部署，生产保持上一稳定版 | 连续计数重置为 0/3 |
| 4 | [33572068696](https://github.com/k-goz/model-selector/actions/runs/33572068696) | success | `900ac5c` | `2026-09-02 07:41` | passed，Ground Truth 17/17，high-risk 0 | `dpl_2FzNJGk13drK8G4rqhp7e3VYGzup` Ready | 2,315 条、Schema `2.0.0`、时间及 SHA-256 一致；新连续计数 1/3 |
| 5 | [33696194319](https://github.com/k-goz/model-selector/actions/runs/33696194319) | success | `aa181a0` | `2026-09-03 07:41` | passed，Ground Truth 17/17，high-risk 0 | `dpl_3wb8rZBKfG2EYjapjpq2VZTZhQev` Ready | 2,328 条、Schema `2.0.0`、时间及 SHA-256 一致；新连续计数 2/3 |

第一次定时刷新产生 6 条报价字段变化、0 新增、0 移除；模型数、平台数、fallback 比例、上下文未知和价格未知均未恶化。变化来源 `https://openrouter.ai/api/v1/models` 验收时 HTTP 200。

第二次定时刷新新增 Together `Qwen/Qwen3.8-Flash`，产生 7 条报价字段变化、0 移除；模型数增至 2,302，fallback 比例略降，上下文未知和价格未知未增加。质量门禁通过，高风险变化为 0，抽样报价来源验收时 HTTP 200。

第三次定时刷新中，Moonshot 官方 API 仅返回 `kimi-k2.6`、`kimi-k2.7-code`、`kimi-k2.7-code-highspeed` 和 `kimi-k3`。核验官方文档后确认 `moonshot-v1`、`kimi-k2` 与 `kimi-k2.5` 系列已经正式下线，并非上游异常。修复提交 `86b7a2a` 更新 Moonshot fallback，防止 API 故障时重新发布已退休模型；Ground Truth 改为同时校验 14 个现役价格和 3 个退休模型不得重新出现。

手工修复验证 [33461839355](https://github.com/k-goz/model-selector/actions/runs/33461839355) 全链路成功：143 个 Python 测试、Schema/质量门禁、Ground Truth 17/17、站点校验以及 Playwright 29 passed/1 skipped 均通过；自动数据提交为 `1f19314`。新目录归档 8 个 Moonshot 已下线 offering，Moonshot 现役目录为 4 个模型。Vercel Git Production 部署 `dpl_37ihsKJNVw8CUZPwNVHoaJEMWcZZ` 为 Ready，自定义域名与仓库 `models_data.json` SHA-256 完全一致；本次手工 `workflow_dispatch` 仅证明修复有效，不计入 schedule 连续成功。

修复后的首个真实定时运行 [33572068696](https://github.com/k-goz/model-selector/actions/runs/33572068696) 成功：目录由 2,323 调整为 2,315，新增 5、移除 13、变更 16，质量门禁判定 high-risk 0；Schema、Ground Truth、站点及 Playwright 全部通过。自动提交 `900ac5c` 已由 Vercel Git Production 部署，自定义域名数据与仓库 SHA-256 一致，因此计为新连续序列的第 1 次成功。

第二个真实定时运行 [33696194319](https://github.com/k-goz/model-selector/actions/runs/33696194319) 成功：目录由 2,315 调整为 2,328，新增 14、移除 1、变更 8，质量门禁判定 high-risk 0；Schema、Ground Truth、站点及 Playwright 全部通过。自动提交 `aa181a0` 已由 Vercel Git Production 部署，自定义域名数据与仓库 SHA-256 一致，因此计为新连续序列的第 2 次成功。

判定标准：默认分支 `Refresh Model Data` 工作流出现连续 3 次 `event=schedule`、`conclusion=success`，每次生成数据通过门禁并自动提交，随后 Vercel Git 部署成功，生产数据时间与该提交一致。任何一次失败都会中断连续计数并进入事件处理。
