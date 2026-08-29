# Phase 19 前端数据驱动改造

## 19-1：动态目录与有界 DOM

- `index.html` 与 `en/index.html` 只保留页面壳，不再静态内嵌全部模型卡片。
- 浏览器以 `models_data.json` 为唯一模型目录来源，搜索、筛选、排序和计算均基于完整数据集。
- 每页最多渲染 66 张卡片；翻页时替换当前窗口，避免 2,000 余个卡片长期驻留 DOM。
- 页面保留 `noscript` 提示，JavaScript 不可用时可直接查看公开 JSON 数据。
- 加载失败会在目录区域显示可见错误，不把空目录伪装为正常结果。

## 验收口径

静态校验会拒绝重新生成的内嵌卡片；浏览器回归同时验证完整目录总数、66 张卡片上限、分页替换、深层搜索、价格显示、计算器及中英文入口。

## 19-2：模块、i18n、可信信息和分享状态

- 前端资源拆为 `assets/js/i18n.js`、`routing.js`、`analytics.js` 与 `core.js`，由页面按依赖顺序延迟加载。
- Python 英文生成器只翻译 HTML 文本节点和属性；`script`、`style` 原文不参与替换。翻译目录使用稳定哈希 key，并在测试中检查中英文完整性。
- 动态卡片文案通过同一中英文字典生成，不再依赖生成后的整页替换。
- 卡片展示数据可信度、采集日期和可用的证据链接；未知价格继续保持未知，不显示成免费。
- `#v2=` 分享状态覆盖搜索、筛选、排序、具体 offering、最多三项对比、计算参数与语言；旧版无前缀 hash 仍可兼容读取。
- 产品指标仅保存在当前浏览器会话并广播匿名动作事件，不采集搜索文本、代码内容或 API Key。

## 19-3：性能与可访问性门禁

- `PerformanceObserver` 采集 LCP、CLS、INP 到同一匿名会话指标通道。
- `scripts/check_frontend_budget.py` 固定 HTML 300 KB、JavaScript 100 KB、零静态卡片预算，并以 2,000+ 模型作为基准规模。
- Lighthouse 门禁覆盖 Performance 75、Accessibility 95、Best Practices 90、SEO 90，并检查文档、脚本、总传输和脚本请求数预算。
- CI 使用 Lighthouse `provided` 实测模式，避免共享 runner 的模拟慢网评分在相同产物上大幅漂移；资源体积和大目录搜索耗时仍由独立硬门禁约束。
- Playwright 对 2,301 条目录执行 50 轮搜索基准，同时在桌面和移动视口运行 axe 自动无障碍审计。
- 卡片支持键盘 Enter/Space，弹窗恢复焦点，页面提供跳转链接、可见焦点、ARIA 状态以及 `prefers-reduced-motion` 降级。
