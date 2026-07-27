from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlmodel import Session

from app.models import (
    KnowledgeBase,
    RepositoryAnalysisKnowledgeBaseRequest,
    RepositoryAnalysisTask,
    get_datetime_utc,
)
from app.services.repository_analysis_task import (
    get_repository_analysis_task,
)


class RepositoryAnalysisKnowledgeBaseError(
    RuntimeError,
):
    """仓库分析任务绑定知识库的基础异常。"""


class RepositoryAnalysisKnowledgeBaseRequestError(
    RepositoryAnalysisKnowledgeBaseError,
):
    """绑定请求参数不合法。"""


class RepositoryAnalysisKnowledgeBaseTaskStateError(
    RepositoryAnalysisKnowledgeBaseError,
):
    """仓库分析任务当前状态不允许绑定知识库。"""


class RepositoryAnalysisKnowledgeBaseNotFoundError(
    RepositoryAnalysisKnowledgeBaseError,
):
    """目标知识库不存在。"""


class RepositoryAnalysisKnowledgeBaseForbiddenError(
    RepositoryAnalysisKnowledgeBaseError,
):
    """当前用户无权使用目标知识库。"""


class RepositoryAnalysisKnowledgeBaseConflictError(
    RepositoryAnalysisKnowledgeBaseError,
):
    """任务已经绑定到另一个知识库。"""


@dataclass(
    frozen=True,
    slots=True,
)
class RepositoryAnalysisKnowledgeBaseBinding:
    """
    绑定服务返回的数据。
    """

    task: RepositoryAnalysisTask
    knowledge_base: KnowledgeBase
    created_new_knowledge_base: bool


def bind_repository_analysis_knowledge_base(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
    request: RepositoryAnalysisKnowledgeBaseRequest,
) -> RepositoryAnalysisKnowledgeBaseBinding | None:
    """
    为完成的仓库分析任务绑定知识库。

    可以选择已有知识库，也可以现场创建新知识库。

    绑定成功后：
    1. 写入 knowledge_base_id；
    2. 自动保存仓库分析记录；
    3. 清除 expires_at，避免任务过期。
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
            RepositoryAnalysisKnowledgeBaseTaskStateError(
                "Only completed repository analyses "
                "can be bound to a knowledge base",
            )
        )

    (
        knowledge_base,
        created_new_knowledge_base,
    ) = _resolve_knowledge_base(
        session=session,
        owner_id=owner_id,
        task=task,
        request=request,
    )

    task.knowledge_base_id = knowledge_base.id

    # 深度分析需要在后续继续访问该任务，
    # 因此绑定知识库时自动将任务保存为长期记录。
    task.is_saved = True
    task.expires_at = None
    task.updated_at = get_datetime_utc()

    try:
        session.add(task)
        session.commit()

        session.refresh(task)
        session.refresh(knowledge_base)
    except Exception:
        session.rollback()
        raise

    return RepositoryAnalysisKnowledgeBaseBinding(
        task=task,
        knowledge_base=knowledge_base,
        created_new_knowledge_base=(
            created_new_knowledge_base
        ),
    )


def _resolve_knowledge_base(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task: RepositoryAnalysisTask,
    request: RepositoryAnalysisKnowledgeBaseRequest,
) -> tuple[KnowledgeBase, bool]:
    """
    根据请求选择已有知识库或创建新知识库。

    返回值：
    tuple[KnowledgeBase, bool]

    bool 为 True 表示本次创建了新知识库。
    """

    requested_id = request.knowledge_base_id

    requested_name = str(
        request.knowledge_base_name or "",
    ).strip()

    requested_description = (
        str(
            request.knowledge_base_description,
        ).strip()
        if (
            request.knowledge_base_description
            is not None
        )
        else None
    )

    if (
        requested_id is not None
        and requested_name
    ):
        raise (
            RepositoryAnalysisKnowledgeBaseRequestError(
                "Choose an existing knowledge base "
                "or create a new one, not both",
            )
        )

    if (
        requested_id is not None
        and requested_description
    ):
        raise (
            RepositoryAnalysisKnowledgeBaseRequestError(
                "knowledge_base_description is only "
                "valid when creating a knowledge base",
            )
        )

    # 如果任务以前已经绑定过知识库，
    # 只允许继续使用原来的知识库。
    if task.knowledge_base_id is not None:
        if (
            requested_id is not None
            and (
                requested_id
                != task.knowledge_base_id
            )
        ):
            raise (
                RepositoryAnalysisKnowledgeBaseConflictError(
                    "The repository analysis is already "
                    "bound to another knowledge base",
                )
            )

        if requested_name:
            raise (
                RepositoryAnalysisKnowledgeBaseConflictError(
                    "The repository analysis is already "
                    "bound to a knowledge base",
                )
            )

        knowledge_base = session.get(
            KnowledgeBase,
            task.knowledge_base_id,
        )

        if knowledge_base is None:
            raise (
                RepositoryAnalysisKnowledgeBaseNotFoundError(
                    "The bound knowledge base "
                    "no longer exists",
                )
            )

        _check_knowledge_base_owner(
            knowledge_base=knowledge_base,
            owner_id=owner_id,
        )

        return knowledge_base, False

    # 使用已有知识库。
    if requested_id is not None:
        knowledge_base = session.get(
            KnowledgeBase,
            requested_id,
        )

        if knowledge_base is None:
            raise (
                RepositoryAnalysisKnowledgeBaseNotFoundError(
                    "Knowledge base was not found",
                )
            )

        _check_knowledge_base_owner(
            knowledge_base=knowledge_base,
            owner_id=owner_id,
        )

        return knowledge_base, False

    # 创建新知识库。
    if not requested_name:
        raise (
            RepositoryAnalysisKnowledgeBaseRequestError(
                "knowledge_base_id or "
                "knowledge_base_name is required",
            )
        )

    knowledge_base = KnowledgeBase(
        name=requested_name,
        description=(
            requested_description or None
        ),
        owner_id=owner_id,
    )

    session.add(knowledge_base)

    # flush 会先生成 knowledge_base.id，
    # 但不会单独提交事务。
    # 后续如果任务绑定失败，整个事务仍然可以回滚。
    session.flush()

    return knowledge_base, True


def _check_knowledge_base_owner(
    *,
    knowledge_base: KnowledgeBase,
    owner_id: uuid.UUID,
) -> None:
    """
    验证知识库属于当前用户。
    """

    if knowledge_base.owner_id != owner_id:
        raise (
            RepositoryAnalysisKnowledgeBaseForbiddenError(
                "The knowledge base does not belong "
                "to the current user",
            )
        )