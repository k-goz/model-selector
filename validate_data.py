#!/usr/bin/env python3
"""发布前数据质量门禁。

验证模型数据的价格语义、必需字段、重复记录和 SSOT 命名空间结构。
任何 error 都会以非零状态退出，阻止错误数据覆盖线上版本。
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys


PRICE_STATUSES = {
    "priced", "free", "free_tier", "non_token", "unknown", "unavailable", "retiring"
}
BILLING_UNITS = {"token", "request", "unknown"}
MODEL_SOURCE_TYPES = {"api", "scrape", "fallback", "legacy_generator", "legacy_snapshot"}
CONTEXT_STATUSES = {"known", "inferred", "not_applicable", "unknown"}
REQUIRED_MODEL_FIELDS = {
    "platform_id", "name", "input_price", "output_price", "currency",
    "price_status", "billing_unit", "price_src", "base_url",
    "price_source_url", "model_source", "source_url", "collected_at",
    "context_status", "context_source", "canonical_model_id",
    "provider_offering_id", "provider_id", "provider_model_name",
    "confidence", "lifecycle", "evidence_at", "data_warnings",
}


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 {path}: {exc}") from exc


def validate_models(
    data: dict,
    max_age_hours: float,
    min_live_ratio: float = 0,
    max_fallback_ratio: float = 1,
    min_models: int = 1,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    meta = data.get("meta", {})
    models = data.get("models")
    if not isinstance(models, list) or not models:
        return ["models_data.json 没有可发布的模型列表"], warnings

    updated_at = meta.get("updated_at", "")
    try:
        updated = datetime.strptime(updated_at, "%Y-%m-%d %H:%M")
        age_hours = (datetime.now() - updated).total_seconds() / 3600
        if age_hours > max_age_hours:
            errors.append(f"数据已过期 {age_hours:.1f} 小时，阈值为 {max_age_hours:.1f} 小时")
    except ValueError:
        errors.append(f"meta.updated_at 格式无效: {updated_at!r}")

    if meta.get("total_models") != len(models):
        errors.append(f"meta.total_models={meta.get('total_models')}，实际为 {len(models)}")
    if len(models) < min_models:
        errors.append(f"模型总数 {len(models)} 低于发布下限 {min_models}")

    seen: Counter[tuple[str, str]] = Counter()
    offering_ids: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    lineage_counts: Counter[str] = Counter()
    platform_counts: Counter[str] = Counter()
    context_status_counts: Counter[str] = Counter()
    missing_price_source_urls = 0
    for index, model in enumerate(models):
        missing = REQUIRED_MODEL_FIELDS - model.keys()
        if missing:
            errors.append(f"models[{index}] 缺少字段: {', '.join(sorted(missing))}")
            continue
        platform = str(model.get("platform_id", "")).strip()
        name = str(model.get("name", "")).strip()
        if not platform or not name:
            errors.append(f"models[{index}] 平台或模型名为空")
        seen[(platform, name)] += 1
        offering_ids[str(model.get("provider_offering_id", ""))] += 1
        platform_counts[platform] += 1
        if model.get("provider_id") != platform or model.get("provider_model_name") != name:
            errors.append(f"{platform}/{name}: provider 身份字段与兼容字段不一致")
        if not str(model.get("canonical_model_id", "")).startswith("model_"):
            errors.append(f"{platform}/{name}: canonical_model_id 无效")

        status = model.get("price_status")
        billing_unit = model.get("billing_unit")
        status_counts[status] += 1
        if status not in PRICE_STATUSES:
            errors.append(f"{platform}/{name}: 非法 price_status={status!r}")
        if billing_unit not in BILLING_UNITS:
            errors.append(f"{platform}/{name}: 非法 billing_unit={billing_unit!r}")

        input_price = float(model.get("input_price") or 0)
        output_price = float(model.get("output_price") or 0)
        has_price = input_price > 0 or output_price > 0
        if status == "priced" and not has_price:
            errors.append(f"{platform}/{name}: priced 状态却没有正价格")
        if status != "priced" and has_price:
            errors.append(f"{platform}/{name}: 有正价格却标记为 {status}")
        if status == "unknown" and ("免费" in model.get("tags", []) or "免费额度" in model.get("tags", [])):
            errors.append(f"{platform}/{name}: 免费标签未转换为明确价格状态")

        model_source = model.get("model_source")
        lineage_counts[model_source] += 1
        if model_source not in MODEL_SOURCE_TYPES:
            errors.append(f"{platform}/{name}: 非法 model_source={model_source!r}")
        if model_source in {"api", "scrape", "fallback"} and not str(model.get("source_url", "")).strip():
            errors.append(f"{platform}/{name}: {model_source} 模型缺少 source_url")
        try:
            datetime.fromisoformat(str(model.get("collected_at", "")))
        except ValueError:
            errors.append(f"{platform}/{name}: collected_at 格式无效")
        if model.get("price_src") in {"A", "S", "SP", "DB", "D", "L", "OR", "P"} and not model.get("price_source_url"):
            missing_price_source_urls += 1
        context_status = model.get("context_status")
        context_status_counts[context_status] += 1
        has_context = model.get("context") not in (None, "", "N/A")
        if context_status not in CONTEXT_STATUSES:
            errors.append(f"{platform}/{name}: 非法 context_status={context_status!r}")
        if context_status in {"known", "inferred"} and not has_context:
            errors.append(f"{platform}/{name}: {context_status} 状态却没有上下文长度")
        if context_status in {"unknown", "not_applicable"} and has_context:
            errors.append(f"{platform}/{name}: {context_status} 状态却包含上下文长度")

    duplicates = [key for key, count in seen.items() if count > 1]
    if duplicates:
        preview = ", ".join(f"{p}/{n}" for p, n in duplicates[:10])
        errors.append(f"存在 {len(duplicates)} 组重复平台模型: {preview}")
    duplicate_offering_ids = [key for key, count in offering_ids.items() if not key or count > 1]
    if duplicate_offering_ids:
        errors.append(f"存在 {len(duplicate_offering_ids)} 个空值或重复 provider_offering_id")

    if meta.get("schema_version") != "2.0.0" or meta.get("identity_version") != "1":
        errors.append("生产目录必须使用 schema_version=2.0.0 和 identity_version=1")

    missing_context = context_status_counts["unknown"]
    if missing_context:
        warnings.append(f"{missing_context} 个模型缺少上下文长度")
    if status_counts["unknown"]:
        warnings.append(f"{status_counts['unknown']} 个模型价格待确认")

    declared_status_counts = meta.get("price_status_counts", {})
    if declared_status_counts != dict(status_counts):
        errors.append("meta.price_status_counts 与实际模型不一致")
    if meta.get("lineage_counts", {}) != dict(lineage_counts):
        errors.append("meta.lineage_counts 与实际模型不一致")
    if meta.get("context_status_counts", {}) != dict(context_status_counts):
        errors.append("meta.context_status_counts 与实际模型不一致")
    if lineage_counts["legacy_generator"]:
        errors.append(f"仍有 {lineage_counts['legacy_generator']} 个模型来自 legacy_generator")
    live_ratio = (lineage_counts["api"] + lineage_counts["scrape"]) / len(models)
    fallback_ratio = lineage_counts["fallback"] / len(models)
    if live_ratio < min_live_ratio:
        errors.append(f"实时来源比例 {live_ratio:.1%} 低于发布下限 {min_live_ratio:.1%}")
    if fallback_ratio > max_fallback_ratio:
        errors.append(f"fallback 比例 {fallback_ratio:.1%} 高于发布上限 {max_fallback_ratio:.1%}")

    source_runs = meta.get("source_runs")
    if not isinstance(source_runs, dict):
        errors.append("meta.source_runs 缺失或格式无效")
    else:
        for platform, count in platform_counts.items():
            run = source_runs.get(platform)
            if not isinstance(run, dict):
                errors.append(f"{platform}: 缺少 source_runs 记录")
                continue
            if run.get("source_type") not in MODEL_SOURCE_TYPES:
                errors.append(f"{platform}: source_runs.source_type 无效")
            if run.get("model_count") != count:
                errors.append(f"{platform}: source_runs.model_count={run.get('model_count')}，实际为 {count}")
    if missing_price_source_urls:
        errors.append(f"{missing_price_source_urls} 个有价格来源标签的模型缺少来源 URL")
    return errors, warnings


def validate_price_db(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    platforms = 0
    for key, value in data.items():
        if key == "_meta":
            continue
        if not isinstance(value, dict) or "_source" not in value or "_currency" not in value:
            errors.append(f"SSOT 根节点 {key!r} 不是合法平台命名空间")
            continue
        platforms += 1
        for model_name, price in value.items():
            if model_name.startswith("_"):
                continue
            if not isinstance(price, dict) or "input" not in price or "output" not in price:
                errors.append(f"SSOT {key}/{model_name} 缺少 input/output")
    if platforms == 0:
        errors.append("SSOT 中没有合法平台")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, default=Path("models_data.json"))
    parser.add_argument("--prices", type=Path, default=Path("official_prices_db.json"))
    parser.add_argument("--max-age-hours", type=float, default=48)
    parser.add_argument("--min-live-ratio", type=float, default=0)
    parser.add_argument("--max-fallback-ratio", type=float, default=1)
    parser.add_argument("--min-models", type=int, default=1)
    args = parser.parse_args()

    try:
        model_errors, model_warnings = validate_models(
            load_json(args.models),
            args.max_age_hours,
            min_live_ratio=args.min_live_ratio,
            max_fallback_ratio=args.max_fallback_ratio,
            min_models=args.min_models,
        )
        price_errors, price_warnings = validate_price_db(load_json(args.prices))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = model_errors + price_errors
    warnings = model_warnings + price_warnings
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"Data quality: {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
