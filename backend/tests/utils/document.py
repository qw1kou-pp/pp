from pathlib import Path

from sqlmodel import Session

from app.models import Document
from tests.utils.knowledge_base import create_random_knowledge_base


def create_random_document(db: Session) -> Document:
    knowledge_base = create_random_knowledge_base(db)

    storage_dir = Path("storage/documents") / str(knowledge_base.owner_id) / str(
        knowledge_base.id
    )
    storage_dir.mkdir(parents=True, exist_ok=True)

    file_content = b"test document content"
    filename = "test.txt"
    storage_path = storage_dir / filename
    storage_path.write_bytes(file_content)

    document = Document(
        knowledge_base_id=knowledge_base.id,
        owner_id=knowledge_base.owner_id,
        filename=filename,
        original_filename="test.txt",
        content_type="text/plain",
        file_size=len(file_content),
        storage_path=str(storage_path),
        status="uploaded",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document