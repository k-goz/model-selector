"""生产平台目录抓取器测试。"""

from datetime import datetime

from src.platforms import (
    AiHubMixPlatform,
    AliyunPlatform,
    BaichuanPlatform,
    ChatAnywherePlatform,
    CoherePlatform,
    DeepInfraPlatform,
    DeepSeekPlatform,
    FireworksPlatform,
    GroqPlatform,
    InfiniPlatform,
    JieyuePlatform,
    MiniMaxPlatform,
    MoonshotPlatform,
    N1NPlatform,
    NovitaPlatform,
    OpenRouterPlatform,
    SiliconFlowPlatform,
    SparkPlatform,
    TencentPlatform,
    TogetherPlatform,
    VolcenginePlatform,
    ZhipuPlatform,
    YiPlatform,
    parse_chatanywhere_pricing_html,
)


def test_aliyun_normalizes_api_model_and_records_lineage():
    calls = []

    def fetcher(url, api_key):
        calls.append((url, api_key))
        return {
            "output": {
                "total": 1,
                "models": [{
                    "name": "qwen-test",
                    "prices": [{"prices": [
                        {"type": "input_token", "price": "0.8"},
                        {"type": "output_token", "price": "2"},
                    ]}],
                    "model_info": {"context_window": 128000},
                    "capabilities": ["Reasoning", "VU"],
                }],
            }
        }

    result = AliyunPlatform(api_key="secret", json_fetcher=fetcher).fetch_result()
    assert calls[0][1] == "secret"
    assert result.metadata.source_type == "api"
    assert result.metadata.model_count == 1
    assert result.models[0] == {
        "id": "qwen-test",
        "name": "qwen-test",
        "input_price": 0.8,
        "output_price": 2.0,
        "context": "128k",
        "tags": ["推理", "视觉"],
        "scene": "视觉图片",
    }
    datetime.fromisoformat(result.metadata.collected_at)


def test_aliyun_without_key_uses_explicit_fallback():
    result = AliyunPlatform().fetch_result()
    assert result.metadata.source_type == "fallback"
    assert "API Key 未配置" in result.metadata.error
    assert any(model["id"] == "qwen-max" for model in result.models)


def test_minimax_uses_openai_compatible_model_list():
    payload = {"data": [{"id": "MiniMax-M2.7"}, {"id": ""}, "invalid"]}
    result = MiniMaxPlatform(api_key="secret", json_fetcher=lambda _url, _key: payload).fetch_result()
    assert result.metadata.source_type == "api"
    assert result.metadata.source_url == "https://api.minimax.chat/v1/models"
    assert result.models == [{"id": "MiniMax-M2.7", "name": "MiniMax-M2.7"}]


def test_deepseek_without_key_uses_current_fallback_models():
    result = DeepSeekPlatform().fetch_result()
    assert result.metadata.source_type == "fallback"
    assert [model["id"] for model in result.models] == ["deepseek-v4-flash", "deepseek-v4-pro"]


def test_moonshot_preserves_api_context_and_records_lineage():
    payload = {"data": [{"id": "kimi-test", "context_length": 262144}]}
    result = MoonshotPlatform(
        api_key="secret", json_fetcher=lambda _url, _key: payload,
    ).fetch_result()
    assert result.metadata.source_type == "api"
    assert result.metadata.source_url == "https://api.moonshot.cn/v1/models"
    assert result.models == [{
        "id": "kimi-test", "name": "kimi-test",
        "context_tokens": 262144, "context": "262k",
    }]


def test_moonshot_fallback_excludes_officially_retired_models():
    result = MoonshotPlatform().fetch_result()
    assert result.metadata.source_type == "fallback"
    assert [model["id"] for model in result.models] == [
        "kimi-k2.6",
        "kimi-k2.7-code",
        "kimi-k2.7-code-highspeed",
        "kimi-k3",
    ]


def test_zhipu_and_groq_use_openai_compatible_catalogs():
    payload = {"data": [{"id": "model-a"}, {"id": ""}]}
    zhipu = ZhipuPlatform(
        api_key="secret", json_fetcher=lambda _url, _key: payload,
    ).fetch_result()
    groq = GroqPlatform(
        api_key="secret", json_fetcher=lambda _url, _key: payload,
    ).fetch_result()
    assert zhipu.models == [{"id": "model-a", "name": "model-a"}]
    assert groq.models == [{"id": "model-a", "name": "model-a"}]
    assert zhipu.metadata.source_url == "https://open.bigmodel.cn/api/paas/v4/models"
    assert groq.metadata.source_url == "https://api.groq.com/openai/v1/models"


