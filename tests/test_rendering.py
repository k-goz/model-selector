"""前端资源与页面组合回归测试。"""

from src.rendering import compose_page, load_asset


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
