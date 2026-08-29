from copy import deepcopy

from src.history import build_catalog_diff, update_lifecycle_archive
from src.quality import assess_catalog_risk
from tests.test_history_contract import catalog, model


def test_unchanged_catalog_passes_risk_gate():
    data = catalog(model())
    report = assess_catalog_risk(data, deepcopy(data), build_catalog_diff(data, data))
    assert report["status"] == "passed"
    assert report["high_risk"] == []


def test_large_catalog_drop_is_blocked_and_archived():
    before = {"meta": {}, "models": [model(), {**model(), "name": "second"}]}
    # Re-enrich the copied second record to assign its own stable identity.
    from src.models.contract import enrich_model_contract
    before["models"][1] = enrich_model_contract(before["models"][1])
    after = {"meta": {}, "models": [before["models"][0]]}
    diff = build_catalog_diff(before, after, discovered_at="2026-08-30T02:00:00+00:00")
    report = assess_catalog_risk(before, after, diff, policy={"max_removed_offerings": 0})
    assert report["status"] == "blocked"
    assert {risk["code"] for risk in report["high_risk"]} >= {"model_count_drop", "removed_offerings"}
    archive = update_lifecycle_archive(None, before, after, diff)
    assert archive["offerings"][0]["status"] == "retired"
    assert archive["offerings"][0]["last_known"]["price_source_url"]


def test_price_change_burst_is_blocked():
    old_models, new_models = [], []
    from src.models.contract import enrich_model_contract
    for index in range(3):
        old = model(1)
        old["name"] = f"model-{index}"
        new = deepcopy(old)
        new["input_price"] = 3
        old_models.append(enrich_model_contract(old))
        new_models.append(enrich_model_contract(new))
    before, after = {"meta": {}, "models": old_models}, {"meta": {}, "models": new_models}
    report = assess_catalog_risk(before, after, build_catalog_diff(before, after), policy={"max_large_price_changes": 1})
    assert report["status"] == "blocked"
    assert any(risk["code"] == "large_price_change_burst" for risk in report["high_risk"])
