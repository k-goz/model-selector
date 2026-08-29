"""Platform registry and one-pass catalog collection orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from src.platforms import (
    AiHubMixPlatform, AliyunPlatform, BaichuanPlatform, ChatAnywherePlatform,
    CoherePlatform, DeepInfraPlatform, DeepSeekPlatform, FireworksPlatform,
    GroqPlatform, InfiniPlatform, JieyuePlatform, MiniMaxPlatform,
    MoonshotPlatform, N1NPlatform, NovitaPlatform, OpenRouterPlatform,
    SiliconFlowPlatform, SparkPlatform, TencentPlatform, TogetherPlatform,
    VolcenginePlatform, YiPlatform, ZhipuPlatform,
)
from src.platforms.base import PlatformFetchResult

from .http import CachedHttpClient


PLATFORM_CLASSES = {
    "aliyun": AliyunPlatform,
    "siliconflow": SiliconFlowPlatform,
    "moonshot": MoonshotPlatform,
    "zhipu": ZhipuPlatform,
    "volcengine": VolcenginePlatform,
    "tencent": TencentPlatform,
    "spark": SparkPlatform,
    "minimax": MiniMaxPlatform,
    "yi": YiPlatform,
    "baichuan": BaichuanPlatform,
    "jieyue": JieyuePlatform,
    "deepseek": DeepSeekPlatform,
    "groq": GroqPlatform,
    "together": TogetherPlatform,
    "fireworks": FireworksPlatform,
    "cohere": CoherePlatform,
    "infini": InfiniPlatform,
    "novita": NovitaPlatform,
    "deepinfra": DeepInfraPlatform,
    "aihubmix": AiHubMixPlatform,
    "n1n": N1NPlatform,
    "ca": ChatAnywherePlatform,
}


@dataclass(frozen=True)
class CatalogCollection:
    results: dict[str, PlatformFetchResult]

    @property
    def source_runs(self) -> dict[str, dict]:
        return {platform: result.metadata.to_dict() for platform, result in self.results.items()}

    def __getitem__(self, platform: str) -> PlatformFetchResult:
        return self.results[platform]


def collect_platform_catalog(
    api_keys: Mapping[str, str],
    cache_dir: Path,
    http_client: CachedHttpClient | None = None,
) -> CatalogCollection:
    client = http_client or CachedHttpClient(cache_dir)
    results: dict[str, PlatformFetchResult] = {}
    for platform, platform_class in PLATFORM_CLASSES.items():
        kwargs = {
            "api_key": api_keys.get(platform, ""),
            "json_fetcher": lambda url, key, platform=platform: client.fetch_json(url, key, platform=platform),
        }
        if platform == "openrouter":
            kwargs["cache_path"] = str(Path(cache_dir) / "openrouter_full.json")
        if platform == "ca":
            kwargs["text_fetcher"] = client.fetch_text
        results[platform] = platform_class(**kwargs).fetch_result()
    return CatalogCollection(results)
