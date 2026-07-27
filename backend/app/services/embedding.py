import json
import math
import os
import uuid

import requests
from sqlmodel import Session, col, select, func
from sqlalchemy import or_
from app.models import Document, DocumentChunk


class EmbeddingError(Exception):
    pass


def get_embedding_model() -> str:
    return os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def get_embedding(text: str) -> list[float]:
    api_key = os.getenv("EMBEDDING_API_KEY")
    api_base = os.getenv("EMBEDDING_API_BASE", "https://ws-v76bnql9ktn95r7o.cn-beijing.maas.aliyuncs.com/compatible-mode/v1")
    model = get_embedding_model()

    if not api_key:
        raise EmbeddingError("EMBEDDING_API_KEY is not configured")

    clean_text = text.replace("\n", " ").strip()

    if not clean_text:
        raise EmbeddingError("Cannot embed empty text")

    url = f"{api_base.rstrip('/')}/embeddings"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "input": clean_text,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise EmbeddingError(f"Embedding request failed: {error}") from error

    data = response.json()

    try:
        embedding = data["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as error:
        raise EmbeddingError(f"Unexpected embedding response format: {data}") from error

    if not isinstance(embedding, list):
        raise EmbeddingError("Embedding response is not a list")

    return [float(value) for value in embedding]

def embedding_to_json(embedding: list[float]) -> str:
    return json.dumps(embedding, ensure_ascii=False, separators=(",", ":"))


def embedding_from_json(embedding_json: str | None) -> list[float]:
    if not embedding_json:
        return []

    try:
        values = json.loads(embedding_json)
    except json.JSONDecodeError:
        return []

    if not isinstance(values, list):
        return []

    return [float(value) for value in values]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0

    if len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def embed_document_chunk(
    *,
    session: Session,
    chunk: DocumentChunk,
) -> None:
    chunk.embedding_model = get_embedding_model()

    try:
        embedding = get_embedding(chunk.content)
        chunk.embedding = embedding_to_json(embedding)
        chunk.embedding_status = "embedded"
        chunk.embedding_error = None
    except Exception as error:
        chunk.embedding = None
        chunk.embedding_status = "failed"
        chunk.embedding_error = str(error)[:1024]

    session.add(chunk)


def semantic_search_chunks(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    query: str,
    top_k: int,
    repository_analysis_task_id: (
        uuid.UUID | None
    ) = None,
) -> list[
    tuple[
        DocumentChunk,
        Document,
        float,
    ]
]:
    query_embedding = get_embedding(query)

    statement = (
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.knowledge_base_id == knowledge_base_id)
        .where(DocumentChunk.embedding_status == "embedded")
        .where(col(DocumentChunk.embedding).is_not(None))
    )
    if repository_analysis_task_id is not None:
        statement = statement.where(
            Document.repository_analysis_task_id
            == repository_analysis_task_id,
        )

    rows = session.exec(statement).all()

    scored_rows: list[tuple[DocumentChunk, Document, float]] = []

    for chunk, document in rows:
        chunk_embedding = embedding_from_json(chunk.embedding)
        similarity = cosine_similarity(query_embedding, chunk_embedding)

        scored_rows.append((chunk, document, similarity))

    scored_rows.sort(key=lambda row: row[2], reverse=True)

    return scored_rows[:top_k]

def build_backfill_conditions(
    *,
    retry_failed: bool,
    force: bool,
):
    if force:
        return []

    conditions = [
        col(DocumentChunk.embedding).is_(None),
        DocumentChunk.embedding_status == "pending",
    ]

    if retry_failed:
        conditions.append(DocumentChunk.embedding_status == "failed")

    return [or_(*conditions)]


def backfill_chunk_embeddings(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    limit: int,
    retry_failed: bool = False,
    force: bool = False,
) -> dict:
    """
    给旧的 DocumentChunk 回填 embedding。

    默认只处理：
    1. embedding 为空的 chunk
    2. embedding_status 为 pending 的 chunk

    如果 retry_failed=True，则也会重新处理 failed 的 chunk。
    如果 force=True，则会强制重新生成当前知识库全部 chunk 的 embedding。
    """
    conditions = build_backfill_conditions(
        retry_failed=retry_failed,
        force=force,
    )

    statement = (
        select(DocumentChunk)
        .where(DocumentChunk.knowledge_base_id == knowledge_base_id)
        .where(*conditions)
        .order_by(col(DocumentChunk.created_at))
        .limit(limit)
    )

    chunks = session.exec(statement).all()

    embedded = 0
    failed = 0

    for chunk in chunks:
        embed_document_chunk(
            session=session,
            chunk=chunk,
        )

        if chunk.embedding_status == "embedded":
            embedded += 1
        else:
            failed += 1

    session.commit()

    remaining_statement = (
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.knowledge_base_id == knowledge_base_id)
        .where(*conditions)
    )

    remaining = session.exec(remaining_statement).one()

    return {
        "model": get_embedding_model(),
        "processed": len(chunks),
        "embedded": embedded,
        "failed": failed,
        "remaining": remaining,
    }