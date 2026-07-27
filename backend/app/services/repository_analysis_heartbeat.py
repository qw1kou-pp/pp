from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from types import TracebackType
from typing import Any

from sqlmodel import Session

from app.core.db import engine
from app.services.repository_analysis_lease import (
    RepositoryAnalysisLeaseLostError,
    renew_repository_analysis_lease,
)


DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30.0
DEFAULT_LEASE_SECONDS = 90
DEFAULT_THREAD_JOIN_TIMEOUT_SECONDS = 10.0


SessionFactory = Callable[[], Session]


class RepositoryAnalysisHeartbeatError(
    RuntimeError,
):
    """
    心跳线程执行失败。

    数据库连接失败、Session 创建失败等非租约异常，
    会包装成该异常并传递给主线程。
    """

    def __init__(
        self,
        message: str,
        *,
        task_id: uuid.UUID,
        worker_id: str,
        original_error: Exception,
    ) -> None:
        super().__init__(message)

        self.task_id = task_id
        self.worker_id = worker_id
        self.original_error = original_error


class RepositoryAnalysisHeartbeat:
    """
    仓库分析任务租约心跳。

    每隔 interval_seconds 创建一个新的数据库 Session，
    调用 renew_repository_analysis_lease() 延长任务租约。

    该类是一次性对象：

    1. 可以 start 一次；
    2. 可以 stop 多次；
    3. stop 后不能再次 start。
    """

    def __init__(
        self,
        *,
        task_id: uuid.UUID,
        worker_id: str,
        interval_seconds: float = (
            DEFAULT_HEARTBEAT_INTERVAL_SECONDS
        ),
        lease_seconds: int = (
            DEFAULT_LEASE_SECONDS
        ),
        session_factory: (
            SessionFactory | None
        ) = None,
        thread_join_timeout_seconds: float = (
            DEFAULT_THREAD_JOIN_TIMEOUT_SECONDS
        ),
    ) -> None:
        self.task_id = task_id
        self.worker_id = _normalize_worker_id(
            worker_id,
        )

        self.interval_seconds = (
            _validate_positive_float(
                interval_seconds,
                parameter_name=(
                    "interval_seconds"
                ),
            )
        )

        self.lease_seconds = (
            _validate_positive_integer(
                lease_seconds,
                parameter_name=(
                    "lease_seconds"
                ),
            )
        )

        if (
            self.lease_seconds
            <= self.interval_seconds
        ):
            raise ValueError(
                (
                    "lease_seconds must be "
                    "greater than interval_seconds"
                ),
            )

        self.thread_join_timeout_seconds = (
            _validate_positive_float(
                thread_join_timeout_seconds,
                parameter_name=(
                    "thread_join_timeout_seconds"
                ),
            )
        )

        self._session_factory = (
            session_factory
            or _create_session
        )

        self._stop_event = threading.Event()
        self._failure_lock = threading.Lock()

        self._failure: Exception | None = None
        self._thread: threading.Thread | None = None
        self._started = False

    @property
    def is_running(self) -> bool:
        """
        心跳线程当前是否仍然运行。
        """

        thread = self._thread

        return bool(
            thread is not None
            and thread.is_alive()
        )

    @property
    def failure(self) -> Exception | None:
        """
        返回心跳线程保存的异常。

        该属性只用于检查，不会抛出异常。
        """

        with self._failure_lock:
            return self._failure

    def start(self) -> None:
        """
        启动心跳线程。

        同一个 Heartbeat 对象只能启动一次。
        """

        if self._started:
            raise RuntimeError(
                (
                    "RepositoryAnalysisHeartbeat "
                    "cannot be started more than once"
                ),
            )

        self._started = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            name=(
                "repository-analysis-heartbeat-"
                f"{self.task_id}"
            ),
            daemon=True,
        )

        self._thread.start()

    def stop(self) -> None:
        """
        请求停止心跳并等待后台线程退出。

        多次调用 stop 是安全的。
        """

        self._stop_event.set()

        thread = self._thread

        if thread is None:
            return

        if (
            threading.current_thread()
            is thread
        ):
            return

        thread.join(
            timeout=(
                self.thread_join_timeout_seconds
            ),
        )

        if thread.is_alive():
            self._record_failure(
                RepositoryAnalysisHeartbeatError(
                    (
                        "Repository analysis "
                        "heartbeat thread did not "
                        "stop within "
                        f"{self.thread_join_timeout_seconds} "
                        "seconds"
                    ),
                    task_id=self.task_id,
                    worker_id=self.worker_id,
                    original_error=RuntimeError(
                        "Heartbeat thread stop timeout",
                    ),
                ),
            )

    def raise_if_failed(self) -> None:
        """
        如果心跳线程发生异常，则在主线程重新抛出。
        """

        failure = self.failure

        if failure is not None:
            raise failure

    def __enter__(
        self,
    ) -> RepositoryAnalysisHeartbeat:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.stop()

        # 主线程没有业务异常时，
        # 才在退出上下文时传播心跳异常。
        #
        # 如果主线程已经发生异常，不能用心跳异常
        # 覆盖原来的业务异常。
        if exc_type is None:
            self.raise_if_failed()

        return False

    def _run(self) -> None:
        """
        心跳线程主体。

        使用 Event.wait 而不是 time.sleep，
        这样 stop() 可以立即唤醒线程。
        """

        while not self._stop_event.wait(
            self.interval_seconds,
        ):
            try:
                with self._session_factory() as session:
                    renew_repository_analysis_lease(
                        session,
                        task_id=self.task_id,
                        worker_id=self.worker_id,
                        lease_seconds=(
                            self.lease_seconds
                        ),
                    )

            except (
                RepositoryAnalysisLeaseLostError
            ) as exc:
                self._record_failure(exc)
                self._stop_event.set()
                return

            except Exception as exc:
                heartbeat_error = (
                    RepositoryAnalysisHeartbeatError(
                        (
                            "Repository analysis "
                            "heartbeat failed: "
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                        task_id=self.task_id,
                        worker_id=self.worker_id,
                        original_error=exc,
                    )
                )

                heartbeat_error.__cause__ = exc

                self._record_failure(
                    heartbeat_error,
                )

                self._stop_event.set()
                return

    def _record_failure(
        self,
        failure: Exception,
    ) -> None:
        """
        只保存第一次心跳异常。

        第一次异常最接近根因，后续异常不能覆盖它。
        """

        with self._failure_lock:
            if self._failure is None:
                self._failure = failure


def _create_session() -> Session:
    """
    为心跳线程创建独立的 SQLModel Session。

    主线程与心跳线程不能共享同一个 Session。
    """

    return Session(engine)


def _normalize_worker_id(
    worker_id: str,
) -> str:
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


def _validate_positive_float(
    value: Any,
    *,
    parameter_name: str,
) -> float:
    try:
        normalized = float(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            (
                f"{parameter_name} must "
                "be a number"
            ),
        ) from exc

    if normalized <= 0:
        raise ValueError(
            (
                f"{parameter_name} must "
                "be greater than zero"
            ),
        )

    return normalized


def _validate_positive_integer(
    value: Any,
    *,
    parameter_name: str,
) -> int:
    if isinstance(value, bool):
        raise ValueError(
            (
                f"{parameter_name} must "
                "be an integer"
            ),
        )

    try:
        normalized = int(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            (
                f"{parameter_name} must "
                "be an integer"
            ),
        ) from exc

    if normalized <= 0:
        raise ValueError(
            (
                f"{parameter_name} must "
                "be greater than zero"
            ),
        )

    return normalized