def test_volcengine_preserves_retirement_status():
    payload = {"data": [
        {"id": "doubao-active", "status": "Active"},
        {"id": "doubao-old", "status": "Retiring"},
    ]}
    result = VolcenginePlatform(
        api_key="secret", json_fetcher=lambda _url, _key: payload,
    ).fetch_result()
    assert result.models == [
        {"id": "doubao-active", "name": "doubao-active", "status": "Active"},
        {"id": "doubao-old", "name": "doubao-old", "status": "Retiring"},
    ]


def test_phase_five_platforms_without_keys_use_explicit_fallbacks():
    for platform in (MoonshotPlatform(), ZhipuPlatform(), VolcenginePlatform(), GroqPlatform()):
        result = platform.fetch_result()
        assert result.metadata.source_type == "fallback"
        assert "API Key 未配置" in result.metadata.error
        assert result.models


def test_fireworks_preserves_context_length():
    payload = {"data": [{"id": "accounts/test/model", "context_length": 131072}]}
    result = FireworksPlatform(
        api_key="secret", json_fetcher=lambda _url, _key: payload,
    ).fetch_result()
    assert result.models == [{
        "id": "accounts/test/model", "name": "accounts/test/model",
        "context_tokens": 131072, "context": "131k",
    }]


def test_cohere_filters_embedding_and_rerank_models():
    payload = {"models": [
        {"name": "command-a"}, {"name": "embed-v4"}, {"name": "rerank-v3"},
    ]}
    result = CoherePlatform(
        api_key="secret", json_fetcher=lambda _url, _key: payload,
    ).fetch_result()
    assert result.models == [{"id": "command-a", "name": "command-a"}]


def test_infini_filters_non_chat_models_and_records_api_source():
    payload = {"data": [
        {"id": "qwen-chat"}, {"id": "bge-reranker"}, {"id": "text-embedding"},
    ]}
    result = InfiniPlatform(
        api_key="secret", json_fetcher=lambda _url, _key: payload,
    ).fetch_result()
    assert result.metadata.source_type == "api"
    assert result.models == [{"id": "qwen-chat", "name": "qwen-chat"}]


def test_phase_six_platforms_without_keys_use_explicit_fallbacks():
    for platform in (FireworksPlatform(), CoherePlatform(), InfiniPlatform()):
        result = platform.fetch_result()
        assert result.metadata.source_type == "fallback"
        assert "API Key 未配置" in result.metadata.error
        assert result.models


def test_remaining_openai_compatible_platforms_normalize_model_ids():
    payload = {"data": [{"id": "chat-model"}, {"id": ""}]}
    platforms = (
        TencentPlatform(api_key="secret", json_fetcher=lambda _url, _key: payload),
        YiPlatform(api_key="secret", json_fetcher=lambda _url, _key: payload),
        BaichuanPlatform(api_key="secret", json_fetcher=lambda _url, _key: payload),
        JieyuePlatform(api_key="secret", json_fetcher=lambda _url, _key: payload),
    )
    for platform in platforms:
        result = platform.fetch_result()
        assert result.metadata.source_type == "api"
        assert result.models == [{"id": "chat-model", "name": "chat-model"}]


def test_spark_uses_documented_static_catalog():
    result = SparkPlatform().fetch_result()
    assert result.metadata.source_type == "fallback"
    assert result.metadata.source_url == "https://www.xfyun.cn/doc/spark/Web.html"
    assert result.metadata.error == "讯飞星火没有公开模型目录 API"
    assert len(result.models) == len(SparkPlatform.FALLBACK_IDS)


def test_phase_seven_keyed_platforms_without_keys_use_explicit_fallbacks():
    for platform in (TencentPlatform(), YiPlatform(), BaichuanPlatform(), JieyuePlatform()):
        result = platform.fetch_result()
        assert result.metadata.source_type == "fallback"
        assert "API Key 未配置" in result.metadata.error
        assert result.models


