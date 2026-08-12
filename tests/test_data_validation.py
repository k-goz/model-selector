"""发布数据门禁测试。"""

from datetime import datetime

from validate_data import validate_models, validate_price_db


def valid_model(**overrides):
    model = {
        "platform_id": "demo",
        "name": "demo-model",
        "input_price": 1.0,
        "output_price": 2.0,
        "currency": "CNY",
        "price_status": "priced",
        "billing_unit": "token",
        "price_src": "DB",
        "price_source_url": "https://example.com/pricing",
        "base_url": "https://example.com/v1/chat/completions",
        "model_source": "api",
        "source_url": "https://example.com/v1/models",
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "context": "32k",
        "tags": [],
    }
    model.update(overrides)
    return model


def model_document(models):
    counts = {}
    for model in models:
        status = model["price_status"]
        counts[status] = counts.get(status, 0) + 1
    return {
        "meta": {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_models": len(models),
            "price_status_counts": counts,
            "lineage_counts": {"api": len(models)},
            "source_runs": {
                "demo": {
                    "platform_id": "demo",
                    "source_type": "api",
                    "source_url": "https://example.com/v1/models",
                    "collected_at": datetime.now().isoformat(timespec="seconds"),
                    "model_count": len(models),
                    "error": "",
                }
            },
        },
        "models": models,
    }


def test_valid_published_data():
    errors, _ = validate_models(model_document([valid_model()]), max_age_hours=2)
    assert errors == []


def test_priced_model_requires_positive_price():
    data = model_document([valid_model(input_price=0, output_price=0)])
    errors, _ = validate_models(data, max_age_hours=2)
    assert any("priced 状态却没有正价格" in error for error in errors)


def test_duplicate_platform_model_is_rejected():
    data = model_document([valid_model(), valid_model()])
    errors, _ = validate_models(data, max_age_hours=2)
    assert any("重复平台模型" in error for error in errors)


def test_flat_ssot_record_is_rejected():
    data = {
        "_meta": {},
        "demo": {"_source": "https://example.com", "_currency": "CNY", "model": {"input": 1, "output": 2}},
        "orphan-model": {"input_price": 1, "output_price": 2},
    }
    errors, _ = validate_price_db(data)
    assert any("orphan-model" in error for error in errors)


def test_model_lineage_requires_matching_source_run():
    data = model_document([valid_model()])
    data["meta"]["source_runs"]["demo"]["model_count"] = 2
    errors, _ = validate_models(data, max_age_hours=2)
    assert any("source_runs.model_count" in error for error in errors)


def test_api_lineage_requires_source_url():
    data = model_document([valid_model(source_url="")])
    errors, _ = validate_models(data, max_age_hours=2)
    assert any("api 模型缺少 source_url" in error for error in errors)


def test_evidenced_price_requires_source_url():
    data = model_document([valid_model(price_source_url="")])
    errors, _ = validate_models(data, max_age_hours=2)
    assert any("价格来源标签" in error for error in errors)
