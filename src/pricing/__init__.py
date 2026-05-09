"""
价格解析模块

实现 SSOT (Single Source of Truth) 四层价格解析系统:
- T1: API 直接返回的价格（最高优先级）
- T2: 官方定价页爬取
- T3: official_prices_db.json 价格数据库
- T4: LiteLLM 社区价格数据（海外平台兜底）
"""

import os
import re
import json
import logging
import urllib.request
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PriceResult:
    """价格解析结果"""
    input_price: float
    output_price: float
    context: str
    source_tag: str  # A/S/DB/L/""
    
    @property
    def is_valid(self) -> bool:
        return self.input_price > 0 or self.output_price > 0


# ═══════════════════════════════════════════════════════════════════════════
# 模型名称标准化（用于跨平台匹配）
# ═══════════════════════════════════════════════════════════════════════════

def normalize_for_match(model_name: str) -> str:
    """
    标准化模型名称，用于跨平台匹配
    
    Args:
        model_name: 原始模型名称
    
    Returns:
        标准化后的模型名称
    """
    n = model_name.strip()
    
    # 去掉常见前缀
    prefixes_to_remove = [
        "deepseek-ai/", "deepseek/", "Qwen/", "qwen/", "Pro/", "meta-llama/",
        "mistralai/", "google/", "microsoft/", "THUDM/", "zai-org/", "moonshotai/",
        "minimaxai/", "stepfun-ai/", "inclusionai/", "bytedance-seed/",
        "ByteDance-Seed/", "bytedance/", "tencent/", "internlm/", "paddlepaddle/",
        "PaddlePaddle/", "kwaipilot/", "Kwai-Kolors/", "FunAudioLLM/",
        "IndexTeam/", "BAAI/", "TeleAI/", "LoRA/", "netease-youdao/",
        "accounts/fireworks/models/", "turing/", "nvidia/",
        "openai/", "anthropic/", "cohere/"
    ]
    
    for pfx in prefixes_to_remove:
        if n.startswith(pfx):
            n = n[len(pfx):]
            break
    
    # 处理路径分隔符
    if "/" in n:
        n = n.split("/")[-1]
    
    # 去掉日期后缀
    n = re.sub(r'-\d{6,8}$', '', n)
    n = re.sub(r'-\d{4}$', '', n)
    
    # 去掉常见后缀
    n = re.sub(r'-(instruct|it|fp\d+|latest|main|default|base)$', '', n, flags=re.IGNORECASE)
    
    # 标准化命名格式
    n = re.sub(r'qwen-(\d)', r'qwen\1', n)
    n = re.sub(r'glm-(\d)', r'glm\1', n)
    n = re.sub(r'doubao-(\d)', r'doubao\1', n)
    
    # 已知别名映射
    ALIAS_MAP = {
        "deepseek-chat": "deepseek-v3",
        "deepseek-reasoner": "deepseek-r1",
    }
    if n in ALIAS_MAP:
        n = ALIAS_MAP[n]
    
    return n.lower().strip()


# ═══════════════════════════════════════════════════════════════════════════
# 价格数据库加载
# ═══════════════════════════════════════════════════════════════════════════

