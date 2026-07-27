from __future__ import annotations

import argparse
import json
import logging
import os
import signal
from threading import Event

from sqlmodel import Session

from app.core.db import engine
from app.services.repository_snapshot_lifecycle import (
    DEFAULT_CLEANUP_BATCH_SIZE,
    RepositorySnapshotRetentionPolicy,
    sweep_repository_snapshots,
)
from app.services.repository_analysis_task import (
    expire_repository_analysis_tasks,
)


logger = logging.getLogger(__name__)

_shutdown_event = Event()


def run_snapshot_cleanup_once(
    *,
    batch_size: int,
    dry_run: bool,
) -> None:
    """
    执行一次快照清理，并将统计结果写入日志。
    """

    policy = (
        RepositorySnapshotRetentionPolicy
        .from_environment()
    )

    with Session(engine) as session:
        expired_task_count = 0

        if not dry_run:
            expired_task_count = (
                expire_repository_analysis_tasks(
                    session=session,
                )
            )

        report = sweep_repository_snapshots(
            session=session,
            policy=policy,
            batch_size=batch_size,
            dry_run=dry_run,
        )

    logger.info(
        "Repository snapshot cleanup result:\n%s",
        json.dumps(
            report.to_dict(),
            ensure_ascii=False,
            indent=2,
        ),
    )


def run_snapshot_cleanup_worker(
    *,
    interval_seconds: float,
    batch_size: int,
    dry_run: bool,
) -> None:
    """
    持续执行快照清理。

    每轮结束后等待 interval_seconds。
    """

    logger.info(
        (
            "Repository snapshot cleanup worker "
            "started; interval=%s, batch_size=%s, "
            "dry_run=%s"
        ),
        interval_seconds,
        batch_size,
        dry_run,
    )

    while not _shutdown_event.is_set():
        try:
            run_snapshot_cleanup_once(
                batch_size=batch_size,
                dry_run=dry_run,
            )
        except Exception:
            logger.exception(
                "Repository snapshot cleanup failed",
            )

        _shutdown_event.wait(
            timeout=interval_seconds,
        )

    logger.info(
        "Repository snapshot cleanup worker stopped",
    )


def _handle_shutdown_signal(
    signal_number: int,
    _frame: object,
) -> None:
    logger.info(
        "Received shutdown signal %s",
        signal_number,
    )

    _shutdown_event.set()


def configure_signal_handlers() -> None:
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
    level_name = os.getenv(
        "LOG_LEVEL",
        "INFO",
    ).upper()

    logging.basicConfig(
        level=getattr(
            logging,
            level_name,
            logging.INFO,
        ),
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean expired and orphaned "
            "repository snapshots"
        ),
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cleanup sweep and exit",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Show cleanup candidates without "
            "deleting files or changing the database"
        ),
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=3600.0,
        help=(
            "Cleanup interval in seconds; "
            "default is one hour"
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(
            os.getenv(
                "REPOSITORY_SNAPSHOT_CLEANUP_BATCH_SIZE",
                str(
                    DEFAULT_CLEANUP_BATCH_SIZE,
                ),
            ),
        ),
        help=(
            "Maximum database task rows "
            "examined in one sweep"
        ),
    )

    return parser.parse_args()


def main() -> int:
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
        run_snapshot_cleanup_once(
            batch_size=arguments.batch_size,
            dry_run=arguments.dry_run,
        )

        return 0

    run_snapshot_cleanup_worker(
        interval_seconds=arguments.interval,
        batch_size=arguments.batch_size,
        dry_run=arguments.dry_run,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())