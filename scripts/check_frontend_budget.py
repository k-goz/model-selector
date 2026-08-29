#!/usr/bin/env python3
"""Deterministic frontend size and data-window performance budget."""

from html.parser import HTMLParser
import json
from pathlib import Path


class CardCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "div" and "mc" in dict(attrs).get("class", "").split():
            self.cards += 1


def main() -> int:
    limits = {"index.html": 300_000, "en/index.html": 300_000}
    failures: list[str] = []
    for filename, maximum in limits.items():
        path = Path(filename)
        size = path.stat().st_size
        parser = CardCounter()
        parser.feed(path.read_text(encoding="utf-8"))
        print(f"{filename}: {size} bytes, {parser.cards} embedded cards")
        if size > maximum:
            failures.append(f"{filename} exceeds {maximum} bytes")
        if parser.cards:
            failures.append(f"{filename} embeds {parser.cards} cards")
    scripts = list(Path("assets/js").glob("*.js"))
    script_bytes = sum(path.stat().st_size for path in scripts)
    models = len(json.loads(Path("models_data.json").read_text(encoding="utf-8"))["models"])
    print(f"scripts: {script_bytes} bytes across {len(scripts)} files; catalog: {models} models")
    if script_bytes > 105_000:
        failures.append("JavaScript exceeds 105000 bytes")
    if models < 2_000:
        failures.append("benchmark catalog is unexpectedly small")
    if failures:
        print("Frontend budget failed: " + "; ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