class PriceDatabase:
    """价格数据库管理类"""
    
    def __init__(self, db_path: str = "official_prices_db.json"):
        """
        初始化价格数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.data: Dict = {}
        self._load()
    
    def _load(self) -> None:
        """加载价格数据库"""
        if not os.path.exists(self.db_path):
            logger.warning(f"价格数据库不存在: {self.db_path}")
            return
        
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            
            # 统计条目数
            count = sum(
                len([k for k in v if not k.startswith("_")])
                for k in self.data
                if k != "_meta"
                for v in [self.data[k]]
            )
            platforms = len([k for k in self.data if k != "_meta"])
            logger.info(f"价格数据库加载成功: {platforms} 个平台, {count} 条记录")
            
        except Exception as e:
            logger.error(f"价格数据库加载失败: {e}")
            self.data = {}
    
    def get_price(self, platform: str, model_id: str) -> Tuple[float, float, str]:
        """
        从数据库获取价格（精确匹配 → 前缀匹配）
        
        Args:
            platform: 平台标识
            model_id: 模型 ID
        
        Returns:
            (input_price, output_price, context)
        """
        if platform not in self.data:
            return 0.0, 0.0, "N/A"
        
        platform_rules = self.data[platform]
        model_id_lower = model_id.lower()
        
        # 去掉常见前缀
        prefixes = [
            "deepseek-ai/", "qwen/", "thudm/", "meta-llama/", "mistralai/",
            "google/", "microsoft/", "zai-org/", "moonshotai/", "pro/",
            "minimaxai/", "stepfun-ai/", "inclusionai/", "bytedance-seed/",
            "tencent/", "internlm/", "paddlepaddle/", "kwaipilot/",
            "nvidia/", "openai/", "anthropic/", "accounts/fireworks/models/"
        ]
        
        for pfx in prefixes:
            if model_id_lower.startswith(pfx):
                stripped = model_id_lower[len(pfx):]
                if stripped in platform_rules:
                    entry = platform_rules[stripped]
                    return (
                        entry.get("input", 0),
                        entry.get("output", 0),
                        entry.get("context", "N/A")
                    )
        
        # 精确匹配
        if model_id_lower in platform_rules:
            entry = platform_rules[model_id_lower]
            return (
                entry.get("input", 0),
                entry.get("output", 0),
                entry.get("context", "N/A")
            )
        
        # 前缀匹配（最长匹配优先）
        sorted_keys = sorted(
            [k for k in platform_rules if not k.startswith("_")],
            key=len,
            reverse=True
        )
        for rule_key in sorted_keys:
            if model_id_lower.startswith(rule_key):
                entry = platform_rules[rule_key]
                return (
                    entry.get("input", 0),
                    entry.get("output", 0),
                    entry.get("context", "N/A")
                )
        
        return 0.0, 0.0, "N/A"


# ═══════════════════════════════════════════════════════════════════════════
# SSOT 价格解析器
# ═══════════════════════════════════════════════════════════════════════════

class SSOTPriceResolver:
    """
    SSOT (Single Source of Truth) 价格解析器
    
    四层价格解析:
    T1: API 直接返回的价格
    T2: 官方定价页爬取
    T3: 价格数据库
    T4: LiteLLM 社区数据
    """
    
    def __init__(
        self,
        db_path: str = "official_prices_db.json",
        script_dir: str = ""
    ):
        """
        初始化解析器
        
        Args:
            db_path: 价格数据库路径
            script_dir: 脚本目录
        """
        self.script_dir = script_dir or os.path.dirname(os.path.abspath(__file__))
        db_full_path = os.path.join(self.script_dir, db_path) if not os.path.isabs(db_path) else db_path
        
        self.price_db = PriceDatabase(db_full_path)
        self.official_prices: Dict = {}  # 官方爬取价格
        self.litellm_prices: Dict = {}   # LiteLLM 社区价格
    
    def load_official_prices(self, prices: Dict) -> None:
        """加载官方爬取的价格"""
        self.official_prices = prices
        logger.info(f"加载官方爬取价格: {len(prices)} 条")
    
    def load_litellm_prices(self, prices: Dict) -> None:
        """加载 LiteLLM 社区价格"""
        self.litellm_prices = prices
        logger.info(f"加载 LiteLLM 社区价格: {len(prices)} 个提供商")
    
    def get_absolute_price(
        self,
        platform: str,
        model_name: str,
        api_price: Optional[Tuple[float, float, str]] = None
    ) -> PriceResult:
        """
        获取模型价格的绝对值
        
        Args:
            platform: 平台标识
            model_name: 模型名称
            api_price: API 直接返回的价格 (input, output, context)
        
        Returns:
            PriceResult 对象
        """
        # T1: API 直接返回的价格（最高优先级）
        if api_price and (api_price[0] > 0 or api_price[1] > 0):
            return PriceResult(
                input_price=api_price[0],
                output_price=api_price[1],
                context=api_price[2] if len(api_price) > 2 else "N/A",
                source_tag="A"
            )
        
        # T2: 官方爬取结果
        mn_lower = model_name.lower()
        official = self.official_prices.get(mn_lower)
        
        if not official:
            official = self.official_prices.get("sf:" + mn_lower)
        
        if not official:
            for sf_pfx in ["deepseek-ai/", "thudm/", "qwen/"]:
                official = self.official_prices.get("sf:" + sf_pfx + mn_lower)
                if official:
                    break
        
        if official and (official.get("input", 0) > 0 or official.get("output", 0) > 0):
            return PriceResult(
                input_price=official["input"],
                output_price=official["output"],
                context=official.get("context", "N/A"),
                source_tag="S"
            )
        
        # T3: 价格数据库
        db_i, db_o, db_c = self.price_db.get_price(platform, model_name)
        if db_i > 0 or db_o > 0:
            return PriceResult(
                input_price=db_i,
                output_price=db_o,
                context=db_c,
                source_tag="DB"
            )
        
        # T4: LiteLLM 社区价格（海外平台兜底）
        ll_result = self._get_litellm_price(platform, model_name)
        if ll_result.is_valid:
            return ll_result
        
        # 未找到 → 返回 0 + 警告
        logger.warning(f"⚠️ PRICE_MISSING: [{platform}] {model_name} → 价格为0，请在 official_prices_db.json 中添加")
        return PriceResult(
            input_price=0.0,
            output_price=0.0,
            context="N/A",
            source_tag=""
        )
    
    def _get_litellm_price(self, platform: str, model_name: str) -> PriceResult:
        """从 LiteLLM 社区价格获取"""
        # 平台名称映射
        key_map = {
            "together": "together_ai",
            "fireworks": "fireworks_ai",
            "cohere": "cohere",
            "groq": "groq",
            "novita": "novita",
            "deepinfra": "deepinfra",
        }
        
        provider = key_map.get(platform, platform)
        if provider not in self.litellm_prices:
            return PriceResult(0.0, 0.0, "N/A", "")
        
        ml = model_name.lower()
        norm = normalize_for_match(model_name)
        
        for k in (ml, norm):
            if k in self.litellm_prices[provider]:
                entry = self.litellm_prices[provider][k]
                return PriceResult(
                    input_price=entry["input"],
                    output_price=entry["output"],
                    context=entry.get("context", "N/A"),
                    source_tag="L"
                )
        
        return PriceResult(0.0, 0.0, "N/A", "")


# ═══════════════════════════════════════════════════════════════════════════
# 价格分级
# ═══════════════════════════════════════════════════════════════════════════

def get_price_tier(
    input_price: float,
    output_price: float,
    currency: str = "CNY",
    price_unit: str = "per_token"
) -> str:
    """
    获取价格分级
    
    Args:
        input_price: 输入价格
        output_price: 输出价格
        currency: 货币类型
        price_unit: 价格单位
    
    Returns:
        价格级别: free/cheap/mid/high/ultra
    """
    input_price = float(input_price or 0)
    output_price = float(output_price or 0)
    
    if input_price == 0 and output_price == 0:
        return "free"
    
    # USD 价格需要转换
    p = input_price
    if currency == "USD" and price_unit == "per_token":
        p = input_price * 1e6
    
    if p < 0.1:
        return "cheap"
    elif p < 10:
        return "mid"
    elif p < 100:
        return "high"
    else:
        return "ultra"


# ═══════════════════════════════════════════════════════════════════════════
# 模型家族识别
# ═══════════════════════════════════════════════════════════════════════════

def get_model_family(model_id: str) -> str:
    """
    根据模型名称识别家族标签
    
    Args:
        model_id: 模型 ID
    
    Returns:
        模型家族名称
    """
    n = model_id.lower()
    
    # 按优先级匹配
    family_patterns = [
        (['gpt-', 'gpt4', 'gpt3', 'o1-', 'o3-', 'o4-'], 'GPT'),
        (['claude'], 'Claude'),
        (['gemini'], 'Gemini'),
        (['llama'], 'Llama'),
        (['mistral', 'mixtral', 'codestral', 'pixtral'], 'Mistral'),
        (['deepseek'], 'DeepSeek'),
        (['qwen', 'qwq'], 'Qwen'),
        (['glm'], 'GLM'),
        (['kimi', 'moonshot'], 'Kimi'),
        (['doubao', 'seed'], 'Doubao'),
        (['yi-', 'yi '], 'Yi'),
        (['phi'], 'Phi'),
        (['command'], 'Command'),
        (['jamba'], 'Jamba'),
        (['grok'], 'Grok'),
        (['nova'], 'Nova'),
        (['sonar'], 'Sonar'),
        (['hunyuan'], 'Hunyuan'),
        (['spark', 'generalv'], 'Spark'),
        (['minimax', 'abab'], 'MiniMax'),
        (['baichuan'], 'Baichuan'),
        (['step'], 'Step'),
        (['ernie', 'wenxin'], 'ERNIE'),
        (['internlm'], 'InternLM'),
        (['kolors'], 'Kolors'),
        (['bge'], 'BGE'),
    ]
    
    for patterns, family in family_patterns:
        if any(p in n for p in patterns):
            return family
    
    return 'Other'
