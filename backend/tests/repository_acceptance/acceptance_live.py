from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tests.repository_acceptance.acceptance_client import AcceptanceClient
from tests.repository_acceptance.acceptance_matrix_runner import (
    AcceptanceMatrixResult,
    AcceptanceMatrixRunner,
)
from tests.repository_acceptance.acceptance_models import RepositoryCase
from tests.repository_acceptance.acceptance_report import (
    AcceptanceReportPaths,
    write_acceptance_reports,
)
from tests.repository_acceptance.acceptance_runner import (
    RepositoryAcceptanceRunner,
)


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True, slots=True)
class LiveAcceptanceSettings:
    base_url: str
    email: str
    password: str = field(repr=False)
    github_token: str = field(repr=False)
    output_dir: Path = Path("artifacts/repository-acceptance")
    poll_interval_seconds: float = 2.0
    request_timeout_seconds: float = 60.0

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        require_enabled: bool = True,
    ) -> LiveAcceptanceSettings:
        values = environ if environ is not None else os.environ
        if require_enabled and not live_acceptance_enabled(values):
            raise ValueError(
                "RUN_REPOSITORY_ACCEPTANCE_LIVE must be enabled"
            )

        email = _required_environment_value(
            values,
            "REPOSITORY_ACCEPTANCE_EMAIL",
        )
        password = _required_environment_value(
            values,
            "REPOSITORY_ACCEPTANCE_PASSWORD",
        )
        github_token = _required_environment_value(values, "GITHUB_TOKEN")
        base_url = values.get(
            "REPOSITORY_ACCEPTANCE_BASE_URL",
            "http://localhost:8000",
        ).strip().rstrip("/")
        if not base_url:
            raise ValueError(
                "REPOSITORY_ACCEPTANCE_BASE_URL must not be empty"
            )

        output_dir = Path(
            values.get(
                "REPOSITORY_ACCEPTANCE_OUTPUT_DIR",
                "artifacts/repository-acceptance",
            )
        )
        poll_interval_seconds = _positive_float(
            values,
            "REPOSITORY_ACCEPTANCE_POLL_INTERVAL_SECONDS",
            2.0,
        )
        request_timeout_seconds = _positive_float(
            values,
            "REPOSITORY_ACCEPTANCE_REQUEST_TIMEOUT_SECONDS",
            60.0,
        )

        return cls(
            base_url=base_url,
            email=email,
            password=password,
            github_token=github_token,
            output_dir=output_dir,
            poll_interval_seconds=poll_interval_seconds,
            request_timeout_seconds=request_timeout_seconds,
        )


def live_acceptance_enabled(
    environ: Mapping[str, str] | None = None,
) -> bool:
    values = environ if environ is not None else os.environ
    return (
        values.get("RUN_REPOSITORY_ACCEPTANCE_LIVE", "")
        .strip()
        .lower()
        in _TRUE_VALUES
    )


def execute_live_acceptance(
    *,
    cases: Sequence[RepositoryCase],
    settings: LiveAcceptanceSettings,
    run_name: str | None = None,
) -> tuple[AcceptanceMatrixResult, AcceptanceReportPaths]:
    """通过真实 HTTP API 运行仓库矩阵并生成报告。

    GITHUB_TOKEN 由部署环境中的后端 GitHub 客户端读取。这里强制校验它
    存在，但不会把 Token 放进 HTTP 请求、日志或报告。
    """

    with AcceptanceClient(
        base_url=settings.base_url,
        timeout_seconds=settings.request_timeout_seconds,
    ) as client:
        client.authenticate(
            email=settings.email,
            password=settings.password,
        )
        repository_runner = RepositoryAcceptanceRunner(
            client=client,
            poll_interval_seconds=settings.poll_interval_seconds,
        )
        matrix_result = AcceptanceMatrixRunner(
            repository_runner=repository_runner,
        ).run(cases)

    report_paths = write_acceptance_reports(
        result=matrix_result,
        output_dir=settings.output_dir,
        run_name=run_name,
    )
    return matrix_result, report_paths


def _required_environment_value(
    environ: Mapping[str, str],
    name: str,
) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} must be configured")
    return value


def _positive_float(
    environ: Mapping[str, str],
    name: str,
    default: float,
) -> float:
    raw_value = environ.get(name)
    value = default if raw_value is None else float(raw_value)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value
