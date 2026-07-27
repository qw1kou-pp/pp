from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from tests.repository_acceptance.acceptance_assertions import (
    assert_commit_present,
    assert_documents_match_scope,
    assert_history_matches_scope,
    assert_sources_match_scope,
    assert_task_reads_reproducible,
)
from tests.repository_acceptance.acceptance_client import (
    AcceptanceApiError,
    AcceptanceClient,
)
from tests.repository_acceptance.acceptance_models import (
    AcceptanceFailure,
    AcceptanceFailureCode,
    AcceptanceRunResult,
    AcceptanceStatus,
    AssertionStatus,
    RepositoryCase,
    SourceEvidence,
    StageTiming,
)


TASK_SUCCESS_STATUSES = frozenset({"completed", "succeeded", "success"})
TASK_FAILURE_STATUSES = frozenset({"failed", "expired", "cancelled", "canceled"})
DOCUMENT_FAILURE_STATUSES = frozenset({"failed", "error", "cancelled", "canceled"})
DOCUMENT_READY_STATUSES = frozenset(
    {"completed", "processed", "ready", "indexed", "succeeded", "success"}
)
EMBEDDING_READY_STATUSES = frozenset(
    {"completed", "embedded", "ready", "indexed", "succeeded", "success"}
)
SOURCE_LIST_KEYS = frozenset(
    {
        "sources",
        "source_documents",
        "sourceDocuments",
        "citations",
        "evidence",
        "evidences",
    }
)


class RunnerStageError(RuntimeError):
    def __init__(
        self,
        *,
        code: AcceptanceFailureCode,
        message: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})


