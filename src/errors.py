"""Domain exceptions shared by collection, pricing and publication layers."""

from __future__ import annotations


class ModelSelectorError(Exception):
    """Base exception for the model selector pipeline."""


class PriceNotFoundError(ModelSelectorError):
    def __init__(self, platform: str, model: str, message: str = ""):
        self.platform = platform
        self.model = model
        super().__init__(message or f"价格未找到: [{platform}] {model}")


class APIFetchError(ModelSelectorError):
    def __init__(self, platform: str, url: str, original_error: Exception | None = None):
        self.platform = platform
        self.url = url
        self.original_error = original_error
        message = f"API 获取失败: [{platform}] {url}"
        if original_error:
            message += f" - {str(original_error)[:100]}"
        super().__init__(message)


class PriceParseError(ModelSelectorError):
    def __init__(self, source: str, raw_data: str = "", message: str = ""):
        self.source = source
        self.raw_data = raw_data[:200] if raw_data else ""
        super().__init__(message or f"价格解析失败: {source}")


class CacheError(ModelSelectorError):
    def __init__(self, operation: str, path: str, original_error: Exception | None = None):
        self.operation = operation
        self.path = path
        self.original_error = original_error
        message = f"缓存{operation}失败: {path}"
        if original_error:
            message += f" - {str(original_error)[:80]}"
        super().__init__(message)
