from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    KnowledgeBasePublic,
    RepositoryAnalysisKnowledgeBaseBindingPublic,
    RepositoryAnalysisKnowledgeBaseRequest,
    RepositoryAnalysisKnowledgeImportPublic,
    RepositoryAnalysisTaskCreate,
    RepositoryAnalysisTaskPublic,
    RepositoryAnalysisTasksPublic,
    RepositoryAnalysisEmbeddingBatchPublic,
    RepositoryAnalysisEmbeddingBatchRequest,
    RepositoryAnalysisEmbeddingStatusPublic,
)
from app.services.github_repository_reference import (
    InvalidGitHubRepositoryUrlError,
    parse_public_github_repository_url,
)
from app.services.repository_analysis_task import (
    create_repository_analysis_task,
    get_repository_analysis_task_detail,
    list_repository_analysis_tasks,
    save_repository_analysis_task,
    serialize_repository_analysis_task_detail,
)
from app.services.repository_analysis_knowledge_base import (
    RepositoryAnalysisKnowledgeBaseConflictError,
    RepositoryAnalysisKnowledgeBaseForbiddenError,
    RepositoryAnalysisKnowledgeBaseNotFoundError,
    RepositoryAnalysisKnowledgeBaseRequestError,
    RepositoryAnalysisKnowledgeBaseTaskStateError,
    bind_repository_analysis_knowledge_base,
)
from app.services.repository_analysis_knowledge_import import (
    RepositoryAnalysisKnowledgeImportCommitError,
    RepositoryAnalysisKnowledgeImportKnowledgeBaseError,
    RepositoryAnalysisKnowledgeImportNoFilesError,
    RepositoryAnalysisKnowledgeImportNotBoundError,
    RepositoryAnalysisKnowledgeImportSnapshotError,
    RepositoryAnalysisKnowledgeImportStorageError,
    RepositoryAnalysisKnowledgeImportTaskStateError,
    RepositoryAnalysisKnowledgeImportTooLargeError,
    import_repository_analysis_into_knowledge_base,
)
from app.services.repository_analysis_embedding import (
    RepositoryAnalysisEmbeddingKnowledgeBaseError,
    RepositoryAnalysisEmbeddingNotBoundError,
    RepositoryAnalysisEmbeddingTaskStateError,
    get_repository_analysis_embedding_status,
    process_repository_analysis_embedding_batch,
)

router = APIRouter(
    prefix="/repository-analyses",
    tags=["repository-analyses"],
)


@router.post(
    "",
    response_model=RepositoryAnalysisTaskPublic,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_repository_analysis(
    request: RepositoryAnalysisTaskCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> RepositoryAnalysisTaskPublic:
    """
    创建公开 GitHub 仓库快速概览任务。

    这里只创建 queued 任务，不在 HTTP 请求中执行仓库分析。
    """

    try:
        repository = parse_public_github_repository_url(
            request.repository_url,
        )

        task = create_repository_analysis_task(
            session=session,
            owner_id=current_user.id,
            request=request,
            repository=repository,
        )
    except InvalidGitHubRepositoryUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_GITHUB_REPOSITORY_URL",
                "message": str(exc),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_REPOSITORY_ANALYSIS_REQUEST",
                "message": str(exc),
            },
        ) from exc

    return serialize_repository_analysis_task_detail(task)


@router.get(
    "",
    response_model=RepositoryAnalysisTasksPublic,
)
def read_repository_analyses(
    session: SessionDep,
    current_user: CurrentUser,
    skip: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 20,
    task_status: Annotated[
        str | None,
        Query(alias="status"),
    ] = None,
) -> RepositoryAnalysisTasksPublic:
    """
    分页查询当前登录用户的仓库分析任务。

    status 可选值：
    queued、running、completed、failed、expired。
    """

    try:
        return list_repository_analysis_tasks(
            session=session,
            owner_id=current_user.id,
            skip=skip,
            limit=limit,
            status=task_status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_REPOSITORY_ANALYSIS_FILTER",
                "message": str(exc),
            },
        ) from exc


@router.get(
    "/{task_id}",
    response_model=RepositoryAnalysisTaskPublic,
)
def read_repository_analysis(
    task_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> RepositoryAnalysisTaskPublic:
    """
    查询当前用户的一条仓库分析任务详情。
    """

    task = get_repository_analysis_task_detail(
        session=session,
        owner_id=current_user.id,
        task_id=task_id,
    )

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REPOSITORY_ANALYSIS_NOT_FOUND",
                "message": "Repository analysis task was not found",
            },
        )

    return task


