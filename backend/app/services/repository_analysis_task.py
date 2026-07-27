from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, update
from sqlmodel import Session, col, select

from app.models import (
    RepositoryAnalysisTask,
    RepositoryAnalysisTaskCreate,
    RepositoryAnalysisTaskPublic,
    RepositoryAnalysisTasksPublic,
    RepositoryAnalysisTaskSummaryPublic,
    get_datetime_utc,
    get_repository_analysis_expiry,
)
from app.services.github_repository_reference import (
    GitHubRepositoryReference,
)
from app.services.repository_analysis_lease import (
    RepositoryAnalysisLeaseLostError,
    assert_repository_analysis_lease,
    claim_next_repository_analysis_task as claim_with_lease,
)


VALID_TASK_STATUSES = {
    "queued",
    "running",
    "completed",
    "failed",
    "expired",
}

VALID_TASK_STAGES = {
    "queued",
    "claimed",
    "fetching_metadata",
    "resolving_commit",
    "downloading_snapshot",
    "scanning_repository",
    "analyzing_code",
    "tracing_backend_flows",
    "tracing_frontend_flows",
    "building_evidence",
    "generating_report",
    "completed",
    "failed",
    "expired",
}

VALID_REPORT_LANGUAGES = {
    "zh-CN",
    "en-US",
}


def normalize_report_language(
    report_language: str,
) -> str:
    """
    规范化报告语言。

    当前第一版支持中文和英文，避免数据库中出现
    zh、ZH-cn、chinese 等多种含义相同的值。
    """

    normalized_language = str(
        report_language or "zh-CN",
    ).strip()

    if normalized_language not in VALID_REPORT_LANGUAGES:
        raise ValueError(
            f"Unsupported report language: "
            f"{normalized_language}",
        )

    return normalized_language


def validate_task_stage(
    stage: str,
) -> str:
    """
    检查 Worker 上报的任务阶段是否合法。
    """

    normalized_stage = str(stage or "").strip()

    if normalized_stage not in VALID_TASK_STAGES:
        raise ValueError(
            f"Unsupported repository analysis stage: "
            f"{normalized_stage}",
        )

    return normalized_stage


def validate_progress_percent(
    progress_percent: int,
) -> int:
    """
    把任务进度限制在 0～100。
    """

    normalized_progress = int(progress_percent)

    if not 0 <= normalized_progress <= 100:
        raise ValueError(
            "progress_percent must be between 0 and 100",
        )

    return normalized_progress


