"""Build and write the public catalog artifact from normalized model cards."""

from __future__ import annotations

from datetime import datetime
import html
import json
import logging
from pathlib import Path
import re
from typing import Any, Iterable

from src.models.context import enrich_context_metadata, restore_inferred_context_metadata
from src.models.contract import enrich_catalog_contract
from src.pricing import resolve_price_source_url


logger = logging.getLogger(__name__)

PLATFORM_INFO = {
    "aliyun": {"name": "阿里百炼", "color": "#ff6a00"},
    "siliconflow": {"name": "硅基流动", "color": "#7C3AED"},
    "moonshot": {"name": "月之暗面", "color": "#4f46e5"},
    "zhipu": {"name": "智谱 AI", "color": "#00c4b4"},
    "volcengine": {"name": "火山引擎", "color": "#dc2626"},
    "baidu": {"name": "百度文心", "color": "#2932e1"},
    "tencent": {"name": "腾讯混元", "color": "#07c160"},
    "spark": {"name": "讯飞星火", "color": "#ff6347"},
    "minimax": {"name": "MiniMax", "color": "#2563eb"},
    "yi": {"name": "零一万物", "color": "#8b5cf6"},
    "baichuan": {"name": "百川智能", "color": "#16a34a"},
    "jieyue": {"name": "阶跃星辰", "color": "#ea580c"},
    "deepseek": {"name": "DeepSeek", "color": "#0ea5e9"},
    "openrouter": {"name": "OpenRouter", "color": "#6366f1"},
    "groq": {"name": "Groq", "color": "#f97316"},
    "together": {"name": "Together AI", "color": "#06b6d4"},
    "fireworks": {"name": "Fireworks AI", "color": "#ef4444"},
    "cohere": {"name": "Cohere", "color": "#d946ef"},
    "infini": {"name": "无问芯穹", "color": "#84cc16"},
    "novita": {"name": "Novita AI", "color": "#f472b6"},
    "deepinfra": {"name": "DeepInfra", "color": "#a78bfa"},
    "aihubmix": {"name": "AiHubMix", "color": "#fb923c"},
    "n1n": {"name": "n1n.ai", "color": "#22d3ee"},
    "ca": {"name": "ChatAnywhere", "color": "#fbbf24"},
}


def _match(pattern: str, card: str):
    return re.search(pattern, card)


def _price_source_url(
    platform_id: str,
    model_name: str,
    source_tag: str,
    source_run: dict[str, Any],
    official_prices: dict[str, Any],
    official_prices_db: dict[str, Any],
) -> str:
    official_price_url = ""
    if source_tag in {"S", "SP"}:
        for candidate in (model_name.lower(), "sf:" + model_name.lower()):
            price = official_prices.get(candidate)
            if price and price.get("source"):
                official_price_url = price["source"]
                break
    return resolve_price_source_url(
        platform_id,
        source_tag,
        source_run_url=source_run.get("source_url", ""),
        database_url=(official_prices_db.get(platform_id) or {}).get("_source", ""),
        official_price_url=official_price_url,
    )


