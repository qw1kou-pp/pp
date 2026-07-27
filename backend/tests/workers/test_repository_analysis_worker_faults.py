from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.repository_analysis_fault_injection import (
    RepositoryAnalysisFaultPoint,
    RepositoryAnalysisInjectedAbandonment,
)
from app.workers import repository_analysis_worker


class _FakeSession:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> object:
        return object()

    def __exit__(self, *_args: object) -> bool:
        return False


def _build_task(*, attempt_count: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        repository_full_name="psf/requests",
        repository_owner="psf",
        repository_name="requests",
        requested_ref=None,
        attempt_count=attempt_count,
    )


def test_injected_abandonment_exits_without_persisting_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _build_task()
    persisted: list[BaseException] = []

    monkeypatch.setattr(
        repository_analysis_worker,
        "Session",
        _FakeSession,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "claim_next_repository_analysis_task",
        lambda **_kwargs: task,
    )

    injected = RepositoryAnalysisInjectedAbandonment(
        task_id=task.id,
        fault_point=RepositoryAnalysisFaultPoint.SCAN,
        attempt_count=1,
        exit_after_trigger=True,
    )

    def raise_injected(**_kwargs: object) -> None:
        raise injected

    monkeypatch.setattr(
        repository_analysis_worker,
        "process_repository_analysis_task",
        raise_injected,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "_persist_task_failure",
        lambda **kwargs: persisted.append(kwargs["exception"]),
    )

    with pytest.raises(SystemExit) as exc_info:
        repository_analysis_worker.run_repository_analysis_worker_once(
            worker_id="fault-worker",
        )

    assert exc_info.value.code == 86
    assert persisted == []


def test_normal_exception_still_persists_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _build_task()
    persisted: list[BaseException] = []
    expected_error = RuntimeError("normal failure")

    monkeypatch.setattr(
        repository_analysis_worker,
        "Session",
        _FakeSession,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "claim_next_repository_analysis_task",
        lambda **_kwargs: task,
    )

    def raise_normal(**_kwargs: object) -> None:
        raise expected_error

    monkeypatch.setattr(
        repository_analysis_worker,
        "process_repository_analysis_task",
        raise_normal,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "_persist_task_failure",
        lambda **kwargs: persisted.append(kwargs["exception"]),
    )

    with pytest.raises(RuntimeError, match="normal failure"):
        repository_analysis_worker.run_repository_analysis_worker_once(
            worker_id="normal-worker",
        )

    assert persisted == [expected_error]


def test_scan_fault_is_checked_before_repository_scan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task = _build_task(attempt_count=1)
    events: list[str] = []

    def record_fault(**kwargs: object) -> None:
        assert kwargs["task_id"] == task.id
        assert kwargs["attempt_count"] == 1
        assert (
            kwargs["fault_point"]
            is RepositoryAnalysisFaultPoint.SCAN
        )
        events.append("fault")

    def record_scan(repository_root: Path) -> str:
        assert repository_root == tmp_path
        events.append("scan")
        return "scan-result"

    monkeypatch.setattr(
        repository_analysis_worker,
        "maybe_inject_repository_analysis_fault",
        record_fault,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "scan_repository_structure",
        record_scan,
    )

    result = repository_analysis_worker._scan_repository_snapshot(
        task=task,
        repository_root=tmp_path,
    )

    assert result == "scan-result"
    assert events == ["fault", "scan"]


def test_non_exit_injected_abandonment_is_re_raised_without_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _build_task()
    persisted: list[BaseException] = []

    monkeypatch.setattr(
        repository_analysis_worker,
        "Session",
        _FakeSession,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "claim_next_repository_analysis_task",
        lambda **_kwargs: task,
    )

    injected = RepositoryAnalysisInjectedAbandonment(
        task_id=task.id,
        fault_point=RepositoryAnalysisFaultPoint.SCAN,
        attempt_count=1,
        exit_after_trigger=False,
    )

    def raise_injected(**_kwargs: object) -> None:
        raise injected

    monkeypatch.setattr(
        repository_analysis_worker,
        "process_repository_analysis_task",
        raise_injected,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "_persist_task_failure",
        lambda **kwargs: persisted.append(kwargs["exception"]),
    )

    with pytest.raises(RepositoryAnalysisInjectedAbandonment):
        repository_analysis_worker.run_repository_analysis_worker_once(
            worker_id="fault-worker",
        )

    assert persisted == []


