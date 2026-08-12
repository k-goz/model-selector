"""价格证据 URL 注册与解析。"""

from __future__ import annotations

from typing import Mapping


COMMUNITY_PRICE_SOURCE = (
    "https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json"
)
OPENROUTER_PRICE_SOURCE = "https://openrouter.ai/api/v1/models"

# 这些地址本身返回价格，或是平台维护的官方价格说明页。
PLATFORM_PRICE_SOURCES: Mapping[str, str] = {
    "aliyun": "https://dashscope.aliyuncs.com/api/v1/models",
    "openrouter": OPENROUTER_PRICE_SOURCE,
    "together": "https://api.together.xyz/v1/models",
    "novita": "https://api.novita.ai/v3/openai/models",
    "deepinfra": "https://api.deepinfra.com/models/list",
    "n1n": "https://api.n1n.ai/api/pricing",
    "ca": "https://chatanywhere.apifox.cn/doc-2694962",
}


def resolve_price_source_url(
    platform_id: str,
    source_tag: str,
    *,
    source_run_url: str = "",
    database_url: str = "",
    official_price_url: str = "",
) -> str:
    """按最具体证据优先返回价格来源 URL。"""

    if source_tag in {"S", "SP"} and official_price_url:
        return official_price_url
    if source_tag in {"DB", "D"} and database_url:
        return database_url
    if source_tag == "L":
        return COMMUNITY_PRICE_SOURCE
    if source_tag == "OR":
        return OPENROUTER_PRICE_SOURCE
    if source_tag in {"A", "P"} and source_run_url:
        return source_run_url
    if source_tag in {"A", "P", "S", "SP", "DB", "D", "OR"}:
        return PLATFORM_PRICE_SOURCES.get(platform_id, "")
    return ""
