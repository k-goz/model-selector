"""已接入生产生成器的平台模型目录抓取器。"""

from __future__ import annotations

from copy import deepcopy
import html as html_lib
import re
from typing import Any, Dict, List

from src.pricing import parse_n1n_token_prices

from .base import BasePlatform, OpenAICompatiblePlatform, TextFetcher, fetch_text


class AliyunPlatform(BasePlatform):
    platform_id = "aliyun"
    platform_name = "阿里百炼"
    platform_color = "#ff6a00"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model_source_url = "https://dashscope.aliyuncs.com/api/v1/models"

    FALLBACK_MODELS = [
        {"id": "qwen-max", "input_price": 2.4, "output_price": 9.6, "context": "32k", "tags": ["旗舰"], "scene": "深度推理"},
        {"id": "qwen-plus", "input_price": 0.8, "output_price": 2.0, "context": "128k", "tags": ["主力", "性价比"], "scene": "日常对话"},
        {"id": "qwen-turbo", "input_price": 0.3, "output_price": 0.6, "context": "1M", "tags": ["快速", "极便宜"], "scene": "日常对话"},
        {"id": "qwen-long", "input_price": 0.5, "output_price": 2.0, "context": "1M", "tags": ["长上下文"], "scene": "日常对话"},
        {"id": "qwen-vl-max", "input_price": 20.0, "output_price": 60.0, "context": "32k", "tags": ["视觉", "旗舰"], "scene": "视觉图片"},
        {"id": "qwen-vl-plus", "input_price": 0.8, "output_price": 2.0, "context": "128k", "tags": ["视觉", "性价比"], "scene": "视觉图片"},
        {"id": "qwen-coder-plus", "input_price": 0.8, "output_price": 2.0, "context": "128k", "tags": ["代码"], "scene": "编程代码"},
        {"id": "qwen3-235b-a22b", "input_price": 0.8, "output_price": 6.4, "context": "128k", "tags": ["旗舰", "MoE"], "scene": "深度推理"},
        {"id": "qwen3-32b", "input_price": 0.6, "output_price": 4.8, "context": "128k", "tags": ["主力"], "scene": "日常对话"},
        {"id": "qwen3-14b", "input_price": 0.4, "output_price": 3.2, "context": "128k", "tags": ["轻量"], "scene": "日常对话"},
        {"id": "qwen3-8b", "input_price": 0.2, "output_price": 2.0, "context": "128k", "tags": ["轻量", "免费额度"], "scene": "日常对话"},
        {"id": "qwen3-4b", "input_price": 0.2, "output_price": 2.0, "context": "128k", "tags": ["轻量", "免费额度"], "scene": "日常对话"},
        {"id": "qwq-32b", "input_price": 0.7, "output_price": 2.0, "context": "128k", "tags": ["推理"], "scene": "深度推理"},
        {"id": "deepseek-v3", "input_price": 1.0, "output_price": 2.0, "context": "1M", "tags": ["满血版", "主力"], "scene": "日常对话"},
        {"id": "deepseek-r1", "input_price": 1.0, "output_price": 2.0, "context": "1M", "tags": ["推理", "旗舰"], "scene": "深度推理"},
    ]

    def fetch_models(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            raise ValueError("阿里百炼 API Key 未配置")

        models: List[Dict[str, Any]] = []
        for page in range(1, 10):
            url = f"{self.model_source_url}?page_no={page}&page_size=100"
            payload = self.json_fetcher(url, self.api_key)
            if not isinstance(payload, dict):
                break
            output = payload.get("output") or {}
            page_models = output.get("models") or []
            if not isinstance(page_models, list) or not page_models:
                break
            for raw in page_models:
                model = self._normalize_model(raw)
                if model:
                    models.append(model)
            total = int(output.get("total") or 0)
            if total and len(models) >= total:
                break
        return models

    @staticmethod
    def _normalize_model(raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        model_id = str(raw.get("name") or raw.get("model") or "").strip()
        if not model_id:
            return {}

        input_price = output_price = 0.0
        price_groups = raw.get("prices") or []
        first_group = price_groups[0] if price_groups and isinstance(price_groups[0], dict) else {}
        for price in first_group.get("prices", []):
            if not isinstance(price, dict):
                continue
            if price.get("type") == "input_token":
                input_price = float(price.get("price") or 0)
            elif price.get("type") == "output_token":
                output_price = float(price.get("price") or 0)

        context_tokens = int((raw.get("model_info") or {}).get("context_window") or 0)
        context = f"{context_tokens // 1000}k" if context_tokens else "N/A"
        capabilities = set(raw.get("capabilities") or [])
        tags: List[str] = []
        if "Reasoning" in capabilities:
            tags.append("推理")
        if "VU" in capabilities:
            tags.append("视觉")
        if "IG" in capabilities:
            tags.append("图片生成")
            scene = "图片生成"
        elif "VG" in capabilities:
            tags.append("视频生成")
            scene = "视频生成"
        elif "VU" in capabilities:
            scene = "视觉图片"
        elif "Reasoning" in capabilities:
            scene = "深度推理"
        else:
            scene = "日常对话"
        if input_price == 0 and output_price == 0 and capabilities.intersection({"IG", "VG"}):
            tags.append("按次计费")
        return {
            "id": model_id,
            "name": model_id,
            "input_price": input_price,
            "output_price": output_price,
            "context": context,
            "tags": tags,
            "scene": scene,
        }

    def get_fallback_models(self) -> List[Dict[str, Any]]:
        return deepcopy(self.FALLBACK_MODELS)


class MiniMaxPlatform(OpenAICompatiblePlatform):
    platform_id = "minimax"
    platform_name = "MiniMax"
    platform_color = "#6366f1"
    base_url = "https://api.minimax.chat/v1"

    FALLBACK_IDS = [
        "MiniMax-M2.7", "MiniMax-M2.1", "abab6.5s", "abab6.5", "abab6.5g",
        "abab5.5", "abab5.5s", "abab6.5s-vision", "abab6.5-vision", "minimax-m1",
    ]

    def get_fallback_models(self) -> List[Dict[str, Any]]:
        return [{"id": model_id, "name": model_id} for model_id in self.FALLBACK_IDS]


class DeepSeekPlatform(OpenAICompatiblePlatform):
    platform_id = "deepseek"
    platform_name = "DeepSeek"
    platform_color = "#4d6dff"
    base_url = "https://api.deepseek.com/v1"

    FALLBACK_IDS = ["deepseek-v4-flash", "deepseek-v4-pro"]

    def get_fallback_models(self) -> List[Dict[str, Any]]:
        return [{"id": model_id, "name": model_id} for model_id in self.FALLBACK_IDS]


class N1NPlatform(BasePlatform):
    platform_id = "n1n"
    platform_name = "n1n.ai"
    platform_color = "#f59e0b"
    base_url = "https://api.n1n.ai/v1"
    model_source_url = "https://api.n1n.ai/api/pricing"

    FALLBACK_IDS = ["gpt-4o", "gpt-4o-mini", "deepseek-chat", "claude-sonnet-4-5", "qwen-plus"]
    SKIP_KEYWORDS = {
        "embed", "rerank", "tts", "whisper", "dall", "midjourney", "mj_",
        "stable-diffusion", "moderation", "bge-", "sd1", "sd3", "flux",
        "cogview", "paint", "audio",
    }

    def fetch_models(self) -> List[Dict[str, Any]]:
        payload = self.json_fetcher(self.model_source_url, "")
        prices = parse_n1n_token_prices(payload)
        models = []
        for model_id, (input_price, output_price) in prices.items():
            lowered = model_id.lower()
            if any(keyword in lowered for keyword in self.SKIP_KEYWORDS):
                continue
            models.append({
                "id": model_id,
                "name": model_id,
                "input_price": input_price,
                "output_price": output_price,
                "context": "128k",
            })
        return models

    def get_fallback_models(self) -> List[Dict[str, Any]]:
        return [{"id": model_id, "name": model_id, "context": "128k"} for model_id in self.FALLBACK_IDS]


class SiliconFlowPlatform(OpenAICompatiblePlatform):
    platform_id = "siliconflow"
    platform_name = "硅基流动"
    platform_color = "#7C3AED"
    base_url = "https://api.siliconflow.cn/v1"

    FALLBACK_IDS = [
        "deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "Qwen/Qwen3-235B-A22B",
        "Qwen/Qwen3-32B", "Qwen/Qwen3-14B", "Qwen/Qwen3-8B", "Qwen/Qwen3-4B",
        "Qwen/Qwen3-Coder-480B-A35B-Instruct", "Qwen/Qwen3-235B-A22B-Thinking", "Qwen/QwQ-32B",
        "Qwen/Qwen2.5-72B-Instruct", "Qwen/Qwen2.5-32B-Instruct", "Qwen/Qwen2.5-14B-Instruct",
        "Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-Coder-32B-Instruct",
        "Qwen/Qwen2.5-VL-72B-Instruct", "Qwen/Qwen2.5-VL-32B-Instruct",
        "Qwen/Qwen2-VL-72B-Instruct", "Qwen/Qwen2-VL-7B-Instruct",
        "Qwen/Qwen2.5-3B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct", "Qwen/Qwen2.5-0.5B-Instruct",
        "GLM-4-32B", "GLM-4-9B", "GLM-4.5-Air", "GLM-Z1-32B", "GLM-Z1-9B", "GLM-4.1V-9B",
        "THUDM/GLM-4.7", "THUDM/GLM-5", "THUDM/GLM-5.1",
        "Pro/deepseek-ai/DeepSeek-V3", "Pro/deepseek-ai/DeepSeek-R1",
        "moonshotai/Kimi-K2-Instruct", "inclusionAI/Ling-flash", "inclusionAI/Ling-mini",
    ]

    def get_fallback_models(self) -> List[Dict[str, Any]]:
        return [{"id": model_id, "name": model_id} for model_id in self.FALLBACK_IDS]


class AiHubMixPlatform(BasePlatform):
    platform_id = "aihubmix"
    platform_name = "AiHubMix"
    platform_color = "#10b981"
    base_url = "https://api.aihubmix.com/v1"
    model_source_url = "https://api.aihubmix.com/v1/models"

    FALLBACK_IDS = ["gpt-4o", "gpt-4o-mini", "claude-sonnet-4-5", "deepseek-chat", "qwen-plus", "glm-4-plus"]
    SKIP_KEYWORDS = {"embed", "rerank", "tts", "whisper", "dall-e", "midjourney"}

    def fetch_models(self) -> List[Dict[str, Any]]:
        payload = self.json_fetcher(self.model_source_url, self.api_key)
        raw_models = payload.get("data", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
        models = []
        for raw in raw_models:
            if not isinstance(raw, dict):
                continue
            model_id = str(raw.get("id") or "").strip()
            lowered = model_id.lower()
            if not model_id or any(keyword in lowered for keyword in self.SKIP_KEYWORDS):
                continue
            models.append({"id": model_id, "name": model_id})
        return models

    def get_fallback_models(self) -> List[Dict[str, Any]]:
        return [{"id": model_id, "name": model_id} for model_id in self.FALLBACK_IDS]


def parse_chatanywhere_pricing_html(document: str) -> List[Dict[str, Any]]:
    """逐表格行解析 ChatAnywhere 文档，避免跨表格错位产生伪模型。"""

    models: List[Dict[str, Any]] = []
    seen = set()
    skip_keywords = {
        "-ca", "-search", "-image", "-audio", "-realtime", "moderation",
        "embed", "bge-", "rerank", "tts", "whisper", "dall", "instruct-0",
        "codex-ca", "chat-latest-ca",
    }

    def clean_cell(value: str) -> str:
        without_tags = re.sub(r"<[^>]+>", "", value)
        return re.sub(r"\s+", " ", html_lib.unescape(without_tags)).replace("\x00", "").strip()

    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", document or "", re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 3:
            continue
        model_id, input_text, output_text = (clean_cell(cell) for cell in cells[:3])
        model_id = re.sub(r"\s*\[\d+\]\s*$", "", model_id).strip()
        lowered = model_id.lower()
        is_tier_range = bool(re.fullmatch(
            r"[><=]?\s*\d+\s*[kKmM]?(?:\s*-\s*\d+\s*[kKmM]?)?",
            model_id,
        ))
        if not model_id or is_tier_range or model_id in seen or any(keyword in lowered for keyword in skip_keywords):
            continue
        input_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", input_text)
        output_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", output_text)
        if not input_match or not output_match:
            continue
        input_price = float(input_match.group(1)) * 1000
        output_price = float(output_match.group(1)) * 1000
        if not (0 < input_price < 100000 and 0 < output_price < 1000000):
            continue
        seen.add(model_id)
        models.append({
            "id": model_id,
            "name": model_id,
            "input_price": round(input_price, 4),
            "output_price": round(output_price, 4),
            "context": "128k",
        })
    return models


class ChatAnywherePlatform(BasePlatform):
    platform_id = "ca"
    platform_name = "ChatAnywhere"
    platform_color = "#06b6d4"
    base_url = "https://api.chatanywhere.org/v1"
    model_source_url = "https://chatanywhere.apifox.cn/doc-2694962"

    FALLBACK_IDS = ["gpt-4o", "gpt-4o-mini", "deepseek-chat", "claude-sonnet-4-5", "gemini-2.5-flash"]

    def __init__(self, *args, text_fetcher: TextFetcher = fetch_text, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_fetcher = text_fetcher

    @property
    def fetch_source_type(self) -> str:
        return "scrape"

    def fetch_models(self) -> List[Dict[str, Any]]:
        return parse_chatanywhere_pricing_html(self.text_fetcher(self.model_source_url))

    def get_fallback_models(self) -> List[Dict[str, Any]]:
        return [{"id": model_id, "name": model_id, "context": "128k"} for model_id in self.FALLBACK_IDS]
