from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
from threading import Event

from sqlmodel import Session

from app.core.db import engine
from app.models import RepositoryAnalysisTask
from app.services.repository_analysis_processor import (
    build_placeholder_repository_analysis,
    build_repository_snapshot_analysis,
)
from app.services.repository_analysis_task import (
    claim_next_repository_analysis_task,
    complete_repository_analysis_task,
    fail_repository_analysis_task,
    update_repository_analysis_progress,
    update_repository_resolution_metadata,
)
from app.services.github_repository_client import (
    GitHubPrivateRepositoryNotSupportedError,
    GitHubRepositoryClient,
    GitHubRepositoryEmptyError,
    GitHubRepositoryNotFoundError,
    GitHubRepositoryRateLimitError,
    GitHubRepositoryUnavailableError,
    GitHubRepositoryAcquisition,
)
from app.services.repository_analysis_processor import (
    build_repository_overview_analysis,
)

from app.services.github_repository_snapshot import (
    GitHubRepositorySnapshotDownloadError,
    GitHubRepositorySnapshotDownloader,
    GitHubRepositorySnapshotInvalidArchiveError,
    GitHubRepositorySnapshotNotFoundError,
    GitHubRepositorySnapshotTooLargeError,
    GitHubRepositorySnapshotUnsafeArchiveError,
)

from app.services.repository_analysis_task import update_repository_snapshot_metadata
from app.services.repository_structure_scanner import (
    scan_repository_structure,
)
from app.services.repository_code_analyzer import (
    analyze_repository_code,
)

logger = logging.getLogger(__name__)

_shutdown_event = Event()


class RepositoryAnalysisWorkerError(RuntimeError):
    """
    Worker 无法继续处理当前任务时抛出的异常。
    """


def build_worker_id(
    explicit_worker_id: str | None = None,
) -> str:
    """
    生成当前 Worker 的唯一标识。

    默认由主机名和进程号组成，例如：
    DESKTOP-ABC123:42
    """

    normalized_worker_id = str(
        explicit_worker_id or "",
    ).strip()

    if normalized_worker_id:
        return normalized_worker_id[:255]

    hostname = socket.gethostname()
    process_id = os.getpid()

    return f"{hostname}:{process_id}"[:255]


def run_repository_analysis_worker_once(
    *,
    worker_id: str,
) -> bool:
    """
    尝试领取并处理一条 queued 任务。

    返回值：
    True  → 本次领取到一条任务
    False → 当前没有待处理任务
    """

    with Session(engine) as session:
        task = claim_next_repository_analysis_task(
            session=session,
            worker_id=worker_id,
        )

    if task is None:
        logger.info(
            "No queued repository analysis task was found",
        )
        return False

    logger.info(
        "Claimed repository analysis task %s for %s",
        task.id,
        task.repository_full_name,
    )

    try:
        process_repository_analysis_task(
            task=task,
            worker_id=worker_id,
        )
    except Exception as exc:
        _persist_task_failure(
            task=task,
            worker_id=worker_id,
            exception=exc,
        )

        raise

    logger.info(
        "Completed repository analysis task %s",
        task.id,
    )

    return True


