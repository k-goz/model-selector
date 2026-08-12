from src.models.context import (
    context_from_model_name,
    enrich_context_metadata,
    restore_inferred_context_metadata,
)


def model(name, context="N/A", **overrides):
    value = {
        "name": name,
        "context": context,
        "billing_unit": "token",
        "price_status": "priced",
        "scene": "日常对话",
    }
    value.update(overrides)
    return value


def test_context_from_model_name_supports_k_and_m_units():
    assert context_from_model_name("moonshot-v1-128k-preview") == "128k"
    assert context_from_model_name("vendor-model-1m") == "1000k"
    assert context_from_model_name("qwen3-32b") == ""


def test_enrichment_uses_name_and_unique_catalog_consensus():
    models = [
        model("vendor/chat-128k"),
        model("vendor/shared", "64k"),
        model("other/shared"),
    ]
    counts = enrich_context_metadata(models)
    assert models[0]["context"] == "128k"
    assert models[0]["context_source"] == "model_name"
    assert models[2]["context"] == "64k"
    assert models[2]["context_source"] == "catalog_consensus"
    assert counts["inferred"] == 2


def test_non_token_models_are_not_reported_as_missing_context():
    models = [model("image-model", price_status="non_token", billing_unit="request")]
    counts = enrich_context_metadata(models)
    assert models[0]["context_status"] == "not_applicable"
    assert counts["unknown"] == 0


def test_conflicting_catalog_context_stays_unknown():
    models = [
        model("vendor/shared", "32k"),
        model("other/shared", "128k"),
        model("third/shared"),
    ]
    enrich_context_metadata(models)
    assert models[2]["context_status"] == "unknown"


def test_enrichment_is_idempotent_and_keeps_inference_auditable():
    models = [
        model("vendor/shared", "64k"),
        model("other/shared"),
        model("vendor/chat-128k"),
    ]
    first_counts = enrich_context_metadata(models)
    first_snapshot = [item.copy() for item in models]
    second_counts = enrich_context_metadata(models)
    assert models == first_snapshot
    assert second_counts == first_counts
    assert second_counts == {"known": 1, "inferred": 2}


def test_cached_render_restores_only_unchanged_inferred_contexts():
    prior = [dict(
        model("shared", "64k"),
        platform_id="demo",
        context_status="inferred",
        context_source="catalog_consensus",
    )]
    current = [dict(model("shared", "64k"), platform_id="demo")]
    changed = [dict(model("shared", "128k"), platform_id="demo")]
    restore_inferred_context_metadata(current, prior)
    restore_inferred_context_metadata(changed, prior)
    assert current[0]["context_status"] == "inferred"
    assert current[0]["context_source"] == "catalog_consensus"
    assert "context_status" not in changed[0]
