"""生成数据的稳定语义签名与机器可读差异。"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any, Iterable


VOLATILE_MODEL_FIELDS = {"collected_at"}


def offering_key(model: dict[str, Any]) -> str:
    """Phase 17 兼容键；Phase 18 将迁移到正式 offering ID。"""

    return f"{model.get('platform_id', '')}/{model.get('name', '')}"


def _semantic_model(model: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in sorted(model.items())
        if key not in VOLATILE_MODEL_FIELDS
    }


def _counter(models: Iterable[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(model.get(field, "")) for model in models).items()))


def build_catalog_signature(data: dict[str, Any]) -> dict[str, Any]:
    """返回不受数组顺序和采集时间影响的发布语义签名。"""

    models = data.get("models", [])
    normalized = sorted(
        (_semantic_model(model) for model in models),
        key=offering_key,
    )
    payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return {
        "total_models": len(models),
        "platform_counts": _counter(models, "platform_id"),
        "price_status_counts": _counter(models, "price_status"),
        "lineage_counts": _counter(models, "model_source"),
        "context_status_counts": _counter(models, "context_status"),
        "semantic_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def compare_catalogs(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """逐 offering 比较两个目录，输出可供 CI 判定的 JSON 报告。"""

    before_models = {offering_key(model): _semantic_model(model) for model in before.get("models", [])}
    after_models = {offering_key(model): _semantic_model(model) for model in after.get("models", [])}
    before_keys = set(before_models)
    after_keys = set(after_models)
    changed: list[dict[str, Any]] = []
    for key in sorted(before_keys & after_keys):
        old = before_models[key]
        new = after_models[key]
        fields = sorted(field for field in set(old) | set(new) if old.get(field) != new.get(field))
        if fields:
            changed.append({
                "offering": key,
                "fields": fields,
                "before": {field: old.get(field) for field in fields},
                "after": {field: new.get(field) for field in fields},
            })
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    return {
        "format_version": "1.0",
        "compatible": not added and not removed and not changed,
        "before": build_catalog_signature(before),
        "after": build_catalog_signature(after),
        "changes": {
            "added": added,
            "removed": removed,
            "changed": changed,
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
        },
    }
