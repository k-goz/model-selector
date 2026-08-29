"""前端资源与页面组合回归测试。"""

import pytest

from src.rendering import compose_page, generate_english_version, load_asset, render_template
from src.rendering.i18n import TRANSLATIONS, validate_translation_catalog


def test_frontend_assets_are_externalized_and_non_empty():
    css = load_asset("assets/styles.css")
    javascript = load_asset("assets/js/core.js")
    i18n = load_asset("assets/js/i18n.js")
    routing = load_asset("assets/js/routing.js")
    analytics = load_asset("assets/js/analytics.js")
    assert ".mc{" in css
    assert "function renderModelsFromJSON" in javascript
    assert len(css) > 10_000
    assert len(javascript) > 20_000
    assert "Missing translation" in i18n
    assert "ModelSelectorRouting" in routing
    assert "ModelSelectorAnalytics" in analytics


def test_page_template_preserves_fragment_boundaries():
    assert compose_page("<head>", ["<card-a>", "<card-b>"], "<footer>") == (
        "<head><card-a>\n<card-b><footer>"
    )


def test_document_head_component_renders_required_values():
    rendered = render_template("templates/document_head.html", {
        "STYLES": "body{}",
        "TOTAL": 12,
        "DATA_NOTE": "fresh",
        "UPDATED_AT": "2026-08-29 12:00",
        "PRICE_CHANGE_HTML": "<div>changed</div>",
    })
    assert "12 个模型" in rendered
    assert "https://model.ai-selector.top/" in rendered
    assert 'id="dataFreshness"' in rendered
    assert 'data-updated-at="2026-08-29 12:00"' in rendered
    assert "{{" not in rendered


def test_template_rejects_missing_or_unused_values():
    with pytest.raises(ValueError, match="缺少变量"):
        render_template("templates/document_head.html", {"STYLES": "body{}"})
    with pytest.raises(ValueError, match="未使用变量"):
        render_template("templates/insights.html", {"EXTRA": "value"})


def test_structured_i18n_catalog_is_complete_and_translates_nodes():
    validate_translation_catalog()
    assert TRANSLATIONS
    translated = generate_english_version(
        '<!DOCTYPE html><html lang="zh-CN"><head><title>AI 模型选择器 - 全网价格对比 2026 | DeepSeek vs GPT-4o vs Claude</title></head>'
        '<body><a class="topnav-link">首页</a><script>const label="首页";</script></body></html>'
    )
    assert 'lang="en"' in translated
    assert "AI Model Selector - Cross-Platform Pricing 2026" in translated
    assert '<a class="topnav-link">Home</a>' in translated
    assert 'const label="首页"' in translated
