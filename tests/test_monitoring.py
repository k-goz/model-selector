from datetime import datetime
import json
import urllib.error

from src.monitoring import collect_ping_targets, probe_target, update_ping_history


def target(**overrides):
    value = {
        "platform_id": "demo",
        "platform_name": "Demo",
        "name": "demo-chat",
        "base_url": "https://example.com/v1/chat/completions",
    }
    value.update(overrides)
    return value


def test_collects_only_one_valid_target_per_platform():
    models = [
        target(name="first"),
        target(name="second"),
        target(platform_id="other", name="third"),
        target(platform_id="missing-url", base_url=""),
    ]
    assert [item["model"] for item in collect_ping_targets(models)] == ["first", "third"]


def test_authentication_http_error_is_still_reachable():
    def denied(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    result = probe_target(collect_ping_targets([target()])[0], opener=denied, clock=lambda: 1.0)
    assert result["status"] == "ok"
    assert result["ms"] == 0


def test_timeout_has_no_misleading_latency():
    def timed_out(request, timeout):
        raise TimeoutError("timed out")

    result = probe_target(collect_ping_targets([target()])[0], opener=timed_out)
    assert result["status"] == "timeout"
    assert result["ms"] == -1


def test_daily_history_is_replaced_and_published(tmp_path):
    history_file = tmp_path / "cache" / "ping_history.json"
    analysis_file = tmp_path / "ping_analysis.json"
    history_file.parent.mkdir()
    history_file.write_text('[{"date":"2026-08-13","time":"01:00","results":[]}]')

    def fake_probe(item, timeout):
        return {"platform_id": item["platform_id"], "model": item["model"], "ms": 12, "status": "ok"}

    assert update_ping_history(
        [target()], history_file, analysis_file,
        now=datetime(2026, 8, 13, 6, 30), probe=fake_probe,
    ) == (1, 1)
    history = json.loads(history_file.read_text())
    analysis = json.loads(analysis_file.read_text())
    assert len(history) == 1
    assert history[0]["time"] == "06:30"
    assert analysis["meta"] == {"updated_at": "2026-08-13 06:30", "days": 1}
