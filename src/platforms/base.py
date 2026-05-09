"""
平台数据获取模块基类

定义平台数据获取的标准接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import logging

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


class BasePlatform(ABC):
    """
    平台数据获取基类
    
    所有平台实现都需要继承此类并实现 fetch_models 方法
    """
    
    def __init__(self, api_key: str = "", config: Optional[PlatformConfig] = None):
        """
        初始化平台
        
        Args:
            api_key: API Key
            config: 平台配置
        """
        self.api_key = api_key
        self.config = config
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
        try:
            models = self.fetch_models()
            if models:
                self.logger.info(f"[{self.platform_name}] 获取到 {len(models)} 个模型")
                return models
        except Exception as e:
            self.logger.warning(f"[{self.platform_name}] API 获取失败: {e}")
        
        # 使用兜底列表
        fallback = self.get_fallback_models()
        if fallback:
            self.logger.info(f"[{self.platform_name}] 使用兜底列表: {len(fallback)} 个模型")
        return fallback


class OpenAICompatiblePlatform(BasePlatform):
    """
    OpenAI 兼容平台基类
    
    适用于支持 OpenAI API 格式的平台
    """
    
    @property
    def models_endpoint(self) -> str:
        """模型列表 API 端点"""
        return f"{self.base_url.rstrip('/')}/models"
    
    def fetch_models(self) -> List[Dict[str, Any]]:
        """获取模型列表（OpenAI 兼容格式）"""
        if not self.is_configured:
            raise ValueError(f"{self.platform_name} API Key 未配置")
        
        import urllib.request
        import json
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        req = urllib.request.Request(self.models_endpoint, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        models = []
        for m in data.get("data", []):
            models.append({
                "id": m.get("id", ""),
                "name": m.get("id", ""),
            })
        
        return models
