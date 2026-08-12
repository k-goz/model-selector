"""生产平台目录抓取器测试。"""

from datetime import datetime

from src.platforms import (
    AiHubMixPlatform,
    AliyunPlatform,
    ChatAnywherePlatform,
    DeepSeekPlatform,
    MiniMaxPlatform,
    N1NPlatform,
    SiliconFlowPlatform,
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
