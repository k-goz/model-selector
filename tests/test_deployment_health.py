import json

from check_deployment import check_deployment


def healthy_fetcher(url, _timeout):
    if url.endswith("models_data.json"):
        payload = {"meta": {"total_models": 1, "updated_at": "2099-01-01 00:00"}, "models": [{}]}
        return 200, "application/json", json.dumps(payload)
    if url.endswith("/en/"):
        return 200, "text/html; charset=utf-8", "<title>AI Model Selector</title>"
    return 200, "text/html; charset=utf-8", "<title>AI 模型选择器</title>"


def test_healthy_deployment_passes():
    assert check_deployment("https://example.com", fetcher=healthy_fetcher) == []


def test_stale_or_incomplete_deployment_fails():
    def fetcher(url, timeout):
        status, content_type, body = healthy_fetcher(url, timeout)
        if url.endswith("models_data.json"):
            body = json.dumps({"meta": {"total_models": 2, "updated_at": "2020-01-01 00:00"}, "models": [{}]})
        return status, content_type, body

    errors = check_deployment("https://example.com", fetcher=fetcher, max_age_hours=1)
    assert any("模型总数" in error for error in errors)
    assert any("数据已过期" in error for error in errors)


def test_network_failure_is_reported():
    def fetcher(url, _timeout):
        raise OSError(f"offline: {url}")

    errors = check_deployment("https://example.com", fetcher=fetcher)
    assert len(errors) == 3
