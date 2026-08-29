import json
from pathlib import Path
import urllib.error

from src.collection.http import CachedHttpClient
from src.collection import catalog as catalog_module
from src.config import API_KEY_ENV, RuntimeConfig
from src.errors import APIFetchError, CacheError, PriceNotFoundError, PriceParseError
from src.platforms.base import FetchMetadata, PlatformFetchResult


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def test_runtime_config_preserves_environment_and_cli_contract(tmp_path):
    env = {name: f"value-{name}" for name in API_KEY_ENV.values()}
    env.update({
        "OUTPUT_FILE": str(tmp_path / "site.html"),
        "CACHE_DIR": str(tmp_path / "cache"),
        "MODELS_JSON": str(tmp_path / "catalog.json"),
        "TELEGRAM_BOT_TOKEN": "bot",
        "TELEGRAM_CHAT_ID": "chat",
        "DEFER_SUCCESS_NOTIFICATION": "1",
    })
    config = RuntimeConfig.from_environment(__file__, ["generate.py", "--refresh"], env)
    assert config.force_refresh is True
    assert config.render_only is False
    assert config.api_keys["deepseek"] == "value-DEEPSEEK_KEY"
    assert config.output_file == tmp_path / "site.html"
    assert config.models_file == tmp_path / "catalog.json"
    assert config.defer_success_notification is True


def test_cached_http_client_writes_and_reuses_json_cache(tmp_path, monkeypatch):
    payload = {"data": [{"id": "model-a"}]}
    client = CachedHttpClient(tmp_path, retries=1)
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse(json.dumps(payload).encode()))
    assert client.fetch_json("https://example.test/models", platform="test") == payload
    assert len(list(tmp_path.glob("*.json"))) == 1

    def fail(*_args, **_kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    assert client.fetch_json("https://example.test/models", platform="test") == payload


def test_domain_errors_keep_safe_diagnostic_context():
    assert "[provider] model" in str(PriceNotFoundError("provider", "model"))
    assert "https://example.test" in str(APIFetchError("provider", "https://example.test", RuntimeError("secret")))
    assert PriceParseError("source", "x" * 500).raw_data == "x" * 200
    assert "缓存读取失败" in str(CacheError("读取", "/tmp/cache"))


def test_catalog_registry_returns_models_and_lineage(tmp_path, monkeypatch):
    class FakePlatform:
        def __init__(self, api_key="", **_kwargs):
            self.api_key = api_key

        def fetch_result(self):
            return PlatformFetchResult(
                models=[{"id": "model-a", "name": "model-a"}],
                metadata=FetchMetadata("fake", "api", "https://example.test/models", "2026-08-30T00:00:00+00:00", 1),
            )

    monkeypatch.setattr(catalog_module, "PLATFORM_CLASSES", {"fake": FakePlatform})
    collection = catalog_module.collect_platform_catalog({"fake": "key"}, tmp_path)
    assert collection["fake"].models[0]["id"] == "model-a"
    assert collection.source_runs["fake"]["source_type"] == "api"
