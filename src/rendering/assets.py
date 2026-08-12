"""读取源代码仓库中的前端资源。"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_asset(relative_path: str) -> str:
    path = PROJECT_ROOT / relative_path
    return path.read_text(encoding="utf-8") + "\n"
