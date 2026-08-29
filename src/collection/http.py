"""Retrying HTTP client with deterministic on-disk JSON cache fallback."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)


class CachedHttpClient:
    def __init__(self, cache_dir: Path, retries: int = 3, timeout: int = 20):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.retries = retries
        self.timeout = timeout

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.md5(url.encode()).hexdigest()}.json"

    def fetch_json(
        self,
        url: str,
        token: str = "",
        timeout: int | None = None,
        retries: int | None = None,
        platform: str = "",
    ) -> Any | None:
        headers = {"User-Agent": "Mozilla/5.0 (ModelSelector/2.0)"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        attempts = retries if retries is not None else self.retries
        for attempt in range(attempts):
            try:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                    raw = response.read()
                data = json.loads(raw)
                try:
                    self._cache_path(url).write_bytes(raw)
                except OSError as error:
                    logger.warning("缓存写入失败: %s - %s", self._cache_path(url), error)
                return data
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                logger.warning(
                    "网络请求失败 (尝试 %d/%d): [%s] %s - %s",
                    attempt + 1,
                    attempts,
                    platform,
                    url,
                    error,
                )
            except json.JSONDecodeError as error:
                logger.error("JSON 解析失败: [%s] %s - %s", platform, url, error)
                break
            except Exception as error:
                logger.error("未知请求错误 (尝试 %d/%d): [%s] %s - %s", attempt + 1, attempts, platform, url, error)
            if attempt < attempts - 1:
                time.sleep(attempt + 1)
        cache_path = self._cache_path(url)
        try:
            logger.info("使用缓存数据: %s", url)
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("API 获取失败且无可用缓存: [%s] %s", platform, url)
            return None

    def fetch_text(self, url: str, timeout: int | None = None, retries: int | None = None) -> str:
        attempts = retries if retries is not None else self.retries
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ModelSelector/2.0)"})
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                    return response.read().decode("utf-8", errors="ignore")
            except Exception as error:
                logger.warning("文本请求失败 (尝试 %d/%d): %s - %s", attempt + 1, attempts, url, error)
                if attempt < attempts - 1:
                    time.sleep(attempt + 1)
        return ""
