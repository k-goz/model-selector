"""
价格解析模块单元测试

测试 SSOT 四层价格解析系统的核心功能
"""

import pytest
import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pricing import (
    normalize_for_match,
    get_price_tier,
    get_model_family,
    PriceDatabase,
    PriceResult,
    SSOTPriceResolver,
)


class TestNormalizeForMatch:
    """测试模型名称标准化"""
    
    def test_remove_prefix_deepseek(self):
        """测试移除 deepseek-ai/ 前缀"""
        assert normalize_for_match("deepseek-ai/DeepSeek-V3") == "deepseek-v3"
        assert normalize_for_match("deepseek-ai/DeepSeek-R1") == "deepseek-r1"
    
    def test_remove_prefix_qwen(self):
        """测试移除 Qwen/ 前缀"""
        assert normalize_for_match("Qwen/Qwen3-32B") == "qwen3-32b"
        assert normalize_for_match("qwen/qwen2.5-72b") == "qwen2.5-72b"
    
    def test_remove_prefix_pro(self):
        """测试移除 Pro/ 前缀"""
        assert normalize_for_match("Pro/deepseek-ai/DeepSeek-V3") == "deepseek-v3"
    
    def test_alias_mapping(self):
        """测试别名映射"""
        assert normalize_for_match("deepseek-chat") == "deepseek-v3"
        assert normalize_for_match("deepseek-reasoner") == "deepseek-r1"
    
    def test_normalize_qwen_format(self):
        """测试 Qwen 格式标准化"""
        assert normalize_for_match("qwen-2.5") == "qwen2.5"
        assert normalize_for_match("qwen-3") == "qwen3"
    
    def test_case_insensitive(self):
        """测试大小写不敏感"""
        assert normalize_for_match("DeepSeek-V3") == normalize_for_match("deepseek-v3")
        assert normalize_for_match("QWEN-MAX") == normalize_for_match("qwen-max")


class TestGetPriceTier:
    """测试价格分级"""
    
    def test_free_tier(self):
        """测试免费分级"""
        assert get_price_tier(0, 0) == "free"
        assert get_price_tier(0, 0, "CNY") == "free"
        assert get_price_tier(0, 0, "USD") == "free"
    
    def test_cheap_tier(self):
        """测试便宜分级"""
        assert get_price_tier(0.05, 0.1) == "cheap"
        assert get_price_tier(0.09, 0.2) == "cheap"
    
    def test_mid_tier(self):
        """测试中等分级"""
        assert get_price_tier(0.5, 1.0) == "mid"
        assert get_price_tier(5.0, 10.0) == "mid"
        assert get_price_tier(9.99, 15.0) == "mid"
    
    def test_high_tier(self):
        """测试高价分级"""
        assert get_price_tier(15.0, 30.0) == "high"
        assert get_price_tier(50.0, 100.0) == "high"
        assert get_price_tier(99.99, 150.0) == "high"
    
    def test_ultra_tier(self):
        """测试极贵分级"""
        assert get_price_tier(100.0, 200.0) == "ultra"
        assert get_price_tier(500.0, 1000.0) == "ultra"
    
    def test_usd_conversion(self):
        """测试 USD 价格转换"""
        # $0.0000001/token = $0.1/1M tokens -> cheap
        assert get_price_tier(0.0000001, 0.0000002, "USD", "per_token") == "cheap"
        # $0.000001/token = $1/1M tokens -> mid
        assert get_price_tier(0.000001, 0.000002, "USD", "per_token") == "mid"