@router.post(
    "/{task_id}/save",
    response_model=RepositoryAnalysisTaskPublic,
)
def save_repository_analysis(
    task_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> RepositoryAnalysisTaskPublic:
    """
    将完成的临时仓库概览保存为长期记录。
    """

    try:
        task = save_repository_analysis_task(
            session=session,
            owner_id=current_user.id,
            task_id=task_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REPOSITORY_ANALYSIS_NOT_COMPLETED",
                "message": str(exc),
            },
        ) from exc

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REPOSITORY_ANALYSIS_NOT_FOUND",
                "message": "Repository analysis task was not found",
            },
        )

    return serialize_repository_analysis_task_detail(task)


@router.post(
    "/{task_id}/knowledge-base",
    response_model=(
        RepositoryAnalysisKnowledgeBaseBindingPublic
    ),
    operation_id=(
        "bind_repository_analysis_knowledge_base"
    ),
)
def bind_repository_analysis_knowledge_base_endpoint(
    task_id: uuid.UUID,
    request: RepositoryAnalysisKnowledgeBaseRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> RepositoryAnalysisKnowledgeBaseBindingPublic:
    """
    选择或创建知识库，并绑定仓库分析任务。
    """

    try:
        result = (
            bind_repository_analysis_knowledge_base(
                session=session,
                owner_id=current_user.id,
                task_id=task_id,
                request=request,
            )
        )
    except (
        RepositoryAnalysisKnowledgeBaseRequestError
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail={
                "code": (
                    "INVALID_REPOSITORY_ANALYSIS_"
                    "KNOWLEDGE_BASE_REQUEST"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeBaseTaskStateError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_NOT_READY_"
                    "FOR_KNOWLEDGE_BASE"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeBaseConflictError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_"
                    "KNOWLEDGE_BASE_CONFLICT"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeBaseNotFoundError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "KNOWLEDGE_BASE_NOT_FOUND",
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeBaseForbiddenError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "KNOWLEDGE_BASE_FORBIDDEN",
                "message": str(exc),
            },
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_NOT_FOUND"
                ),
                "message": (
                    "Repository analysis task "
                    "was not found"
                ),
            },
        )

    return (
        RepositoryAnalysisKnowledgeBaseBindingPublic(
            task=(
                serialize_repository_analysis_task_detail(
                    result.task,
                )
            ),
            knowledge_base=(
                KnowledgeBasePublic.model_validate(
                    result.knowledge_base,
                )
            ),
            created_new_knowledge_base=(
                result.created_new_knowledge_base
            ),
        )
    )


