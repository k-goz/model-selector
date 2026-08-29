#!/usr/bin/env python3
"""为 CI 故障提供去重、恢复通知和自愈冷却状态。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def transition_alert_state(
    previous: dict[str, Any],
    status: str,
    *,
    now: datetime,
    cooldown: timedelta,
    summary: str = "",
) -> tuple[dict[str, Any], dict[str, bool]]:
    """计算本次是否通知/自愈；相同故障在冷却期内只记录不重复发送。"""

    prior_status = str(previous.get("status") or "unknown")
    state = dict(previous)
    state["status"] = status
    state["checked_at"] = now.isoformat()
    state["last_summary"] = summary[-2000:]
    decision = {"should_notify": False, "should_remediate": False, "is_recovery": False}

    if status == "failure":
        state["consecutive_failures"] = int(previous.get("consecutive_failures") or 0) + 1
        if prior_status != "failure":
            state["first_failed_at"] = now.isoformat()
        last_notified = _parse_time(previous.get("last_notified_at"))
        last_remediated = _parse_time(previous.get("last_remediated_at"))
        decision["should_notify"] = prior_status != "failure" or not last_notified or now - last_notified >= cooldown
        decision["should_remediate"] = prior_status != "failure" or not last_remediated or now - last_remediated >= cooldown
        if decision["should_notify"]:
            state["last_notified_at"] = now.isoformat()
        if decision["should_remediate"]:
            state["last_remediated_at"] = now.isoformat()
    else:
        decision["is_recovery"] = prior_status == "failure"
        decision["should_notify"] = decision["is_recovery"]
        state["consecutive_failures"] = 0
        if decision["is_recovery"]:
            state["recovered_at"] = now.isoformat()

    return state, decision


def status_message(kind: str, status: str, state: dict[str, Any], summary: str, env: dict[str, str]) -> str:
    labels = {"deployment": "生产部署健康检查", "refresh": "模型数据刷新"}
    repository = env.get("GITHUB_REPOSITORY", "k-goz/model-selector")
    run_id = env.get("GITHUB_RUN_ID", "")
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if run_id else ""
    if status == "failure":
        title = "❌ AI 模型选择器自动任务失败"
        detail = f"连续失败: {state.get('consecutive_failures', 1)} 次"
    else:
        title = "✅ AI 模型选择器自动任务已恢复"
        detail = "故障状态已关闭"
    lines = [title, f"任务: {labels.get(kind, kind)}", detail]
    if summary:
        lines.append("摘要: " + " ".join(summary.strip().split())[-800:])
    if run_url:
        lines.append(run_url)
    return "\n".join(lines)


def send_telegram(message: str, env: dict[str, str]) -> bool:
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Telegram secrets not configured; notification skipped")
        return False
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }).encode()
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=10):
            pass
    except Exception as error:  # 通知失败不能覆盖原始任务结论
        print(f"Telegram notification failed: {type(error).__name__}")
        return False
    print("Telegram status notification sent")
    return True


def _write_outputs(decision: dict[str, bool]) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    with Path(output_file).open("a", encoding="utf-8") as handle:
        for key, value in decision.items():
            handle.write(f"{key}={str(value).lower()}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("deployment", "refresh"), required=True)
    parser.add_argument("--status", choices=("success", "failure"), required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--summary-file", type=Path)
    parser.add_argument("--cooldown-hours", type=float, default=24)
    args = parser.parse_args()

    summary = ""
    if args.summary_file and args.summary_file.exists():
        summary = args.summary_file.read_text(encoding="utf-8", errors="replace")
    now = datetime.now(timezone.utc)
    state, decision = transition_alert_state(
        load_state(args.state_file),
        args.status,
        now=now,
        cooldown=timedelta(hours=args.cooldown_hours),
        summary=summary,
    )
    args.state_file.parent.mkdir(parents=True, exist_ok=True)
    args.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_outputs(decision)
    if decision["should_notify"]:
        send_telegram(status_message(args.kind, args.status, state, summary, dict(os.environ)), dict(os.environ))
    else:
        print("Alert unchanged inside cooldown; notification skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