def test_empty_api_response_records_fallback_reason():
    result = DeepSeekPlatform(
        api_key="secret",
        json_fetcher=lambda _url, _key: {"data": []},
    ).fetch_result()
    assert result.metadata.source_type == "fallback"
    assert result.metadata.error == "API 返回空模型列表"


def test_n1n_parses_public_pricing_and_excludes_non_text_models():
    payload = {"data": [
        {"model_name": "gpt-4o-mini", "quota_type": 0, "model_ratio": 0.075,
         "completion_ratio": 4, "available": True},
        {"model_name": "text-embedding-3", "quota_type": 0, "model_ratio": 0.02,
         "completion_ratio": 1, "available": True},
        {"model_name": "image-model", "quota_type": 1, "model_price": 0.1,
         "completion_ratio": 0, "available": True},
    ]}
    result = N1NPlatform(json_fetcher=lambda _url, _key: payload).fetch_result()
    assert result.metadata.source_type == "api"
    assert result.models == [{
        "id": "gpt-4o-mini",
        "name": "gpt-4o-mini",
        "input_price": 0.075,
        "output_price": 0.3,
        "context": "128k",
    }]


def test_n1n_network_failure_keeps_auditable_fallback_error():
    def failing_fetcher(_url, _key):
        raise RuntimeError("upstream unavailable")

    result = N1NPlatform(json_fetcher=failing_fetcher).fetch_result()
    assert result.metadata.source_type == "fallback"
    assert result.metadata.error == "upstream unavailable"
    assert len(result.models) == len(N1NPlatform.FALLBACK_IDS)


def test_siliconflow_requires_key_and_records_fallback():
    result = SiliconFlowPlatform().fetch_result()
    assert result.metadata.source_type == "fallback"
    assert result.metadata.source_url == "https://api.siliconflow.cn/v1/models"
    assert len(result.models) == len(SiliconFlowPlatform.FALLBACK_IDS)


def test_aihubmix_public_catalog_filters_non_chat_models():
    payload = {"data": [
        {"id": "gpt-4o"},
        {"id": "text-embedding-3-large"},
        {"id": "whisper-1"},
        {"id": ""},
    ]}
    result = AiHubMixPlatform(json_fetcher=lambda _url, _key: payload).fetch_result()
    assert result.metadata.source_type == "api"
    assert result.models == [{"id": "gpt-4o", "name": "gpt-4o"}]


def test_openrouter_normalizes_per_token_prices_and_capabilities(tmp_path):
    payload = {"data": [{
        "id": "vendor/reasoning-vision", "name": "Reasoning Vision",
        "pricing": {"prompt": "0.000001", "completion": "0.000004"},
        "context_length": 128000,
        "architecture": {"input_modalities": ["text", "image"]},
        "reasoning": {"mandatory": True},
    }]}
    cache_path = tmp_path / "openrouter.json"
    result = OpenRouterPlatform(
        cache_path=str(cache_path), json_fetcher=lambda _url, _key: payload,
    ).fetch_result()
    assert result.metadata.source_type == "api"
    assert result.models == [{
        "id": "vendor/reasoning-vision", "name": "Reasoning Vision",
        "input_price": 0.000001, "output_price": 0.000004,
        "context_tokens": 128000, "context": "128k", "vision": True, "reasoning": True,
    }]
    assert cache_path.exists()


def test_openrouter_network_failure_uses_cached_catalog(tmp_path):
    cache_path = tmp_path / "openrouter.json"
    cache_path.write_text('{"data":[{"id":"cached/model","pricing":{"prompt":"0","completion":"0"}}]}')

    def failing_fetcher(_url, _key):
        raise RuntimeError("network unavailable")

    result = OpenRouterPlatform(
        cache_path=str(cache_path), json_fetcher=failing_fetcher,
    ).fetch_result()
    assert result.metadata.source_type == "fallback"
    assert result.metadata.error == "network unavailable"
    assert result.models[0]["id"] == "cached/model"


def test_together_requires_key_and_normalizes_priced_text_models():
    payload = [{
        "id": "vendor/chat-model",
        "pricing": {"input": "0.2", "output": "0.6"},
        "context_length": 131072,
    }, {
        "id": "vendor/unpriced-model",
        "pricing": {"input": 0, "output": 0},
        "context_length": 131072,
    }]
    result = TogetherPlatform(
        api_key="secret", json_fetcher=lambda _url, _key: payload,
    ).fetch_result()
    assert result.metadata.source_type == "api"
    assert result.models == [{
        "id": "vendor/chat-model", "name": "vendor/chat-model",
        "input_price": 0.2, "output_price": 0.6,
        "context_tokens": 131072, "context": "131k",
    }]


