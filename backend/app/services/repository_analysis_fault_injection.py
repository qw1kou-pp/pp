from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)


class RepositoryAnalysisFaultPoint(StrEnum):
    """受控故障可以触发的仓库分析阶段。"""

    SCAN = "scan"
    HEARTBEAT = "heartbeat"


class RepositoryAnalysisFaultMode(StrEnum):
    """决定故障在哪些领取次数触发。"""

    RAISE_ONCE = "raise_once"
    RAISE_ALWAYS = "raise_always"


class RepositoryAnalysisInjectedAbandonment(RuntimeError):
    """模拟 Worker 突然中断，但不把任务持久化为普通失败。"""

    def __init__(
        self,
        *,
        task_id: UUID,
        fault_point: RepositoryAnalysisFaultPoint,
        attempt_count: int,
        exit_after_trigger: bool,
    ) -> None:
        super().__init__(
            "Injected repository analysis abandonment "
            f"task_id={task_id} "
            f"fault_point={fault_point.value} "
            f"attempt_count={attempt_count}"
        )
        self.task_id = task_id
        self.fault_point = fault_point
        self.attempt_count = attempt_count
        self.exit_after_trigger = exit_after_trigger


@dataclass(frozen=True, slots=True)
class RepositoryAnalysisFaultConfig:
    """当前 Worker 进程已经校验过的故障配置。"""

    enabled: bool
    task_id: UUID | None
    point: RepositoryAnalysisFaultPoint | None
    mode: RepositoryAnalysisFaultMode | None
    exit_after_trigger: bool
    valid: bool


def _parse_optional_uuid(value: str | None) -> UUID | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return UUID(normalized)
    except ValueError:
        return None


def _parse_optional_fault_point(
    value: str | None,
) -> RepositoryAnalysisFaultPoint | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    try:
        return RepositoryAnalysisFaultPoint(normalized)
    except ValueError:
        return None


def _parse_optional_fault_mode(
    value: str | None,
) -> RepositoryAnalysisFaultMode | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    try:
        return RepositoryAnalysisFaultMode(normalized)
    except ValueError:
        return None


def get_repository_analysis_fault_config() -> RepositoryAnalysisFaultConfig:
    """从应用 Settings 中读取并校验故障注入配置。"""

    enabled = bool(
        settings.REPOSITORY_ANALYSIS_FAULT_INJECTION_ENABLED
    )
    task_id = _parse_optional_uuid(
        settings.REPOSITORY_ANALYSIS_FAULT_TASK_ID
    )
    point = _parse_optional_fault_point(
        settings.REPOSITORY_ANALYSIS_FAULT_POINT
    )
    mode = _parse_optional_fault_mode(
        settings.REPOSITORY_ANALYSIS_FAULT_MODE
    )
    valid = (
        not enabled
        or (
            task_id is not None
            and point is not None
            and mode is not None
        )
    )

    if enabled and not valid:
        logger.warning(
            "Invalid repository analysis fault injection configuration",
            extra={
                "fault_task_id_configured": bool(
                    str(
                        settings.REPOSITORY_ANALYSIS_FAULT_TASK_ID
                        or ""
                    ).strip()
                ),
                "fault_point": (
                    settings.REPOSITORY_ANALYSIS_FAULT_POINT
                ),
                "fault_mode": (
                    settings.REPOSITORY_ANALYSIS_FAULT_MODE
                ),
            },
        )

    return RepositoryAnalysisFaultConfig(
        enabled=enabled,
        task_id=task_id,
        point=point,
        mode=mode,
        exit_after_trigger=bool(
            settings.REPOSITORY_ANALYSIS_FAULT_EXIT_AFTER_TRIGGER
        ),
        valid=valid,
    )


def maybe_inject_repository_analysis_fault(
    *,
    task_id: UUID,
    attempt_count: int,
    fault_point: RepositoryAnalysisFaultPoint,
) -> None:
    """仅对配置中精确匹配的任务和阶段触发放弃异常。"""

    config = get_repository_analysis_fault_config()

    if not config.enabled or not config.valid:
        return
    if config.task_id != task_id:
        return
    if config.point is not fault_point:
        return
    if (
        config.mode is RepositoryAnalysisFaultMode.RAISE_ONCE
        and attempt_count != 1
    ):
        return

    raise RepositoryAnalysisInjectedAbandonment(
        task_id=task_id,
        fault_point=fault_point,
        attempt_count=attempt_count,
        exit_after_trigger=config.exit_after_trigger,
    )