def serialize_repository_analysis_task_summary(
    task: RepositoryAnalysisTask,
) -> RepositoryAnalysisTaskSummaryPublic:
    """
    将数据库任务转换为列表页使用的轻量响应。

    不返回 Evidence、Markdown 和仓库快照路径，
    防止列表接口一次返回大量数据。
    """

    return RepositoryAnalysisTaskSummaryPublic(
        id=task.id,
        repository_full_name=task.repository_full_name,
        canonical_url=task.canonical_url,
        analysis_mode=task.analysis_mode,
        status=task.status,
        stage=task.stage,
        progress_percent=task.progress_percent,
        is_saved=task.is_saved,
        knowledge_base_id=task.knowledge_base_id,
        error_code=task.error_code,
        error_message=task.error_message,
        expires_at=task.expires_at,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


def serialize_repository_analysis_task_detail(
    task: RepositoryAnalysisTask,
) -> RepositoryAnalysisTaskPublic:
    """
    将数据库任务转换为详情响应。

    详情接口才会返回结果 JSON、Evidence 和 Markdown。
    snapshot_storage_path、worker_id 等内部字段不对外暴露。
    """

    return RepositoryAnalysisTaskPublic(
        id=task.id,
        repository_full_name=task.repository_full_name,
        canonical_url=task.canonical_url,
        analysis_mode=task.analysis_mode,
        status=task.status,
        stage=task.stage,
        progress_percent=task.progress_percent,
        is_saved=task.is_saved,
        knowledge_base_id=task.knowledge_base_id,
        error_code=task.error_code,
        error_message=task.error_message,
        expires_at=task.expires_at,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        source_url=task.source_url,
        repository_owner=task.repository_owner,
        repository_name=task.repository_name,
        requested_ref=task.requested_ref,
        default_branch=task.default_branch,
        resolved_commit_sha=task.resolved_commit_sha,
        report_language=task.report_language,
        result_json=task.result_json,
        evidence_json=task.evidence_json,
        report_markdown=task.report_markdown,
        updated_at=task.updated_at,
    )


def create_repository_analysis_task(
    *,
    session: Session,
    owner_id: uuid.UUID,
    request: RepositoryAnalysisTaskCreate,
    repository: GitHubRepositoryReference,
) -> RepositoryAnalysisTask:
    """
    创建一条待处理仓库分析任务。

    URL 解析在进入本函数前完成。本函数只负责：
    1. 构造数据库对象；
    2. 设置初始状态；
    3. 提交事务。
    """

    task = RepositoryAnalysisTask(
        owner_id=owner_id,
        source_url=request.repository_url.strip(),
        canonical_url=repository.canonical_url,
        repository_owner=repository.owner,
        repository_name=repository.name,
        repository_full_name=repository.repository,
        analysis_mode="overview",
        report_language=normalize_report_language(
            request.report_language,
        ),
        status="queued",
        stage="queued",
        progress_percent=0,
        attempt_count=0,
        is_saved=False,
    )

    try:
        session.add(task)
        session.commit()
        session.refresh(task)
    except Exception:
        session.rollback()
        raise

    return task


def get_repository_analysis_task(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
) -> RepositoryAnalysisTask | None:
    """
    查询属于当前用户的一条任务。

    必须同时按照 task_id 和 owner_id 查询，不能只使用 task_id。
    这能避免用户通过猜测 UUID 查看其他用户的分析报告。
    """

    statement = select(
        RepositoryAnalysisTask,
    ).where(
        RepositoryAnalysisTask.id == task_id,
        RepositoryAnalysisTask.owner_id == owner_id,
    )

    return session.exec(statement).first()


def get_repository_analysis_task_detail(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
) -> RepositoryAnalysisTaskPublic | None:
    """
    查询并序列化一条任务详情。
    """

    task = get_repository_analysis_task(
        session=session,
        owner_id=owner_id,
        task_id=task_id,
    )

    if task is None:
        return None

    return serialize_repository_analysis_task_detail(task)


def list_repository_analysis_tasks(
    *,
    session: Session,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
) -> RepositoryAnalysisTasksPublic:
    """
    分页查询当前用户的仓库分析任务。

    最大 limit 限制为 100，防止一次查询过多任务。
    """

    safe_skip = max(
        int(skip),
        0,
    )

    safe_limit = min(
        max(
            int(limit),
            1,
        ),
        100,
    )

    filters: list[Any] = [
        RepositoryAnalysisTask.owner_id == owner_id,
    ]

    if status:
        normalized_status = status.strip().lower()

        if normalized_status not in VALID_TASK_STATUSES:
            raise ValueError(
                f"Unsupported repository analysis status: "
                f"{normalized_status}",
            )

        filters.append(
            RepositoryAnalysisTask.status
            == normalized_status,
        )

    count_statement = select(
        func.count(
            RepositoryAnalysisTask.id,
        )
    ).where(
        *filters,
    )

    total_count = int(
        session.exec(count_statement).one()
    )

    query_statement = (
        select(
            RepositoryAnalysisTask,
        )
        .where(
            *filters,
        )
        .order_by(
            col(
                RepositoryAnalysisTask.created_at,
            ).desc(),
            col(
                RepositoryAnalysisTask.id,
            ).desc(),
        )
        .offset(safe_skip)
        .limit(safe_limit)
    )

    tasks = list(
        session.exec(query_statement).all()
    )

    return RepositoryAnalysisTasksPublic(
        data=[
            serialize_repository_analysis_task_summary(
                task,
            )
            for task in tasks
        ],
        count=total_count,
    )


def claim_next_repository_analysis_task(
    *,
    session: Session,
    worker_id: str,
) -> RepositoryAnalysisTask | None:
    """
    兼容现有 Worker 调用的任务领取入口。

    实际的原子领取、最大尝试次数检查和 90 秒租约创建，
    统一交给 repository_analysis_lease 服务处理。
    """

    return claim_with_lease(
        session=session,
        worker_id=worker_id,
    )


def get_claimed_repository_analysis_task(
    *,
    session: Session,
    task_id: uuid.UUID,
    worker_id: str,
) -> RepositoryAnalysisTask | None:
    """
    兼容旧调用方的运行中任务查询入口。

    新代码应直接调用 assert_repository_analysis_lease()，
    以便获得具体的租约丢失原因。该兼容函数仍维持
    “找不到或不再拥有任务时返回 None”的旧行为。
    """

    try:
        return assert_repository_analysis_lease(
            session,
            task_id=task_id,
            worker_id=worker_id,
        )
    except RepositoryAnalysisLeaseLostError:
        session.rollback()
        return None


def update_repository_analysis_progress(
    *,
    session: Session,
    task_id: uuid.UUID,
    worker_id: str,
    stage: str,
    progress_percent: int,
) -> RepositoryAnalysisTask:
    """
    更新当前 Worker 的执行阶段和进度。

    写入前必须验证任务仍属于当前 Worker，且租约尚未过期。
    心跳时间和租约到期时间只由独立心跳服务维护。
    """

    normalized_stage = validate_task_stage(stage)

    normalized_progress = validate_progress_percent(
        progress_percent,
    )

    if normalized_stage in {
        "completed",
        "failed",
        "expired",
    }:
        raise ValueError(
            "Terminal stages must use their dedicated "
            "transition functions",
        )

    current_time = get_datetime_utc()

    try:
        task = assert_repository_analysis_lease(
            session,
            task_id=task_id,
            worker_id=worker_id,
            now=current_time,
        )

        task.stage = normalized_stage
        task.progress_percent = normalized_progress
        task.updated_at = current_time

        session.add(task)
        session.commit()
        session.refresh(task)
    except Exception:
        session.rollback()
        raise

    return task


def update_repository_resolution_metadata(
    *,
    session: Session,
    task_id: uuid.UUID,
    worker_id: str,
    requested_ref: str,
    default_branch: str,
    resolved_commit_sha: str,
) -> RepositoryAnalysisTask:
    """
    保存 GitHub 默认分支和固定 Commit。

    写入前必须验证任务仍属于当前 Worker，且租约尚未过期。
    """

    normalized_ref = str(requested_ref or "").strip()
    normalized_branch = str(default_branch or "").strip()
    normalized_sha = str(
        resolved_commit_sha or "",
    ).strip()

    if not normalized_ref:
        raise ValueError(
            "requested_ref must not be empty",
        )

    if not normalized_branch:
        raise ValueError(
            "default_branch must not be empty",
        )

    if not normalized_sha:
        raise ValueError(
            "resolved_commit_sha must not be empty",
        )

    current_time = get_datetime_utc()

    try:
        task = assert_repository_analysis_lease(
            session,
            task_id=task_id,
            worker_id=worker_id,
            now=current_time,
        )

        task.requested_ref = normalized_ref
        task.default_branch = normalized_branch
        task.resolved_commit_sha = normalized_sha
        task.updated_at = current_time

        session.add(task)
        session.commit()
        session.refresh(task)
    except Exception:
        session.rollback()
        raise

    return task


def update_repository_snapshot_metadata(
    *,
    session: Session,
    task_id: uuid.UUID,
    worker_id: str,
    snapshot_source: str,
    snapshot_storage_path: str,
) -> RepositoryAnalysisTask:
    """
    保存仓库快照来源和本地路径。

    写入前必须验证任务仍属于当前 Worker，且租约尚未过期。
    """

    normalized_source = str(
        snapshot_source or "",
    ).strip()

    normalized_path = str(
        snapshot_storage_path or "",
    ).strip()

    if not normalized_source:
        raise ValueError(
            "snapshot_source must not be empty",
        )

    if not normalized_path:
        raise ValueError(
            "snapshot_storage_path must not be empty",
        )

    current_time = get_datetime_utc()

    try:
        task = assert_repository_analysis_lease(
            session,
            task_id=task_id,
            worker_id=worker_id,
            now=current_time,
        )

        task.snapshot_source = normalized_source
        task.snapshot_storage_path = normalized_path
        task.updated_at = current_time

        session.add(task)
        session.commit()
        session.refresh(task)
    except Exception:
        session.rollback()
        raise

    return task


def complete_repository_analysis_task(
    *,
    session: Session,
    task_id: uuid.UUID,
    worker_id: str,
    result_json: dict[str, Any],
    evidence_json: dict[str, Any],
    report_markdown: str,
) -> RepositoryAnalysisTask:
    """
    将当前 Worker 持有租约的任务标记为成功。

    完成时保存结构化结果、Evidence 和 Markdown，
    并清除活动心跳及租约字段。
    """

    normalized_markdown = str(
        report_markdown or "",
    ).strip()

    if not normalized_markdown:
        raise ValueError(
            "report_markdown must not be empty",
        )

    current_time = get_datetime_utc()

    try:
        task = assert_repository_analysis_lease(
            session,
            task_id=task_id,
            worker_id=worker_id,
            now=current_time,
        )

        task.result_json = result_json
        task.evidence_json = evidence_json
        task.report_markdown = normalized_markdown

        task.status = "completed"
        task.stage = "completed"
        task.progress_percent = 100

        task.error_code = None
        task.error_message = None

        task.heartbeat_at = None
        task.lease_expires_at = None
        task.next_attempt_at = None
        task.completed_at = current_time
        task.expires_at = get_repository_analysis_expiry()
        task.updated_at = current_time

        session.add(task)
        session.commit()
        session.refresh(task)
    except Exception:
        session.rollback()
        raise

    return task


def fail_repository_analysis_task(
    *,
    session: Session,
    task_id: uuid.UUID,
    worker_id: str,
    error_code: str,
    error_message: str,
) -> RepositoryAnalysisTask:
    """
    将当前 Worker 持有租约的任务标记为业务失败。

    租约丢失异常会继续向上抛出，不能被当作普通业务失败写入。
    业务失败落库后清除活动心跳及租约字段。
    """

    normalized_error_code = str(
        error_code or "",
    ).strip()

    normalized_error_message = str(
        error_message or "",
    ).strip()

    if not normalized_error_code:
        raise ValueError(
            "error_code must not be empty",
        )

    if len(normalized_error_code) > 100:
        raise ValueError(
            "error_code must not exceed 100 characters",
        )

    if not normalized_error_message:
        normalized_error_message = (
            "Repository analysis failed"
        )

    current_time = get_datetime_utc()

    try:
        task = assert_repository_analysis_lease(
            session,
            task_id=task_id,
            worker_id=worker_id,
            now=current_time,
        )

        task.status = "failed"
        task.stage = "failed"
        task.error_code = normalized_error_code
        task.error_message = normalized_error_message

        task.heartbeat_at = None
        task.lease_expires_at = None
        task.next_attempt_at = None
        task.completed_at = current_time
        task.expires_at = get_repository_analysis_expiry()
        task.updated_at = current_time

        session.add(task)
        session.commit()
        session.refresh(task)
    except Exception:
        session.rollback()
        raise

    return task


def save_repository_analysis_task(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
) -> RepositoryAnalysisTask | None:
    """
    将临时快速概览保存为长期记录。

    保存后：
    - is_saved 变为 True；
    - expires_at 变为 None；
    - 24 小时清理任务不会处理该记录。
    """

    task = get_repository_analysis_task(
        session=session,
        owner_id=owner_id,
        task_id=task_id,
    )

    if task is None:
        return None

    if task.status != "completed":
        raise ValueError(
            "Only completed repository analyses can be saved",
        )

    task.is_saved = True
    task.expires_at = None
    task.updated_at = get_datetime_utc()

    try:
        session.add(task)
        session.commit()
        session.refresh(task)
    except Exception:
        session.rollback()
        raise

    return task


def expire_repository_analysis_tasks(
    *,
    session: Session,
) -> int:
    """
    标记已经过期且未保存的任务。

    当前先标记为 expired，不直接物理删除，
    这样更容易排查问题，也更安全。
    """

    current_time = get_datetime_utc()

    statement = (
        update(
            RepositoryAnalysisTask,
        )
        .where(
            RepositoryAnalysisTask.is_saved.is_(False),
            col(
                RepositoryAnalysisTask.expires_at,
            ).is_not(None),
            col(
                RepositoryAnalysisTask.expires_at,
            )
            <= current_time,
            col(
                RepositoryAnalysisTask.status,
            ).in_(
                {
                    "queued",
                    "completed",
                    "failed",
                },
            ),
        )
        .values(
            status="expired",
            stage="expired",
            updated_at=current_time,
        )
    )

    try:
        result = session.exec(statement)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return int(
        getattr(
            result,
            "rowcount",
            0,
        )
        or 0
    )