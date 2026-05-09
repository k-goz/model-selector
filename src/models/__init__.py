"""
数据模型定义

使用 dataclass 定义模型数据结构，提高代码可读性和类型安全性
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Model:
    """AI 模型数据类"""
    
    # 必需字段
    id: str                          # 模型唯一标识
    name: str                        # 模型显示名称
    platform: str                    # 平台标识 (如 aliyun, openrouter)
    platform_name: str               # 平台中文名 (如 阿里百炼)
    platform_color: str              # 平台主题色 (如 #ff6a00)
    
    # 价格字段
    input_price: float = 0.0         # 输入价格
    output_price: float = 0.0        # 输出价格
    currency: str = "CNY"            # 货币类型 (CNY/USD)
    price_unit: str = "per_token"    # 价格单位 (per_token/per_1m)
    price_source: str = ""           # 价格来源标签 (A/S/DB/L/P)
    
    # 模型属性
    context: str = "N/A"             # 上下文长度 (如 32k, 128k)
    context_tokens: int = 0          # 上下文长度（数值）
    family: str = ""                 # 模型家族 (如 Qwen, GPT, Claude)
    
    # 标签和场景
    tags: List[str] = field(default_factory=list)  # 标签列表
    scene: str = "日常对话"          # 使用场景
    
    # API 信息
    base_url: str = ""               # API Base URL
    
    # 状态
    status: str = ""                 # 模型状态 (如 Shutdown, Retiring)
    
    def __post_init__(self):
        """初始化后处理"""
        # 自动计算上下文 token 数
        if self.context and self.context != "N/A":
            try:
                self.context_tokens = int(''.join(filter(str.isdigit, self.context)))
            except ValueError:
                self.context_tokens = 0
    
    @property
    def price_tier(self) -> str:
        """价格分级"""
        if self.input_price == 0 and self.output_price == 0:
            return "free"
        
        # USD 价格需要转换
        p = self.input_price
        if self.currency == "USD" and self.price_unit == "per_token":
            p = self.input_price * 1e6
        
        if p < 0.1:
            return "cheap"
        elif p < 10:
            return "mid"
        elif p < 100:
            return "high"
        else:
            return "ultra"
    
    @property
    def is_free(self) -> bool:
        """是否免费"""
        return self.input_price == 0 and self.output_price == 0
    
    @property
    def is_online(self) -> bool:
        """是否在线（未下线）"""
        return self.status not in ("Shutdown", "Retiring")
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "platform_name": self.platform_name,
            "platform_color": self.platform_color,
            "input_price": self.input_price,
            "output_price": self.output_price,
            "currency": self.currency,
            "price_unit": self.price_unit,
            "price_source": self.price_source,
            "context": self.context,
            "context_tokens": self.context_tokens,
            "family": self.family,
            "tags": self.tags,
            "scene": self.scene,
            "base_url": self.base_url,
            "status": self.status,
        }


@dataclass
class PriceInfo:
    """价格信息数据类"""
    
    input_price: float               # 输入价格
    output_price: float              # 输出价格
    context: str = "N/A"             # 上下文长度
    currency: str = "CNY"            # 货币类型
    source: str = ""                 # 价格来源
    source_url: str = ""             # 来源 URL
    
    @property
    def is_valid(self) -> bool:
        """价格是否有效"""
        return self.input_price > 0 or self.output_price > 0


@dataclass
class PlatformInfo:
    """平台信息数据类"""
    
    id: str                          # 平台标识
    name: str                        # 平台名称
    color: str                       # 主题色
    base_url: str = ""               # API Base URL
    currency: str = "CNY"            # 默认货币
    requires_key: bool = True        # 是否需要 API Key
    key_env_name: str = ""           # API Key 环境变量名
    model_count: int = 0             # 模型数量
