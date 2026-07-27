from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = PROJECT_ROOT / ".github/workflows/repository-acceptance.yml"


def workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_workflow_defines_pr_schedule_and_manual_triggers() -> None:
    text = workflow_text()

    assert "pull_request:" in text
    assert 'cron: "0 2 * * 1"' in text
    assert "workflow_dispatch:" in text
    assert "mode:" in text
    assert "repository:" in text


def test_workflow_starts_required_repository_services() -> None:
    text = workflow_text()

    for service in (
        "db",
        "backend",
        "repository-analysis-worker",
        "repository-analysis-recovery",
        "repository-snapshot-cleaner",
    ):
        assert service in text

    assert "/api/v1/utils/health-check/" in text


def test_workflow_selects_smoke_matrix_or_single_repository() -> None:
    text = workflow_text()

    assert "--smoke" in text
    assert "--all" in text
    assert "--repository" in text
    assert "github.event_name" in text
    assert "inputs.mode" in text
    assert "inputs.repository" in text


def test_workflow_always_collects_reports_and_redacted_logs() -> None:
    text = workflow_text()

    assert "if: always()" in text
    assert "artifacts/repository-acceptance" in text
    assert "actions/upload-artifact@v6" in text
    assert "REDACTION_VALUES" in text
    assert "docker compose logs" in text


def test_workflow_uses_required_live_secrets_without_printing_them() -> None:
    text = workflow_text()

    for secret_name in (
        "REPOSITORY_ACCEPTANCE_EMAIL",
        "REPOSITORY_ACCEPTANCE_PASSWORD",
        "REPOSITORY_ACCEPTANCE_GITHUB_TOKEN",
        "LLM_API_KEY",
        "LLM_API_BASE",
        "LLM_MODEL",
        "EMBEDDING_API_KEY",
    ):
        assert f"secrets.{secret_name}" in text

    assert "GITHUB_TOKEN:" in text
    assert "::add-mask::" in text
    assert "set -x" not in text
