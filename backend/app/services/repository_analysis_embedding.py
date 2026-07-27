from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.models import (
    Document,
    DocumentChunk,
    KnowledgeBase,
    RepositoryAnalysisTask,
    get_datetime_utc,
)
from app.services.embedding import (
    embed_document_chunk,
    get_embedding_model,
)
from app.services.repository_analysis_task import (
    get_repository_analysis_task,
)


class RepositoryAnalysisEmbeddingError(
    RuntimeError,
):
    """仓库代码 Embedding 处理基础异常。"""


class RepositoryAnalysisEmbeddingTaskStateError(
    RepositoryAnalysisEmbeddingError,
):
    """仓库分析任务状态不允许生成索引。"""


class RepositoryAnalysisEmbeddingNotBoundError(
    RepositoryAnalysisEmbeddingError,
):
    """仓库分析任务尚未绑定知识库。"""


class RepositoryAnalysisEmbeddingKnowledgeBaseError(
    RepositoryAnalysisEmbeddingError,
):
    """绑定的知识库不存在或不属于当前用户。"""


@dataclass(
    frozen=True,
    slots=True,
)
class RepositoryAnalysisEmbeddingStatus:
    """
    仓库代码块的完整索引状态。
    """

    task_id: uuid.UUID
    knowledge_base_id: uuid.UUID

    embedding_model: str

    total_count: int
    pending_count: int
    embedded_count: int
    failed_count: int

    progress_percent: int

    index_status: str
    ready_for_search: bool

    sample_error_message: str | None


@dataclass(
    frozen=True,
    slots=True,
)
class RepositoryAnalysisEmbeddingBatchResult(
    RepositoryAnalysisEmbeddingStatus,
):
    """
    一次批处理的结果。
    """

    processed_count: int
    embedded_in_batch: int
    failed_in_batch: int


def get_repository_analysis_embedding_status(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
) -> RepositoryAnalysisEmbeddingStatus | None:
    """
    查询当前仓库分析任务的 Embedding 状态。

    这里只统计通过 repository_analysis_task_id
    导入的 DocumentChunk，不统计知识库中的其他文档。
    """

    resolved = _resolve_task_and_knowledge_base(
        session=session,
        owner_id=owner_id,
        task_id=task_id,
    )

    if resolved is None:
        return None

    task, _knowledge_base = resolved

    return _build_embedding_status(
        session=session,
        task=task,
    )


def process_repository_analysis_embedding_batch(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
    limit: int,
    retry_failed: bool = False,
) -> RepositoryAnalysisEmbeddingBatchResult | None:
    """
    给当前仓库任务处理一批 Embedding。

    默认只处理 pending；
    retry_failed=True 时同时处理 failed。

    每次最多处理 limit 个，避免一个 HTTP 请求
    持续太长时间。
    """

    resolved = _resolve_task_and_knowledge_base(
        session=session,
        owner_id=owner_id,
        task_id=task_id,
    )

    if resolved is None:
        return None

    task, _knowledge_base = resolved

    status_condition = (
        DocumentChunk.embedding_status
        == "pending"
    )

    if retry_failed:
        status_condition = or_(
            DocumentChunk.embedding_status
            == "pending",
            DocumentChunk.embedding_status
            == "failed",
        )

    statement = (
        select(DocumentChunk)
        .join(
            Document,
            Document.id
            == DocumentChunk.document_id,
        )
        .where(
            Document.repository_analysis_task_id
            == task.id,
        )
        .where(
            Document.knowledge_base_id
            == task.knowledge_base_id,
        )
        .where(
            Document.owner_id
            == owner_id,
        )
        .where(status_condition)
        .order_by(
            col(DocumentChunk.created_at),
            col(DocumentChunk.chunk_index),
        )
        .limit(limit)
    )

    chunks = list(
        session.exec(statement).all()
    )

    embedded_in_batch = 0
    failed_in_batch = 0

    for chunk in chunks:
        embed_document_chunk(
            session=session,
            chunk=chunk,
        )

        if (
            chunk.embedding_status
            == "embedded"
        ):
            embedded_in_batch += 1
        else:
            failed_in_batch += 1

    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    current_status = _build_embedding_status(
        session=session,
        task=task,
    )

    # 所有代码块处理结束，并且至少存在一个
    # 可用于检索的 Embedding 后，才正式标记
    # 为深度分析模式。
    if (
        current_status.ready_for_search
        and task.analysis_mode != "deep"
    ):
        task.analysis_mode = "deep"
        task.updated_at = get_datetime_utc()

        try:
            session.add(task)
            session.commit()
            session.refresh(task)
        except Exception:
            session.rollback()
            raise

    return (
        RepositoryAnalysisEmbeddingBatchResult(
            task_id=current_status.task_id,
            knowledge_base_id=(
                current_status.knowledge_base_id
            ),
            embedding_model=(
                current_status.embedding_model
            ),
            total_count=(
                current_status.total_count
            ),
            pending_count=(
                current_status.pending_count
            ),
            embedded_count=(
                current_status.embedded_count
            ),
            failed_count=(
                current_status.failed_count
            ),
            progress_percent=(
                current_status.progress_percent
            ),
            index_status=(
                current_status.index_status
            ),
            ready_for_search=(
                current_status.ready_for_search
            ),
            sample_error_message=(
                current_status
                .sample_error_message
            ),
            processed_count=len(chunks),
            embedded_in_batch=(
                embedded_in_batch
            ),
            failed_in_batch=(
                failed_in_batch
            ),
        )
    )


