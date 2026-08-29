from copy import deepcopy

from src.models.contract import canonical_model_key, enrich_catalog_contract, enrich_model_contract


BASE = {
    "platform_id": "demo",
    "name": "deepseek-ai/DeepSeek-Chat",
    "family": "DeepSeek",
    "price_status": "priced",
    "price_src": "A",
    "price_source_url": "https://example.com/pricing",
    "model_source": "api",
    "collected_at": "2026-08-30T00:00:00+00:00",
    "context_status": "known",
    "tags": [],
}


def test_stable_ids_ignore_order_and_known_alias_case():
    first = enrich_model_contract(deepcopy(BASE))
    second = enrich_model_contract(deepcopy({**BASE, "name": "DEEPSEEK/deepseek-chat"}))
    assert first["canonical_model_id"] == second["canonical_model_id"]
    assert first["provider_offering_id"] != second["provider_offering_id"]
    assert canonical_model_key("deepseek-reasoner") == "deepseek-r1"


def test_contract_explains_confidence_and_lifecycle():
    model = enrich_model_contract(deepcopy(BASE))
    assert model["confidence"]["score"] == 0.95
    assert model["confidence"]["grade"] == "high"
    assert len(model["confidence"]["factors"]) >= 3
    assert model["lifecycle"]["status"] == "active"
    assert model["evidence_at"] == BASE["collected_at"]
    assert model["price_effective_at"] is None
    assert model["data_warnings"] == []


def test_provider_offering_id_preserves_case_sensitive_provider_identity():
    lower = enrich_model_contract(deepcopy({**BASE, "name": "cc-minimax-m2"}))
    mixed = enrich_model_contract(deepcopy({**BASE, "name": "cc-MiniMax-M2"}))
    assert lower["canonical_model_id"] == mixed["canonical_model_id"]
    assert lower["provider_offering_id"] != mixed["provider_offering_id"]


def test_unchanged_lifecycle_since_is_preserved_across_refreshes():
    previous = enrich_model_contract(deepcopy(BASE))
    previous["lifecycle"]["since"] = "2026-08-01T00:00:00+00:00"
    refreshed = deepcopy(BASE)
    refreshed["collected_at"] = "2026-08-31T00:00:00+00:00"
    catalog = {"meta": {}, "models": [refreshed]}
    enrich_catalog_contract(catalog, previous_models=[previous])
    assert catalog["models"][0]["lifecycle"]["since"] == "2026-08-01T00:00:00+00:00"
