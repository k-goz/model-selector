"""价格证据 URL 注册与解析。"""

from __future__ import annotations

from typing import Mapping
import html
import re


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


def parse_moonshot_pricing_markdown(content: str) -> dict[str, dict[str, float | str]]:
    """从 Moonshot 官方 Markdown 表格中严格解析逐模型输入/输出价格。"""

    prices: dict[str, dict[str, float | str]] = {}
    for line in content.splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith('["moonshot-'):
            continue
        fields = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line)
        if len(fields) < 4:
            continue
        input_match = re.fullmatch(r"¥([\d.]+)", fields[2])
        output_match = re.fullmatch(r"¥([\d.]+)", fields[3])
        if not input_match or not output_match:
            continue
        prices[fields[0].lower()] = {
            "input": float(input_match.group(1)),
            "output": float(output_match.group(1)),
            "currency": "CNY",
        }
    return prices


def parse_deepseek_pricing_html(content: str) -> dict[str, dict[str, float | str]]:
    """解析 DeepSeek 官方时段定价表，发布高峰价并保留完整价格区间。

    站点的排序和预算计算使用高峰价，避免把仅在空闲时段生效的折扣价
    当作全天价格；展示层可用 ``*_min`` 字段呈现空闲至高峰区间。
    """

    def clean(cell: str) -> str:
        value = re.sub(r"<[^>]+>", " ", cell)
        return re.sub(r"\s+", " ", html.unescape(value).replace("\x00", "")).strip()

    rows: list[list[str]] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", content, re.DOTALL | re.IGNORECASE):
        cells = [clean(cell) for cell in re.findall(
            r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL | re.IGNORECASE
        )]
        if cells:
            rows.append(cells)

    models: list[str] = []
    for cells in rows:
        if cells[0] == "模型":
            models = [cell.lower() for cell in cells[1:] if cell.lower().startswith("deepseek-")]
            break
    if not models:
        return {}

    values: dict[str, dict[str, float]] = {model: {} for model in models}
    metric = ""
    for cells in rows:
        joined = " ".join(cells)
        if "缓存未命中" in joined:
            metric = "input"
        elif "百万tokens输出" in joined:
            metric = "output"
        if not metric:
            continue

        period = ""
        if "空闲时段" in cells:
            period = "min"
            value_start = cells.index("空闲时段") + 1
        elif cells[0] == "高峰时段":
            period = "max"
            value_start = 1
        else:
            continue

        parsed: list[float] = []
        for cell in cells[value_start:value_start + len(models)]:
            match = re.fullmatch(r"([\d.]+)元", cell)
            if not match:
                parsed = []
                break
            parsed.append(float(match.group(1)))
        if len(parsed) != len(models):
            continue
        for model, value in zip(models, parsed):
            values[model][f"{metric}_{period}"] = value

    prices: dict[str, dict[str, float | str]] = {}
    for model, tiers in values.items():
        required = {"input_min", "input_max", "output_min", "output_max"}
        if not required.issubset(tiers):
            continue
        prices[model] = {
            "input": tiers["input_max"],
            "output": tiers["output_max"],
            **tiers,
            "currency": "CNY",
            "pricing_note": "空闲时段至高峰时段；排序按高峰价",
        }
    return prices


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
