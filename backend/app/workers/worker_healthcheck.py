from __future__ import annotations

import argparse
import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.core.db import engine
from app.services.repository_snapshot_lifecycle import (
    get_repository_snapshot_root,
)


@dataclass(frozen=True, slots=True)
class WorkerHealthcheckResult:
    """
    Worker 容器健康检查结果。

    database_ok：
    Worker 是否能连接 PostgreSQL。

    snapshot_root_ok：
    Worker 是否可以访问共享快照目录。

    snapshot_root_writable：
    Worker 是否可以实际写入共享快照目录。
    """

    healthy: bool

    database_ok: bool

    snapshot_root_ok: bool
    snapshot_root_writable: bool
    snapshot_root: str | None

    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_worker_healthcheck(
    *,
    check_snapshot_write: bool = True,
) -> WorkerHealthcheckResult:
    """
    检查 Worker 运行所依赖的基础设施。

    检查内容：

    1. PostgreSQL 可执行 SELECT 1；
    2. 快照根目录存在；
    3. 快照根目录是目录；
    4. 可选：实际创建并删除一个探针文件。
    """

    snapshot_root: Path | None = None

    try:
        _check_database_connection()

        snapshot_root = (
            get_repository_snapshot_root()
        )

        _check_snapshot_root(
            snapshot_root,
            check_write=check_snapshot_write,
        )

        return WorkerHealthcheckResult(
            healthy=True,
            database_ok=True,
            snapshot_root_ok=True,
            snapshot_root_writable=(
                check_snapshot_write
            ),
            snapshot_root=str(snapshot_root),
        )

    except Exception as exc:
        message = str(exc).strip()

        if len(message) > 500:
            message = (
                message[:500]
                + "...[truncated]"
            )

        return WorkerHealthcheckResult(
            healthy=False,
            database_ok=False,
            snapshot_root_ok=(
                snapshot_root is not None
                and snapshot_root.exists()
                and snapshot_root.is_dir()
            ),
            snapshot_root_writable=False,
            snapshot_root=(
                str(snapshot_root)
                if snapshot_root is not None
                else None
            ),
            error_type=type(exc).__name__,
            error_message=message,
        )


def _check_database_connection() -> None:
    """
    使用 SELECT 1 验证数据库连接。

    不读取业务数据，也不会修改数据库。
    """

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT 1"),
        ).scalar_one()

    if result != 1:
        raise RuntimeError(
            "Database healthcheck returned "
            "an unexpected result",
        )


def _check_snapshot_root(
    snapshot_root: Path,
    *,
    check_write: bool,
) -> None:
    """
    验证共享快照目录及其写权限。
    """

    if not snapshot_root.exists():
        raise FileNotFoundError(
            "Repository snapshot root "
            "does not exist",
        )

    if not snapshot_root.is_dir():
        raise NotADirectoryError(
            "Repository snapshot root "
            "is not a directory",
        )

    if not os.access(
        snapshot_root,
        os.R_OK | os.X_OK,
    ):
        raise PermissionError(
            "Repository snapshot root "
            "is not readable",
        )

    if not check_write:
        return

    probe_path = (
        snapshot_root
        / (
            ".worker-healthcheck-"
            f"{uuid.uuid4().hex}"
        )
    )

    try:
        probe_path.write_text(
            "ok",
            encoding="utf-8",
        )

        content = probe_path.read_text(
            encoding="utf-8",
        )

        if content != "ok":
            raise RuntimeError(
                "Snapshot write probe "
                "could not be read back",
            )
    finally:
        probe_path.unlink(
            missing_ok=True,
        )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check repository worker "
            "database and storage dependencies"
        ),
    )

    parser.add_argument(
        "--skip-write-check",
        action="store_true",
        help=(
            "Check snapshot directory access "
            "without writing a probe file"
        ),
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    result = run_worker_healthcheck(
        check_snapshot_write=(
            not arguments.skip_write_check
        ),
    )

    print(
        json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )

    return 0 if result.healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())