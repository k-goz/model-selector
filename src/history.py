"""生成数据的轻量历史记录工具。"""

from typing import Any, Dict, List


def upsert_daily_history(
    history: List[Dict[str, Any]],
    entry: Dict[str, Any],
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """按日期替换当天数据，保留最近 ``limit`` 个不同日期。"""

    by_date: Dict[str, Dict[str, Any]] = {}
    for item in history:
        if not isinstance(item, dict):
            continue
        date = str(item.get("date") or "").strip()
        if date:
            by_date[date] = item
    date = str(entry.get("date") or "").strip()
    if not date:
        raise ValueError("history entry 缺少 date")
    by_date[date] = entry
    return list(by_date.values())[-limit:]
