# Model Selector Data API v1

生产基址：`https://model.ai-selector.top/api/v1`

API 面向受控的服务端集成。第一版不计费，但必须使用项目方签发的 API Key，不得把 Key 放入浏览器、移动端包或公开仓库。接口不开放跨域浏览器调用。

## 认证

任选一种请求头：

```http
Authorization: Bearer $MODEL_API_KEY
X-API-Key: $MODEL_API_KEY
```

生产环境从 Vercel `MODEL_API_KEYS` 读取逗号分隔的 Key。Key 缺失时 API 返回 `503 api_not_configured`，不会退化为匿名公开访问。

## 查询模型

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $MODEL_API_KEY" \
  "https://model.ai-selector.top/api/v1/models?platform=deepseek&status=priced&limit=20"
```

参数：

| 参数 | 含义 |
|---|---|
| `q` | 在模型名、平台名、模型家族和别名中搜索 |
| `platform` | 精确平台 ID |
| `status` | `priced`、`free`、`free_tier`、`non_token`、`unknown`、`retiring`、`unavailable` |
| `confidence` | `high`、`medium`、`low`、`unknown` |
| `limit` | 1–100，默认 50 |
| `cursor` | 使用上次响应的 `next_cursor`，不要自行拼接 |

响应包含 API 版本、数据 Schema 版本、数据更新时间、许可提示、分页信息和原始模型记录。正式响应契约见 [`schemas/models-api.v1.schema.json`](../schemas/models-api.v1.schema.json)，模型数据契约见 [`schemas/models-data.v2.schema.json`](../schemas/models-data.v2.schema.json)。

## 缓存与 ETag

- 成功响应：`Cache-Control: private, max-age=60, stale-while-revalidate=300`；
- 返回强 ETag；客户端可发送 `If-None-Match`，未变化时返回 304；
- `Vary: Authorization, X-API-Key`，防止不同凭据错误复用缓存；
- 错误响应统一 `no-store`。

## 限流与使用量

默认每个“API Key + 来源 IP”每分钟 60 次，请以响应头为准：

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
- 超限返回 429，并包含 `Retry-After`

每次调用会写入不含完整 Key、原始 IP、查询参数的结构化 Vercel 日志，只记录请求 ID、Key 哈希前缀、路径、状态和返回数量。当前限流/计数为单个 Serverless 实例的运营级 MVP，不是跨实例、不可规避的计费级配额；API Key 门禁、每页 100 条上限和客户端缓存共同控制第一版滥用风险。在收费或扩大公开范围前，必须接入共享限流/计量存储。

## 错误语义

```json
{
  "error": {
    "code": "invalid_limit",
    "message": "limit must be an integer between 1 and 100.",
    "request_id": "..."
  }
}
```

常见状态：400 参数错误、401 Key 无效、405 方法不支持、429 超限、500 数据读取失败、503 生产 Key 未配置。

## 数据许可与边界

- 数据来自各供应商 API、官方页面和明确标记的回退来源；原始事实仍受各来源条款约束。
- 使用方必须保留来源、采集时间和可信度字段，不能把本 API 标成供应商官方报价。
- 禁止移除“不确定/未知”语义、把免费额度改写成永久免费，或用本数据替代供应商正式账单。
- 价格数据可用于内部选型和带来源的分析；大规模再分发、转售或训练用途须另行确认来源许可。
