from __future__ import annotations

import argparse
import logging
import os
import signal
from threading import Event

from sqlmodel import Session

from app.core.db import engine
from app.services.repository_analysis_lease import (
    RepositoryAnalysisRecoveryReport,
    recover_expired_repository_analysis_leases,
)
from app.services.repository_snapshot_lifecycle import (
    cleanup_repository_analysis_task_snapshot,
)

logger = logging.getLogger(__name__)

_shutdown_event = Event()

DEFAULT_RECOVERY_INTERVAL_SECONDS = 60.0
DEFAULT_RECOVERY_BATCH_SIZE = 100

def run_repository_analysis_recovery_once(
    *,
    batch_size: int,
) -> RepositoryAnalysisRecoveryReport:
    """
    执行一轮过期租约恢复。

    数据库恢复成功提交后，再对最终失败的任务
    逐个执行快照清理。
    """

    normalized_batch_size = int(
        batch_size,
    )

    if normalized_batch_size <= 0:
        raise ValueError(
            "batch_size must be greater than zero",
        )

    with Session(engine) as session:
        report = (
            recover_expired_repository_analysis_leases(
                session,
                batch_size=normalized_batch_size,
            )
        )

    logger.info(
        (
            "Repository analysis recovery completed: "
            "scanned=%s requeued=%s failed=%s"
        ),
        report.scanned_count,
        report.requeued_count,
        report.failed_count,
    )

    for task_id in report.requeued_task_ids:
        logger.info(
            "Requeued repository analysis task %s "
            "after its lease expired",
            task_id,
        )

    for task_id in report.failed_task_ids:
        logger.warning(
            "Repository analysis task %s reached "
            "its retry limit",
            task_id,
        )

        _cleanup_failed_task_snapshot(
            task_id=task_id,
        )

    return report


def _cleanup_failed_task_snapshot(
    *,
    task_id: object,
) -> None:
    """
    清理已经达到最大尝试次数的任务快照。

    单个快照清理失败不会阻止 Recovery Worker
    继续处理其他任务。
    """

    try:
        with Session(engine) as session:
            cleanup_action = (
                cleanup_repository_analysis_task_snapshot(
                    session=session,
                    task_id=task_id,
                    force_reason=(
                        "retry_limit_reached"
                    ),
                )
            )

        if cleanup_action.reference_cleared:
            logger.info(
                "Cleaned repository snapshot "
                "for failed task %s",
                task_id,
            )
        else:
            logger.info(
                "No repository snapshot needed cleanup "
                "for failed task %s",
                task_id,
            )

    except Exception:
        logger.exception(
            "Could not clean repository snapshot "
            "for failed task %s",
            task_id,
        )


def run_repository_analysis_recovery_worker(
    *,
    interval_seconds: float,
    batch_size: int,
) -> None:
    """
    持续扫描过期的仓库分析任务租约。
    """

    normalized_interval = float(
        interval_seconds,
    )

    if normalized_interval <= 0:
        raise ValueError(
            "interval_seconds must be greater than zero",
        )

    normalized_batch_size = int(
        batch_size,
    )

    if normalized_batch_size <= 0:
        raise ValueError(
            "batch_size must be greater than zero",
        )

    logger.info(
        (
            "Repository analysis recovery worker started: "
            "interval=%s batch_size=%s"
        ),
        normalized_interval,
        normalized_batch_size,
    )

    while not _shutdown_event.is_set():
        try:
            run_repository_analysis_recovery_once(
                batch_size=normalized_batch_size,
            )

        except Exception:
            logger.exception(
                "Repository analysis lease recovery failed",
            )

        _shutdown_event.wait(
            timeout=normalized_interval,
        )

    logger.info(
        "Repository analysis recovery worker stopped",
    )


def _read_positive_float_environment(
    name: str,
    *,
    default: float,
) -> float:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return float(default)

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a number",
        ) from exc

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero",
        )

    return value


def _read_positive_integer_environment(
    name: str,
    *,
    default: int,
) -> int:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return int(default)

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer",
        ) from exc

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero",
        )

    return value


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
    注册 Windows 和 Linux 常用停止信号。
    """

    signal.signal(
        signal.SIGINT,
        _handle_shutdown_signal,
    )

    if hasattr(
        signal,
        "SIGTERM",
    ):
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
    解析 Recovery Worker 启动参数。
    """

    parser = argparse.ArgumentParser(
        description=(
            "Recover expired repository "
            "analysis task leases"
        ),
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Run one recovery scan and exit"
        ),
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=(
            _read_positive_float_environment(
                (
                    "REPOSITORY_ANALYSIS_"
                    "RECOVERY_INTERVAL_SECONDS"
                ),
                default=(
                    DEFAULT_RECOVERY_INTERVAL_SECONDS
                ),
            )
        ),
        help=(
            "Recovery scan interval in seconds"
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=(
            _read_positive_integer_environment(
                (
                    "REPOSITORY_ANALYSIS_"
                    "RECOVERY_BATCH_SIZE"
                ),
                default=(
                    DEFAULT_RECOVERY_BATCH_SIZE
                ),
            )
        ),
        help=(
            "Maximum expired tasks processed "
            "in one scan"
        ),
    )

    return parser.parse_args()


def main() -> int:
    """
    Recovery Worker 命令行入口。
    """

    configure_logging()
    configure_signal_handlers()

    arguments = parse_arguments()

    if arguments.interval <= 0:
        raise ValueError(
            "interval must be greater than zero",
        )

    if arguments.batch_size <= 0:
        raise ValueError(
            "batch size must be greater than zero",
        )

    if arguments.once:
        run_repository_analysis_recovery_once(
            batch_size=arguments.batch_size,
        )

        return 0

    run_repository_analysis_recovery_worker(
        interval_seconds=arguments.interval,
        batch_size=arguments.batch_size,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())