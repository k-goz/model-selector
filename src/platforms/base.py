"""
平台数据获取模块基类

定义平台数据获取的标准接口
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)


@dataclass
class PlatformConfig:
    """平台配置"""
    id: str                    # 平台标识
    name: str                  # 平台名称
    color: str                 # 主题色
    base_url: str              # API Base URL
    currency: str = "CNY"      # 默认货币
    key_env_name: str = ""     # API Key 环境变量名


@dataclass(frozen=True)
class FetchMetadata:
    """一次平台模型目录抓取的审计信息。"""

    platform_id: str
    source_type: str
    source_url: str
    collected_at: str
    model_count: int
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "collected_at": self.collected_at,
            "model_count": self.model_count,
            "error": self.error,
        }


@dataclass(frozen=True)
class PlatformFetchResult:
    """标准化模型列表及其来源元数据。"""

    models: List[Dict[str, Any]]
    metadata: FetchMetadata


JsonFetcher = Callable[[str, str], Optional[Any]]
TextFetcher = Callable[[str], str]


def fetch_json(url: str, api_key: str = "") -> Optional[Any]:
    """默认 JSON 请求器；平台类可注入测试请求器或生产重试器。"""

    headers = {"User-Agent": "Mozilla/5.0 (ModelSelector/2.0)"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    """默认文本请求器，用于官方文档或价格页。"""

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (ModelSelector/2.0)"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


class BasePlatform(ABC):
    """
    平台数据获取基类
    
    所有平台实现都需要继承此类并实现 fetch_models 方法
    """
    
    def __init__(
        self,
        api_key: str = "",
        config: Optional[PlatformConfig] = None,
        json_fetcher: Optional[JsonFetcher] = None,
    ):
        """
        初始化平台
        
        Args:
            api_key: API Key
            config: 平台配置
        """
        self.api_key = api_key
        self.config = config
        self.json_fetcher = json_fetcher or fetch_json
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def platform_id(self) -> str:
        """平台标识"""
        pass
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称"""
        pass
    
    @property
    @abstractmethod
    def platform_color(self) -> str:
        """平台主题色"""
        pass
    
    @property
    @abstractmethod
    def base_url(self) -> str:
        """API Base URL"""
        pass
    
    @property
    def currency(self) -> str:
        """默认货币"""
        return "CNY"

    @property
    def model_source_url(self) -> str:
        """模型目录来源；默认使用 API Base URL。"""
        return self.base_url

    @property
    def fetch_source_type(self) -> str:
        """成功抓取时的来源类型。"""
        return "api"
    
    @property
    def is_configured(self) -> bool:
        """是否已配置 API Key"""
        return bool(self.api_key)
    
    @abstractmethod
    def fetch_models(self) -> List[Dict[str, Any]]:
        """
        获取模型列表
        
        Returns:
            模型信息列表，每个元素包含:
            - id: 模型 ID
            - name: 模型名称
            - input_price: 输入价格（可选，如果 API 返回）
            - output_price: 输出价格（可选）
            - context: 上下文长度（可选）
            - tags: 标签列表（可选）
            - scene: 使用场景（可选）
        """
        pass
    
    def get_fallback_models(self) -> List[Dict[str, Any]]:
        """
        获取兜底模型列表（当 API 不可用时）
        
        Returns:
            兜底模型列表
        """
        return []
    
    def fetch_with_fallback(self) -> List[Dict[str, Any]]:
        """
        获取模型列表（带兜底）
        
        Returns:
            模型列表
        """
        return self.fetch_result().models

    def fetch_result(self) -> PlatformFetchResult:
        """抓取模型并保留 API/回退来源、时间与错误。"""

        collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        error = ""
        try:
            models = self.fetch_models()
            if models:
                self.logger.info(f"[{self.platform_name}] 获取到 {len(models)} 个模型")
                return PlatformFetchResult(
                    models=models,
                    metadata=FetchMetadata(
                        platform_id=self.platform_id,
                        source_type=self.fetch_source_type,
                        source_url=self.model_source_url,
                        collected_at=collected_at,
                        model_count=len(models),
                    ),
                )
            error = "API 返回空模型列表"
        except Exception as e:
            error = str(e)[:300]
            self.logger.warning(f"[{self.platform_name}] API 获取失败: {e}")
        
        # 使用兜底列表
        fallback = self.get_fallback_models()
        if fallback:
            self.logger.info(f"[{self.platform_name}] 使用兜底列表: {len(fallback)} 个模型")
        return PlatformFetchResult(
            models=fallback,
            metadata=FetchMetadata(
                platform_id=self.platform_id,
                source_type="fallback",
                source_url=self.model_source_url,
                collected_at=collected_at,
                model_count=len(fallback),
                error=error,
            ),
        )


class OpenAICompatiblePlatform(BasePlatform):
    """
    OpenAI 兼容平台基类
    
    适用于支持 OpenAI API 格式的平台
    """
    
    @property
    def models_endpoint(self) -> str:
        """模型列表 API 端点"""
        return f"{self.base_url.rstrip('/')}/models"

    @property
    def model_source_url(self) -> str:
        return self.models_endpoint
    
    def fetch_models(self) -> List[Dict[str, Any]]:
        """获取模型列表（OpenAI 兼容格式）"""
        if not self.is_configured:
            raise ValueError(f"{self.platform_name} API Key 未配置")
        
        data = self.json_fetcher(self.models_endpoint, self.api_key)
        if not isinstance(data, dict):
            return []
        
        models = []
        for m in data.get("data", []):
            if not isinstance(m, dict):
                continue
            model_id = str(m.get("id") or "").strip()
            if not model_id:
                continue
            models.append({
                "id": model_id,
                "name": model_id,
            })
        
        return models
