from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse


class RepositoryCategory(StrEnum):
    PYTHON = "python"
    FASTAPI = "fastapi"
    REACT_TYPESCRIPT = "react-typescript"
    FULL_STACK = "full-stack"


class AcceptanceStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class AssertionStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class AcceptanceFailureCode(StrEnum):
    GITHUB_NETWORK_ERROR = "GITHUB_NETWORK_ERROR"
    GITHUB_RATE_LIMITED = "GITHUB_RATE_LIMITED"
    REPOSITORY_TASK_FAILED = "REPOSITORY_TASK_FAILED"
    REPOSITORY_TASK_TIMEOUT = "REPOSITORY_TASK_TIMEOUT"
    DEEP_IMPORT_FAILED = "DEEP_IMPORT_FAILED"
    EMBEDDING_TIMEOUT = "EMBEDDING_TIMEOUT"
    RAG_SCOPE_VIOLATION = "RAG_SCOPE_VIOLATION"
    AGENT_SCOPE_VIOLATION = "AGENT_SCOPE_VIOLATION"
    HISTORY_SCOPE_VIOLATION = "HISTORY_SCOPE_VIOLATION"
    COMMIT_MISMATCH = "COMMIT_MISMATCH"
    COMMIT_MISSING = "COMMIT_MISSING"
    RESULT_NOT_REPRODUCIBLE = "RESULT_NOT_REPRODUCIBLE"


@dataclass(frozen=True, slots=True)
class RepositoryCase:
    key: str
    repository_url: str
    category: RepositoryCategory
    smoke: bool
    questions: tuple[str, ...]
    task_timeout_seconds: int = 1800
    deep_import_timeout_seconds: int = 1800
    embedding_timeout_seconds: int = 1800

    def __post_init__(self) -> None:
        normalized_key = self.key.strip()
        if not normalized_key:
            raise ValueError("repository case key must not be empty")

        parsed = urlparse(self.repository_url.strip())
        if parsed.scheme != "https" or parsed.netloc != "github.com":
            raise ValueError(
                "repository_url must be an https://github.com URL"
            )

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) != 2:
            raise ValueError(
                "repository_url must identify exactly owner/repository"
            )

        if not self.questions:
            raise ValueError("repository case must define at least one question")

        if any(not question.strip() for question in self.questions):
            raise ValueError("repository questions must not be empty")

        for timeout in (
            self.task_timeout_seconds,
            self.deep_import_timeout_seconds,
            self.embedding_timeout_seconds,
        ):
            if timeout <= 0:
                raise ValueError("acceptance timeouts must be positive")

    @property
    def repository_full_name(self) -> str:
        parsed = urlparse(self.repository_url)
        return parsed.path.strip("/")


@dataclass(frozen=True, slots=True)
class StageTiming:
    name: str
    started_at: datetime
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at is None:
            return None
        return max(
            0.0,
            (self.finished_at - self.started_at).total_seconds(),
        )


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    repository_analysis_task_id: str | None
    repository_relative_path: str | None
    source_commit_sha: str | None
    document_id: str | None = None
    chunk_id: str | None = None
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class AssertionResult:
    name: str
    status: AssertionStatus
    message: str
    code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AcceptanceFailure:
    code: AcceptanceFailureCode
    message: str
    stage: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AcceptanceRunResult:
    repository_key: str
    repository_url: str
    category: RepositoryCategory
    status: AcceptanceStatus = AcceptanceStatus.PENDING
    default_branch: str | None = None
    resolved_commit_sha: str | None = None
    repository_analysis_task_id: str | None = None
    knowledge_base_id: str | None = None
    stage_timings: list[StageTiming] = field(default_factory=list)
    sources: list[SourceEvidence] = field(default_factory=list)
    assertions: list[AssertionResult] = field(default_factory=list)
    failures: list[AcceptanceFailure] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