def build_catalog(
    cards: Iterable[str],
    updated_at: str,
    source_runs: dict[str, dict[str, Any]],
    price_changes: list[dict[str, Any]],
    use_json_data: bool,
    official_prices: dict[str, Any],
    official_prices_db: dict[str, Any],
    prior_context_models: list[dict[str, Any]],
) -> dict[str, Any]:
    cards = list(cards)
    catalog = {
        "meta": {
            "updated_at": updated_at,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_models": len(cards),
            "platform_counts": {},
            "price_tiers": {},
            "price_status_counts": {},
            "lineage_counts": {},
            "source_runs": source_runs,
            "price_changes": price_changes,
        },
        "platforms": PLATFORM_INFO,
        "models": [],
    }
    platform_counts: dict[str, int] = {}
    price_tiers: dict[str, int] = {}
    price_status_counts: dict[str, int] = {}
    lineage_counts: dict[str, int] = {}
    for card in cards:
        platform_match = _match(r'data-p="([^"]*)"', card)
        model_match = _match(r'class="mname">([^<]*)', card)
        if not platform_match or not model_match or not model_match.group(1).strip():
            logger.warning("跳过无法序列化的空模型卡片")
            continue
        platform_id = platform_match.group(1)
        if platform_id not in source_runs:
            source_runs[platform_id] = {
                "platform_id": platform_id,
                "source_type": "legacy_snapshot" if use_json_data else "legacy_generator",
                "source_url": "",
                "collected_at": updated_at,
                "model_count": 0,
                "error": "",
            }
        source_run = source_runs[platform_id]
        source_run["model_count"] = source_run.get("model_count") or 0
        model_source = source_run.get("source_type", "legacy_generator")
        platform_counts[platform_id] = platform_counts.get(platform_id, 0) + 1
        lineage_counts[model_source] = lineage_counts.get(model_source, 0) + 1

        fields = {
            "context": _match(r'data-ctx-display="([^"]*)"', card),
            "input": _match(r'data-inp="([^"]*)"', card),
            "output": _match(r'data-out="([^"]*)"', card),
            "currency": _match(r'data-cur="([^"]*)"', card),
            "scene": _match(r'data-s="([^"]*)"', card),
            "family": _match(r'data-family="([^"]*)"', card),
            "price_unit": _match(r'data-pu="([^"]*)"', card),
            "price_tier": _match(r'data-pt="([^"]*)"', card),
            "price_src": _match(r'data-src="([^"]*)"', card),
            "input_display": _match(r'data-inp-display="([^"]*)"', card),
            "output_display": _match(r'data-out-display="([^"]*)"', card),
            "pricing_note": _match(r'data-pricing-note="([^"]*)"', card),
            "price_status": _match(r'data-price-status="([^"]*)"', card),
            "billing_unit": _match(r'data-billing-unit="([^"]*)"', card),
            "provider": _match(r'class="prov">([^<]*)', card),
            "base_url": _match(r'class="base-url">([^<]*)', card),
        }
        if fields["price_tier"]:
            tier = fields["price_tier"].group(1)
            price_tiers[tier] = price_tiers.get(tier, 0) + 1
        if fields["price_status"]:
            status = fields["price_status"].group(1)
            price_status_counts[status] = price_status_counts.get(status, 0) + 1
        model_name = html.unescape(model_match.group(1))
        source_tag = fields["price_src"].group(1) if fields["price_src"] else ""
        catalog["models"].append({
            "platform_id": platform_id,
            "platform_name": html.unescape(fields["provider"].group(1)) if fields["provider"] else "",
            "platform_color": PLATFORM_INFO.get(platform_id, {}).get("color", ""),
            "name": model_name,
            "input_price": float(fields["input"].group(1)) if fields["input"] else 0,
            "output_price": float(fields["output"].group(1)) if fields["output"] else 0,
            "input_price_display": html.unescape(fields["input_display"].group(1)) if fields["input_display"] else "",
            "output_price_display": html.unescape(fields["output_display"].group(1)) if fields["output_display"] else "",
            "pricing_note": html.unescape(fields["pricing_note"].group(1)) if fields["pricing_note"] else "",
            "currency": fields["currency"].group(1) if fields["currency"] else "CNY",
            "price_unit": fields["price_unit"].group(1) if fields["price_unit"] else "per_token",
            "context": fields["context"].group(1) if fields["context"] else "",
            "tags": re.findall(r'class="tg[^"]*">([^<]*)', card),
            "scene": fields["scene"].group(1) if fields["scene"] else "",
            "family": fields["family"].group(1) if fields["family"] else "",
            "base_url": html.unescape(fields["base_url"].group(1)) if fields["base_url"] else "",
            "price_src": source_tag,
            "price_source_url": _price_source_url(platform_id, model_name, source_tag, source_run, official_prices, official_prices_db),
            "price_status": fields["price_status"].group(1) if fields["price_status"] else "unknown",
            "billing_unit": fields["billing_unit"].group(1) if fields["billing_unit"] else "unknown",
            "model_source": model_source,
            "source_url": source_run.get("source_url", ""),
            "collected_at": source_run.get("collected_at", updated_at),
        })
    catalog["meta"]["platform_counts"] = platform_counts
    catalog["meta"]["price_tiers"] = price_tiers
    catalog["meta"]["price_status_counts"] = price_status_counts
    catalog["meta"]["lineage_counts"] = lineage_counts
    restore_inferred_context_metadata(catalog["models"], prior_context_models)
    catalog["meta"]["context_status_counts"] = dict(enrich_context_metadata(catalog["models"]))
    for platform_id, count in platform_counts.items():
        source_run = source_runs.get(platform_id, {})
        if source_run.get("source_type", "").startswith("legacy_"):
            source_run["model_count"] = count
    return enrich_catalog_contract(catalog)


def write_catalog(path: Path, catalog: dict[str, Any]) -> None:
    path.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
