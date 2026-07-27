from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from tests.repository_acceptance.acceptance_matrix_runner import (
    AcceptanceMatrixRunner,
)
from tests.repository_acceptance.acceptance_models import (
    AcceptanceRunResult,
    AcceptanceStatus,
    RepositoryCase,
    RepositoryCategory,
    SourceEvidence,
)


@dataclass
class FakeRepositoryRunner:
    results: dict[str, AcceptanceRunResult]

    def run(self, case: RepositoryCase) -> AcceptanceRunResult:
        return self.results[case.key]


def make_case(key: str) -> RepositoryCase:
    return RepositoryCase(
        key=key,
        repository_url=f"https://github.com/example/{key}",
        category=RepositoryCategory.PYTHON,
        smoke=True,
        questions=("入口是什么？",),
    )


def make_result(key: str, index: int) -> AcceptanceRunResult:
    task_id = f"task-{index}"
    return AcceptanceRunResult(
        repository_key=key,
        repository_url=f"https://github.com/example/{key}",
        category=RepositoryCategory.PYTHON,
        status=AcceptanceStatus.PASSED,
        resolved_commit_sha=str(index) * 40,
        repository_analysis_task_id=task_id,
        knowledge_base_id=f"kb-{index}",
        sources=[
            SourceEvidence(
                repository_analysis_task_id=task_id,
                repository_relative_path=f"src/{key}.py",
                source_commit_sha=str(index) * 40,
                document_id=f"doc-{index}",
                chunk_id=f"chunk-{index}",
            )
        ],
        metadata={"documents": [{"id": f"doc-{index}"}]},
    )


def test_matrix_runner_runs_cases_and_checks_pairwise_isolation() -> None:
    cases = (make_case("one"), make_case("two"), make_case("three"))
    fake = FakeRepositoryRunner(
        results={
            case.key: make_result(case.key, index)
            for index, case in enumerate(cases, start=1)
        }
    )
    moments = iter(
        [
            datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 27, 8, 5, tzinfo=timezone.utc),
        ]
    )

    result = AcceptanceMatrixRunner(
        repository_runner=fake,
        now=lambda: next(moments),
    ).run(cases)

    assert result.status is AcceptanceStatus.PASSED
    assert [run.repository_key for run in result.runs] == [
        "one",
        "two",
        "three",
    ]
    assert len(result.isolation_assertions) == 3
    assert all(
        assertion.status.value == "passed"
        for assertion in result.isolation_assertions
    )
    assert result.duration_seconds == 300.0


def test_matrix_runner_fails_when_any_repository_run_fails() -> None:
    case = make_case("failed")
    failed = make_result("failed", 1)
    failed.status = AcceptanceStatus.FAILED

    result = AcceptanceMatrixRunner(
        repository_runner=FakeRepositoryRunner({"failed": failed}),
    ).run((case,))

    assert result.status is AcceptanceStatus.FAILED
