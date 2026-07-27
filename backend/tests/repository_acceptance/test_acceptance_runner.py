from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from tests.repository_acceptance.acceptance_models import (
    AcceptanceFailureCode,
    AcceptanceStatus,
    RepositoryCase,
    RepositoryCategory,
)
from tests.repository_acceptance.acceptance_runner import (
    RepositoryAcceptanceRunner,
)


COMMIT_SHA = "a" * 40
TASK_ID = "task-1"
KNOWLEDGE_BASE_ID = "kb-1"


def build_case(*, task_timeout_seconds: int = 30) -> RepositoryCase:
    return RepositoryCase(
        key="example",
        repository_url="https://github.com/example/project",
        category=RepositoryCategory.PYTHON,
        smoke=True,
        questions=(
            "项目入口在哪里？",
            "核心调用流程是什么？",
        ),
        task_timeout_seconds=task_timeout_seconds,
        deep_import_timeout_seconds=30,
        embedding_timeout_seconds=30,
    )


def build_source(path: str) -> dict[str, Any]:
    return {
        "repository_analysis_task_id": TASK_ID,
        "repository_relative_path": path,
        "source_commit_sha": COMMIT_SHA,
        "document_id": f"doc-{path}",
        "chunk_id": f"chunk-{path}",
    }


