"""上下文长度的保守推断与审计元数据。"""

from __future__ import annotations

from collections import Counter, defaultdict
import re
from typing import Any

from src.pricing import normalize_for_match


CONTEXT_STATUSES = {"known", "inferred", "not_applicable", "unknown"}
NAME_CONTEXT = re.compile(r"(?i)(?:^|[-_])(\d+(?:\.\d+)?)\s*([km])(?:$|[-_])")


def context_from_model_name(model_name: str) -> str:
    match = NAME_CONTEXT.search(model_name or "")
    if not match:
        return ""
    value = float(match.group(1))
    if match.group(2).lower() == "m":
        value *= 1000
    rounded = int(value) if value.is_integer() else value
    return f"{rounded}k"


def _has_context(model: dict[str, Any]) -> bool:
    return model.get("context") not in (None, "", "N/A")


def _is_prior_inference(model: dict[str, Any]) -> bool:
    return model.get("context_status") == "inferred"


def _not_applicable(model: dict[str, Any]) -> bool:
    return (
        model.get("billing_unit") == "request"
        or model.get("price_status") == "non_token"
        or model.get("scene") in {"图片生成", "视频生成"}
    )


def enrich_context_metadata(models: list[dict[str, Any]]) -> Counter[str]:
    """原地补齐可证实的上下文，并返回状态计数。"""

    known_by_name: dict[str, set[str]] = defaultdict(set)
    for model in models:
        # 上一次生成得到的推断值不能反过来成为下一次生成的“目录证据”。
        if _has_context(model) and not _is_prior_inference(model):
            known_by_name[normalize_for_match(str(model.get("name") or ""))].add(str(model["context"]))

    counts: Counter[str] = Counter()
    for model in models:
        prior_inference = _is_prior_inference(model)
        if _has_context(model) and not prior_inference:
            status, source = "known", "catalog"
        elif _not_applicable(model):
            if prior_inference:
                model["context"] = "N/A"
            status, source = "not_applicable", "billing_semantics"
        else:
            from_name = context_from_model_name(str(model.get("name") or ""))
            consensus = known_by_name[normalize_for_match(str(model.get("name") or ""))]
            if from_name:
                model["context"] = from_name
                status, source = "inferred", "model_name"
            elif len(consensus) == 1:
                model["context"] = next(iter(consensus))
                status, source = "inferred", "catalog_consensus"
            else:
                if prior_inference:
                    model["context"] = "N/A"
                status, source = "unknown", "unknown"
        model["context_status"] = status
        model["context_source"] = source
        counts[status] += 1
    return counts


def restore_inferred_context_metadata(
    models: list[dict[str, Any]],
    prior_models: list[dict[str, Any]],
) -> None:
    """在缓存重渲染时恢复推断来源，防止其被误认作目录原始值。"""

    prior_inferences = {
        (str(model.get("platform_id") or ""), str(model.get("name") or "")): model
        for model in prior_models
        if _is_prior_inference(model) and _has_context(model)
    }
    for model in models:
        prior = prior_inferences.get((
            str(model.get("platform_id") or ""),
            str(model.get("name") or ""),
        ))
        if prior and model.get("context") == prior.get("context"):
            model["context_status"] = "inferred"
            model["context_source"] = str(prior.get("context_source") or "unknown")
