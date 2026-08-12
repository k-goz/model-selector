"""平台接口连通性探测与历史发布。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any, Callable, Iterable
import urllib.error
import urllib.request

from src.history import upsert_daily_history


ACCEPTED_HTTP_STATUSES = {400, 401, 402, 403, 429}


def collect_ping_targets(models: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    """每个平台选择一个有模型名和接口地址的代表性目标。"""

    targets: list[dict[str, str]] = []
    seen_platforms: set[str] = set()
    for model in models:
        platform_id = str(model.get("platform_id") or "")
        model_name = str(model.get("name") or "")
        base_url = str(model.get("base_url") or "")
        if not platform_id or not model_name or not base_url or platform_id in seen_platforms:
            continue
        seen_platforms.add(platform_id)
        targets.append({
            "platform_id": platform_id,
            "platform_name": str(model.get("platform_name") or ""),
            "model": model_name,
            "base_url": base_url,
        })
    return targets


def probe_target(
    target: dict[str, str],
    timeout: float = 8,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """测量一个接口的 TTFB；认证类响应仍代表网络可达。"""

    body = json.dumps({
        "model": target["model"],
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
    }).encode()
    request = urllib.request.Request(
        target["base_url"],
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    started_at = clock()
    status = "error"
    milliseconds = -1
    try:
        with opener(request, timeout=timeout) as response:
            response.read(1)
        milliseconds = int((clock() - started_at) * 1000)
        status = "ok"
    except urllib.error.HTTPError as error:
        milliseconds = int((clock() - started_at) * 1000)
        status = "ok" if error.code in ACCEPTED_HTTP_STATUSES else "error"
    except Exception as error:  # 网络库会抛出多种平台相关异常
        if "timed out" in str(error).lower():
            status = "timeout"
        else:
            milliseconds = int((clock() - started_at) * 1000)
    return {
        "platform_id": target["platform_id"],
        "model": target["model"],
        "ms": milliseconds,
        "status": status,
    }


def probe_targets(
    targets: Iterable[dict[str, str]],
    *,
    timeout: float = 8,
    max_workers: int = 8,
    probe: Callable[..., dict[str, Any]] = probe_target,
) -> list[dict[str, Any]]:
    """并发探测目标；单个平台失败不会中断整批结果。"""

    target_list = list(targets)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(probe, target, timeout=timeout) for target in target_list]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                continue
    return results


def update_ping_history(
    models: Iterable[dict[str, Any]],
    history_file: str | Path,
    analysis_file: str | Path,
    *,
    now: datetime | None = None,
    probe: Callable[..., dict[str, Any]] = probe_target,
) -> tuple[int, int]:
    """执行每日探测并写入缓存历史和供网页使用的分析文件。"""

    timestamp = now or datetime.now()
    targets = collect_ping_targets(models)
    results = probe_targets(targets, probe=probe)
    history_path = Path(history_file)
    analysis_path = Path(analysis_file)
    history: list[dict[str, Any]] = []
    if history_path.exists():
        try:
            loaded = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                history = loaded
        except (OSError, json.JSONDecodeError):
            pass

    entry = {
        "date": timestamp.strftime("%Y-%m-%d"),
        "time": timestamp.strftime("%H:%M"),
        "results": sorted(
            results,
            key=lambda result: result.get("ms", 99999) if result.get("ms", -1) > 0 else 99999,
        ),
    }
    history = upsert_daily_history(history, entry, limit=30)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(history, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    analysis_path.write_text(
        json.dumps({
            "meta": {"updated_at": timestamp.strftime("%Y-%m-%d %H:%M"), "days": len(history)},
            "daily": history,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return sum(result.get("status") == "ok" for result in results), len(targets)
