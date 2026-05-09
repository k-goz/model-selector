"""
模型数据类单元测试

测试 Model 数据类的功能
"""

import pytest
import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import Model, PriceInfo, PlatformInfo


class TestModel:
    """测试 Model 数据类"""
    
    def test_model_creation(self):
        """测试模型创建"""
        model = Model(
            id="qwen-max",
            name="qwen-max",
            platform="aliyun",
            platform_name="阿里百炼",
            platform_color="#ff6a00",
            input_price=20.0,
            output_price=60.0,
            context="32k",
        )
        
        assert model.id == "qwen-max"
        assert model.input_price == 20.0
        assert model.output_price == 60.0
        assert model.currency == "CNY"
    
    def test_price_tier_free(self):
        """测试免费分级"""
        model = Model(
            id="free-model",
            name="Free Model",
            platform="test",
            platform_name="Test",
            platform_color="#000",
            input_price=0,
            output_price=0,
        )
        
        assert model.price_tier == "free"
        assert model.is_free is True
    
    def test_price_tier_mid(self):
        """测试中等分级"""
        model = Model(
            id="mid-model",
            name="Mid Model",
            platform="test",
            platform_name="Test",
            platform_color="#000",
            input_price=5.0,
            output_price=10.0,
        )
        
        assert model.price_tier == "mid"
        assert model.is_free is False
    
    def test_context_tokens_extraction(self):
        """测试上下文 token 数提取"""
        model = Model(
            id="test-model",
            name="Test",
            platform="test",
            platform_name="Test",
            platform_color="#000",
            context="128k",
        )
        
        assert model.context_tokens == 128
    
    def test_is_online(self):
        """测试模型在线状态"""
        model = Model(
            id="test-model",
            name="Test",
            platform="test",
            platform_name="Test",
            platform_color="#000",
        )
        
        assert model.is_online is True
        
        model.status = "Shutdown"
        assert model.is_online is False
    
    def test_to_dict(self):
        """测试转换为字典"""
        model = Model(
            id="test-model",
            name="Test Model",
            platform="test",
            platform_name="Test",
            platform_color="#ff0000",
            input_price=1.0,
            output_price=2.0,
            context="32k",
            tags=["便宜", "快速"],
        )
        
        d = model.to_dict()
        
        assert d["id"] == "test-model"
        assert d["input_price"] == 1.0
        assert d["tags"] == ["便宜", "快速"]


class TestPriceInfo:
    """测试 PriceInfo 数据类"""
    
    def test_valid_price(self):
        """测试有效价格"""
        info = PriceInfo(
            input_price=1.0,
            output_price=2.0,
            context="32k",
        )
        
        assert info.is_valid is True
    
    def test_invalid_price(self):
        """测试无效价格"""
        info = PriceInfo(
            input_price=0.0,
            output_price=0.0,
        )
        
        assert info.is_valid is False


class TestPlatformInfo:
    """测试 PlatformInfo 数据类"""
    
    def test_platform_info(self):
        """测试平台信息"""
        info = PlatformInfo(
            id="aliyun",
            name="阿里百炼",
            color="#ff6a00",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            currency="CNY",
            requires_key=True,
            key_env_name="ALIYUN_KEY",
        )
        
        assert info.id == "aliyun"
        assert info.requires_key is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
