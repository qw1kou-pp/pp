from __future__ import annotations

from uuid import uuid4

import pytest

from app.services import repository_analysis_fault_injection as fault_injection


def _configure_fault(
    monkeypatch: pytest.MonkeyPatch,
    *,
    task_id: str,
    point: str,
    mode: str,
    enabled: bool = True,
    exit_after_trigger: bool = True,
) -> None:
    monkeypatch.setattr(
        fault_injection.settings,
        "REPOSITORY_ANALYSIS_FAULT_INJECTION_ENABLED",
        enabled,
    )
    monkeypatch.setattr(
        fault_injection.settings,
        "REPOSITORY_ANALYSIS_FAULT_TASK_ID",
        task_id,
    )
    monkeypatch.setattr(
        fault_injection.settings,
        "REPOSITORY_ANALYSIS_FAULT_POINT",
        point,
    )
    monkeypatch.setattr(
        fault_injection.settings,
        "REPOSITORY_ANALYSIS_FAULT_MODE",
        mode,
    )
    monkeypatch.setattr(
        fault_injection.settings,
        "REPOSITORY_ANALYSIS_FAULT_EXIT_AFTER_TRIGGER",
        exit_after_trigger,
    )


def test_fault_injection_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        fault_injection.settings,
        "REPOSITORY_ANALYSIS_FAULT_INJECTION_ENABLED",
        False,
    )

    fault_injection.maybe_inject_repository_analysis_fault(
        task_id=uuid4(),
        attempt_count=1,
        fault_point=fault_injection.RepositoryAnalysisFaultPoint.SCAN,
    )


def test_fault_injection_ignores_other_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_task_id = uuid4()
    _configure_fault(
        monkeypatch,
        task_id=str(target_task_id),
        point="scan",
        mode="raise_always",
    )

    fault_injection.maybe_inject_repository_analysis_fault(
        task_id=uuid4(),
        attempt_count=1,
        fault_point=fault_injection.RepositoryAnalysisFaultPoint.SCAN,
    )


def test_raise_once_only_triggers_on_first_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id = uuid4()
    _configure_fault(
        monkeypatch,
        task_id=str(task_id),
        point="scan",
        mode="raise_once",
    )

    with pytest.raises(
        fault_injection.RepositoryAnalysisInjectedAbandonment
    ) as exc_info:
        fault_injection.maybe_inject_repository_analysis_fault(
            task_id=task_id,
            attempt_count=1,
            fault_point=fault_injection.RepositoryAnalysisFaultPoint.SCAN,
        )

    assert exc_info.value.task_id == task_id
    assert exc_info.value.attempt_count == 1
    assert exc_info.value.exit_after_trigger is True

    fault_injection.maybe_inject_repository_analysis_fault(
        task_id=task_id,
        attempt_count=2,
        fault_point=fault_injection.RepositoryAnalysisFaultPoint.SCAN,
    )


def test_raise_always_triggers_on_every_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id = uuid4()
    _configure_fault(
        monkeypatch,
        task_id=str(task_id),
        point="scan",
        mode="raise_always",
    )

    for attempt_count in (1, 2, 3):
        with pytest.raises(
            fault_injection.RepositoryAnalysisInjectedAbandonment
        ):
            fault_injection.maybe_inject_repository_analysis_fault(
                task_id=task_id,
                attempt_count=attempt_count,
                fault_point=fault_injection.RepositoryAnalysisFaultPoint.SCAN,
            )


def test_fault_injection_ignores_other_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id = uuid4()
    _configure_fault(
        monkeypatch,
        task_id=str(task_id),
        point="heartbeat",
        mode="raise_always",
    )

    fault_injection.maybe_inject_repository_analysis_fault(
        task_id=task_id,
        attempt_count=1,
        fault_point=fault_injection.RepositoryAnalysisFaultPoint.SCAN,
    )


def test_invalid_configuration_is_safe_and_warns(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    task_id = uuid4()
    _configure_fault(
        monkeypatch,
        task_id="not-a-uuid",
        point="not-a-point",
        mode="not-a-mode",
    )

    fault_injection.maybe_inject_repository_analysis_fault(
        task_id=task_id,
        attempt_count=1,
        fault_point=fault_injection.RepositoryAnalysisFaultPoint.SCAN,
    )

    assert (
        "Invalid repository analysis fault injection configuration"
        in caplog.text
    )
