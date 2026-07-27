from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from typing import Protocol

from tests.repository_acceptance.acceptance_assertions import (
    assert_runs_are_isolated,
)
from tests.repository_acceptance.acceptance_models import (
    AcceptanceRunResult,
    AcceptanceStatus,
    AssertionResult,
    AssertionStatus,
    RepositoryCase,
)


class RepositoryRunner(Protocol):
    def run(self, case: RepositoryCase) -> AcceptanceRunResult: ...


@dataclass(slots=True)
class AcceptanceMatrixResult:
    status: AcceptanceStatus
    started_at: datetime
    finished_at: datetime
    runs: list[AcceptanceRunResult] = field(default_factory=list)
    isolation_assertions: list[AssertionResult] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return max(
            0.0,
            (self.finished_at - self.started_at).total_seconds(),
        )

    @property
    def passed_count(self) -> int:
        return sum(
            run.status is AcceptanceStatus.PASSED for run in self.runs
        )

    @property
    def failed_count(self) -> int:
        return len(self.runs) - self.passed_count


class AcceptanceMatrixRunner:
    """顺序执行仓库验收矩阵，并验证任意两次运行相互隔离。"""

    def __init__(
        self,
        *,
        repository_runner: RepositoryRunner,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository_runner = repository_runner
        self._now = now or (lambda: datetime.now(timezone.utc))

    def run(
        self,
        cases: Sequence[RepositoryCase],
    ) -> AcceptanceMatrixResult:
        if not cases:
            raise ValueError("acceptance matrix must contain at least one case")

        started_at = self._now()
        runs = [self.repository_runner.run(case) for case in cases]
        isolation_assertions = [
            assert_runs_are_isolated(left=left, right=right)
            for left, right in combinations(runs, 2)
        ]
        finished_at = self._now()

        repositories_passed = all(
            run.status is AcceptanceStatus.PASSED for run in runs
        )
        isolation_passed = all(
            assertion.status is AssertionStatus.PASSED
            for assertion in isolation_assertions
        )

        return AcceptanceMatrixResult(
            status=(
                AcceptanceStatus.PASSED
                if repositories_passed and isolation_passed
                else AcceptanceStatus.FAILED
            ),
            started_at=started_at,
            finished_at=finished_at,
            runs=runs,
            isolation_assertions=isolation_assertions,
        )
