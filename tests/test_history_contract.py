from copy import deepcopy

from src.history import build_catalog_diff, price_events_from_diff, summarize_history, update_price_history
from src.models.contract import enrich_model_contract


def model(price=1.0):
    return enrich_model_contract({
        "platform_id": "demo", "name": "demo-v1", "family": "Demo",
        "input_price": price, "output_price": price * 2, "cache_input_price": None,
        "currency": "CNY", "price_unit": "per_token", "price_status": "priced",
        "price_src": "DB", "price_source_url": "https://example.com/pricing",
        "model_source": "api", "source_url": "https://example.com/models",
        "collected_at": "2026-08-30T00:00:00+00:00", "price_effective_at": None,
        "context": "32k", "context_status": "known", "context_source": "catalog", "tags": [],
    })


def catalog(item):
    return {"meta": {"schema_version": "2.0.0", "updated_at": "2026-08-30 00:00"}, "models": [item]}


def test_diff_and_history_record_real_price_change_once():
    before, after = catalog(model(1)), catalog(model(2))
    diff = build_catalog_diff(before, after, discovered_at="2026-08-30T01:00:00+00:00")
    assert diff["summary"]["changed"] == 1
    assert diff["summary"]["field_changes"]["input_price"] == 1
    events = price_events_from_diff(diff, after)
    history = update_price_history(None, events)
    repeated = update_price_history(history, events)
    assert len(history["events"]) == len(repeated["events"]) == 1
    assert history["events"][0]["before"]["input_price"] == 1
    assert history["events"][0]["after"]["input_price"] == 2
    assert summarize_history(history)["periods"]["day"]["event_counts"] == {"2026-08-30": 1}


def test_context_only_change_does_not_create_price_event():
    old = model(1)
    new = deepcopy(old)
    new["context"] = "128k"
    diff = build_catalog_diff(catalog(old), catalog(new), discovered_at="2026-08-30T01:00:00+00:00")
    assert diff["changes"][0]["fields"] == ["context"]
    assert price_events_from_diff(diff, catalog(new)) == []
