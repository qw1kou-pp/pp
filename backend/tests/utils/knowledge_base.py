import uuid

from sqlmodel import Session

from app.models import KnowledgeBase, KnowledgeBaseCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_knowledge_base(
    db: Session,
    owner_id: uuid.UUID | None = None,
) -> KnowledgeBase:
    if owner_id is None:
        user = create_random_user(db)
        owner_id = user.id

    name = random_lower_string()
    description = random_lower_string()

    knowledge_base_in = KnowledgeBaseCreate(
        name=name,
        description=description,
    )

    knowledge_base = KnowledgeBase.model_validate(
        knowledge_base_in,
        update={"owner_id": owner_id},
    )

    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)

    return knowledge_base