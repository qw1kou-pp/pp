from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass

from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.models import (
    RepositoryAnalysisTask,
    get_repository_analysis_expiry,
)


DEFAULT_REPOSITORY_ANALYSIS_LEASE_SECONDS = 90
DEFAULT_REPOSITORY_ANALYSIS_RECOVERY_BATCH_SIZE = 100

FIRST_RETRY_DELAY_SECONDS = 10
SECOND_RETRY_DELAY_SECONDS = 30

LEASE_EXPIRED_RECOVERY_REASON = "lease_expired"
RETRY_LIMIT_REACHED_REASON = "retry_limit_reached"

LEASE_EXPIRED_ERROR_CODE = "worker_lease_expired"
LEASE_EXPIRED_ERROR_MESSAGE = (
    "Worker lost its lease and retry limit was reached"
)

QUEUED_STATUS = "queued"
RUNNING_STATUS = "running"
CLAIMED_STAGE = "claimed"


class RepositoryAnalysisLeaseError(
    RuntimeError,
):
    """
    仓库分析任务租约相关异常的基类。
    """


class RepositoryAnalysisLeaseLostError(
    RepositoryAnalysisLeaseError,
):
    """
    当前 Worker 已经不再拥有任务租约。

    出现这个异常时，旧 Worker 必须停止后续写入，
    不能把任务记录成普通业务失败。
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        task_id: uuid.UUID | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(message)

        self.reason = reason
        self.task_id = task_id
        self.worker_id = worker_id


@dataclass(
    frozen=True,
    slots=True,
)
class RepositoryAnalysisRecoveryReport:
    """
    一轮过期租约恢复结果。
    """

    scanned_count: int
    requeued_task_ids: tuple[uuid.UUID, ...]
    failed_task_ids: tuple[uuid.UUID, ...]

    @property
    def requeued_count(self) -> int:
        return len(self.requeued_task_ids)

    @property
    def failed_count(self) -> int:
        return len(self.failed_task_ids)


def claim_next_repository_analysis_task(
    session: Session,
    *,
    worker_id: str,
    now: datetime | None = None,
    lease_seconds: int = (
        DEFAULT_REPOSITORY_ANALYSIS_LEASE_SECONDS
    ),
) -> RepositoryAnalysisTask | None:
    """
    原子领取下一条可执行的仓库分析任务。

    可领取条件：

    1. status 为 queued；
    2. attempt_count 小于 max_attempts；
    3. next_attempt_at 为空，或者已经到达；
    4. 任务没有被其他事务锁住。

    PostgreSQL 的 FOR UPDATE SKIP LOCKED 可以防止
    多个 Worker 同时领取同一条任务。
    """

    normalized_worker_id = _normalize_worker_id(
        worker_id,
    )

    normalized_lease_seconds = (
        _validate_lease_seconds(
            lease_seconds,
        )
    )

    current_time = _normalize_datetime(
        now or _utc_now(),
    )

    statement = (
        select(RepositoryAnalysisTask)
        .where(
            col(RepositoryAnalysisTask.status)
            == QUEUED_STATUS,
            col(
                RepositoryAnalysisTask
                .attempt_count,
            )
            < col(
                RepositoryAnalysisTask
                .max_attempts,
            ),
            or_(
                col(
                    RepositoryAnalysisTask
                    .next_attempt_at,
                ).is_(None),
                col(
                    RepositoryAnalysisTask
                    .next_attempt_at,
                )
                <= current_time,
            ),
        )
        .order_by(
            col(
                RepositoryAnalysisTask
                .created_at,
            ).asc(),
        )
        .with_for_update(
            skip_locked=True,
        )
        .limit(1)
    )

    try:
        task = session.exec(
            statement,
        ).first()

        if task is None:
            session.rollback()
            return None

        task.status = RUNNING_STATUS
        task.stage = CLAIMED_STAGE
        task.worker_id = normalized_worker_id

        task.attempt_count = (
            int(task.attempt_count or 0)
            + 1
        )

        task.heartbeat_at = current_time

        task.lease_expires_at = (
            current_time
            + timedelta(
                seconds=(
                    normalized_lease_seconds
                ),
            )
        )

        task.next_attempt_at = None

        if getattr(
            task,
            "started_at",
            None,
        ) is None:
            task.started_at = current_time

        _set_updated_at(
            task,
            current_time,
        )

        session.add(task)
        session.commit()
        session.refresh(task)

        return task

    except Exception:
        session.rollback()
        raise


def assert_repository_analysis_lease(
    session: Session,
    *,
    task_id: uuid.UUID,
    worker_id: str,
    now: datetime | None = None,
) -> RepositoryAnalysisTask:
    """
    验证当前 Worker 是否仍然拥有任务租约。

    该函数会对任务行加锁，适合在更新进度、完成任务、
    保存失败结果之前调用。

    调用成功后，不会自动提交事务。调用方修改任务后，
    需要自行 commit 或 rollback。
    """

    normalized_worker_id = _normalize_worker_id(
        worker_id,
    )

    current_time = _normalize_datetime(
        now or _utc_now(),
    )

    statement = (
        select(RepositoryAnalysisTask)
        .where(
            col(RepositoryAnalysisTask.id)
            == task_id,
        )
        .with_for_update()
        .limit(1)
    )

    task = session.exec(
        statement,
    ).first()

    if task is None:
        raise RepositoryAnalysisLeaseLostError(
            (
                "Repository analysis task "
                "does not exist"
            ),
            reason="task_not_found",
            task_id=task_id,
            worker_id=normalized_worker_id,
        )

    status = _status_value(
        task.status,
    )

    if status != RUNNING_STATUS:
        raise RepositoryAnalysisLeaseLostError(
            (
                "Repository analysis task "
                f"is not running: {status!r}"
            ),
            reason="task_not_running",
            task_id=task_id,
            worker_id=normalized_worker_id,
        )

    task_worker_id = str(
        task.worker_id or "",
    ).strip()

    if (
        task_worker_id
        != normalized_worker_id
    ):
        raise RepositoryAnalysisLeaseLostError(
            (
                "Repository analysis task "
                "belongs to another worker"
            ),
            reason="worker_mismatch",
            task_id=task_id,
            worker_id=normalized_worker_id,
        )

    raw_lease_expires_at = getattr(
        task,
        "lease_expires_at",
        None,
    )

    if raw_lease_expires_at is None:
        raise RepositoryAnalysisLeaseLostError(
            (
                "Repository analysis task "
                "does not have an active lease"
            ),
            reason="lease_missing",
            task_id=task_id,
            worker_id=normalized_worker_id,
        )

    lease_expires_at = _normalize_datetime(
        raw_lease_expires_at,
    )

    if lease_expires_at <= current_time:
        raise RepositoryAnalysisLeaseLostError(
            (
                "Repository analysis task "
                "lease has expired"
            ),
            reason="lease_expired",
            task_id=task_id,
            worker_id=normalized_worker_id,
        )

    return task


def renew_repository_analysis_lease(
    session: Session,
    *,
    task_id: uuid.UUID,
    worker_id: str,
    now: datetime | None = None,
    lease_seconds: int = (
        DEFAULT_REPOSITORY_ANALYSIS_LEASE_SECONDS
    ),
) -> RepositoryAnalysisTask:
    """
    续租仓库分析任务。

    只有满足以下条件时才可以续租：

    1. 任务存在；
    2. status 为 running；
    3. worker_id 与当前 Worker 一致；
    4. 原租约尚未过期。

    续租成功后：

    heartbeat_at = 当前时间
    lease_expires_at = 当前时间 + lease_seconds
    """

    normalized_worker_id = _normalize_worker_id(
        worker_id,
    )

    normalized_lease_seconds = (
        _validate_lease_seconds(
            lease_seconds,
        )
    )

    current_time = _normalize_datetime(
        now or _utc_now(),
    )

    try:
        task = assert_repository_analysis_lease(
            session,
            task_id=task_id,
            worker_id=normalized_worker_id,
            now=current_time,
        )

        task.heartbeat_at = current_time

        task.lease_expires_at = (
            current_time
            + timedelta(
                seconds=(
                    normalized_lease_seconds
                ),
            )
        )

        _set_updated_at(
            task,
            current_time,
        )

        session.add(task)
        session.commit()
        session.refresh(task)

        return task

    except Exception:
        session.rollback()
        raise


def recover_expired_repository_analysis_leases(
    session: Session,
    *,
    now: datetime | None = None,
    batch_size: int = (
        DEFAULT_REPOSITORY_ANALYSIS_RECOVERY_BATCH_SIZE
    ),
) -> RepositoryAnalysisRecoveryReport:
    """
    恢复已经超过租约时间的 running 任务。

    可继续重试：
    → 回到 queued
    → 清除当前 Worker 所有权
    → 设置 next_attempt_at

    已达到最大尝试次数：
    → 标记 failed
    → 返回 failed_task_ids
    → 由 Recovery Worker 在事务提交后清理快照
    """

    normalized_batch_size = int(batch_size)

    if normalized_batch_size <= 0:
        raise ValueError(
            "batch_size must be greater than zero",
        )

    normalized_batch_size = min(
        normalized_batch_size,
        1000,
    )

    current_time = _normalize_datetime(
        now or _utc_now(),
    )

    statement = (
        select(RepositoryAnalysisTask)
        .where(
            col(
                RepositoryAnalysisTask.status,
            )
            == RUNNING_STATUS,
            col(
                RepositoryAnalysisTask
                .lease_expires_at,
            ).is_not(None),
            col(
                RepositoryAnalysisTask
                .lease_expires_at,
            )
            <= current_time,
        )
        .order_by(
            col(
                RepositoryAnalysisTask
                .lease_expires_at,
            ).asc(),
            col(
                RepositoryAnalysisTask.id,
            ).asc(),
        )
        .with_for_update(
            skip_locked=True,
        )
        .limit(normalized_batch_size)
    )

    requeued_task_ids: list[uuid.UUID] = []
    failed_task_ids: list[uuid.UUID] = []

    try:
        tasks = list(
            session.exec(statement).all(),
        )

        if not tasks:
            session.rollback()

            return RepositoryAnalysisRecoveryReport(
                scanned_count=0,
                requeued_task_ids=(),
                failed_task_ids=(),
            )

        for task in tasks:
            attempt_count = int(
                task.attempt_count or 0,
            )

            max_attempts = int(
                task.max_attempts or 3,
            )

            if attempt_count < max_attempts:
                _requeue_expired_task(
                    task,
                    current_time=current_time,
                    attempt_count=attempt_count,
                )

                requeued_task_ids.append(
                    task.id,
                )

            else:
                _fail_expired_task(
                    task,
                    current_time=current_time,
                )

                failed_task_ids.append(
                    task.id,
                )

            session.add(task)

        session.commit()

    except Exception:
        session.rollback()
        raise

    return RepositoryAnalysisRecoveryReport(
        scanned_count=len(tasks),
        requeued_task_ids=tuple(
            requeued_task_ids,
        ),
        failed_task_ids=tuple(
            failed_task_ids,
        ),
    )


def _requeue_expired_task(
    task: RepositoryAnalysisTask,
    *,
    current_time: datetime,
    attempt_count: int,
) -> None:
    """
    将仍可重试的失联任务重新放回队列。
    """

    retry_delay = retry_delay_for_attempt(
        attempt_count,
    )

    task.status = QUEUED_STATUS
    task.stage = QUEUED_STATUS
    task.progress_percent = 0

    task.worker_id = None
    task.claimed_at = None
    task.heartbeat_at = None
    task.lease_expires_at = None

    task.next_attempt_at = (
        current_time
        + retry_delay
    )

    task.last_recovery_reason = (
        LEASE_EXPIRED_RECOVERY_REASON
    )

    task.error_code = None
    task.error_message = None

    _set_updated_at(
        task,
        current_time,
    )


def _fail_expired_task(
    task: RepositoryAnalysisTask,
    *,
    current_time: datetime,
) -> None:
    """
    将已经达到最大尝试次数的失联任务标记为失败。
    """

    task.status = "failed"
    task.stage = "failed"

    task.worker_id = None
    task.heartbeat_at = None
    task.lease_expires_at = None
    task.next_attempt_at = None

    task.error_code = (
        LEASE_EXPIRED_ERROR_CODE
    )

    task.error_message = (
        LEASE_EXPIRED_ERROR_MESSAGE
    )

    task.last_recovery_reason = (
        RETRY_LIMIT_REACHED_REASON
    )

    task.completed_at = current_time

    _set_updated_at(
        task,
        current_time,
    )


def retry_delay_for_attempt(
    attempt_count: int,
) -> timedelta:
    """
    根据已经执行的次数计算下一次重试等待时间。

    attempt_count 表示已经领取执行过多少次：
    1 → 等待 10 秒
    2 → 等待 30 秒
    """

    normalized_attempt_count = int(
        attempt_count or 0,
    )

    if normalized_attempt_count <= 1:
        return timedelta(
            seconds=FIRST_RETRY_DELAY_SECONDS,
        )

    return timedelta(
        seconds=SECOND_RETRY_DELAY_SECONDS,
    )


def _normalize_worker_id(
    worker_id: str,
) -> str:
    """
    检查并标准化 Worker ID。
    """

    normalized = str(
        worker_id or "",
    ).strip()

    if not normalized:
        raise ValueError(
            "worker_id must not be empty",
        )

    if len(normalized) > 200:
        raise ValueError(
            (
                "worker_id must not exceed "
                "200 characters"
            ),
        )

    return normalized


def _validate_lease_seconds(
    lease_seconds: int,
) -> int:
    """
    验证租约时长。
    """

    try:
        normalized = int(
            lease_seconds,
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "lease_seconds must be an integer",
        ) from exc

    if normalized <= 0:
        raise ValueError(
            (
                "lease_seconds must be "
                "greater than zero"
            ),
        )

    return normalized


def _set_updated_at(
    task: RepositoryAnalysisTask,
    current_time: datetime,
) -> None:
    """
    兼容有 updated_at 字段和没有该字段的模型。
    """

    if hasattr(
        task,
        "updated_at",
    ):
        task.updated_at = current_time


def _status_value(
    status: Any,
) -> str:
    """
    同时兼容字符串状态和 Enum 状态。
    """

    enum_value = getattr(
        status,
        "value",
        status,
    )

    return str(
        enum_value or "",
    ).strip()


def _normalize_datetime(
    value: datetime,
) -> datetime:
    """
    把时间统一转换成 UTC 时区时间。

    部分测试数据库可能返回无时区 datetime，
    因此也进行兼容处理。
    """

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc,
        )

    return value.astimezone(
        timezone.utc,
    )


def _utc_now() -> datetime:
    """
    获取带 UTC 时区的当前时间。
    """

    return datetime.now(
        timezone.utc,
    )