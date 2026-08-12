#!/usr/bin/env python3
"""检查静态站点可用性、页面完整性与数据新鲜度。"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
from typing import Callable
from urllib.parse import urljoin
from urllib.request import urlopen


Fetcher = Callable[[str, float], tuple[int, str, str]]


def fetch_url(url: str, timeout: float) -> tuple[int, str, str]:
    with urlopen(url, timeout=timeout) as response:
        return response.status, response.headers.get("content-type", ""), response.read().decode("utf-8")


def check_deployment(
    base_url: str,
    *,
    max_age_hours: float = 48,
    timeout: float = 15,
    fetcher: Fetcher = fetch_url,
) -> list[str]:
    base_url = base_url.rstrip("/") + "/"
    errors: list[str] = []
    responses: dict[str, tuple[int, str, str]] = {}
    for path in ("", "en/", "models_data.json"):
        url = urljoin(base_url, path)
        try:
            responses[path] = fetcher(url, timeout)
        except Exception as exc:  # 网络异常需要转为稳定的健康检查结果。
            errors.append(f"{url}: 请求失败: {exc}")

    for path, expected_type in (("", "text/html"), ("en/", "text/html"), ("models_data.json", "application/json")):
        if path not in responses:
            continue
        status, content_type, _ = responses[path]
        url = urljoin(base_url, path)
        if status != 200:
            errors.append(f"{url}: HTTP {status}")
        if expected_type not in content_type:
            errors.append(f"{url}: Content-Type={content_type!r}")

    if "" in responses and "AI 模型选择器" not in responses[""][2]:
        errors.append(f"{base_url}: 中文首页标题缺失")
    if "en/" in responses and "AI Model Selector" not in responses["en/"][2]:
        errors.append(f"{urljoin(base_url, 'en/')}: 英文首页标题缺失")

    if "models_data.json" in responses:
        try:
            data = json.loads(responses["models_data.json"][2])
            models = data.get("models") or []
            meta = data.get("meta") or {}
            if meta.get("total_models") != len(models) or not models:
                errors.append(f"{base_url}: 模型总数元数据不一致")
            updated = datetime.strptime(str(meta.get("updated_at") or ""), "%Y-%m-%d %H:%M")
            age_hours = (datetime.now() - updated).total_seconds() / 3600
            if max_age_hours > 0 and age_hours > max_age_hours:
                errors.append(f"{base_url}: 数据已过期 {age_hours:.1f} 小时")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"{base_url}: models_data.json 无效: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        action="append",
        dest="base_urls",
        help="可重复指定；默认检查 DEPLOYMENT_URL 或 Vercel 主域名",
    )
    parser.add_argument("--max-age-hours", type=float, default=48)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    urls = args.base_urls or [
        os.environ.get("DEPLOYMENT_URL", "https://model.ai-selector.top")
    ]
    errors = [
        error
        for base_url in urls
        for error in check_deployment(
            base_url, max_age_hours=args.max_age_hours, timeout=args.timeout
        )
    ]
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"Deployment health: {len(errors)} errors, {len(urls)} origins")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
