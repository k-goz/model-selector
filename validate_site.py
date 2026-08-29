#!/usr/bin/env python3
"""生成站点静态门禁：DOM、模型数量、URL 与脚本结构。"""

from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from urllib.parse import urlparse


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.cards = 0
        self.card_names = 0
        self.invalid_urls: list[str] = []
        self.inline_scripts = 0
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        classes = set(str(values.get("class") or "").split())
        if tag == "div" and "mc" in classes:
            self.cards += 1
        if tag == "div" and "mname" in classes:
            self.card_names += 1
        if tag == "script" and not values.get("src"):
            self.inline_scripts += 1
            self._in_script = True
        for key in ("href", "src", "data-base-url"):
            value = values.get(key)
            if not value or value.startswith(("#", "./", "../", "data:")):
                continue
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                self.invalid_urls.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False


def validate_page(page_path: Path, expected_models: int) -> list[str]:
    parser = SiteParser()
    source = page_path.read_text(encoding="utf-8")
    parser.feed(source)
    errors: list[str] = []
    duplicates = [item for item, count in Counter(parser.ids).items() if count > 1]
    if duplicates:
        errors.append(f"{page_path}: 重复 DOM id: {', '.join(duplicates[:10])}")
    if parser.cards != 0:
        errors.append(f"{page_path}: 数据驱动页面仍内嵌 {parser.cards} 个模型卡片")
    if parser.card_names != parser.cards:
        errors.append(f"{page_path}: {parser.cards - parser.card_names} 个卡片缺少模型名节点")
    if parser.invalid_urls:
        errors.append(f"{page_path}: 非法 URL: {parser.invalid_urls[:5]}")
    if parser.inline_scripts < 1:
        errors.append(f"{page_path}: 没有浏览器交互脚本")
    if "renderModelsFromJSON" not in source or "models_data.json" not in source:
        errors.append(f"{page_path}: 缺少数据驱动目录加载器")
    if "<noscript>" not in source:
        errors.append(f"{page_path}: 缺少无 JavaScript 基础说明")
    return errors


def main() -> int:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--models", type=Path, default=Path("models_data.json"))
    arg_parser.add_argument("pages", nargs="*", type=Path, default=[Path("index.html"), Path("en/index.html")])
    args = arg_parser.parse_args()
    models = json.loads(args.models.read_text(encoding="utf-8")).get("models", [])
    errors = [error for page in args.pages for error in validate_page(page, len(models))]
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"Site quality: {len(errors)} errors, {len(args.pages)} pages, {len(models)} models")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
