"""生产目录 v2 身份、证据、可信度与生命周期合同。"""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Mapping

from src.pricing import normalize_for_match

SCHEMA_VERSION = "2.0.0"
IDENTITY_VERSION = "1"


def _stable_id(prefix: str, value: str) -> str:
    digest = sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def canonical_model_key(name: str, aliases: Mapping[str, str] | None = None) -> str:
    """返回大小写、常见厂商前缀和显式别名归一后的标准模型 key。"""
    normalized = normalize_for_match(name)
    built_in_aliases = {
        "deepseek-chat": "deepseek-v3",
        "deepseek-reasoner": "deepseek-r1",
    }
    alias_map = {
        **built_in_aliases,
        **{normalize_for_match(key): normalize_for_match(value) for key, value in (aliases or {}).items()},
    }
    return alias_map.get(normalized, normalized)


def infer_version(name: str) -> str | None:
    matches = re.findall(r"(?:^|[-_.])((?:20)?\d{6,8}|v?\d+(?:\.\d+){0,2})(?:$|[-_.])", name, re.I)
    return matches[-1] if matches else None


def lifecycle_for(model: Mapping[str, Any]) -> dict[str, Any]:
    status = str(model.get("price_status", "unknown"))
    tags = {str(tag).lower() for tag in model.get("tags", [])}
    if status == "unavailable" or "已下线" in tags:
        lifecycle = "unavailable"
    elif status == "retiring" or "即将下线" in tags:
        lifecycle = "retiring"
    elif any("deprecated" in tag or "弃用" in tag for tag in tags):
        lifecycle = "deprecated"
    elif any("preview" in tag or "预览" in tag for tag in tags):
        lifecycle = "preview"
    elif status == "unknown":
        lifecycle = "unknown"
    else:
        lifecycle = "active"
    return {
        "status": lifecycle,
        "since": model.get("collected_at") or None,
        "retirement_at": None,
    }


def confidence_for(model: Mapping[str, Any]) -> dict[str, Any]:
    """用可解释规则计算可信度，而不是写入装饰性分数。"""
    source_type = str(model.get("model_source", "legacy_snapshot"))
    source_scores = {"api": 0.72, "scrape": 0.62, "fallback": 0.42, "legacy_generator": 0.35, "legacy_snapshot": 0.35}
    score = source_scores.get(source_type, 0.30)
    factors = [{"factor": f"catalog_source:{source_type}", "impact": round(score, 2)}]

    price_tag = str(model.get("price_src", ""))
    price_impacts = {"S": 0.18, "SP": 0.16, "A": 0.15, "DB": 0.12, "D": 0.12, "P": 0.08, "OR": 0.05, "L": 0.04}
    impact = price_impacts.get(price_tag, 0.0)
    if impact:
        score += impact
        factors.append({"factor": f"price_source:{price_tag}", "impact": impact})
    if model.get("price_source_url"):
        score += 0.05
        factors.append({"factor": "price_evidence_url", "impact": 0.05})
    context_status = model.get("context_status")
    if context_status == "known":
        score += 0.03
        factors.append({"factor": "context_known", "impact": 0.03})
    elif context_status == "inferred":
        score -= 0.05
        factors.append({"factor": "context_inferred", "impact": -0.05})
    score = round(max(0.1, min(0.99, score)), 2)
    grade = "high" if score >= 0.80 else "medium" if score >= 0.60 else "low"
    return {"score": score, "grade": grade, "factors": factors, "method": "catalog-confidence-v1"}


def warnings_for(model: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    if model.get("price_status") == "unknown":
        warnings.append("price_unknown")
    if model.get("context_status") == "unknown":
        warnings.append("context_unknown")
    if model.get("context_status") == "inferred":
        warnings.append("context_inferred")
    if model.get("model_source") in {"fallback", "legacy_generator", "legacy_snapshot"}:
        warnings.append("catalog_fallback")
    if not model.get("price_source_url"):
        warnings.append("price_evidence_url_missing")
    return warnings


def enrich_model_contract(model: dict[str, Any], aliases: Mapping[str, str] | None = None) -> dict[str, Any]:
    provider_id = str(model["platform_id"])
    provider_model_name = str(model["name"])
    canonical_key = canonical_model_key(provider_model_name, aliases)
    model.update(
        {
            "identity_version": IDENTITY_VERSION,
            "canonical_model_id": _stable_id("model", canonical_key),
            # 平台原始 ID 可能区分大小写；跨平台关联由 canonical_model_id 负责。
            "provider_offering_id": _stable_id("offering", f"{provider_id}\0{provider_model_name}"),
            "provider_id": provider_id,
            "provider_model_name": provider_model_name,
            "model_family": model.get("family") or "unknown",
            "version": infer_version(provider_model_name),
            "region": model.get("region") or "unspecified",
            "aliases": list(model.get("aliases") or []),
            "cache_input_price": model.get("cache_input_price"),
            "evidence_at": model.get("collected_at"),
            "price_effective_at": model.get("price_effective_at"),
            "confidence": confidence_for(model),
            "lifecycle": lifecycle_for(model),
            "data_warnings": warnings_for(model),
        }
    )
    return model


def enrich_catalog_contract(
    catalog: dict[str, Any],
    aliases: Mapping[str, str] | None = None,
    previous_models: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    catalog.setdefault("meta", {})["schema_version"] = SCHEMA_VERSION
    catalog["meta"]["identity_version"] = IDENTITY_VERSION
    previous_index = {
        str(model.get("provider_offering_id")): model
        for model in (previous_models or [])
        if model.get("provider_offering_id")
    }
    for model in catalog.get("models", []):
        enrich_model_contract(model, aliases)
        previous = previous_index.get(model["provider_offering_id"])
        if not previous:
            continue
        previous_lifecycle = previous.get("lifecycle") or {}
        if previous_lifecycle.get("status") == model["lifecycle"]["status"]:
            model["lifecycle"]["since"] = previous_lifecycle.get("since")
            model["lifecycle"]["retirement_at"] = previous_lifecycle.get("retirement_at")
        if previous.get("aliases"):
            model["aliases"] = list(previous["aliases"])
        if (
            previous.get("input_price") == model.get("input_price")
            and previous.get("output_price") == model.get("output_price")
            and previous.get("price_status") == model.get("price_status")
        ):
            model["price_effective_at"] = previous.get("price_effective_at")
    return catalog
