"""基于已发布快照的高风险目录差异门禁。"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


DEFAULT_POLICY = {
    "max_model_drop_ratio": 0.05,
    "max_platform_drop": 0,
    "max_fallback_ratio_increase": 0.05,
    "max_unknown_context_increase": 100,
    "max_removed_offerings": 100,
    "large_price_change_ratio": 0.50,
    "max_large_price_changes": 20,
}


def catalog_metrics(catalog: dict[str, Any]) -> dict[str, Any]:
    models = catalog.get("models", [])
    total = len(models)
    sources = Counter(str(model.get("model_source", "")) for model in models)
    return {
        "models": total,
        "platforms": len({model.get("provider_id") or model.get("platform_id") for model in models}),
        "fallback_ratio": sources["fallback"] / total if total else 1.0,
        "unknown_context": sum(model.get("context_status") == "unknown" for model in models),
        "unknown_price": sum(model.get("price_status") == "unknown" for model in models),
    }


def load_policy(path: Path | None = None) -> dict[str, Any]:
    if path and path.exists():
        document = json.loads(path.read_text(encoding="utf-8"))
        return {**DEFAULT_POLICY, **document.get("policy", {})}
    return dict(DEFAULT_POLICY)


def assess_catalog_risk(
    before: dict[str, Any],
    after: dict[str, Any],
    diff: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = {**DEFAULT_POLICY, **(policy or {})}
    old = catalog_metrics(before)
    new = catalog_metrics(after)
    risks: list[dict[str, Any]] = []

    drop_ratio = max(0.0, (old["models"] - new["models"]) / old["models"]) if old["models"] else 0.0
    if drop_ratio > rules["max_model_drop_ratio"]:
        risks.append({"code": "model_count_drop", "actual": round(drop_ratio, 4), "limit": rules["max_model_drop_ratio"]})
    platform_drop = old["platforms"] - new["platforms"]
    if platform_drop > rules["max_platform_drop"]:
        risks.append({"code": "platform_count_drop", "actual": platform_drop, "limit": rules["max_platform_drop"]})
    fallback_increase = new["fallback_ratio"] - old["fallback_ratio"]
    if fallback_increase > rules["max_fallback_ratio_increase"]:
        risks.append({"code": "fallback_ratio_increase", "actual": round(fallback_increase, 4), "limit": rules["max_fallback_ratio_increase"]})
    unknown_increase = new["unknown_context"] - old["unknown_context"]
    if unknown_increase > rules["max_unknown_context_increase"]:
        risks.append({"code": "unknown_context_increase", "actual": unknown_increase, "limit": rules["max_unknown_context_increase"]})
    removed = int(diff.get("summary", {}).get("removed", 0))
    if removed > rules["max_removed_offerings"]:
        risks.append({"code": "removed_offerings", "actual": removed, "limit": rules["max_removed_offerings"]})

    large_price_changes: list[dict[str, Any]] = []
    for change in diff.get("changes", []):
        for field in ("input_price", "output_price", "cache_input_price"):
            if field not in change.get("fields", []):
                continue
            old_value = change.get("before", {}).get(field)
            new_value = change.get("after", {}).get(field)
            if not isinstance(old_value, (int, float)) or not isinstance(new_value, (int, float)) or old_value <= 0:
                continue
            ratio = abs(new_value - old_value) / old_value
            if ratio > rules["large_price_change_ratio"]:
                large_price_changes.append({
                    "provider_offering_id": change["provider_offering_id"],
                    "field": field,
                    "before": old_value,
                    "after": new_value,
                    "ratio": round(ratio, 4),
                })
    if len(large_price_changes) > rules["max_large_price_changes"]:
        risks.append({"code": "large_price_change_burst", "actual": len(large_price_changes), "limit": rules["max_large_price_changes"]})

    return {
        "format_version": "1.0",
        "status": "blocked" if risks else "passed",
        "baseline": old,
        "candidate": new,
        "policy": rules,
        "high_risk": risks,
        "large_price_changes": large_price_changes,
        "ground_truth_gate": "delegated_to_verify_ground_truth.py",
    }


def write_quality_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
