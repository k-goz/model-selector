from src.publication import build_catalog


CARD = '''
<div class="mc" data-s="日常对话" data-p="deepseek" data-pt="mid"
 data-inp="3.0" data-out="9.0" data-cur="CNY" data-ctx-display="128k"
 data-pu="per_token" data-src="S" data-inp-display="¥1.50–3.00/M"
 data-out-display="¥4.50–9.00/M" data-pricing-note="时段价"
 data-price-status="priced" data-billing-unit="token" data-family="DeepSeek">
 <div class="prov">DeepSeek</div><div class="mname">deepseek-v4-flash</div>
 <div class="tags"><span class="tg tg-hot">旗舰</span></div>
 <div class="base-url">https://api.deepseek.com/v1/chat/completions</div>
</div>
'''


def test_build_catalog_preserves_semantics_and_lineage():
    source_runs = {
        "deepseek": {
            "platform_id": "deepseek",
            "source_type": "api",
            "source_url": "https://api.deepseek.com/v1/models",
            "collected_at": "2026-08-30T00:00:00+00:00",
            "model_count": 1,
            "error": "",
        }
    }
    catalog = build_catalog(
        cards=[CARD],
        updated_at="2026-08-30 00:00",
        source_runs=source_runs,
        price_changes=[],
        use_json_data=False,
        official_prices={
            "deepseek-v4-flash": {
                "source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing"
            }
        },
        official_prices_db={},
        prior_context_models=[],
    )
    model = catalog["models"][0]
    assert model["name"] == "deepseek-v4-flash"
    assert model["input_price"] == 3.0
    assert model["pricing_note"] == "时段价"
    assert model["model_source"] == "api"
    assert model["price_source_url"].startswith("https://api-docs.deepseek.com/")
    assert catalog["meta"]["price_status_counts"] == {"priced": 1}
    assert catalog["meta"]["lineage_counts"] == {"api": 1}