@dataclass
class FakeClient:
    task_reads: list[dict[str, Any]]
    document_reads: list[dict[str, Any]]
    calls: list[str] = field(default_factory=list)
    rag_history_payload: dict[str, Any] | None = None
    agent_history_payload: dict[str, Any] | None = None

    def create_repository_task(
        self,
        *,
        repository_url: str,
        report_language: str = "zh-CN",
    ) -> dict[str, Any]:
        self.calls.append("create_repository_task")
        return {
            "id": TASK_ID,
            "status": "queued",
            "repository_url": repository_url,
        }

    def read_repository_task(self, *, task_id: str) -> dict[str, Any]:
        self.calls.append("read_repository_task")
        assert task_id == TASK_ID
        if not self.task_reads:
            raise AssertionError("unexpected repository task read")
        return self.task_reads.pop(0)

    def save_repository_task(self, *, task_id: str) -> dict[str, Any]:
        self.calls.append("save_repository_task")
        assert task_id == TASK_ID
        return {
            "id": TASK_ID,
            "status": "completed",
            "saved": True,
            "resolved_commit_sha": COMMIT_SHA,
        }

    def create_knowledge_base(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append("create_knowledge_base")
        assert "example" in name
        return {
            "id": KNOWLEDGE_BASE_ID,
            "name": name,
            "description": description,
        }

    def start_deep_analysis(
        self,
        *,
        task_id: str,
        knowledge_base_id: str,
    ) -> dict[str, Any]:
        self.calls.append("start_deep_analysis")
        assert task_id == TASK_ID
        assert knowledge_base_id == KNOWLEDGE_BASE_ID
        return {
            "status": "accepted",
            "repository_analysis_task_id": task_id,
            "knowledge_base_id": knowledge_base_id,
        }

    def read_documents(
        self,
        *,
        knowledge_base_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        self.calls.append("read_documents")
        assert knowledge_base_id == KNOWLEDGE_BASE_ID
        assert skip == 0
        assert limit == 100
        if not self.document_reads:
            raise AssertionError("unexpected document read")
        return self.document_reads.pop(0)

    def chat_with_repository(
        self,
        *,
        knowledge_base_id: str,
        repository_analysis_task_id: str,
        question: str,
        **_: Any,
    ) -> dict[str, Any]:
        self.calls.append(f"rag:{question}")
        assert knowledge_base_id == KNOWLEDGE_BASE_ID
        assert repository_analysis_task_id == TASK_ID
        return {
            "answer": f"RAG: {question}",
            "sources": [build_source("backend/app/main.py")],
        }

    def agent_chat_with_repository(
        self,
        *,
        knowledge_base_id: str,
        repository_analysis_task_id: str,
        question: str,
        **_: Any,
    ) -> dict[str, Any]:
        self.calls.append(f"agent:{question}")
        assert knowledge_base_id == KNOWLEDGE_BASE_ID
        assert repository_analysis_task_id == TASK_ID
        return {
            "answer": f"Agent: {question}",
            "result": {
                "evidence": [build_source("frontend/src/main.tsx")],
            },
        }

    def read_rag_history(
        self,
        *,
        knowledge_base_id: str,
        repository_analysis_task_id: str,
        **_: Any,
    ) -> dict[str, Any]:
        self.calls.append("read_rag_history")
        if self.rag_history_payload is not None:
            return self.rag_history_payload
        return {
            "data": [
                {
                    "id": "rag-run-1",
                    "repository_analysis_task_id": (
                        repository_analysis_task_id
                    ),
                    "source_commit_sha": COMMIT_SHA,
                }
            ],
            "count": 1,
        }

    def read_agent_history(
        self,
        *,
        knowledge_base_id: str,
        repository_analysis_task_id: str,
        **_: Any,
    ) -> dict[str, Any]:
        self.calls.append("read_agent_history")
        if self.agent_history_payload is not None:
            return self.agent_history_payload
        return {
            "data": [
                {
                    "id": "agent-run-1",
                    "repository_analysis_task_id": (
                        repository_analysis_task_id
                    ),
                    "source_commit_sha": COMMIT_SHA,
                }
            ],
            "count": 1,
        }


def completed_task() -> dict[str, Any]:
    return {
        "id": TASK_ID,
        "status": "completed",
        "default_branch": "main",
        "resolved_commit_sha": COMMIT_SHA,
        "report_markdown": "# Repository report",
        "result": {"summary": "stable"},
    }


def make_clock() -> tuple[
    Callable[[], datetime],
    Callable[[], float],
    Callable[[float], None],
]:
    current_datetime = datetime(2026, 7, 27, tzinfo=timezone.utc)
    current_seconds = 0.0

    def now() -> datetime:
        return current_datetime + timedelta(seconds=current_seconds)

    def monotonic() -> float:
        return current_seconds

    def sleep(seconds: float) -> None:
        nonlocal current_seconds
        current_seconds += seconds

    return now, monotonic, sleep


def test_runner_executes_complete_flow_in_expected_order() -> None:
    final_task = completed_task()
    client = FakeClient(
        task_reads=[
            {"id": TASK_ID, "status": "running"},
            final_task,
            final_task,
            final_task,
        ],
        document_reads=[
            {
                "data": [
                    {
                        "id": "doc-1",
                        "status": "processing",
                        "embedding_status": "pending",
                    }
                ],
                "count": 1,
            },
            {
                "data": [
                    {
                        "id": "doc-1",
                        "status": "completed",
                        "embedding_status": "completed",
                        "repository_analysis_task_id": TASK_ID,
                        "source_commit_sha": COMMIT_SHA,
                    }
                ],
                "count": 1,
            },
        ],
    )
    now, monotonic, sleep = make_clock()
    runner = RepositoryAcceptanceRunner(
        client=client,
        poll_interval_seconds=1.0,
        now=now,
        monotonic=monotonic,
        sleep=sleep,
    )

    result = runner.run(build_case())

    assert result.status is AcceptanceStatus.PASSED
    assert result.repository_analysis_task_id == TASK_ID
    assert result.knowledge_base_id == KNOWLEDGE_BASE_ID
    assert result.default_branch == "main"
    assert result.resolved_commit_sha == COMMIT_SHA
    assert result.failures == []
    assert len(result.sources) == 4
    assert all(
        assertion.status.value == "passed"
        for assertion in result.assertions
    )
    assert result.metadata["document_count"] == 1
    assert len(result.metadata["rag_responses"]) == 2
    assert len(result.metadata["agent_responses"]) == 2
    assert len(result.metadata["final_task_reads"]) == 2
    assert [timing.name for timing in result.stage_timings] == [
        "repository_overview",
        "save_repository_task",
        "create_knowledge_base",
        "deep_import_and_embedding",
        "repository_rag",
        "repository_agent",
        "scoped_history",
        "reproducibility_reads",
    ]
    assert client.calls == [
        "create_repository_task",
        "read_repository_task",
        "read_repository_task",
        "save_repository_task",
        "create_knowledge_base",
        "start_deep_analysis",
        "read_documents",
        "read_documents",
        "rag:项目入口在哪里？",
        "rag:核心调用流程是什么？",
        "agent:项目入口在哪里？",
        "agent:核心调用流程是什么？",
        "read_rag_history",
        "read_agent_history",
        "read_repository_task",
        "read_repository_task",
    ]


def test_runner_maps_terminal_repository_failure() -> None:
    client = FakeClient(
        task_reads=[
            {
                "id": TASK_ID,
                "status": "failed",
                "error_code": "GITHUB_REPOSITORY_NOT_FOUND",
                "error_message": "repository not found",
            }
        ],
        document_reads=[],
    )
    now, monotonic, sleep = make_clock()
    runner = RepositoryAcceptanceRunner(
        client=client,
        poll_interval_seconds=1.0,
        now=now,
        monotonic=monotonic,
        sleep=sleep,
    )

    result = runner.run(build_case())

    assert result.status is AcceptanceStatus.FAILED
    assert result.failures[0].code is (
        AcceptanceFailureCode.REPOSITORY_TASK_FAILED
    )
    assert result.failures[0].stage == "repository_overview"
    assert result.failures[0].details["backend_error_code"] == (
        "GITHUB_REPOSITORY_NOT_FOUND"
    )
    assert client.calls == [
        "create_repository_task",
        "read_repository_task",
    ]


def test_runner_fails_when_repository_polling_times_out() -> None:
    client = FakeClient(
        task_reads=[
            {"id": TASK_ID, "status": "running"},
            {"id": TASK_ID, "status": "running"},
            {"id": TASK_ID, "status": "running"},
        ],
        document_reads=[],
    )
    now, monotonic, sleep = make_clock()
    runner = RepositoryAcceptanceRunner(
        client=client,
        poll_interval_seconds=1.0,
        now=now,
        monotonic=monotonic,
        sleep=sleep,
    )

    result = runner.run(build_case(task_timeout_seconds=2))

    assert result.status is AcceptanceStatus.FAILED
    assert result.failures[0].code is (
        AcceptanceFailureCode.REPOSITORY_TASK_TIMEOUT
    )
    assert result.failures[0].stage == "repository_overview"
    assert client.calls == [
        "create_repository_task",
        "read_repository_task",
        "read_repository_task",
        "read_repository_task",
    ]


def test_runner_maps_failed_document_import() -> None:
    final_task = completed_task()
    client = FakeClient(
        task_reads=[final_task],
        document_reads=[
            {
                "data": [
                    {
                        "id": "doc-1",
                        "status": "failed",
                        "error_message": "parse failed",
                    }
                ],
                "count": 1,
            }
        ],
    )
    now, monotonic, sleep = make_clock()
    runner = RepositoryAcceptanceRunner(
        client=client,
        poll_interval_seconds=1.0,
        now=now,
        monotonic=monotonic,
        sleep=sleep,
    )

    result = runner.run(build_case())

    assert result.status is AcceptanceStatus.FAILED
    assert result.failures[0].code is (
        AcceptanceFailureCode.DEEP_IMPORT_FAILED
    )
    assert result.failures[0].stage == "deep_import_and_embedding"
    assert result.failures[0].details["failed_document_ids"] == [
        "doc-1"
    ]


def test_runner_fails_when_history_contains_another_task() -> None:
    final_task = completed_task()
    client = FakeClient(
        task_reads=[final_task, final_task, final_task],
        document_reads=[
            {
                "data": [
                    {
                        "id": "doc-1",
                        "status": "completed",
                        "embedding_status": "completed",
                        "repository_analysis_task_id": TASK_ID,
                        "source_commit_sha": COMMIT_SHA,
                    }
                ],
                "count": 1,
            }
        ],
        rag_history_payload={
            "data": [
                {
                    "id": "rag-run-leaked",
                    "repository_analysis_task_id": "task-other",
                    "source_commit_sha": COMMIT_SHA,
                }
            ],
            "count": 1,
        },
    )
    now, monotonic, sleep = make_clock()
    runner = RepositoryAcceptanceRunner(
        client=client,
        poll_interval_seconds=1.0,
        now=now,
        monotonic=monotonic,
        sleep=sleep,
    )

    result = runner.run(build_case())

    assert result.status is AcceptanceStatus.FAILED
    assert any(
        failure.code is AcceptanceFailureCode.HISTORY_SCOPE_VIOLATION
        and failure.stage == "scoped_history"
        for failure in result.failures
    )


def test_runner_fails_when_final_task_reads_change() -> None:
    initial_task = completed_task()
    changed_task = {
        **completed_task(),
        "report_markdown": "# Changed repository report",
    }
    client = FakeClient(
        task_reads=[initial_task, initial_task, changed_task],
        document_reads=[
            {
                "data": [
                    {
                        "id": "doc-1",
                        "status": "completed",
                        "embedding_status": "completed",
                        "repository_analysis_task_id": TASK_ID,
                        "source_commit_sha": COMMIT_SHA,
                    }
                ],
                "count": 1,
            }
        ],
    )
    now, monotonic, sleep = make_clock()
    runner = RepositoryAcceptanceRunner(
        client=client,
        poll_interval_seconds=1.0,
        now=now,
        monotonic=monotonic,
        sleep=sleep,
    )

    result = runner.run(build_case())

    assert result.status is AcceptanceStatus.FAILED
    assert any(
        failure.code is AcceptanceFailureCode.RESULT_NOT_REPRODUCIBLE
        and failure.stage == "reproducibility_reads"
        for failure in result.failures
    )


def test_runner_fails_when_imported_document_has_another_task() -> None:
    final_task = completed_task()
    client = FakeClient(
        task_reads=[final_task, final_task, final_task],
        document_reads=[
            {
                "data": [
                    {
                        "id": "doc-leaked",
                        "status": "completed",
                        "embedding_status": "completed",
                        "repository_analysis_task_id": "task-other",
                        "source_commit_sha": COMMIT_SHA,
                    }
                ],
                "count": 1,
            }
        ],
    )
    now, monotonic, sleep = make_clock()
    runner = RepositoryAcceptanceRunner(
        client=client,
        poll_interval_seconds=1.0,
        now=now,
        monotonic=monotonic,
        sleep=sleep,
    )

    result = runner.run(build_case())

    assert result.status is AcceptanceStatus.FAILED
    assert any(
        failure.code is AcceptanceFailureCode.DOCUMENT_SCOPE_VIOLATION
        and failure.stage == "deep_import_and_embedding"
        for failure in result.failures
    )