def _resolve_task_and_knowledge_base(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
) -> (
    tuple[
        RepositoryAnalysisTask,
        KnowledgeBase,
    ]
    | None
):
    """
    查询并验证仓库任务和知识库权限。
    """

    task = get_repository_analysis_task(
        session=session,
        owner_id=owner_id,
        task_id=task_id,
    )

    if task is None:
        return None

    if task.status != "completed":
        raise (
            RepositoryAnalysisEmbeddingTaskStateError(
                "Only completed repository analyses "
                "can generate embeddings",
            )
        )

    if task.knowledge_base_id is None:
        raise (
            RepositoryAnalysisEmbeddingNotBoundError(
                "Repository analysis is not bound "
                "to a knowledge base",
            )
        )

    knowledge_base = session.get(
        KnowledgeBase,
        task.knowledge_base_id,
    )

    if (
        knowledge_base is None
        or knowledge_base.owner_id
        != owner_id
    ):
        raise (
            RepositoryAnalysisEmbeddingKnowledgeBaseError(
                "The bound knowledge base "
                "was not found",
            )
        )

    return task, knowledge_base


def _build_embedding_status(
    *,
    session: Session,
    task: RepositoryAnalysisTask,
) -> RepositoryAnalysisEmbeddingStatus:
    """
    按当前 repository_analysis_task_id
    统计代码块状态。
    """

    total_count = _count_task_chunks(
        session=session,
        task=task,
    )

    embedded_count = _count_task_chunks(
        session=session,
        task=task,
        status="embedded",
        require_embedding=True,
    )

    failed_count = _count_task_chunks(
        session=session,
        task=task,
        status="failed",
    )

    # 除已成功和已失败之外的状态，
    # 都当作等待处理。
    pending_count = max(
        total_count
        - embedded_count
        - failed_count,
        0,
    )

    processed_count = (
        embedded_count + failed_count
    )

    if total_count <= 0:
        progress_percent = 0
    else:
        progress_percent = min(
            int(
                round(
                    processed_count
                    * 100
                    / total_count,
                )
            ),
            100,
        )

    if total_count == 0:
        index_status = "not_imported"
    elif pending_count > 0:
        index_status = "pending"
    elif (
        failed_count > 0
        and embedded_count == 0
    ):
        index_status = "failed"
    elif failed_count > 0:
        index_status = (
            "completed_with_errors"
        )
    else:
        index_status = "completed"

    ready_for_search = (
        total_count > 0
        and pending_count == 0
        and embedded_count > 0
    )

    error_statement = (
        select(
            DocumentChunk.embedding_error,
        )
        .join(
            Document,
            Document.id
            == DocumentChunk.document_id,
        )
        .where(
            Document.repository_analysis_task_id
            == task.id,
        )
        .where(
            DocumentChunk.embedding_status
            == "failed",
        )
        .where(
            col(
                DocumentChunk.embedding_error
            ).is_not(None),
        )
        .limit(1)
    )

    sample_error_message = (
        session.exec(
            error_statement,
        ).first()
    )

    return RepositoryAnalysisEmbeddingStatus(
        task_id=task.id,
        knowledge_base_id=(
            task.knowledge_base_id
        ),
        embedding_model=(
            get_embedding_model()
        ),
        total_count=total_count,
        pending_count=pending_count,
        embedded_count=embedded_count,
        failed_count=failed_count,
        progress_percent=progress_percent,
        index_status=index_status,
        ready_for_search=ready_for_search,
        sample_error_message=(
            str(sample_error_message)
            if sample_error_message
            else None
        ),
    )


def _count_task_chunks(
    *,
    session: Session,
    task: RepositoryAnalysisTask,
    status: str | None = None,
    require_embedding: bool = False,
) -> int:
    """
    统计当前仓库分析任务创建的代码块数量。
    """

    statement = (
        select(
            func.count(
                DocumentChunk.id,
            ),
        )
        .select_from(DocumentChunk)
        .join(
            Document,
            Document.id
            == DocumentChunk.document_id,
        )
        .where(
            Document.repository_analysis_task_id
            == task.id,
        )
        .where(
            Document.knowledge_base_id
            == task.knowledge_base_id,
        )
        .where(
            Document.owner_id
            == task.owner_id,
        )
    )

    if status is not None:
        statement = statement.where(
            DocumentChunk.embedding_status
            == status,
        )

    if require_embedding:
        statement = statement.where(
            col(
                DocumentChunk.embedding
            ).is_not(None),
        )

    return int(
        session.exec(statement).one()
    )