class RepositoryAcceptanceRunner:
    """编排一次真实仓库端到端验收。

    Runner 只组织业务阶段和记录结果。所有 HTTP 路径、鉴权和重试由
    AcceptanceClient 负责；可重复验证的纯断言由 acceptance_assertions
    负责。通过注入时钟和 sleep，轮询流程能够被单元测试稳定覆盖。
    """

    def __init__(
        self,
        *,
        client: AcceptanceClient,
        poll_interval_seconds: float = 2.0,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")

        self.client = client
        self.poll_interval_seconds = poll_interval_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic
        self._sleep = sleep

    def run(self, case: RepositoryCase) -> AcceptanceRunResult:
        result = AcceptanceRunResult(
            repository_key=case.key,
            repository_url=case.repository_url,
            category=case.category,
            status=AcceptanceStatus.RUNNING,
        )
        active_stage: str | None = None

        try:
            active_stage = "repository_overview"
            with self._record_stage(result, active_stage):
                created_task = self.client.create_repository_task(
                    repository_url=case.repository_url,
                )
                task_id = self._require_identifier(
                    created_task,
                    keys=("id", "task_id", "repository_analysis_task_id"),
                    label="repository analysis task",
                )
                result.repository_analysis_task_id = task_id

                completed_task = self._wait_for_repository_task(
                    task_id=task_id,
                    timeout_seconds=case.task_timeout_seconds,
                )
                result.default_branch = self._optional_text(
                    completed_task,
                    "default_branch",
                    "repository_default_branch",
                )
                result.resolved_commit_sha = self._optional_text(
                    completed_task,
                    "resolved_commit_sha",
                    "source_commit_sha",
                    "commit_sha",
                )
                result.metadata["repository_task"] = completed_task

                commit_assertion = assert_commit_present(
                    result.resolved_commit_sha
                )
                result.assertions.append(commit_assertion)
                if commit_assertion.status is AssertionStatus.FAILED:
                    raise RunnerStageError(
                        code=AcceptanceFailureCode.COMMIT_MISSING,
                        message=commit_assertion.message,
                    )

            active_stage = "save_repository_task"
            with self._record_stage(result, active_stage):
                saved_task = self.client.save_repository_task(
                    task_id=task_id,
                )
                result.metadata["saved_repository_task"] = saved_task

            active_stage = "create_knowledge_base"
            with self._record_stage(result, active_stage):
                knowledge_base = self.client.create_knowledge_base(
                    name=self._build_knowledge_base_name(case),
                    description=(
                        "Repository acceptance knowledge base for "
                        f"{case.repository_full_name} at "
                        f"{result.resolved_commit_sha}"
                    ),
                )
                knowledge_base_id = self._require_identifier(
                    knowledge_base,
                    keys=("id", "knowledge_base_id"),
                    label="knowledge base",
                )
                result.knowledge_base_id = knowledge_base_id
                result.metadata["knowledge_base"] = knowledge_base

            active_stage = "deep_import_and_embedding"
            with self._record_stage(result, active_stage):
                deep_analysis = self.client.start_deep_analysis(
                    task_id=task_id,
                    knowledge_base_id=knowledge_base_id,
                )
                self._raise_if_operation_failed(
                    deep_analysis,
                    code=AcceptanceFailureCode.DEEP_IMPORT_FAILED,
                    operation="deep analysis",
                )
                result.metadata["deep_analysis"] = deep_analysis

                documents = self._wait_for_documents_ready(
                    knowledge_base_id=knowledge_base_id,
                    import_timeout_seconds=(
                        case.deep_import_timeout_seconds
                    ),
                    embedding_timeout_seconds=(
                        case.embedding_timeout_seconds
                    ),
                )
                result.metadata["document_count"] = len(documents)
                result.metadata["documents"] = documents
                result.assertions.append(
                    assert_documents_match_scope(
                        documents=documents,
                        expected_task_id=task_id,
                        expected_commit_sha=(
                            result.resolved_commit_sha or ""
                        ),
                    )
                )

            active_stage = "repository_rag"
            with self._record_stage(result, active_stage):
                rag_responses: list[dict[str, Any]] = []
                for question_index, question in enumerate(
                    case.questions,
                    start=1,
                ):
                    response = self.client.chat_with_repository(
                        knowledge_base_id=knowledge_base_id,
                        repository_analysis_task_id=task_id,
                        question=question,
                    )
                    rag_responses.append(
                        {"question": question, "response": response}
                    )
                    sources = self._extract_sources(response)
                    result.sources.extend(sources)
                    result.assertions.append(
                        assert_sources_match_scope(
                            sources=sources,
                            expected_task_id=task_id,
                            expected_commit_sha=(
                                result.resolved_commit_sha or ""
                            ),
                            assertion_name=(
                                f"rag_sources_{question_index}"
                            ),
                        )
                    )
                result.metadata["rag_responses"] = rag_responses

            active_stage = "repository_agent"
            with self._record_stage(result, active_stage):
                agent_responses: list[dict[str, Any]] = []
                for question_index, question in enumerate(
                    case.questions,
                    start=1,
                ):
                    response = self.client.agent_chat_with_repository(
                        knowledge_base_id=knowledge_base_id,
                        repository_analysis_task_id=task_id,
                        question=question,
                    )
                    agent_responses.append(
                        {"question": question, "response": response}
                    )
                    sources = self._extract_sources(response)
                    result.sources.extend(sources)
                    result.assertions.append(
                        assert_sources_match_scope(
                            sources=sources,
                            expected_task_id=task_id,
                            expected_commit_sha=(
                                result.resolved_commit_sha or ""
                            ),
                            assertion_name=(
                                f"agent_sources_{question_index}"
                            ),
                        )
                    )
                result.metadata["agent_responses"] = agent_responses

            active_stage = "scoped_history"
            with self._record_stage(result, active_stage):
                rag_history = self.client.read_rag_history(
                    knowledge_base_id=knowledge_base_id,
                    repository_analysis_task_id=task_id,
                )
                agent_history = self.client.read_agent_history(
                    knowledge_base_id=knowledge_base_id,
                    repository_analysis_task_id=task_id,
                )
                result.metadata["rag_history"] = rag_history
                result.metadata["agent_history"] = agent_history
                result.assertions.extend(
                    [
                        assert_history_matches_scope(
                            history_payload=rag_history,
                            expected_task_id=task_id,
                            expected_commit_sha=(
                                result.resolved_commit_sha or ""
                            ),
                            assertion_name="rag_history_scope",
                        ),
                        assert_history_matches_scope(
                            history_payload=agent_history,
                            expected_task_id=task_id,
                            expected_commit_sha=(
                                result.resolved_commit_sha or ""
                            ),
                            assertion_name="agent_history_scope",
                        ),
                    ]
                )

            active_stage = "reproducibility_reads"
            with self._record_stage(result, active_stage):
                final_task_reads = [
                    self.client.read_repository_task(task_id=task_id),
                    self.client.read_repository_task(task_id=task_id),
                ]
                result.metadata["final_task_reads"] = final_task_reads
                result.assertions.append(
                    assert_task_reads_reproducible(
                        task_reads=final_task_reads,
                        expected_task_id=task_id,
                        expected_commit_sha=(
                            result.resolved_commit_sha or ""
                        ),
                    )
                )

            self._append_assertion_failures(result)
            result.status = (
                AcceptanceStatus.FAILED
                if result.failures
                else AcceptanceStatus.PASSED
            )
            return result

        except RunnerStageError as exc:
            result.failures.append(
                AcceptanceFailure(
                    code=exc.code,
                    message=exc.message,
                    stage=active_stage,
                    details=exc.details,
                )
            )
        except AcceptanceApiError as exc:
            result.failures.append(
                AcceptanceFailure(
                    code=self._map_api_error_code(
                        error_code=exc.code,
                        stage=active_stage,
                    ),
                    message=exc.message,
                    stage=active_stage,
                    details={
                        "status_code": exc.status_code,
                        "backend_error_code": exc.code,
                        "backend_details": exc.details,
                    },
                )
            )
        except Exception as exc:
            result.failures.append(
                AcceptanceFailure(
                    code=self._fallback_failure_code(active_stage),
                    message=str(exc) or exc.__class__.__name__,
                    stage=active_stage,
                    details={"exception_type": exc.__class__.__name__},
                )
            )

        result.status = AcceptanceStatus.FAILED
        return result

    @contextmanager
    def _record_stage(
        self,
        result: AcceptanceRunResult,
        name: str,
    ) -> Iterator[None]:
        started_at = self._now()
        try:
            yield
        finally:
            result.stage_timings.append(
                StageTiming(
                    name=name,
                    started_at=started_at,
                    finished_at=self._now(),
                )
            )

    def _wait_for_repository_task(
        self,
        *,
        task_id: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        started = self._monotonic()

        while True:
            task = self.client.read_repository_task(task_id=task_id)
            status = self._normalized_status(task)

            if status in TASK_SUCCESS_STATUSES:
                return task

            if status in TASK_FAILURE_STATUSES:
                backend_error_code = self._optional_text(
                    task,
                    "error_code",
                    "failure_code",
                    "code",
                )
                backend_error_message = self._optional_text(
                    task,
                    "error_message",
                    "failure_message",
                    "message",
                )
                raise RunnerStageError(
                    code=AcceptanceFailureCode.REPOSITORY_TASK_FAILED,
                    message=(
                        backend_error_message
                        or f"Repository task ended with status {status}"
                    ),
                    details={
                        "task_status": status,
                        "backend_error_code": backend_error_code,
                    },
                )

            if self._monotonic() - started >= timeout_seconds:
                raise RunnerStageError(
                    code=AcceptanceFailureCode.REPOSITORY_TASK_TIMEOUT,
                    message=(
                        "Repository analysis task did not complete within "
                        f"{timeout_seconds} seconds"
                    ),
                    details={"last_status": status},
                )

            self._sleep(self.poll_interval_seconds)

    def _wait_for_documents_ready(
        self,
        *,
        knowledge_base_id: str,
        import_timeout_seconds: int,
        embedding_timeout_seconds: int,
    ) -> list[dict[str, Any]]:
        import_started = self._monotonic()
        embedding_started: float | None = None

        while True:
            documents = self._read_all_documents(
                knowledge_base_id=knowledge_base_id
            )

            if not documents:
                if (
                    self._monotonic() - import_started
                    >= import_timeout_seconds
                ):
                    raise RunnerStageError(
                        code=AcceptanceFailureCode.DEEP_IMPORT_FAILED,
                        message=(
                            "Repository deep import produced no documents "
                            f"within {import_timeout_seconds} seconds"
                        ),
                    )
                self._sleep(self.poll_interval_seconds)
                continue

            failed_documents = [
                document
                for document in documents
                if self._document_failed(document)
            ]
            if failed_documents:
                raise RunnerStageError(
                    code=AcceptanceFailureCode.DEEP_IMPORT_FAILED,
                    message="One or more repository documents failed",
                    details={
                        "failed_document_ids": [
                            str(document.get("id") or "<unknown>")
                            for document in failed_documents
                        ],
                        "errors": [
                            document.get("embedding_error")
                            or document.get("error_message")
                            for document in failed_documents
                        ],
                    },
                )

            if all(self._document_ready(document) for document in documents):
                return documents

            if embedding_started is None:
                embedding_started = self._monotonic()

            if (
                self._monotonic() - embedding_started
                >= embedding_timeout_seconds
            ):
                raise RunnerStageError(
                    code=AcceptanceFailureCode.EMBEDDING_TIMEOUT,
                    message=(
                        "Repository document embeddings did not complete "
                        f"within {embedding_timeout_seconds} seconds"
                    ),
                    details={
                        "pending_document_ids": [
                            str(document.get("id") or "<unknown>")
                            for document in documents
                            if not self._document_ready(document)
                        ]
                    },
                )

            self._sleep(self.poll_interval_seconds)

    def _read_all_documents(
        self,
        *,
        knowledge_base_id: str,
    ) -> list[dict[str, Any]]:
        page_size = 100
        first_page = self.client.read_documents(
            knowledge_base_id=knowledge_base_id,
            skip=0,
            limit=page_size,
        )
        documents = self._extract_document_list(first_page)
        total = self._extract_count(first_page, default=len(documents))

        while len(documents) < total:
            page = self.client.read_documents(
                knowledge_base_id=knowledge_base_id,
                skip=len(documents),
                limit=page_size,
            )
            next_documents = self._extract_document_list(page)
            if not next_documents:
                break
            documents.extend(next_documents)

        return documents

    @staticmethod
    def _extract_document_list(
        payload: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        raw_documents = payload.get("data")
        if raw_documents is None:
            raw_documents = payload.get("documents")

        if not isinstance(raw_documents, Sequence) or isinstance(
            raw_documents,
            (str, bytes, bytearray),
        ):
            return []

        return [
            dict(document)
            for document in raw_documents
            if isinstance(document, Mapping)
        ]

    @staticmethod
    def _extract_count(
        payload: Mapping[str, Any],
        *,
        default: int,
    ) -> int:
        value = payload.get("count", default)
        try:
            return max(default, int(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _document_failed(document: Mapping[str, Any]) -> bool:
        document_status = str(document.get("status") or "").lower()
        embedding_status = str(
            document.get("embedding_status") or ""
        ).lower()
        return (
            document_status in DOCUMENT_FAILURE_STATUSES
            or embedding_status in DOCUMENT_FAILURE_STATUSES
        )

    @staticmethod
    def _document_ready(document: Mapping[str, Any]) -> bool:
        document_status = str(document.get("status") or "").lower()
        raw_embedding_status = document.get("embedding_status")

        if raw_embedding_status is not None:
            embedding_status = str(raw_embedding_status).lower()
            return embedding_status in EMBEDDING_READY_STATUSES

        return document_status in DOCUMENT_READY_STATUSES

    @staticmethod
    def _normalized_status(payload: Mapping[str, Any]) -> str:
        value = payload.get("status")
        if value is None:
            value = payload.get("task_status")
        return str(value or "").strip().lower()

    def _raise_if_operation_failed(
        self,
        payload: Mapping[str, Any],
        *,
        code: AcceptanceFailureCode,
        operation: str,
    ) -> None:
        status = self._normalized_status(payload)
        if status not in TASK_FAILURE_STATUSES:
            return

        raise RunnerStageError(
            code=code,
            message=(
                self._optional_text(
                    payload,
                    "error_message",
                    "message",
                )
                or f"{operation} ended with status {status}"
            ),
            details={
                "operation_status": status,
                "backend_error_code": self._optional_text(
                    payload,
                    "error_code",
                    "code",
                ),
            },
        )

    def _build_knowledge_base_name(self, case: RepositoryCase) -> str:
        timestamp = self._now().strftime("%Y%m%d-%H%M%S")
        return f"repository-acceptance-{case.key}-{timestamp}"

    @staticmethod
    def _require_identifier(
        payload: Mapping[str, Any],
        *,
        keys: Sequence[str],
        label: str,
    ) -> str:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value)

        raise ValueError(f"{label} response does not contain an identifier")

    @staticmethod
    def _optional_text(
        payload: Mapping[str, Any],
        *keys: str,
    ) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value)
        return None

    @classmethod
    def _extract_sources(cls, payload: Any) -> list[SourceEvidence]:
        source_mappings: list[Mapping[str, Any]] = []
        cls._collect_source_mappings(payload, source_mappings)
        return [cls._source_from_mapping(source) for source in source_mappings]

    @classmethod
    def _collect_source_mappings(
        cls,
        value: Any,
        output: list[Mapping[str, Any]],
    ) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if key in SOURCE_LIST_KEYS and isinstance(
                    nested,
                    Sequence,
                ) and not isinstance(nested, (str, bytes, bytearray)):
                    output.extend(
                        item for item in nested if isinstance(item, Mapping)
                    )
                    continue
                cls._collect_source_mappings(nested, output)
            return

        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            for nested in value:
                cls._collect_source_mappings(nested, output)

    @classmethod
    def _source_from_mapping(
        cls,
        source: Mapping[str, Any],
    ) -> SourceEvidence:
        metadata = source.get("metadata")
        combined: dict[str, Any] = dict(metadata) if isinstance(
            metadata,
            Mapping,
        ) else {}
        combined.update(source)

        return SourceEvidence(
            repository_analysis_task_id=cls._first_text(
                combined,
                "repository_analysis_task_id",
                "repositoryAnalysisTaskId",
                "repository_task_id",
            ),
            repository_relative_path=cls._first_text(
                combined,
                "repository_relative_path",
                "repositoryRelativePath",
                "file_path",
                "path",
            ),
            source_commit_sha=cls._first_text(
                combined,
                "source_commit_sha",
                "sourceCommitSha",
                "commit_sha",
            ),
            document_id=cls._first_text(
                combined,
                "document_id",
                "documentId",
            ),
            chunk_id=cls._first_text(
                combined,
                "chunk_id",
                "chunkId",
            ),
            original_filename=cls._first_text(
                combined,
                "original_filename",
                "originalFilename",
                "filename",
            ),
        )

    @staticmethod
    def _first_text(
        payload: Mapping[str, Any],
        *keys: str,
    ) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value)
        return None

    @staticmethod
    def _append_assertion_failures(
        result: AcceptanceRunResult,
    ) -> None:
        for assertion in result.assertions:
            if assertion.status is not AssertionStatus.FAILED:
                continue

            if assertion.name.startswith("rag_sources_"):
                code = AcceptanceFailureCode.RAG_SCOPE_VIOLATION
                stage = "repository_rag"
            elif assertion.name.startswith("agent_sources_"):
                code = AcceptanceFailureCode.AGENT_SCOPE_VIOLATION
                stage = "repository_agent"
            elif assertion.name == "documents_scope":
                code = AcceptanceFailureCode.DOCUMENT_SCOPE_VIOLATION
                stage = "deep_import_and_embedding"
            elif assertion.name in {
                "rag_history_scope",
                "agent_history_scope",
            }:
                code = AcceptanceFailureCode.HISTORY_SCOPE_VIOLATION
                stage = "scoped_history"
            elif assertion.name == "task_reads_reproducible":
                code = AcceptanceFailureCode.RESULT_NOT_REPRODUCIBLE
                stage = "reproducibility_reads"
            elif assertion.name == "cross_repository_isolation":
                code = (
                    AcceptanceFailureCode.CROSS_REPOSITORY_SCOPE_VIOLATION
                )
                stage = "cross_repository_isolation"
            else:
                code = AcceptanceFailureCode.COMMIT_MISMATCH
                stage = None

            result.failures.append(
                AcceptanceFailure(
                    code=code,
                    message=assertion.message,
                    stage=stage,
                    details={
                        "assertion_name": assertion.name,
                        "assertion_code": assertion.code,
                        **assertion.details,
                    },
                )
            )

    @staticmethod
    def _map_api_error_code(
        *,
        error_code: str,
        stage: str | None,
    ) -> AcceptanceFailureCode:
        for candidate in (
            AcceptanceFailureCode.GITHUB_NETWORK_ERROR,
            AcceptanceFailureCode.GITHUB_RATE_LIMITED,
        ):
            if error_code == candidate.value:
                return candidate

        return RepositoryAcceptanceRunner._fallback_failure_code(stage)

    @staticmethod
    def _fallback_failure_code(
        stage: str | None,
    ) -> AcceptanceFailureCode:
        if stage == "deep_import_and_embedding":
            return AcceptanceFailureCode.DEEP_IMPORT_FAILED
        if stage == "repository_rag":
            return AcceptanceFailureCode.RAG_SCOPE_VIOLATION
        if stage == "repository_agent":
            return AcceptanceFailureCode.AGENT_SCOPE_VIOLATION
        if stage == "scoped_history":
            return AcceptanceFailureCode.HISTORY_SCOPE_VIOLATION
        if stage == "reproducibility_reads":
            return AcceptanceFailureCode.RESULT_NOT_REPRODUCIBLE
        return AcceptanceFailureCode.REPOSITORY_TASK_FAILED
