from pathlib import Path


WORKFLOWS = Path(".github/workflows")


def test_refresh_entry_owns_schedule_manual_trigger_and_concurrency():
    entry = (WORKFLOWS / "refresh-model-data.yml").read_text(encoding="utf-8")
    reusable = (WORKFLOWS / "update-models.yml").read_text(encoding="utf-8")
    assert "schedule:" in entry
    assert "workflow_dispatch:" in entry
    assert "production-model-data-refresh-v2" in entry
    assert "contents: write" in entry
    assert "uses: ./.github/workflows/update-models.yml" in entry
    assert "workflow_call:" in reusable
    assert "schedule:" not in reusable
    assert "workflow_dispatch:" not in reusable


def test_vercel_is_the_only_production_deployment_path():
    names = {path.name for path in WORKFLOWS.glob("*.yml")}
    assert "deploy-aliyun.yml" not in names
    health = (WORKFLOWS / "deployment-health.yml").read_text(encoding="utf-8")
    assert "https://model.ai-selector.top" in health
    assert "ai-model-selector-eight.vercel.app" not in health
    assert "notify_ci_status.py" in health
    assert "Trigger one recovery refresh" in health
