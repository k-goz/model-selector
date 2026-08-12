from scripts.notify_ci_failure import failure_message


def test_failure_message_contains_workflow_and_run_url():
    message = failure_message({
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_WORKFLOW": "Deployment Health",
        "GITHUB_RUN_ID": "123",
        "GITHUB_SERVER_URL": "https://github.com",
    })
    assert "Deployment Health" in message
    assert "https://github.com/owner/repo/actions/runs/123" in message
