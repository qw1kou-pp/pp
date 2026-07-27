from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.repository_acceptance.acceptance_models import (
    AcceptanceRunResult,
    AcceptanceStatus,
    AssertionResult,
    AssertionStatus,
    RepositoryCategory,
    RepositoryCase,
    SourceEvidence,
    StageTiming,
)


def test_repository_case_requires_real_github_url_and_questions() -> None:
    case = RepositoryCase(
        key="requests",
        repository_url="https://github.com/psf/requests",
        category=RepositoryCategory.PYTHON,
        smoke=True,
        questions=("这个项目的核心模块是什么？",),
    )

    assert case.repository_full_name == "psf/requests"
    assert case.questions == ("这个项目的核心模块是什么？",)


def test_stage_timing_calculates_duration() -> None:
    started_at = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
    timing = StageTiming(
        name="overview",
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=12.5),
    )

    assert timing.duration_seconds == 12.5


def test_acceptance_result_serializes_nested_data() -> None:
    result = AcceptanceRunResult(
        repository_key="requests",
        repository_url="https://github.com/psf/requests",
        category=RepositoryCategory.PYTHON,
        status=AcceptanceStatus.PASSED,
        resolved_commit_sha="a" * 40,
        sources=[
            SourceEvidence(
                repository_analysis_task_id="task-1",
                repository_relative_path="src/requests/api.py",
                source_commit_sha="a" * 40,
            )
        ],
        assertions=[
            AssertionResult(
                name="commit_present",
                status=AssertionStatus.PASSED,
                message="Commit 已记录",
            )
        ],
    )

    payload = result.to_dict()

    assert payload["category"] == "python"
    assert payload["status"] == "passed"
    assert payload["sources"][0]["repository_relative_path"] == (
        "src/requests/api.py"
    )
    assert payload["assertions"][0]["status"] == "passed"