class TestGetModelFamily:
    """测试模型家族识别"""
    
    def test_gpt_family(self):
        """测试 GPT 家族"""
        assert get_model_family("gpt-4o") == "GPT"
        assert get_model_family("gpt-4-turbo") == "GPT"
        assert get_model_family("o1-preview") == "GPT"
        assert get_model_family("o3-mini") == "GPT"
    
    def test_claude_family(self):
        """测试 Claude 家族"""
        assert get_model_family("claude-sonnet-4-5") == "Claude"
        assert get_model_family("claude-3-opus") == "Claude"
    
    def test_deepseek_family(self):
        """测试 DeepSeek 家族"""
        assert get_model_family("deepseek-v3") == "DeepSeek"
        assert get_model_family("deepseek-r1") == "DeepSeek"
        assert get_model_family("deepseek-ai/DeepSeek-V3") == "DeepSeek"
    
    def test_qwen_family(self):
        """测试 Qwen 家族"""
        assert get_model_family("qwen-max") == "Qwen"
        assert get_model_family("qwen3-32b") == "Qwen"
        assert get_model_family("qwq-32b") == "Qwen"
    
    def test_glm_family(self):
        """测试 GLM 家族"""
        assert get_model_family("glm-5") == "GLM"
        assert get_model_family("glm-4-plus") == "GLM"
    
    def test_other_family(self):
        """测试未知家族"""
        assert get_model_family("unknown-model") == "Other"
        assert get_model_family("random-name") == "Other"


class TestPriceResult:
    """测试价格结果数据类"""
    
    def test_valid_price(self):
        """测试有效价格"""
        result = PriceResult(
            input_price=1.0,
            output_price=2.0,
            context="32k",
            source_tag="A"
        )
        assert result.is_valid is True
    
    def test_invalid_price(self):
        """测试无效价格"""
        result = PriceResult(
            input_price=0.0,
            output_price=0.0,
            context="N/A",
            source_tag=""
        )
        assert result.is_valid is False


class TestPriceDatabase:
    """测试价格数据库"""
    
    def test_load_database(self):
        """测试加载数据库"""
        # 使用项目根目录的数据库
        db_path = os.path.join(os.path.dirname(__file__), '..', 'official_prices_db.json')
        if os.path.exists(db_path):
            db = PriceDatabase(db_path)
            assert len(db.data) > 0
        else:
            pytest.skip("价格数据库不存在")
    
    def test_get_price_exact_match(self):
        """测试精确匹配"""
        db_path = os.path.join(os.path.dirname(__file__), '..', 'official_prices_db.json')
        if not os.path.exists(db_path):
            pytest.skip("价格数据库不存在")
        
        db = PriceDatabase(db_path)
        
        # 测试智谱 AI 的模型
        inp, out, ctx = db.get_price("zhipu", "glm-5")
        assert inp > 0
        assert out > 0
        assert ctx != "N/A"
    
    def test_get_price_not_found(self):
        """测试未找到价格"""
        db_path = os.path.join(os.path.dirname(__file__), '..', 'official_prices_db.json')
        if not os.path.exists(db_path):
            pytest.skip("价格数据库不存在")
        
        db = PriceDatabase(db_path)
        
        inp, out, ctx = db.get_price("unknown_platform", "unknown_model")
        assert inp == 0
        assert out == 0
        assert ctx == "N/A"


class TestSSOTPriceResolver:
    """测试 SSOT 价格解析器"""
    
    def test_api_price_priority(self):
        """测试 API 价格优先级最高"""
        db_path = os.path.join(os.path.dirname(__file__), '..', 'official_prices_db.json')
        resolver = SSOTPriceResolver(db_path if os.path.exists(db_path) else "")
        
        # API 价格应该优先返回
        result = resolver.get_absolute_price(
            "aliyun",
            "qwen-max",
            api_price=(20.0, 60.0, "32k")
        )
        
        assert result.input_price == 20.0
        assert result.output_price == 60.0
        assert result.source_tag == "A"
    
    def test_missing_price_warning(self):
        """测试价格缺失警告"""
        resolver = SSOTPriceResolver("")
        
        result = resolver.get_absolute_price(
            "unknown_platform",
            "unknown_model"
        )
        
        assert result.input_price == 0.0
        assert result.output_price == 0.0
        assert result.source_tag == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
