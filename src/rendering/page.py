"""使用稳定模板组合生成后的页面片段。"""

from pathlib import Path
import re
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAGE_TEMPLATE = PROJECT_ROOT / "templates" / "page.html"
PLACEHOLDER = re.compile(r"{{([A-Z][A-Z0-9_]*)}}")


def render_template(relative_path: str, values: dict[str, object] | None = None) -> str:
    """渲染受控 HTML 片段，并拒绝漏传或多传变量。"""

    template = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    values = values or {}
    required = set(PLACEHOLDER.findall(template))
    supplied = set(values)
    missing = required - supplied
    unexpected = supplied - required
    if missing:
        raise ValueError(f"模板缺少变量: {', '.join(sorted(missing))}")
    if unexpected:
        raise ValueError(f"模板存在未使用变量: {', '.join(sorted(unexpected))}")
    return PLACEHOLDER.sub(lambda match: str(values[match.group(1)]), template)


def compose_page(header: str, cards: Iterable[str], footer: str) -> str:
    return render_template("templates/page.html", {
        "HEADER": header,
        "CARDS": "\n".join(cards),
        "FOOTER": footer,
    }).rstrip("\n")
