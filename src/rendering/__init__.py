"""静态页面渲染辅助模块。"""

from .assets import load_asset
from .cards import Te, make_card, make_or_card, set_official_prices
from .i18n import generate_english_version, write_english_version
from .page import compose_page, render_template

__all__ = [
    "compose_page",
    "generate_english_version",
    "load_asset",
    "make_card",
    "make_or_card",
    "render_template",
    "write_english_version",
    "set_official_prices",
    "Te",
]
