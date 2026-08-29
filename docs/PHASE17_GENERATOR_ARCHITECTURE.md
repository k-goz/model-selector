# Phase 17 生成器模块化架构

## Phase 17-1：配置与采集边界

- `src/config.py`：唯一运行配置入口，集中解析 API Key、路径、通知开关和三个兼容 CLI 参数。
- `src/errors.py`：采集、缓存和价格层共享的安全异常类型。
- `src/collection/http.py`：统一 JSON 重试、确定性缓存写入、失败缓存回退和文本请求。
- `src/collection/catalog.py`：平台注册表与一次性采集编排，统一返回模型列表和 `source_runs` 血缘。
- `src/platforms/`：每个平台只负责自身响应解析、规范化和平台级 fallback。

真实生成器通过 `RuntimeConfig`、`CachedHttpClient` 和 `collect_platform_catalog` 使用上述边界。旧的 `fj` 名称暂保留为薄兼容包装，待 Phase 17-3 收缩入口时删除。

## 兼容证明

- `generate.py --render-only` 前后 `models_data.json` 语义 diff 为零。
- 中文和英文 HTML 字节级一致。
- CLI 参数和全部环境变量契约由自动化测试锁定。
- 网络成功写缓存、网络失败读缓存、平台注册与血缘均有单元测试。

后续 Phase 17-2 将迁移定价、模型规范化和发布逻辑；Phase 17-3 再迁移渲染、监控、通知并将 `generate.py` 收缩为 CLI 编排入口。
