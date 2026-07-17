import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.knowledge_base import create_random_knowledge_base


def create_knowledge_base_by_api(
    client: TestClient,
    headers: dict[str, str],
) -> dict:
    data = {
        "name": "Test Knowledge Base",
        "description": "Used for document tests",
    }

    response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/",
        headers=headers,
        json=data,
    )

    assert response.status_code == 200
    return response.json()


def test_upload_document_without_login(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    knowledge_base = create_knowledge_base_by_api(
        client,
        normal_user_token_headers,
    )

    files = {
        "file": ("test.txt", b"hello document", "text/plain"),
    }

    response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base['id']}/documents/",
        files=files,
    )

    assert response.status_code == 401


def test_upload_document(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    knowledge_base = create_knowledge_base_by_api(
        client,
        normal_user_token_headers,
    )

    files = {
        "file": ("test.txt", b"hello document", "text/plain"),
    }

    response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base['id']}/documents/",
        headers=normal_user_token_headers,
        files=files,
    )

    assert response.status_code == 200

    content = response.json()
    assert content["original_filename"] == "test.txt"
    assert content["content_type"] == "text/plain"
    assert content["file_size"] == len(b"hello document")
    assert content["status"] == "uploaded"
    assert "id" in content
    assert "filename" in content
    assert "storage_path" in content
    assert "knowledge_base_id" in content
    assert "owner_id" in content

    storage_path = Path(content["storage_path"])
    assert storage_path.exists()


def test_upload_document_to_other_users_knowledge_base(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    knowledge_base = create_random_knowledge_base(db)

    files = {
        "file": ("test.txt", b"hello document", "text/plain"),
    }

    response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base.id}/documents/",
        headers=normal_user_token_headers,
        files=files,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_upload_document_to_not_found_knowledge_base(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    files = {
        "file": ("test.txt", b"hello document", "text/plain"),
    }

    response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{uuid.uuid4()}/documents/",
        headers=normal_user_token_headers,
        files=files,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge base not found"


def test_upload_unsupported_file_type(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    knowledge_base = create_knowledge_base_by_api(
        client,
        normal_user_token_headers,
    )

    files = {
        "file": ("test.exe", b"bad file", "application/octet-stream"),
    }

    response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base['id']}/documents/",
        headers=normal_user_token_headers,
        files=files,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type"


def test_upload_too_large_file(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    knowledge_base = create_knowledge_base_by_api(
        client,
        normal_user_token_headers,
    )

    large_content = b"x" * (20 * 1024 * 1024 + 1)

    files = {
        "file": ("large.txt", large_content, "text/plain"),
    }

    response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base['id']}/documents/",
        headers=normal_user_token_headers,
        files=files,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File too large"


def test_download_document(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    knowledge_base = create_knowledge_base_by_api(
        client,
        normal_user_token_headers,
    )

    files = {
        "file": ("test.txt", b"hello document", "text/plain"),
    }

    upload_response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base['id']}/documents/",
        headers=normal_user_token_headers,
        files=files,
    )

    assert upload_response.status_code == 200

    document = upload_response.json()

    download_response = client.get(
        f"{settings.API_V1_STR}/documents/{document['id']}/download",
        headers=normal_user_token_headers,
    )

    assert download_response.status_code == 200
    assert download_response.content == b"hello document"


def test_read_documents_by_knowledge_base(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    knowledge_base = create_knowledge_base_by_api(
        client,
        normal_user_token_headers,
    )

    files = {
        "file": ("test.txt", b"hello document", "text/plain"),
    }

    upload_response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base['id']}/documents/",
        headers=normal_user_token_headers,
        files=files,
    )
    assert upload_response.status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base['id']}/documents/",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200

    content = response.json()
    assert "data" in content
    assert "count" in content
    assert content["count"] >= 1
    assert len(content["data"]) >= 1


def test_read_documents_from_other_users_knowledge_base(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    knowledge_base = create_random_knowledge_base(db)

    response = client.get(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base.id}/documents/",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_read_document(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    knowledge_base = create_knowledge_base_by_api(
        client,
        normal_user_token_headers,
    )

    files = {
        "file": ("test.txt", b"hello document", "text/plain"),
    }

    upload_response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base['id']}/documents/",
        headers=normal_user_token_headers,
        files=files,
    )
    assert upload_response.status_code == 200

    document = upload_response.json()

    response = client.get(
        f"{settings.API_V1_STR}/documents/{document['id']}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200

    content = response.json()
    assert content["id"] == document["id"]
    assert content["original_filename"] == "test.txt"


def test_read_document_not_found(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/documents/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_delete_document(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    knowledge_base = create_knowledge_base_by_api(
        client,
        normal_user_token_headers,
    )

    files = {
        "file": ("test.txt", b"hello document", "text/plain"),
    }

    upload_response = client.post(
        f"{settings.API_V1_STR}/knowledge-bases/{knowledge_base['id']}/documents/",
        headers=normal_user_token_headers,
        files=files,
    )
    assert upload_response.status_code == 200

    document = upload_response.json()
    storage_path = Path(document["storage_path"])
    assert storage_path.exists()

    delete_response = client.delete(
        f"{settings.API_V1_STR}/documents/{document['id']}",
        headers=normal_user_token_headers,
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Document deleted successfully"
    assert not storage_path.exists()

    get_response = client.get(
        f"{settings.API_V1_STR}/documents/{document['id']}",
        headers=normal_user_token_headers,
    )

    assert get_response.status_code == 404


def test_delete_other_users_document(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    knowledge_base = create_random_knowledge_base(db)

    storage_dir = Path("storage/documents") / str(knowledge_base.owner_id) / str(
        knowledge_base.id
    )
    storage_dir.mkdir(parents=True, exist_ok=True)

    file_content = b"other user document"
    storage_path = storage_dir / "other.txt"
    storage_path.write_bytes(file_content)

    from app.models import Document

    document = Document(
        knowledge_base_id=knowledge_base.id,
        owner_id=knowledge_base.owner_id,
        filename="other.txt",
        original_filename="other.txt",
        content_type="text/plain",
        file_size=len(file_content),
        storage_path=str(storage_path),
        status="uploaded",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    response = client.delete(
        f"{settings.API_V1_STR}/documents/{document.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"