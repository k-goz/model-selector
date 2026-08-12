"""已接入生产生成器的平台模型目录抓取器。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from src.pricing import parse_n1n_token_prices

from .base import BasePlatform, OpenAICompatiblePlatform


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

