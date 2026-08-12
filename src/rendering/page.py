"""使用稳定模板组合生成后的页面片段。"""

from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAGE_TEMPLATE = PROJECT_ROOT / "templates" / "page.html"


def compose_page(header: str, cards: Iterable[str], footer: str) -> str:
    template = PAGE_TEMPLATE.read_text(encoding="utf-8").rstrip("\n")
    return (template
            .replace("{{HEADER}}", header)
            .replace("{{CARDS}}", "\n".join(cards))
            .replace("{{FOOTER}}", footer))
