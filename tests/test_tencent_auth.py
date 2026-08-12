import json

import pytest

from src.tencent_auth import load_tencent_cookies, tencent_uin


def test_loads_local_cookie_file_and_derives_uin(tmp_path):
    path = tmp_path / "cookies.json"
    path.write_text(json.dumps([
        {"name": "uin", "value": "o123456", "domain": ".cloud.tencent.com", "path": "/"},
        {"name": "skey", "value": "secret", "domain": ".cloud.tencent.com", "path": "/"},
    ]), encoding="utf-8")
    cookies = load_tencent_cookies(path)
    assert tencent_uin(cookies) == "123456"


def test_cookie_file_requires_uin(tmp_path):
    path = tmp_path / "cookies.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_tencent_cookies(path)
