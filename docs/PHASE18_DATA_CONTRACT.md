# Phase 18 正式数据合同

## v2.0.0 身份与证据

生产目录使用 `schemas/models-data.v2.schema.json`。旧字段继续保留，新增字段包括：

- `canonical_model_id`：由规范化标准模型 key 生成，同一模型可跨平台关联；
- `provider_offering_id`：由平台 ID 与平台原始模型名生成，标识具体 offering；
- `provider_id`、`provider_model_name`、`model_family`、`version`、`region` 和 `aliases`；
- `evidence_at`、`price_effective_at`、`cache_input_price`；
- 可解释的 `confidence`、统一 `lifecycle` 与 `data_warnings`。

ID 算法由 `identity_version=1` 标识。常见厂商前缀、大小写和已知别名先规范化，再生成标准模型 ID；offering ID 保留平台原始名称边界。未来别名迁移必须保留旧 ID 映射，不得直接重算历史身份。

可信度算法 `catalog-confidence-v1` 由目录来源、价格来源、证据 URL 和上下文证据逐项加减分；每条记录保留 factors，不把分数冒充官方认证。未知价格、推断上下文、fallback 和证据链接缺失均进入 `data_warnings`。

`price_effective_at=null` 表示来源没有给出有效时间，不能用抓取时间伪装。`region=unspecified` 表示尚无可验证的地域限制信息。

## 迁移

```bash
python scripts/migrate_catalog_v2.py
python scripts/validate_catalog_schema.py
```

迁移只补充合同字段，不改模型、价格、来源、上下文和页面展示。Schema 后续变更必须提升版本并记录迁移说明。
