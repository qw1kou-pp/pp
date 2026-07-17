import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import KnowledgeBase
from tests.utils.user import create_random_user


def create_random_knowledge_base(db: Session) -> KnowledgeBase:
    user = create_random_user(db)
    knowledge_base = KnowledgeBase(
        name="Random Knowledge Base",
        description="Random knowledge base description",
        owner_id=user.id,
    )
    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


def test_create_knowledge_base(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    data = {
        "name": "Test Knowledge Base",
        "description": "This is a test knowledge base",
    }
    response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert "owner_id" in content


def test_read_knowledge_base(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    knowledge_base = create_random_knowledge_base(db)
    response = client.get(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == knowledge_base.name
    assert content["description"] == knowledge_base.description
    assert content["id"] == str(knowledge_base.id)
    assert content["owner_id"] == str(knowledge_base.owner_id)


def test_read_knowledge_base_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/knowledge-bases/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Knowledge base not found"


def test_read_knowledge_base_not_enough_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    knowledge_base = create_random_knowledge_base(db)
    response = client.get(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_read_knowledge_bases(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    create_random_knowledge_base(db)
    create_random_knowledge_base(db)
    response = client.get(
        f"{settings.API_V1_STR}/knowledge-bases/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2


def test_update_knowledge_base(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    knowledge_base = create_random_knowledge_base(db)
    data = {
        "name": "Updated Knowledge Base",
        "description": "Updated description",
    }
    response = client.put(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["id"] == str(knowledge_base.id)
    assert content["owner_id"] == str(knowledge_base.owner_id)


def test_update_knowledge_base_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    data = {
        "name": "Updated Knowledge Base",
        "description": "Updated description",
    }
    response = client.put(
        f"{settings.API_V1_STR}/knowledge-bases/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Knowledge base not found"


def test_update_knowledge_base_not_enough_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    knowledge_base = create_random_knowledge_base(db)
    data = {
        "name": "Updated Knowledge Base",
        "description": "Updated description",
    }
    response = client.put(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_delete_knowledge_base(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    knowledge_base = create_random_knowledge_base(db)
    response = client.delete(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Knowledge base deleted successfully"


def test_delete_knowledge_base_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/knowledge-bases/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Knowledge base not found"


def test_delete_knowledge_base_not_enough_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    knowledge_base = create_random_knowledge_base(db)
    response = client.delete(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"