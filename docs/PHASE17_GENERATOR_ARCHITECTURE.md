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

## 验证记录纠正

Phase 17-1 首次隔离刷新命令的后续恢复步骤掩盖了前段退出码，因此当时“隔离真实刷新完成”的表述无效。Phase 17-2 重新以失败即停止方式执行后，发现平台注册表遗漏 `openrouter`；现已补齐，并新增 23 个生产采集器的完整性门禁。静态生产站未受影响，且 06:00 计划刷新尚未发生。

## Phase 17-2：定价、规范化与发布边界

- `src/pricing/official.py`：官方价格页与公开价格端点采集。
- `src/pricing/__init__.py`：唯一模型名称标准化、模型家族/标签/场景推断、价格数据库与四层 SSOT 解析。
- `src/publication/catalog.py`：从规范化卡片生成目录、价格来源证据、数据血缘、上下文状态和统计元数据。
- `generate.py`：不再自行实现上述规则，只保留阶段性薄包装和编排。

隔离真实刷新在本机无平台私钥的条件下生成 1627 个模型，其中 API 1331、scrape 89、fallback 207；Phase 17 兼容 Schema 通过，且包含 OpenRouter。该结果仅是隔离工程验证，没有覆盖正式 2301 模型生产快照。
