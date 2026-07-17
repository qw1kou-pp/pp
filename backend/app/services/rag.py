import uuid

from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.models import (
    Document,
    DocumentChunk,
    RagChatSource,
)
from app.services.llm import LLMError, call_llm
from app.services.embedding import EmbeddingError, semantic_search_chunks

def build_search_terms(query: str) -> list[str]:
    query = query.strip()

    if not query:
        return []

    terms = [term.strip() for term in query.split() if term.strip()]

    if not terms:
        return [query]

    return terms


def count_keyword_matches(content: str, terms: list[str]) -> int:
    content_lower = content.lower()
    count = 0

    for term in terms:
        term_lower = term.lower()
        count += content_lower.count(term_lower)

    return count


def retrieve_chunks_for_rag(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    query: str,
    top_k: int,
) -> list[tuple[DocumentChunk, Document, int]]:
    """
    RAG 检索阶段。

    当前版本是关键词检索：
    1. 把用户问题拆成关键词
    2. 在 DocumentChunk.content 和 Document.original_filename 中查找
    3. 根据关键词命中次数排序
    4. 返回 top_k 个 chunk
    """
    terms = build_search_terms(query)

    if not terms:
        return []

    search_conditions = []

    for term in terms:
        pattern = f"%{term}%"
        search_conditions.append(col(DocumentChunk.content).ilike(pattern))
        search_conditions.append(col(Document.original_filename).ilike(pattern))

    statement = (
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.knowledge_base_id == knowledge_base_id)
        .where(or_(*search_conditions))
        .order_by(col(DocumentChunk.chunk_index))
        .limit(top_k * 3)
    )

    rows = session.exec(statement).all()

    scored_rows: list[tuple[DocumentChunk, Document, int]] = []

    for chunk, document in rows:
        match_count = count_keyword_matches(chunk.content, terms)
        scored_rows.append((chunk, document, match_count))

    scored_rows.sort(
        key=lambda row: (
            -row[2],
            row[1].original_filename,
            row[0].chunk_index,
        )
    )

    return scored_rows[:top_k]


def hybrid_retrieve_chunks_for_rag(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    query: str,
    top_k: int,
    semantic_weight: float = 0.75,
    keyword_weight: float = 0.25,
) -> list[tuple[DocumentChunk, Document, float, int, float]]:
    """
    Hybrid Search：
    同时使用语义检索和关键词检索，然后融合排序。

    返回：
    (chunk, document, similarity, match_count, hybrid_score)
    """
    candidates: dict[uuid.UUID, dict] = {}

    try:
        semantic_rows = semantic_search_chunks(
            session=session,
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=top_k * 3,
        )
    except EmbeddingError:
        semantic_rows = []

    for chunk, document, similarity in semantic_rows:
        candidates[chunk.id] = {
            "chunk": chunk,
            "document": document,
            "similarity": similarity,
            "match_count": 0,
        }

    keyword_rows = retrieve_chunks_for_rag(
        session=session,
        knowledge_base_id=knowledge_base_id,
        query=query,
        top_k=top_k * 3,
    )

    for chunk, document, match_count in keyword_rows:
        if chunk.id not in candidates:
            candidates[chunk.id] = {
                "chunk": chunk,
                "document": document,
                "similarity": 0.0,
                "match_count": match_count,
            }
        else:
            candidates[chunk.id]["match_count"] = match_count

    if not candidates:
        return []

    max_match_count = max(
        item["match_count"]
        for item in candidates.values()
    )

    results: list[tuple[DocumentChunk, Document, float, int, float]] = []

    for item in candidates.values():
        similarity = float(item["similarity"] or 0.0)
        match_count = int(item["match_count"] or 0)

        keyword_score = 0.0
        if max_match_count > 0:
            keyword_score = match_count / max_match_count

        hybrid_score = (
            semantic_weight * similarity
            + keyword_weight * keyword_score
        )

        results.append(
            (
                item["chunk"],
                item["document"],
                similarity,
                match_count,
                hybrid_score,
            )
        )

    results.sort(key=lambda row: row[4], reverse=True)

    return results[:top_k]

def build_rag_context(
    *,
    sources: list[RagChatSource],
) -> str:
    """
    Context Builder。

    把检索到的 chunk 组织成大模型能读懂的上下文。
    """
    context_parts = []

    for index, source in enumerate(sources, start=1):
        context_parts.append(
            f"[资料 {index}]\n"
            f"来源文件：{source.original_filename}\n"
            f"Chunk：{source.chunk_index}\n"
            f"内容：\n{source.content}"
        )

    return "\n\n".join(context_parts)


def build_rag_prompt(
    *,
    question: str,
    sources: list[RagChatSource],
) -> str:
    """
    Prompt Builder。

    后面接真实 LLM 时，就把这个 prompt 发送给大模型。
    """
    context = build_rag_context(sources=sources)

    return f"""
你是一名严谨的知识库问答助手。

请根据下面的知识库资料回答用户问题。

要求：
1. 只能根据给定资料回答。
2. 如果资料不足，请明确说明“当前知识库资料不足，无法可靠回答”。
3. 不要编造资料中没有的信息。
4. 回答要清晰、有条理。
5. 回答最后可以简要说明依据来源。

用户问题：
{question}

知识库资料：
{context}

请开始回答：
""".strip()


def generate_rag_answer(
    *,
    question: str,
    sources: list[RagChatSource],
) -> str:
    """
    Answer Generator。

    RAG Chat v1：
    1. 没有检索结果时，返回可控 fallback
    2. 有检索结果时，构造 prompt
    3. 调用真实 LLM
    4. 如果 LLM 调用失败，返回降级回答
    """
    if not sources:
        return (
            "当前知识库中没有检索到与问题直接相关的资料，"
            "因此我暂时不能基于知识库给出可靠回答。"
        )

    prompt = build_rag_prompt(
        question=question,
        sources=sources,
    )

    try:
        return call_llm(prompt)
    except LLMError as error:
        context = build_rag_context(sources=sources)

        return (
            "大模型调用失败，因此当前返回检索到的原始资料，"
            "你可以先根据这些资料判断检索是否正确。\n\n"
            f"错误信息：{error}\n\n"
            "【检索到的资料】\n\n"
            f"{context}"
        )