"""
平台数据获取模块

提供各平台模型数据获取的统一接口
"""

from .base import (
    BasePlatform,
    FetchMetadata,
    OpenAICompatiblePlatform,
    PlatformConfig,
    PlatformFetchResult,
)
from .catalog import AliyunPlatform, DeepSeekPlatform, MiniMaxPlatform, N1NPlatform

__all__ = [
    "BasePlatform",
    "FetchMetadata",
    "OpenAICompatiblePlatform", 
    "PlatformConfig",
    "PlatformFetchResult",
    "AliyunPlatform",
    "DeepSeekPlatform",
    "MiniMaxPlatform",
    "N1NPlatform",
]