@router.post(
    "/{task_id}/knowledge-base/import",
    response_model=(
        RepositoryAnalysisKnowledgeImportPublic
    ),
    operation_id=(
        "import_repository_analysis_knowledge_base"
    ),
)
def import_repository_analysis_knowledge_base(
    task_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> RepositoryAnalysisKnowledgeImportPublic:
    """
    把仓库分析任务固定的 Commit
    导入已经绑定的知识库。
    """

    try:
        result = (
            import_repository_analysis_into_knowledge_base(
                session=session,
                owner_id=current_user.id,
                task_id=task_id,
            )
        )
    except (
        RepositoryAnalysisKnowledgeImportTaskStateError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_"
                    "NOT_READY_FOR_IMPORT"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeImportNotBoundError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_"
                    "KNOWLEDGE_BASE_NOT_BOUND"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeImportCommitError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_"
                    "COMMIT_NOT_RESOLVED"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeImportKnowledgeBaseError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": (
                    "BOUND_KNOWLEDGE_BASE_NOT_FOUND"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeImportNoFilesError
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail={
                "code": (
                    "NO_SUPPORTED_REPOSITORY_CODE_FILES"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeImportTooLargeError
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail={
                "code": (
                    "REPOSITORY_CODE_IMPORT_TOO_LARGE"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeImportSnapshotError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": (
                    "REPOSITORY_IMPORT_SNAPSHOT_FAILED"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisKnowledgeImportStorageError
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail={
                "code": (
                    "REPOSITORY_IMPORT_STORAGE_FAILED"
                ),
                "message": str(exc),
            },
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_NOT_FOUND"
                ),
                "message": (
                    "Repository analysis task "
                    "was not found"
                ),
            },
        )

    return (
        RepositoryAnalysisKnowledgeImportPublic(
            task_id=result.task_id,
            knowledge_base_id=(
                result.knowledge_base_id
            ),
            repository_full_name=(
                result.repository_full_name
            ),
            commit_sha=result.commit_sha,
            document_count=(
                result.document_count
            ),
            chunk_count=result.chunk_count,
            imported_bytes=(
                result.imported_bytes
            ),
            skipped_unsupported_file_count=(
                result
                .skipped_unsupported_file_count
            ),
            skipped_large_file_count=(
                result.skipped_large_file_count
            ),
            skipped_unreadable_file_count=(
                result
                .skipped_unreadable_file_count
            ),
            import_truncated=(
                result.import_truncated
            ),
            already_imported=(
                result.already_imported
            ),
        )
    )


@router.get(
    "/{task_id}/knowledge-base/embedding-status",
    response_model=(
        RepositoryAnalysisEmbeddingStatusPublic
    ),
    operation_id=(
        "read_repository_analysis_embedding_status"
    ),
)
def read_repository_analysis_embedding_status(
    task_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> RepositoryAnalysisEmbeddingStatusPublic:
    """
    查询当前仓库代码块的索引状态。
    """

    try:
        result = (
            get_repository_analysis_embedding_status(
                session=session,
                owner_id=current_user.id,
                task_id=task_id,
            )
        )
    except (
        RepositoryAnalysisEmbeddingTaskStateError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_"
                    "NOT_READY_FOR_EMBEDDING"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisEmbeddingNotBoundError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_"
                    "KNOWLEDGE_BASE_NOT_BOUND"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisEmbeddingKnowledgeBaseError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": (
                    "BOUND_KNOWLEDGE_BASE_NOT_FOUND"
                ),
                "message": str(exc),
            },
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_NOT_FOUND"
                ),
                "message": (
                    "Repository analysis task "
                    "was not found"
                ),
            },
        )

    return (
        RepositoryAnalysisEmbeddingStatusPublic(
            task_id=result.task_id,
            knowledge_base_id=(
                result.knowledge_base_id
            ),
            embedding_model=(
                result.embedding_model
            ),
            total_count=result.total_count,
            pending_count=result.pending_count,
            embedded_count=(
                result.embedded_count
            ),
            failed_count=result.failed_count,
            progress_percent=(
                result.progress_percent
            ),
            index_status=result.index_status,
            ready_for_search=(
                result.ready_for_search
            ),
            sample_error_message=(
                result.sample_error_message
            ),
        )
    )


@router.post(
    "/{task_id}/knowledge-base/embeddings/backfill",
    response_model=(
        RepositoryAnalysisEmbeddingBatchPublic
    ),
    operation_id=(
        "backfill_repository_analysis_embeddings"
    ),
)
def backfill_repository_analysis_embeddings(
    task_id: uuid.UUID,
    request: (
        RepositoryAnalysisEmbeddingBatchRequest
    ),
    session: SessionDep,
    current_user: CurrentUser,
) -> RepositoryAnalysisEmbeddingBatchPublic:
    """
    为当前仓库任务处理一批 Embedding。
    """

    try:
        result = (
            process_repository_analysis_embedding_batch(
                session=session,
                owner_id=current_user.id,
                task_id=task_id,
                limit=request.limit,
                retry_failed=(
                    request.retry_failed
                ),
            )
        )
    except (
        RepositoryAnalysisEmbeddingTaskStateError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_"
                    "NOT_READY_FOR_EMBEDDING"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisEmbeddingNotBoundError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_"
                    "KNOWLEDGE_BASE_NOT_BOUND"
                ),
                "message": str(exc),
            },
        ) from exc
    except (
        RepositoryAnalysisEmbeddingKnowledgeBaseError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": (
                    "BOUND_KNOWLEDGE_BASE_NOT_FOUND"
                ),
                "message": str(exc),
            },
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": (
                    "REPOSITORY_ANALYSIS_NOT_FOUND"
                ),
                "message": (
                    "Repository analysis task "
                    "was not found"
                ),
            },
        )

    return (
        RepositoryAnalysisEmbeddingBatchPublic(
            task_id=result.task_id,
            knowledge_base_id=(
                result.knowledge_base_id
            ),
            embedding_model=(
                result.embedding_model
            ),
            total_count=result.total_count,
            pending_count=result.pending_count,
            embedded_count=(
                result.embedded_count
            ),
            failed_count=result.failed_count,
            progress_percent=(
                result.progress_percent
            ),
            index_status=result.index_status,
            ready_for_search=(
                result.ready_for_search
            ),
            sample_error_message=(
                result.sample_error_message
            ),
            processed_count=(
                result.processed_count
            ),
            embedded_in_batch=(
                result.embedded_in_batch
            ),
            failed_in_batch=(
                result.failed_in_batch
            ),
        )
    )