class _RecordingHeartbeat:
    def __init__(
        self,
        *,
        task_id: object,
        worker_id: str,
        interval_seconds: float,
        lease_seconds: int,
        events: list[str],
    ) -> None:
        self.task_id = task_id
        self.worker_id = worker_id
        self.interval_seconds = interval_seconds
        self.lease_seconds = lease_seconds
        self.events = events

    def __enter__(self) -> "_RecordingHeartbeat":
        self.events.append("heartbeat-start")
        return self

    def __exit__(self, *_args: object) -> bool:
        self.events.append("heartbeat-stop")
        return False

    def raise_if_failed(self) -> None:
        return None


def test_heartbeat_fault_is_checked_after_claim_before_periodic_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _build_task(attempt_count=1)
    events: list[str] = []

    monkeypatch.setattr(
        repository_analysis_worker,
        "Session",
        _FakeSession,
    )

    def claim_task(**_kwargs: object) -> SimpleNamespace:
        events.append("claim")
        return task

    monkeypatch.setattr(
        repository_analysis_worker,
        "claim_next_repository_analysis_task",
        claim_task,
    )

    def build_heartbeat(**kwargs: object) -> _RecordingHeartbeat:
        return _RecordingHeartbeat(
            task_id=kwargs["task_id"],
            worker_id=str(kwargs["worker_id"]),
            interval_seconds=float(kwargs["interval_seconds"]),
            lease_seconds=int(kwargs["lease_seconds"]),
            events=events,
        )

    monkeypatch.setattr(
        repository_analysis_worker,
        "RepositoryAnalysisHeartbeat",
        build_heartbeat,
    )

    def record_fault(**kwargs: object) -> None:
        assert kwargs["task_id"] == task.id
        assert kwargs["attempt_count"] == 1
        assert (
            kwargs["fault_point"]
            is RepositoryAnalysisFaultPoint.HEARTBEAT
        )
        events.append("fault:heartbeat")

    monkeypatch.setattr(
        repository_analysis_worker,
        "maybe_inject_repository_analysis_fault",
        record_fault,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "process_repository_analysis_task",
        lambda **_kwargs: events.append("process"),
    )

    processed = (
        repository_analysis_worker
        .run_repository_analysis_worker_once(
            worker_id="heartbeat-worker",
        )
    )

    assert processed is True
    assert events == [
        "claim",
        "fault:heartbeat",
        "heartbeat-start",
        "process",
        "heartbeat-stop",
    ]


def test_heartbeat_fault_exits_before_periodic_heartbeat_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _build_task(attempt_count=1)
    events: list[str] = []
    persisted: list[BaseException] = []

    monkeypatch.setattr(
        repository_analysis_worker,
        "Session",
        _FakeSession,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "claim_next_repository_analysis_task",
        lambda **_kwargs: task,
    )

    def build_heartbeat(**kwargs: object) -> _RecordingHeartbeat:
        return _RecordingHeartbeat(
            task_id=kwargs["task_id"],
            worker_id=str(kwargs["worker_id"]),
            interval_seconds=float(kwargs["interval_seconds"]),
            lease_seconds=int(kwargs["lease_seconds"]),
            events=events,
        )

    monkeypatch.setattr(
        repository_analysis_worker,
        "RepositoryAnalysisHeartbeat",
        build_heartbeat,
    )

    def raise_heartbeat_fault(**kwargs: object) -> None:
        if (
            kwargs["fault_point"]
            is RepositoryAnalysisFaultPoint.HEARTBEAT
        ):
            raise RepositoryAnalysisInjectedAbandonment(
                task_id=task.id,
                fault_point=(
                    RepositoryAnalysisFaultPoint.HEARTBEAT
                ),
                attempt_count=1,
                exit_after_trigger=True,
            )

    monkeypatch.setattr(
        repository_analysis_worker,
        "maybe_inject_repository_analysis_fault",
        raise_heartbeat_fault,
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "process_repository_analysis_task",
        lambda **_kwargs: events.append("process"),
    )
    monkeypatch.setattr(
        repository_analysis_worker,
        "_persist_task_failure",
        lambda **kwargs: persisted.append(
            kwargs["exception"]
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        repository_analysis_worker.run_repository_analysis_worker_once(
            worker_id="fault-worker",
        )

    assert exc_info.value.code == 86
    assert events == []
    assert persisted == []
