"""刷新任务通知边界。"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from typing import Any, Callable, Mapping, Sequence
import urllib.request

logger = logging.getLogger(__name__)


def build_refresh_message(
    total_models: int,
    changes: Sequence[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> str:
    """构建不依赖 Telegram Markdown 的刷新摘要。"""
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")
    lines = [
        "✅ 模型数据每日更新",
        f"⏰ {timestamp}",
        f"📊 模型总数: {total_models}",
        "",
    ]
    if changes:
        lines.append(f"🔔 价格变动: {len(changes)} 个模型")
        for change in changes[:5]:
            platform = change["p"]
            model = change["n"]
            old_input = float(change.get("old_i", 0) or 0)
            new_input = float(change.get("new_i", 0) or 0)
            if old_input == 0:
                trend = "🆕 新增"
            else:
                percentage = ((new_input - old_input) / old_input) * 100
                trend = f"📈 +{percentage:.1f}%" if percentage > 0 else f"📉 {percentage:.1f}%"
            lines.extend(
                [
                    f"  • {model} ({platform})",
                    f"    ¥{old_input:.4f} → ¥{new_input:.4f} {trend}",
                ]
            )
        if len(changes) > 5:
            lines.append(f"  ... 还有 {len(changes) - 5} 个")
    else:
        lines.append("✨ 价格无变动")
    lines.extend(["", "🌐 https://model.ai-selector.top"])
    return "\n".join(lines)


def send_telegram_refresh(
    bot_token: str,
    chat_id: str,
    total_models: int,
    changes: Sequence[Mapping[str, Any]],
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> bool:
    """发送刷新摘要；未配置或网络失败时返回 False。"""
    if not bot_token or not chat_id:
        return False
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": build_refresh_message(total_models, changes),
            "disable_web_page_preview": True,
        }
    ).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        opener(request, timeout=10)
    except Exception as error:  # 通知失败不得覆盖刷新结果
        logger.warning("Telegram notification failed: %s", error)
        return False
    logger.info("Telegram notification sent")
    return True
