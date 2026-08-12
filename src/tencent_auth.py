"""腾讯控制台抓取器的本地凭证加载工具。"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


def load_tencent_cookies(path: str | Path) -> list[dict[str, Any]]:
    cookie_path = Path(path)
    cookies = json.loads(cookie_path.read_text(encoding="utf-8"))
    if not isinstance(cookies, list) or not cookies:
        raise ValueError("腾讯 Cookie 文件必须是非空 JSON 数组")
    normalized = [dict(cookie) for cookie in cookies if isinstance(cookie, dict)]
    names = {str(cookie.get("name") or "") for cookie in normalized}
    if "uin" not in names:
        raise ValueError("腾讯 Cookie 文件缺少 uin")
    return normalized


def tencent_uin(cookies: list[dict[str, Any]]) -> str:
    value = next((str(cookie.get("value") or "") for cookie in cookies if cookie.get("name") == "uin"), "")
    match = re.search(r"\d+", value)
    if not match:
        raise ValueError("腾讯 uin Cookie 格式无效")
    return match.group(0)