def process_repository_analysis_task(
    *,
    task: RepositoryAnalysisTask,
    worker_id: str,
) -> None:
    """
    执行一条仓库分析任务。

    完整流程：
    1. 获取 GitHub 仓库元数据；
    2. 解析固定 Commit；
    3. 下载并安全解压仓库快照；
    4. 扫描仓库结构；
    5. 构建 Evidence 和概览报告；
    6. 保存最终分析结果。
    """

    # 第一阶段：获取 GitHub 仓库元数据
    _update_progress_or_raise(
        task=task,
        worker_id=worker_id,
        stage="fetching_metadata",
        progress_percent=10,
    )

    with GitHubRepositoryClient() as client:
        metadata = client.get_repository_metadata(
            owner=task.repository_owner,
            repository_name=task.repository_name,
        )

        # 第二阶段：将分支或 Tag 解析为固定 Commit
        _update_progress_or_raise(
            task=task,
            worker_id=worker_id,
            stage="resolving_commit",
            progress_percent=25,
        )

        requested_ref = (
            task.requested_ref
            or metadata.default_branch
        )

        commit = client.get_commit(
            owner=task.repository_owner,
            repository_name=task.repository_name,
            ref=requested_ref,
        )

    acquisition = GitHubRepositoryAcquisition(
        metadata=metadata,
        commit=commit,
    )

    # 先保存仓库版本解析结果
    with Session(engine) as session:
        updated_task = (
            update_repository_resolution_metadata(
                session=session,
                task_id=task.id,
                worker_id=worker_id,
                requested_ref=commit.requested_ref,
                default_branch=metadata.default_branch,
                resolved_commit_sha=commit.sha,
            )
        )

    if updated_task is None:
        raise RepositoryAnalysisWorkerError(
            "Unable to persist resolved repository commit",
        )

    # 第三阶段：下载固定 Commit 对应的 ZIP 快照
    _update_progress_or_raise(
        task=task,
        worker_id=worker_id,
        stage="downloading_snapshot",
        progress_percent=35,
    )

    with GitHubRepositorySnapshotDownloader() as downloader:
        snapshot = downloader.download_and_extract(
            owner=task.repository_owner,
            repository_name=task.repository_name,
            commit_sha=commit.sha,
            task_id=task.id,
        )

    # 保存快照来源和本地解压路径
    with Session(engine) as session:
        snapshot_task = (
            update_repository_snapshot_metadata(
                session=session,
                task_id=task.id,
                worker_id=worker_id,
                snapshot_source=snapshot.source,
                snapshot_storage_path=str(
                    snapshot.repository_root,
                ),
            )
        )

    if snapshot_task is None:
        raise RepositoryAnalysisWorkerError(
            "Unable to persist repository snapshot metadata",
        )

    # 第四阶段：扫描已经下载并解压的仓库
    _update_progress_or_raise(
        task=task,
        worker_id=worker_id,
        stage="scanning_repository",
        progress_percent=55,
    )

    scan = scan_repository_structure(
        snapshot.repository_root,
    )

    # 第五阶段：根据扫描结果分析代码
    _update_progress_or_raise(
        task=task,
        worker_id=worker_id,
        stage="analyzing_code",
        progress_percent=68,
    )

    code_analysis = analyze_repository_code(
        snapshot.repository_root,
    )

    # 第六阶段：根据扫描结果构建 Evidence
    _update_progress_or_raise(
        task=task,
        worker_id=worker_id,
        stage="building_evidence",
        progress_percent=80,
    )

    output = build_repository_overview_analysis(
        task=task,
        acquisition=acquisition,
        snapshot=snapshot,
        scan=scan,
    )

    # 第七阶段：生成并保存最终报告
    _update_progress_or_raise(
        task=task,
        worker_id=worker_id,
        stage="generating_report",
        progress_percent=90,
    )

    with Session(engine) as session:
        completed_task = (
            complete_repository_analysis_task(
                session=session,
                task_id=task.id,
                worker_id=worker_id,
                result_json=output.result_json,
                evidence_json=output.evidence_json,
                report_markdown=output.report_markdown,
            )
        )

    if completed_task is None:
        raise RepositoryAnalysisWorkerError(
            "The worker no longer owns the claimed task",
        )
def _update_progress_or_raise(
    *,
    task: RepositoryAnalysisTask,
    worker_id: str,
    stage: str,
    progress_percent: int,
) -> None:
    """
    更新任务进度。

    找不到任务通常表示任务所有权已经变化，
    此时 Worker 必须停止继续写入。
    """

    with Session(engine) as session:
        updated_task = update_repository_analysis_progress(
            session=session,
            task_id=task.id,
            worker_id=worker_id,
            stage=stage,
            progress_percent=progress_percent,
        )

    if updated_task is None:
        raise RepositoryAnalysisWorkerError(
            "Unable to update the claimed task",
        )


def _map_repository_analysis_error(
    exception: Exception,
) -> tuple[str, str]:
    """
    将 GitHub Client 异常转换为稳定的业务错误码。

    前端不需要理解 httpx、HTTP 状态码等底层细节。
    """

    if isinstance(
        exception,
        GitHubRepositoryNotFoundError,
    ):
        return (
            "REPOSITORY_NOT_FOUND",
            (
                "GitHub 仓库不存在，"
                "或者该仓库不是公开仓库。"
            ),
        )

    if isinstance(
        exception,
        GitHubPrivateRepositoryNotSupportedError,
    ):
        return (
            "PRIVATE_REPOSITORY_NOT_SUPPORTED",
            "当前版本只支持公开 GitHub 仓库。",
        )

    if isinstance(
        exception,
        GitHubRepositoryEmptyError,
    ):
        return (
            "REPOSITORY_EMPTY",
            "GitHub 仓库没有可分析的 Commit。",
        )

    if isinstance(
        exception,
        GitHubRepositoryRateLimitError,
    ):
        return (
            "GITHUB_RATE_LIMITED",
            (
                "GitHub API 请求频率已达到限制，"
                "请稍后重新提交任务。"
            ),
        )

    if isinstance(
        exception,
        GitHubRepositoryUnavailableError,
    ):
        return (
            "GITHUB_UNAVAILABLE",
            (
                "暂时无法连接 GitHub，"
                "请稍后重新提交任务。"
            ),
        )

    if isinstance(
        exception,
        GitHubRepositorySnapshotNotFoundError,
    ):
        return (
            "REPOSITORY_SNAPSHOT_NOT_FOUND",
            "无法获取该 Commit 对应的仓库快照。",
        )

    if isinstance(
        exception,
        GitHubRepositorySnapshotTooLargeError,
    ):
        return (
            "REPOSITORY_SNAPSHOT_TOO_LARGE",
            (
                "仓库快照超出当前系统允许的"
                "文件大小或文件数量限制。"
            ),
        )

    if isinstance(
        exception,
        GitHubRepositorySnapshotUnsafeArchiveError,
    ):
        return (
            "REPOSITORY_SNAPSHOT_UNSAFE",
            (
                "仓库 ZIP 包含不安全的路径"
                "或文件系统条目。"
            ),
        )

    if isinstance(
        exception,
        GitHubRepositorySnapshotInvalidArchiveError,
    ):
        return (
            "REPOSITORY_SNAPSHOT_INVALID",
            "GitHub 返回的仓库快照不是有效 ZIP。",
        )

    if isinstance(
        exception,
        GitHubRepositorySnapshotDownloadError,
    ):
        return (
            "REPOSITORY_SNAPSHOT_DOWNLOAD_FAILED",
            "仓库快照下载失败，请稍后重试。",
        )

    return (
        "REPOSITORY_ANALYSIS_PROCESSING_FAILED",
        (
            f"{type(exception).__name__}: "
            f"{exception}"
        ),
    )


