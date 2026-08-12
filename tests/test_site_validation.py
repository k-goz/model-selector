"""静态站点门禁测试。"""

from pathlib import Path
import json

from validate_site import validate_page


def test_current_pages_match_published_model_count():
    expected = len(json.loads(Path("models_data.json").read_text(encoding="utf-8"))["models"])
    assert validate_page(Path("index.html"), expected) == []
    assert validate_page(Path("en/index.html"), expected) == []
