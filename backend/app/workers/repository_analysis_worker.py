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
)
from app.services.repository_analysis_task import (
    claim_next_repository_analysis_task,
    complete_repository_analysis_task,
    fail_repository_analysis_task,
    update_repository_analysis_progress,
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
    执行一条已经领取的仓库分析任务。

    当前调用占位处理器，后续在这里替换成正式分析流水线。
    """

    _update_progress_or_raise(
        task=task,
        worker_id=worker_id,
        stage="building_evidence",
        progress_percent=60,
    )

    output = build_placeholder_repository_analysis(
        task,
    )

    _update_progress_or_raise(
        task=task,
        worker_id=worker_id,
        stage="generating_report",
        progress_percent=90,
    )

    with Session(engine) as session:
        completed_task = complete_repository_analysis_task(
            session=session,
            task_id=task.id,
            worker_id=worker_id,
            result_json=output.result_json,
            evidence_json=output.evidence_json,
            report_markdown=output.report_markdown,
        )

    if completed_task is None:
        raise RepositoryAnalysisWorkerError(
            "The workers no longer owns the claimed task",
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

    error_message = (
        f"{type(exception).__name__}: {exception}"
    ).strip()

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
                error_code=(
                    "REPOSITORY_ANALYSIS_PROCESSING_FAILED"
                ),
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













































