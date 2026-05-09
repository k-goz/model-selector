"""
平台数据获取模块

提供各平台模型数据获取的统一接口
"""

from .base import BasePlatform, OpenAICompatiblePlatform, PlatformConfig

__all__ = [
    "BasePlatform",
    "OpenAICompatiblePlatform", 
    "PlatformConfig",
]
