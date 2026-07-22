from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models import RepositoryAnalysisTask


DEFAULT_FAILED_RETENTION_HOURS = 0
DEFAULT_SAVED_RETENTION_HOURS = 168
DEFAULT_ORPHAN_GRACE_HOURS = 6
DEFAULT_CLEANUP_BATCH_SIZE = 100

_CLEANABLE_TASK_STATUSES = {
    "completed",
    "failed",
    "expired",
}

_WORKSPACE_NAME_PATTERN = re.compile(
    r"^[0-9a-fA-F-]{36}-.+",
)


class RepositorySnapshotLifecycleError(
    RuntimeError,
):
    """仓库快照生命周期基础异常。"""


class UnsafeRepositorySnapshotPathError(
    RepositorySnapshotLifecycleError,
):
    """快照路径不在允许的根目录中。"""


class RepositorySnapshotOwnershipError(
    RepositorySnapshotLifecycleError,
):
    """快照目录与任务 ID 不匹配。"""


@dataclass(frozen=True, slots=True)
class RepositorySnapshotRetentionPolicy:
    """
    仓库快照保留策略。

    failed_retention：
    失败任务在多长时间后清理，默认立即清理。

    saved_retention：
    保存过的快速概览保留快照的时间。
    快照删除后仍然可以根据固定 Commit 重新下载。

    orphan_grace：
    孤儿目录的安全等待时间，防止误删正在下载、
    但数据库路径还没来得及写入的目录。
    """

    failed_retention: timedelta
    saved_retention: timedelta
    orphan_grace: timedelta

    @classmethod
    def from_environment(
        cls,
    ) -> RepositorySnapshotRetentionPolicy:
        return cls(
            failed_retention=timedelta(
                hours=_read_non_negative_float(
                    "REPOSITORY_SNAPSHOT_FAILED_RETENTION_HOURS",
                    DEFAULT_FAILED_RETENTION_HOURS,
                ),
            ),
            saved_retention=timedelta(
                hours=_read_non_negative_float(
                    "REPOSITORY_SNAPSHOT_SAVED_RETENTION_HOURS",
                    DEFAULT_SAVED_RETENTION_HOURS,
                ),
            ),
            orphan_grace=timedelta(
                hours=_read_non_negative_float(
                    "REPOSITORY_SNAPSHOT_ORPHAN_GRACE_HOURS",
                    DEFAULT_ORPHAN_GRACE_HOURS,
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class RepositorySnapshotCleanupAction:
    """一次任务快照清理结果。"""

    task_id: str
    repository_full_name: str

    reason: str

    storage_path: str | None
    workspace_path: str | None

    deleted: bool
    reference_cleared: bool
    dry_run: bool

    error: str | None = None


@dataclass(frozen=True, slots=True)
class RepositorySnapshotSweepReport:
    """一次完整清理扫描的统计结果。"""

    started_at: str
    finished_at: str

    task_candidates: int
    task_snapshots_deleted: int
    task_references_cleared: int

    orphan_candidates: int
    orphan_directories_deleted: int

    dry_run: bool

    actions: tuple[
        RepositorySnapshotCleanupAction,
        ...
    ]

    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "actions": [
                asdict(item)
                for item in self.actions
            ],
            "errors": list(self.errors),
        }


def get_repository_snapshot_root(
    snapshot_root: Path | str | None = None,
) -> Path:
    """
    获取仓库快照根目录。

    优先顺序：

    1. 函数参数；
    2. REPOSITORY_SNAPSHOT_ROOT；
    3. 系统临时目录。
    """

    configured_root = (
        snapshot_root
        or os.getenv(
            "REPOSITORY_SNAPSHOT_ROOT",
            "",
        ).strip()
        or (
            Path(tempfile.gettempdir())
            / "repoguard-repository-snapshots"
        )
    )

    root = Path(
        configured_root,
    ).resolve()

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    return root


def resolve_repository_snapshot_workspace(
    storage_path: Path | str,
    *,
    task_id: uuid.UUID | str | None = None,
    snapshot_root: Path | str | None = None,
) -> Path:
    """
    根据数据库中的 repository_root 路径找到对应工作目录。

    数据库里可能保存：

    /data/repository-snapshots/
      <task-id>-abc123/
        extracted/
          owner-repository-sha/

    真正需要删除的是：

    <task-id>-abc123/
    """

    root = get_repository_snapshot_root(
        snapshot_root,
    )

    raw_path = str(
        storage_path or "",
    ).strip()

    if not raw_path:
        raise UnsafeRepositorySnapshotPathError(
            "Snapshot storage path is empty",
        )

    candidate = Path(
        raw_path,
    ).resolve(
        strict=False,
    )

    try:
        relative_path = candidate.relative_to(
            root,
        )
    except ValueError as exc:
        raise UnsafeRepositorySnapshotPathError(
            "Snapshot path is outside the configured root",
        ) from exc

    if not relative_path.parts:
        raise UnsafeRepositorySnapshotPathError(
            "Snapshot root itself cannot be deleted",
        )

    workspace_name = relative_path.parts[0]

    workspace = (
        root / workspace_name
    ).resolve(
        strict=False,
    )

    if workspace.parent != root:
        raise UnsafeRepositorySnapshotPathError(
            "Snapshot workspace is not a direct child "
            "of the configured root",
        )

    if not _WORKSPACE_NAME_PATTERN.fullmatch(
        workspace.name,
    ):
        raise UnsafeRepositorySnapshotPathError(
            "Snapshot workspace name is not recognized",
        )

    if task_id is not None:
        normalized_task_id = str(
            task_id,
        )

        if not workspace.name.startswith(
            f"{normalized_task_id}-",
        ):
            raise RepositorySnapshotOwnershipError(
                "Snapshot workspace does not belong "
                "to the requested task",
            )

    return workspace


def determine_snapshot_cleanup_reason(
    task: RepositoryAnalysisTask,
    *,
    current_time: datetime | None = None,
    policy: RepositorySnapshotRetentionPolicy | None = None,
) -> str | None:
    """
    判断一个任务的快照当前是否应该清理。

    返回 None 表示继续保留。
    """

    now = _normalize_datetime(
        current_time or _utc_now(),
    )

    effective_policy = (
        policy
        or RepositorySnapshotRetentionPolicy
        .from_environment()
    )

    status = _status_value(
        task.status,
    )

    if status == "failed":
        reference_time = _first_datetime(
            getattr(
                task,
                "finished_at",
                None,
            ),
            getattr(
                task,
                "updated_at",
                None,
            ),
            getattr(
                task,
                "created_at",
                None,
            ),
        )

        if reference_time is None:
            return "failed_task"

        if (
            reference_time
            + effective_policy.failed_retention
            <= now
        ):
            return "failed_task"

        return None

    if status == "expired":
        return "expired_task"

    if status != "completed":
        return None

    saved_at = getattr(
        task,
        "saved_at",
        None,
    )

    is_saved = bool(
        getattr(
            task,
            "is_saved",
            False,
        )
        or saved_at is not None
    )

    if is_saved:
        retention_start = _first_datetime(
            saved_at,
            getattr(
                task,
                "finished_at",
                None,
            ),
            getattr(
                task,
                "updated_at",
                None,
            ),
        )

        if retention_start is None:
            return None

        if (
            retention_start
            + effective_policy.saved_retention
            <= now
        ):
            return "saved_snapshot_retention_elapsed"

        return None

    expires_at = getattr(
        task,
        "expires_at",
        None,
    )

    if expires_at is None:
        return None

    if _normalize_datetime(expires_at) <= now:
        return "unsaved_task_expired"

    return None


def cleanup_repository_analysis_task_snapshot(
    *,
    session: Session,
    task_id: uuid.UUID,
    snapshot_root: Path | str | None = None,
    policy: RepositorySnapshotRetentionPolicy | None = None,
    force_reason: str | None = None,
    dry_run: bool = False,
) -> RepositorySnapshotCleanupAction:
    """
    清理一个任务对应的仓库快照。

    默认会先根据任务状态判断是否允许清理。

    force_reason 只用于已经明确完成状态转换的内部流程，
    例如 Worker 已经把任务写成 failed 后立即清理。
    """

    task = session.get(
        RepositoryAnalysisTask,
        task_id,
    )

    if task is None:
        return RepositorySnapshotCleanupAction(
            task_id=str(task_id),
            repository_full_name="",
            reason=(
                force_reason
                or "task_not_found"
            ),
            storage_path=None,
            workspace_path=None,
            deleted=False,
            reference_cleared=False,
            dry_run=dry_run,
            error="Repository analysis task was not found",
        )

    repository_full_name = str(
        task.repository_full_name or "",
    )

    storage_path = str(
        task.snapshot_storage_path or "",
    ).strip()

    reason = (
        force_reason
        or determine_snapshot_cleanup_reason(
            task,
            policy=policy,
        )
    )

    if reason is None:
        return RepositorySnapshotCleanupAction(
            task_id=str(task.id),
            repository_full_name=(
                repository_full_name
            ),
            reason="retained",
            storage_path=storage_path or None,
            workspace_path=None,
            deleted=False,
            reference_cleared=False,
            dry_run=dry_run,
        )

    if not storage_path:
        return RepositorySnapshotCleanupAction(
            task_id=str(task.id),
            repository_full_name=(
                repository_full_name
            ),
            reason=reason,
            storage_path=None,
            workspace_path=None,
            deleted=False,
            reference_cleared=False,
            dry_run=dry_run,
        )

    workspace = (
        resolve_repository_snapshot_workspace(
            storage_path,
            task_id=task.id,
            snapshot_root=snapshot_root,
        )
    )

    if dry_run:
        return RepositorySnapshotCleanupAction(
            task_id=str(task.id),
            repository_full_name=(
                repository_full_name
            ),
            reason=reason,
            storage_path=storage_path,
            workspace_path=str(workspace),
            deleted=False,
            reference_cleared=False,
            dry_run=True,
        )

    workspace_existed = workspace.exists()

    if workspace_existed:
        if workspace.is_symlink():
            raise UnsafeRepositorySnapshotPathError(
                "Snapshot workspace cannot be a symbolic link",
            )

        if not workspace.is_dir():
            raise UnsafeRepositorySnapshotPathError(
                "Snapshot workspace is not a directory",
            )

        shutil.rmtree(workspace)

    current_time = _utc_now()

    task.snapshot_storage_path = None

    if reason in {
        "expired_task",
        "unsaved_task_expired",
    }:
        task.status = "expired"
        task.stage = "expired"

    result_payload = dict(
        task.result_json or {},
    )

    result_payload[
        "snapshot_lifecycle"
    ] = {
        "available": False,
        "cleaned_at": (
            current_time.isoformat()
        ),
        "reason": reason,
        "original_storage_path": (
            storage_path
        ),
        "redownload_available": bool(
            task.resolved_commit_sha
        ),
    }

    task.result_json = result_payload

    if hasattr(
        task,
        "updated_at",
    ):
        task.updated_at = current_time

    try:
        session.add(task)
        session.commit()
        session.refresh(task)
    except Exception:
        session.rollback()
        raise

    return RepositorySnapshotCleanupAction(
        task_id=str(task.id),
        repository_full_name=(
            repository_full_name
        ),
        reason=reason,
        storage_path=storage_path,
        workspace_path=str(workspace),
        deleted=workspace_existed,
        reference_cleared=True,
        dry_run=False,
    )


def sweep_repository_snapshots(
    *,
    session: Session,
    snapshot_root: Path | str | None = None,
    policy: RepositorySnapshotRetentionPolicy | None = None,
    batch_size: int = DEFAULT_CLEANUP_BATCH_SIZE,
    dry_run: bool = False,
) -> RepositorySnapshotSweepReport:
    """
    执行一次完整的仓库快照清理。

    先处理数据库中有引用的任务快照，
    再处理数据库没有引用的孤儿目录。
    """

    if batch_size <= 0:
        raise ValueError(
            "batch_size must be greater than zero",
        )

    started_at = _utc_now()

    effective_policy = (
        policy
        or RepositorySnapshotRetentionPolicy
        .from_environment()
    )

    root = get_repository_snapshot_root(
        snapshot_root,
    )

    statement = (
        select(RepositoryAnalysisTask)
        .where(
            RepositoryAnalysisTask
            .snapshot_storage_path
            .is_not(None),
            RepositoryAnalysisTask.status.in_(
                tuple(
                    _CLEANABLE_TASK_STATUSES,
                ),
            ),
        )
        .limit(batch_size)
    )

    tasks = list(
        session.exec(statement).all(),
    )

    actions: list[
        RepositorySnapshotCleanupAction
    ] = []

    errors: list[str] = []

    task_candidates = 0
    task_snapshots_deleted = 0
    task_references_cleared = 0

    for task in tasks:
        reason = determine_snapshot_cleanup_reason(
            task,
            current_time=started_at,
            policy=effective_policy,
        )

        if reason is None:
            continue

        task_candidates += 1

        try:
            action = (
                cleanup_repository_analysis_task_snapshot(
                    session=session,
                    task_id=task.id,
                    snapshot_root=root,
                    policy=effective_policy,
                    force_reason=reason,
                    dry_run=dry_run,
                )
            )
        except Exception as exc:
            error_text = (
                f"Task {task.id}: "
                f"{type(exc).__name__}: {exc}"
            )

            errors.append(error_text)

            actions.append(
                RepositorySnapshotCleanupAction(
                    task_id=str(task.id),
                    repository_full_name=str(
                        task.repository_full_name
                        or "",
                    ),
                    reason=reason,
                    storage_path=str(
                        task.snapshot_storage_path
                        or "",
                    )
                    or None,
                    workspace_path=None,
                    deleted=False,
                    reference_cleared=False,
                    dry_run=dry_run,
                    error=error_text,
                ),
            )

            continue

        actions.append(action)

        if action.deleted:
            task_snapshots_deleted += 1

        if action.reference_cleared:
            task_references_cleared += 1

    (
        orphan_candidates,
        orphan_directories_deleted,
        orphan_errors,
    ) = _cleanup_orphan_snapshot_directories(
        session=session,
        snapshot_root=root,
        current_time=started_at,
        orphan_grace=(
            effective_policy.orphan_grace
        ),
        dry_run=dry_run,
    )

    errors.extend(orphan_errors)

    finished_at = _utc_now()

    return RepositorySnapshotSweepReport(
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        task_candidates=task_candidates,
        task_snapshots_deleted=(
            task_snapshots_deleted
        ),
        task_references_cleared=(
            task_references_cleared
        ),
        orphan_candidates=orphan_candidates,
        orphan_directories_deleted=(
            orphan_directories_deleted
        ),
        dry_run=dry_run,
        actions=tuple(actions),
        errors=tuple(errors),
    )


def _cleanup_orphan_snapshot_directories(
    *,
    session: Session,
    snapshot_root: Path,
    current_time: datetime,
    orphan_grace: timedelta,
    dry_run: bool,
) -> tuple[int, int, list[str]]:
    """
    清理没有任何数据库任务引用的工作目录。

    只删除符合 task-id-random 格式的直接子目录。
    """

    referenced_paths = session.exec(
        select(
            RepositoryAnalysisTask
            .snapshot_storage_path,
        ).where(
            RepositoryAnalysisTask
            .snapshot_storage_path
            .is_not(None),
        ),
    ).all()

    referenced_workspaces: set[Path] = set()

    for storage_path in referenced_paths:
        if not storage_path:
            continue

        try:
            workspace = (
                resolve_repository_snapshot_workspace(
                    storage_path,
                    snapshot_root=snapshot_root,
                )
            )
        except RepositorySnapshotLifecycleError:
            continue

        referenced_workspaces.add(
            workspace,
        )

    orphan_candidates = 0
    orphan_directories_deleted = 0
    errors: list[str] = []

    try:
        children = list(
            snapshot_root.iterdir(),
        )
    except OSError as exc:
        return (
            0,
            0,
            [
                (
                    f"Unable to inspect snapshot root: "
                    f"{type(exc).__name__}: {exc}"
                ),
            ],
        )

    for child in children:
        try:
            if child.is_symlink():
                continue

            if not child.is_dir():
                continue

            resolved_child = child.resolve()

            if resolved_child.parent != snapshot_root:
                continue

            if not _WORKSPACE_NAME_PATTERN.fullmatch(
                child.name,
            ):
                continue

            if (
                resolved_child
                in referenced_workspaces
            ):
                continue

            modified_at = datetime.fromtimestamp(
                child.stat().st_mtime,
                tz=timezone.utc,
            )

            if (
                modified_at + orphan_grace
                > current_time
            ):
                continue

            orphan_candidates += 1

            if dry_run:
                continue

            shutil.rmtree(resolved_child)

            orphan_directories_deleted += 1

        except Exception as exc:
            errors.append(
                (
                    f"Orphan directory {child}: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    return (
        orphan_candidates,
        orphan_directories_deleted,
        errors,
    )


def _status_value(
    value: Any,
) -> str:
    enum_value = getattr(
        value,
        "value",
        value,
    )

    return str(
        enum_value or "",
    ).strip()


def _first_datetime(
    *values: Any,
) -> datetime | None:
    for value in values:
        if isinstance(value, datetime):
            return _normalize_datetime(
                value,
            )

    return None


def _normalize_datetime(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc,
        )

    return value.astimezone(
        timezone.utc,
    )


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc,
    )


def _read_non_negative_float(
    environment_name: str,
    default_value: float,
) -> float:
    raw_value = os.getenv(
        environment_name,
        "",
    ).strip()

    if not raw_value:
        return float(default_value)

    try:
        parsed_value = float(raw_value)
    except ValueError as exc:
        raise ValueError(
            (
                f"{environment_name} must be "
                "a valid number"
            ),
        ) from exc

    if parsed_value < 0:
        raise ValueError(
            (
                f"{environment_name} must not "
                "be negative"
            ),
        )

    return parsed_value