#!/usr/bin/env python3
"""在 GitHub Actions 失败时发送可选 Telegram 通知。"""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


def failure_message(env: dict[str, str]) -> str:
    repository = env.get("GITHUB_REPOSITORY", "model-selector")
    workflow = env.get("GITHUB_WORKFLOW", "CI")
    run_id = env.get("GITHUB_RUN_ID", "")
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if run_id else ""
    return "\n".join(filter(None, [
        "❌ AI 模型选择器自动任务失败",
        f"工作流: {workflow}",
        f"仓库: {repository}",
        run_url,
    ]))


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Telegram secrets not configured; failure notification skipped")
        return 0
    payload = json.dumps({
        "chat_id": chat_id,
        "text": failure_message(dict(os.environ)),
        "disable_web_page_preview": True,
    }).encode()
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=10):
        pass
    print("Failure notification sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
