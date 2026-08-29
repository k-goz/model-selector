from datetime import datetime
import json

from src.notifications import build_refresh_message, send_telegram_refresh


def test_refresh_message_lists_changes_and_caps_details():
    changes = [
        {"p": "demo", "n": f"model-{index}", "old_i": 1, "new_i": 2}
        for index in range(7)
    ]
    message = build_refresh_message(10, changes, now=datetime(2026, 8, 30, 1, 20))
    assert "2026-08-30 01:20" in message
    assert "价格变动: 7 个模型" in message
    assert "model-4" in message
    assert "model-5" not in message
    assert "还有 2 个" in message


def test_telegram_boundary_is_optional_and_injectable():
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))

    assert send_telegram_refresh("", "", 1, [], opener=opener) is False
    assert send_telegram_refresh("token", "chat", 1, [], opener=opener) is True
    request, timeout = calls[0]
    assert request.full_url.endswith("/bottoken/sendMessage")
    assert timeout == 10
    assert json.loads(request.data)["chat_id"] == "chat"