def test_together_without_key_records_static_fallback():
    result = TogetherPlatform().fetch_result()
    assert result.metadata.source_type == "fallback"
    assert "API Key 未配置" in result.metadata.error
    assert len(result.models) == len(TogetherPlatform.FALLBACK_IDS)


def test_novita_converts_price_units_and_filters_non_chat_models():
    payload = {"data": [{
        "id": "vendor/chat-model", "display_name": "Chat Model", "model_type": "chat", "status": 1,
        "input_token_price_per_m": 30000, "output_token_price_per_m": 150000,
        "context_size": 1048576,
    }, {
        "id": "vendor/image-model", "model_type": "image", "status": 1,
        "input_token_price_per_m": 30000, "output_token_price_per_m": 150000,
    }]}
    result = NovitaPlatform(json_fetcher=lambda _url, _key: payload).fetch_result()
    assert result.models == [{
        "id": "vendor/chat-model", "name": "Chat Model",
        "input_price": 3.0, "output_price": 15.0,
        "context_tokens": 1048576, "context": "1048k",
    }]


def test_deepinfra_converts_cents_per_token_and_excludes_deprecated_models():
    payload = [{
        "model_name": "vendor/chat-model", "type": "text-generation", "deprecated": None,
        "pricing": {"type": "tokens", "cents_per_input_token": 0.00012,
                    "cents_per_output_token": 0.0006},
        "max_tokens": 256000,
    }, {
        "model_name": "vendor/old-model", "type": "text-generation", "deprecated": 1,
        "pricing": {"type": "tokens", "cents_per_input_token": 0.0001,
                    "cents_per_output_token": 0.0002},
    }, {
        "model_name": "vendor/embed-model", "type": "embeddings", "deprecated": None,
        "pricing": {"type": "tokens", "cents_per_input_token": 0.0001},
    }]
    result = DeepInfraPlatform(json_fetcher=lambda _url, _key: payload).fetch_result()
    assert result.models == [{
        "id": "vendor/chat-model", "name": "vendor/chat-model",
        "input_price": 1.2, "output_price": 6.0,
        "context_tokens": 256000, "context": "256k",
    }]


def test_chatanywhere_parser_uses_rows_and_rejects_tier_ranges():
    document = """
    <table>
      <tr><td>deepseek-v4-flash</td><td>0.0008 / 1K Tokens</td><td>0.0016 / 1K Tokens</td><td>支持</td></tr>
      <tr><td>0 - 272K</td><td>0.001 / 1K Tokens</td><td>0.002 / 1K Tokens</td></tr>
      <tr><td>32K - 128K</td><td>0.001 / 1K Tokens</td><td>0.002 / 1K Tokens</td></tr>
      <tr><td>&gt;512K</td><td>0.001 / 1K Tokens</td><td>0.002 / 1K Tokens</td></tr>
      <tr><td>text-embedding-3</td><td>0.001 / 1K Tokens</td><td>0.001 / 1K Tokens</td></tr>
      <tr><td>o3-mini [5]</td><td>0.0011 / 1K Tokens</td><td>0.0044 / 1K Tokens</td></tr>
    </table>
    """
    assert parse_chatanywhere_pricing_html(document) == [{
        "id": "deepseek-v4-flash",
        "name": "deepseek-v4-flash",
        "input_price": 0.8,
        "output_price": 1.6,
        "context": "128k",
    }, {
        "id": "o3-mini",
        "name": "o3-mini",
        "input_price": 1.1,
        "output_price": 4.4,
        "context": "128k",
    }]


def test_chatanywhere_records_scrape_lineage():
    document = "<tr><td>gpt-4o</td><td>0.002 / 1K</td><td>0.008 / 1K</td></tr>"
    result = ChatAnywherePlatform(text_fetcher=lambda _url: document).fetch_result()
    assert result.metadata.source_type == "scrape"
    assert result.metadata.source_url == "https://chatanywhere.apifox.cn/doc-2694962"
    assert result.models[0]["input_price"] == 2.0