def _persist_task_failure(
    *,
    task: RepositoryAnalysisTask,
    worker_id: str,
    exception: Exception,
) -> None:
    """
    使用新的数据库会话记录任务失败。

    使用新会话是为了避免原处理会话已经处于
    rollback required 状态，导致错误信息无法落库。
    """

    error_code, error_message = (
        _map_repository_analysis_error(
            exception,
        )
    )

    error_message = error_message.strip()

    if not error_message:
        error_message = (
            "Repository analysis workers failed"
        )

    error_message = error_message[:4000]

    try:
        with Session(engine) as session:
            failed_task = fail_repository_analysis_task(
                session=session,
                task_id=task.id,
                worker_id=worker_id,
                error_code=error_code,
                error_message=error_message,
            )

        if failed_task is None:
            logger.error(
                "Could not persist failure for task %s "
                "because task ownership was lost",
                task.id,
            )
    except Exception:
        logger.exception(
            "Could not persist failure state for task %s",
            task.id,
        )


def run_repository_analysis_worker(
    *,
    worker_id: str,
    poll_interval_seconds: float,
) -> None:
    """
    持续轮询 PostgreSQL 任务队列。

    没有任务时等待 poll_interval_seconds，
    收到停止信号后结束循环。
    """

    logger.info(
        "Repository analysis workers started: %s",
        worker_id,
    )

    while not _shutdown_event.is_set():
        try:
            task_processed = (
                run_repository_analysis_worker_once(
                    worker_id=worker_id,
                )
            )
        except Exception:
            logger.exception(
                "Repository analysis task processing failed",
            )

            task_processed = False

        if not task_processed:
            _shutdown_event.wait(
                timeout=poll_interval_seconds,
            )

    logger.info(
        "Repository analysis workers stopped: %s",
        worker_id,
    )


def _handle_shutdown_signal(
    signal_number: int,
    _frame: object,
) -> None:
    """
    接收 Ctrl+C 或容器停止信号。
    """

    logger.info(
        "Received shutdown signal %s",
        signal_number,
    )

    _shutdown_event.set()


def configure_signal_handlers() -> None:
    """
    注册 Windows 和 Linux 常用退出信号。
    """

    signal.signal(
        signal.SIGINT,
        _handle_shutdown_signal,
    )

    if hasattr(signal, "SIGTERM"):
        signal.signal(
            signal.SIGTERM,
            _handle_shutdown_signal,
        )


def configure_logging() -> None:
    """
    配置 Worker 标准输出日志。
    """

    level_name = os.getenv(
        "LOG_LEVEL",
        "INFO",
    ).upper()

    log_level = getattr(
        logging,
        level_name,
        logging.INFO,
    )

    logging.basicConfig(
        level=log_level,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )


def parse_arguments() -> argparse.Namespace:
    """
    解析 Worker 启动参数。
    """

    parser = argparse.ArgumentParser(
        description=(
            "Process repository analysis tasks"
        ),
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Process at most one queued task and exit"
        ),
    )

    parser.add_argument(
        "--workers-id",
        default=None,
        help=(
            "Optional explicit workers identifier"
        ),
    )

    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help=(
            "Queue polling interval in seconds"
        ),
    )

    return parser.parse_args()


def main() -> int:
    """
    Worker 命令行入口。
    """

    configure_logging()
    configure_signal_handlers()

    arguments = parse_arguments()

    if arguments.poll_interval <= 0:
        raise ValueError(
            "poll interval must be greater than zero",
        )

    worker_id = build_worker_id(
        arguments.worker_id,
    )

    if arguments.once:
        run_repository_analysis_worker_once(
            worker_id=worker_id,
        )

        return 0

    run_repository_analysis_worker(
        worker_id=worker_id,
        poll_interval_seconds=(
            arguments.poll_interval
        ),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())













































