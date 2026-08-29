"""前端资源与页面组合回归测试。"""

import pytest

from src.rendering import compose_page, load_asset, render_template


def test_frontend_assets_are_externalized_and_non_empty():
    css = load_asset("assets/styles.css")
    javascript = load_asset("assets/app.js")
    assert ".mc{" in css
    assert "function renderModelsFromJSON" in javascript
    assert len(css) > 10_000
    assert len(javascript) > 20_000


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
