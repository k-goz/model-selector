from datetime import datetime, timedelta, timezone

from scripts.notify_ci_failure import failure_message
from scripts.notify_ci_status import status_message, transition_alert_state


def test_failure_message_contains_workflow_and_run_url():
    message = failure_message({
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_WORKFLOW": "Deployment Health",
        "GITHUB_RUN_ID": "123",
        "GITHUB_SERVER_URL": "https://github.com",
    })
    assert "Deployment Health" in message
    assert "https://github.com/owner/repo/actions/runs/123" in message


def test_alert_state_deduplicates_failure_inside_cooldown_and_recovers():
    started = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)
    first, decision = transition_alert_state(
        {}, "failure", now=started, cooldown=timedelta(hours=24), summary="stale data"
    )
    assert decision == {"should_notify": True, "should_remediate": True, "is_recovery": False}
    assert first["consecutive_failures"] == 1

    repeated, decision = transition_alert_state(
        first,
        "failure",
        now=started + timedelta(hours=6),
        cooldown=timedelta(hours=24),
        summary="still stale",
    )
    assert decision == {"should_notify": False, "should_remediate": False, "is_recovery": False}
    assert repeated["consecutive_failures"] == 2

    recovered, decision = transition_alert_state(
        repeated,
        "success",
        now=started + timedelta(hours=7),
        cooldown=timedelta(hours=24),
    )
    assert decision == {"should_notify": True, "should_remediate": False, "is_recovery": True}
    assert recovered["consecutive_failures"] == 0


def test_status_message_includes_failure_summary_and_run_url():
    message = status_message(
        "deployment",
        "failure",
        {"consecutive_failures": 3},
        "data is stale",
        {
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "456",
            "GITHUB_SERVER_URL": "https://github.com",
        },
    )
    assert "连续失败: 3 次" in message
    assert "data is stale" in message
    assert "https://github.com/owner/repo/actions/runs/456" in message
