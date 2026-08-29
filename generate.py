#!/usr/bin/env python3
"""AI 模型选择器命令行入口。"""

from __future__ import annotations

import sys

from src.pipeline import run


def main() -> None:
    """执行模型目录刷新或静态页面重建。"""
    run(__file__, sys.argv)


if __name__ == "__main__":
    main()
