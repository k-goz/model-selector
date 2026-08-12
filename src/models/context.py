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
        if _has_context(model):
            known_by_name[normalize_for_match(str(model.get("name") or ""))].add(str(model["context"]))

    counts: Counter[str] = Counter()
    for model in models:
        if _has_context(model):
            status, source = "known", "catalog"
        elif _not_applicable(model):
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
                status, source = "unknown", "unknown"
        model["context_status"] = status
        model["context_source"] = source
        counts[status] += 1
    return counts
