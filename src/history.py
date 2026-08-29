"""稳定 offering 维度的目录差异与轻量价格历史。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

DIFF_FIELDS = (
    "input_price", "output_price", "cache_input_price", "currency", "price_unit",
    "price_status", "context", "context_status", "price_src", "price_source_url",
    "model_source", "confidence", "canonical_model_id", "lifecycle",
)
PRICE_FIELDS = {"input_price", "output_price", "cache_input_price", "currency", "price_unit", "price_status"}
MAX_HISTORY_EVENTS = 5000


def upsert_daily_history(
    history: List[Dict[str, Any]],
    entry: Dict[str, Any],
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """按日期替换当天测速数据，保留最近 ``limit`` 个不同日期。"""
    by_date: Dict[str, Dict[str, Any]] = {}
    for item in history:
        if not isinstance(item, dict):
            continue
        date = str(item.get("date") or "").strip()
        if date:
            by_date[date] = item
    date = str(entry.get("date") or "").strip()
    if not date:
        raise ValueError("history entry 缺少 date")
    by_date[date] = entry
    return list(by_date.values())[-limit:]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(model["provider_offering_id"]): model
        for model in catalog.get("models", [])
        if model.get("provider_offering_id")
    }


def _identity(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_offering_id": model["provider_offering_id"],
        "canonical_model_id": model["canonical_model_id"],
        "provider_id": model["provider_id"],
        "provider_model_name": model["provider_model_name"],
    }


def build_catalog_diff(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    discovered_at: str | None = None,
) -> dict[str, Any]:
    old_index = _index(before)
    new_index = _index(after)
    old_ids, new_ids = set(old_index), set(new_index)
    changes: list[dict[str, Any]] = []
    field_counts: Counter[str] = Counter()
    for offering_id in sorted(old_ids & new_ids):
        old, new = old_index[offering_id], new_index[offering_id]
        changed_fields = [field for field in DIFF_FIELDS if old.get(field) != new.get(field)]
        if not changed_fields:
            continue
        field_counts.update(changed_fields)
        changes.append(
            {
                **_identity(new),
                "fields": changed_fields,
                "before": {field: old.get(field) for field in changed_fields},
                "after": {field: new.get(field) for field in changed_fields},
            }
        )
    added = [_identity(new_index[key]) for key in sorted(new_ids - old_ids)]
    removed = [_identity(old_index[key]) for key in sorted(old_ids - new_ids)]
    timestamp = discovered_at or _now_iso()
    return {
        "format_version": "2.0",
        "schema_version": after.get("meta", {}).get("schema_version"),
        "discovered_at": timestamp,
        "baseline_updated_at": before.get("meta", {}).get("updated_at"),
        "candidate_updated_at": after.get("meta", {}).get("updated_at"),
        "summary": {
            "before_models": len(old_index),
            "after_models": len(new_index),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changes),
            "field_changes": dict(sorted(field_counts.items())),
        },
        "added": added,
        "removed": removed,
        "changes": changes,
    }


def _event_key(event: dict[str, Any]) -> str:
    payload = {
        "provider_offering_id": event["provider_offering_id"],
        "before": event["before"],
        "after": event["after"],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def price_events_from_diff(
    diff: dict[str, Any],
    after: dict[str, Any],
) -> list[dict[str, Any]]:
    after_index = _index(after)
    events: list[dict[str, Any]] = []
    for change in diff.get("changes", []):
        fields = [field for field in change["fields"] if field in PRICE_FIELDS]
        if not fields:
            continue
        model = after_index[change["provider_offering_id"]]
        events.append(
            {
                **_identity(model),
                "event_type": "price_change",
                "fields": fields,
                "before": {field: change["before"].get(field) for field in fields},
                "after": {field: change["after"].get(field) for field in fields},
                "effective_at": model.get("price_effective_at") or diff["discovered_at"],
                "discovered_at": diff["discovered_at"],
                "evidence": {
                    "url": model.get("price_source_url", ""),
                    "evidence_at": model.get("evidence_at"),
                    "confidence": model.get("confidence"),
                },
            }
        )
    return events


def update_price_history(
    existing: dict[str, Any] | None,
    events: Iterable[dict[str, Any]],
    *,
    max_events: int = MAX_HISTORY_EVENTS,
) -> dict[str, Any]:
    history = dict(existing or {"format_version": "1.0", "events": []})
    stored = list(history.get("events", []))
    known = {_event_key(event) for event in stored}
    for event in events:
        key = _event_key(event)
        if key not in known:
            stored.append(event)
            known.add(key)
    history["format_version"] = "1.0"
    history["updated_at"] = stored[-1]["discovered_at"] if stored else history.get("updated_at")
    history["retention"] = {"max_events": max_events, "strategy": "latest-events"}
    history["events"] = stored[-max_events:]
    return history


def summarize_history(history: dict[str, Any]) -> dict[str, Any]:
    events = history.get("events", [])
    periods: dict[str, dict[str, Any]] = {}
    for period, length in (("day", 10), ("week", 7), ("month", 7)):
        counts: Counter[str] = Counter()
        for event in events:
            stamp = str(event.get("discovered_at", ""))
            if period == "day": key = stamp[:length]
            elif period == "week":
                try: key = datetime.fromisoformat(stamp).date().strftime("%G-W%V")
                except ValueError: key = "unknown"
            else: key = stamp[:length]
            counts[key] += 1
        periods[period] = {"event_counts": dict(sorted(counts.items()))}
    return {"format_version": "1.0", "generated_at": history.get("updated_at"), "periods": periods}


def write_history_artifacts(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    history_path: Path,
    diff_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    diff = build_catalog_diff(before, after)
    existing = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else None
    history = update_price_history(existing, price_events_from_diff(diff, after))
    summary = summarize_history(history)
    for path, payload in ((history_path, history), (diff_path, diff), (summary_path, summary)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return diff
