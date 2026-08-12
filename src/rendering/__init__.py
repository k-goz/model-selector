"""静态页面渲染辅助模块。"""

from .assets import load_asset
from .page import compose_page

__all__ = ["compose_page", "load_asset"]
