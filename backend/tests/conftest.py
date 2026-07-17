from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, col

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import Item, KnowledgeBase, User, Document
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers
import shutil
from pathlib import Path
from app.models import (
    CodeReviewRun,
    KnowledgeBase,
    CodeReviewPublication,
)

@pytest.fixture(
    scope="session",
    autouse=True,
)
def db() -> Generator[
    Session,
    None,
    None,
]:
    database_name = (
        engine.url.database
        or ""
    )

    if not database_name.endswith(
        "_test",
    ):
        raise RuntimeError(
            "Refusing to run tests "
            "with destructive cleanup "
            "against non-test database: "
            f"{database_name}"
        )
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(
            CodeReviewRun,
            CodeReviewPublication,
            KnowledgeBase,

        )
        session.execute(statement)
        statement = delete(KnowledgeBase)
        session.execute(statement)
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User).where(col(User.email) != settings.FIRST_SUPERUSER)
        session.execute(statement)
        statement = delete(Document)
        session.execute(statement)
        session.commit()
        storage_dir = Path("storage/documents")
        if storage_dir.exists():
            shutil.rmtree(storage_dir)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
