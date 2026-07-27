from __future__ import annotations

from tests.repository_acceptance.acceptance_assertions import (
    assert_commit_present,
    assert_sources_match_scope,
)
from tests.repository_acceptance.acceptance_models import (
    AssertionStatus,
    SourceEvidence,
)


def test_commit_assertion_fails_for_missing_commit() -> None:
    result = assert_commit_present(None)

    assert result.status is AssertionStatus.FAILED
    assert result.code == "COMMIT_MISSING"


def test_sources_match_expected_task_and_commit() -> None:
    sources = [
        SourceEvidence(
            repository_analysis_task_id="task-a",
            repository_relative_path="backend/app/main.py",
            source_commit_sha="b" * 40,
        )
    ]

    result = assert_sources_match_scope(
        sources=sources,
        expected_task_id="task-a",
        expected_commit_sha="b" * 40,
        assertion_name="rag_sources_scope",
    )

    assert result.status is AssertionStatus.PASSED


def test_sources_fail_when_another_task_leaks() -> None:
    sources = [
        SourceEvidence(
            repository_analysis_task_id="task-b",
            repository_relative_path="frontend/src/main.tsx",
            source_commit_sha="c" * 40,
        )
    ]

    result = assert_sources_match_scope(
        sources=sources,
        expected_task_id="task-a",
        expected_commit_sha="c" * 40,
        assertion_name="agent_sources_scope",
    )

    assert result.status is AssertionStatus.FAILED
    assert result.code == "SOURCE_TASK_SCOPE_MISMATCH"
