import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    KnowledgeBase,          # 数据库表模型，table=true
    KnowledgeBaseCreate,    # 创建知识库，前端给后端传的数据模型（id，oownerid，createdat自动生成）
    KnowledgeBasePublic,    # 返回给前端的单个知识库模型
    KnowledgeBasesPublic,
    KnowledgeBaseUpdate,    # 更新数据模型
    Message,
    Document,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.get("/", response_model=KnowledgeBasesPublic)
def read_knowledge_bases(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve knowledge bases.

    Superusers can view all knowledge bases.
    Normal users can only view their own knowledge bases.
    """

    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(KnowledgeBase)
        count = session.exec(count_statement).one()

        statement = (
            select(KnowledgeBase)
            .order_by(col(KnowledgeBase.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        knowledge_bases = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()

        statement = (
            select(KnowledgeBase)
            .where(KnowledgeBase.owner_id == current_user.id)
            .order_by(col(KnowledgeBase.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        knowledge_bases = session.exec(statement).all()

    knowledge_bases_public = [
        KnowledgeBasePublic.model_validate(knowledge_base)
        for knowledge_base in knowledge_bases
    ]

    return KnowledgeBasesPublic(data=knowledge_bases_public, count=count)


@router.post("/", response_model=KnowledgeBasePublic)
def create_knowledge_base(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_in: KnowledgeBaseCreate,
) -> Any:
    """
    Create a new knowledge base.

    The owner_id is automatically set to current_user.id.
    The frontend should not pass owner_id.
    """

    knowledge_base = KnowledgeBase.model_validate(
        knowledge_base_in,
        update={"owner_id": current_user.id},
    )

    session.add(knowledge_base)
    session.commit()
    session.refresh(knowledge_base)

    return knowledge_base


@router.get("/{id}", response_model=KnowledgeBasePublic)
def read_knowledge_base(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """
    Get a knowledge base by ID.
    """

    knowledge_base = session.get(KnowledgeBase, id)

    if not knowledge_base:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    if (
        not current_user.is_superuser
        and knowledge_base.owner_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return knowledge_base


@router.put("/{id}", response_model=KnowledgeBasePublic)
def update_knowledge_base(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    knowledge_base_in: KnowledgeBaseUpdate,
) -> Any:
    """
    Update a knowledge base.
    """

    knowledge_base = session.get(KnowledgeBase, id)

    if not knowledge_base:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    if (
        not current_user.is_superuser
        and knowledge_base.owner_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_dict = knowledge_base_in.model_dump(exclude_unset=True)
    knowledge_base.sqlmodel_update(update_dict)

    session.add(knowledge_base)
    session.commit()
    session.refresh(knowledge_base)

    return knowledge_base


@router.delete("/{id}")
def delete_knowledge_base(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Message:
    """
    Delete a knowledge base.
    """

    knowledge_base = session.get(KnowledgeBase, id)

    if not knowledge_base:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    if (
        not current_user.is_superuser
        and knowledge_base.owner_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    documents = session.exec(
        select(Document).where(Document.knowledge_base_id == knowledge_base.id)
    ).all()

    for document in documents:
        storage_path = Path(document.storage_path)
        if storage_path.exists() and storage_path.is_file():
            try:
                storage_path.unlink()
            except OSError:
                pass

    session.delete(knowledge_base)
    session.commit()
    session.delete(knowledge_base)
    session.commit()

    return Message(message="Knowledge base deleted successfully")