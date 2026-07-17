import re
import uuid
from pathlib import Path
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.models import Document, DocumentChunk, RagChatSource, RagRun
from app.services.rag import hybrid_retrieve_chunks_for_rag, build_search_terms, count_keyword_matches
from app.services.code_parser import is_code_file


def list_documents_tool(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    limit: int = 20,
) -> str:
    statement = (
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(col(Document.created_at).desc())
        .limit(limit)
    )

    documents = session.exec(statement).all()

    if not documents:
        return "当前知识库下还没有文档。"

    lines = ["当前知识库包含以下文档："]

    for index, document in enumerate(documents, start=1):
        lines.append(
            f"{index}. {document.original_filename} "
            f"(document_id={document.id})"
        )

    return "\n".join(lines)


def search_knowledge_base_tool(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    query: str,
    top_k: int,
    semantic_weight: float,
    keyword_weight: float,
) -> tuple[str, list[RagChatSource]]:
    rows = hybrid_retrieve_chunks_for_rag(
        session=session,
        knowledge_base_id=knowledge_base_id,
        query=query,
        top_k=top_k,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
    )

    sources = [
        RagChatSource(
            document_id=document.id,
            original_filename=document.original_filename,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            content_length=chunk.content_length,
            match_count=match_count,
            similarity=similarity,
            retrieval_type="hybrid",
        )
        for chunk, document, similarity, match_count, hybrid_score in rows
    ]

    if not sources:
        return "没有检索到和问题相关的知识库内容。", []

    lines = [f"检索到 {len(sources)} 条相关资料："]

    for index, source in enumerate(sources, start=1):
        similarity_text = (
            f"{source.similarity:.4f}"
            if source.similarity is not None
            else "-"
        )

        lines.append(
            f"[资料 {index}] 文件：{source.original_filename}，"
            f"Chunk：{source.chunk_index}，"
            f"相似度：{similarity_text}，"
            f"关键词命中：{source.match_count}\n"
            f"{source.content[:500]}"
        )

    return "\n\n".join(lines), sources


def read_document_chunks_tool(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    center_chunk_index: int,
    window: int = 1,
) -> tuple[str, list[RagChatSource]]:
    window = max(0, min(window, 5))

    document_statement = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.knowledge_base_id == knowledge_base_id)
    )

    document = session.exec(document_statement).first()

    if not document:
        return "没有找到指定文档，或者该文档不属于当前知识库。", []

    start_index = max(0, center_chunk_index - window)
    end_index = center_chunk_index + window

    chunk_statement = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .where(DocumentChunk.chunk_index >= start_index)
        .where(DocumentChunk.chunk_index <= end_index)
        .order_by(col(DocumentChunk.chunk_index).asc())
    )

    chunks = session.exec(chunk_statement).all()

    if not chunks:
        return (
            f"没有读取到文档 {document.original_filename} "
            f"中 chunk_index={center_chunk_index} 附近的内容。"
        ), []

    sources = [
        RagChatSource(
            document_id=document.id,
            original_filename=document.original_filename,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            content_length=chunk.content_length,
            match_count=0,
            similarity=None,
            retrieval_type="document_window",
        )
        for chunk in chunks
    ]

    lines = [
        f"已读取文档 {document.original_filename} 中 "
        f"chunk_index={center_chunk_index} 前后 {window} 个 chunk："
    ]

    for source in sources:
        lines.append(
            f"[Chunk {source.chunk_index}]\n"
            f"{source.content[:800]}"
        )

    return "\n\n".join(lines), sources

def extract_history_keywords(query: str) -> list[str]:
    text = query.lower().strip()

    stop_words = [
        "之前",
        "历史",
        "问过",
        "回答过",
        "上次",
        "最近",
        "相关",
        "关于",
        "帮我",
        "查一下",
        "搜索",
        "rag",
        "问答",
        "记录",
        "什么",
        "哪些",
        "吗",
        "呢",
        "？",
        "?",
        "，",
        ",",
        "的",
    ]

    for word in stop_words:
        text = text.replace(word, " ")

    text = text.replace("_", " ")

    keywords = [
        item.strip()
        for item in text.split()
        if len(item.strip()) >= 2
    ]

    if keywords:
        return keywords[:5]

    return [query.lower().strip()]


def search_rag_history_tool(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    query: str,
    limit: int = 10,
) -> str:
    keywords = extract_history_keywords(query)

    statement = (
        select(RagRun)
        .where(RagRun.knowledge_base_id == knowledge_base_id)
        .order_by(col(RagRun.created_at).desc())
        .limit(100)
    )

    rag_runs = session.exec(statement).all()

    matched_runs: list[RagRun] = []

    for rag_run in rag_runs:
        searchable_text = f"{rag_run.question}\n{rag_run.answer}".lower()

        if any(keyword in searchable_text for keyword in keywords):
            matched_runs.append(rag_run)

        if len(matched_runs) >= limit:
            break

    if not matched_runs:
        return (
            "没有在当前知识库的 RAG 问答历史中找到相关记录。"
            f"\n本次提取的搜索关键词：{', '.join(keywords)}"
        )

    lines = [
        f"在当前知识库的 RAG 问答历史中找到 {len(matched_runs)} 条相关记录："
    ]

    for index, rag_run in enumerate(matched_runs, start=1):
        created_at = (
            rag_run.created_at.isoformat()
            if rag_run.created_at
            else "-"
        )

        answer_preview = rag_run.answer[:500]

        lines.append(
            f"[历史记录 {index}]\n"
            f"时间：{created_at}\n"
            f"检索方式：{rag_run.retrieval_type}\n"
            f"参数：top_k={rag_run.top_k}, "
            f"S={rag_run.semantic_weight}, "
            f"K={rag_run.keyword_weight}\n"
            f"问题：{rag_run.question}\n"
            f"回答摘要：{answer_preview}"
        )

    return "\n\n".join(lines)


def summarize_document_tool(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID | None = None,
    filename_keyword: str | None = None,
    max_chunks: int = 5,
) -> tuple[str, list[RagChatSource]]:
    max_chunks = max(1, min(max_chunks, 20))

    document = None

    if document_id is not None:
        document_statement = (
            select(Document)
            .where(Document.id == document_id)
            .where(Document.knowledge_base_id == knowledge_base_id)
        )
        document = session.exec(document_statement).first()

    if document is None and filename_keyword:
        keyword_pattern = f"%{filename_keyword.strip()}%"

        document_statement = (
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .where(col(Document.original_filename).ilike(keyword_pattern))
            .order_by(col(Document.created_at).desc())
            .limit(1)
        )

        document = session.exec(document_statement).first()

    if document is None:
        document_statement = (
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(col(Document.created_at).desc())
            .limit(1)
        )

        document = session.exec(document_statement).first()

    if document is None:
        return "当前知识库下没有可总结的文档。", []

    chunk_statement = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(col(DocumentChunk.chunk_index).asc())
        .limit(max_chunks)
    )

    chunks = session.exec(chunk_statement).all()

    if not chunks:
        return (
            f"文档 {document.original_filename} 暂无可用 chunk，"
            "可能是文件还没有成功解析，或者解析后内容为空。"
        ), []

    sources = [
        RagChatSource(
            document_id=document.id,
            original_filename=document.original_filename,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            content_length=chunk.content_length,
            match_count=0,
            similarity=None,
            retrieval_type="document_summary",
        )
        for chunk in chunks
    ]

    lines = [
        f"准备总结文档：{document.original_filename}",
        f"document_id：{document.id}",
        f"共读取前 {len(sources)} 个 chunk 作为总结依据。",
    ]

    for source in sources:
        content_preview = source.content

        if len(content_preview) > 1000:
            content_preview = content_preview[:1000] + "\n...（内容过长，已截断）"

        lines.append(
            f"[Chunk {source.chunk_index}]\n"
            f"{content_preview}"
        )

    return "\n\n".join(lines), sources


def build_sources_context(
    *,
    sources: list[RagChatSource],
) -> str:
    if not sources:
        return "无可用知识库资料。"

    context_parts = []

    for index, source in enumerate(sources, start=1):
        context_parts.append(
            f"[资料 {index}]\n"
            f"来源文件：{source.original_filename}\n"
            f"Chunk：{source.chunk_index}\n"
            f"内容：\n{source.content}"
        )

    return "\n\n".join(context_parts)


def list_code_files_tool(
    *,
    session,
    knowledge_base_id,
    limit: int = 200,
    language: str | None = None,
) -> str:
    statement = (
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(col(Document.original_filename))
        .limit(limit * 3)
    )

    documents = session.exec(statement).all()

    code_documents = [
        document
        for document in documents
        if is_code_file(document.original_filename)
    ]

    if language:
        language_lower = language.lower().strip()

        extension_map = {
            "python": {".py"},
            "py": {".py"},
            "typescript": {".ts", ".tsx"},
            "ts": {".ts"},
            "tsx": {".tsx"},
            "javascript": {".js", ".jsx"},
            "js": {".js"},
            "jsx": {".jsx"},
            "java": {".java"},
            "go": {".go"},
        }

        allowed_suffixes = extension_map.get(language_lower)

        if allowed_suffixes:
            code_documents = [
                document
                for document in code_documents
                if Path(document.original_filename).suffix.lower() in allowed_suffixes
            ]

    code_documents = code_documents[:limit]

    if not code_documents:
        if language:
            return f"当前知识库中没有找到 {language} 相关代码文件。"

        return "当前知识库中没有找到代码文件。"

    lines = [
        f"当前知识库中共找到 {len(code_documents)} 个代码文件：",
        "",
    ]

    for index, document in enumerate(code_documents, start=1):
        suffix = Path(document.original_filename).suffix.lower()
        file_size = document.file_size or 0

        lines.append(
            f"{index}. {document.original_filename}\n"
            f"   document_id: {document.id}\n"
            f"   extension: {suffix}\n"
            f"   status: {document.status}\n"
            f"   size: {file_size} bytes"
        )

    return "\n".join(lines)


def get_code_language_suffixes(language: str | None) -> set[str] | None:
    if not language:
        return None

    language_lower = language.lower().strip()

    extension_map = {
        "python": {".py"},
        "py": {".py"},
        "typescript": {".ts", ".tsx"},
        "ts": {".ts"},
        "tsx": {".tsx"},
        "javascript": {".js", ".jsx"},
        "js": {".js"},
        "jsx": {".jsx"},
        "java": {".java"},
        "go": {".go"},
        "c": {".c", ".h"},
        "cpp": {".cpp", ".hpp"},
        "c++": {".cpp", ".hpp"},
        "csharp": {".cs"},
        "cs": {".cs"},
        "rust": {".rs"},
        "rs": {".rs"},
        "vue": {".vue"},
    }

    return extension_map.get(language_lower)


def is_code_document_matched(
    *,
    filename: str,
    language: str | None = None,
    filename_keyword: str | None = None,
) -> bool:
    if not is_code_file(filename):
        return False

    suffixes = get_code_language_suffixes(language)

    if suffixes is not None:
        suffix = Path(filename).suffix.lower()

        if suffix not in suffixes:
            return False

    if filename_keyword:
        keyword = filename_keyword.lower().strip()

        if keyword and keyword not in filename.lower():
            return False

    return True


def search_code_tool(
    *,
    session,
    knowledge_base_id,
    query: str,
    top_k: int = 5,
    semantic_weight: float = 0.75,
    keyword_weight: float = 0.25,
    language: str | None = None,
    filename_keyword: str | None = None,
) -> tuple[str, list[RagChatSource]]:
    query = query.strip()

    if not query:
        return "代码检索 query 不能为空。", []

    top_k = max(1, min(int(top_k), 20))

    search_limit = max(top_k * 5, 20)

    hybrid_rows = hybrid_retrieve_chunks_for_rag(
        session=session,
        knowledge_base_id=knowledge_base_id,
        query=query,
        top_k=search_limit,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
    )

    sources: list[RagChatSource] = []
    seen_chunk_ids = set()

    for chunk, document, similarity, match_count, hybrid_score in hybrid_rows:
        if not is_code_document_matched(
            filename=document.original_filename,
            language=language,
            filename_keyword=filename_keyword,
        ):
            continue

        if chunk.id in seen_chunk_ids:
            continue

        sources.append(
            RagChatSource(
                document_id=document.id,
                original_filename=document.original_filename,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                content_length=chunk.content_length,
                match_count=match_count,
                similarity=similarity,
                retrieval_type="code_hybrid",
            )
        )

        seen_chunk_ids.add(chunk.id)

        if len(sources) >= top_k:
            break

    if len(sources) < top_k:
        terms = build_search_terms(query)
        search_conditions = []

        for term in terms:
            pattern = f"%{term}%"
            search_conditions.append(col(DocumentChunk.content).ilike(pattern))
            search_conditions.append(col(Document.original_filename).ilike(pattern))

        if search_conditions:
            statement = (
                select(DocumentChunk, Document)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.knowledge_base_id == knowledge_base_id)
                .where(or_(*search_conditions))
                .order_by(col(Document.original_filename), col(DocumentChunk.chunk_index))
                .limit(search_limit)
            )

            keyword_rows = session.exec(statement).all()

            for chunk, document in keyword_rows:
                if not is_code_document_matched(
                    filename=document.original_filename,
                    language=language,
                    filename_keyword=filename_keyword,
                ):
                    continue

                if chunk.id in seen_chunk_ids:
                    continue

                match_count = count_keyword_matches(chunk.content, terms)

                sources.append(
                    RagChatSource(
                        document_id=document.id,
                        original_filename=document.original_filename,
                        chunk_id=chunk.id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        content_length=chunk.content_length,
                        match_count=match_count,
                        similarity=None,
                        retrieval_type="code_keyword",
                    )
                )

                seen_chunk_ids.add(chunk.id)

                if len(sources) >= top_k:
                    break

    if not sources:
        filters = []

        if language:
            filters.append(f"language={language}")

        if filename_keyword:
            filters.append(f"filename_keyword={filename_keyword}")

        filter_text = f"筛选条件：{', '.join(filters)}。" if filters else ""

        return (
            f"没有检索到与 query='{query}' 相关的代码片段。{filter_text}",
            [],
        )

    lines = [
        f"代码检索完成。query='{query}'，共找到 {len(sources)} 个相关代码片段。",
        "",
    ]

    for index, source in enumerate(sources, start=1):
        content = source.content

        if len(content) > 1200:
            content = content[:1200] + "\n...（代码片段过长，已截断）"

        similarity_text = (
            f"{source.similarity:.4f}"
            if source.similarity is not None
            else "-"
        )

        lines.append(
            f"[代码片段 {index}]\n"
            f"file: {source.original_filename}\n"
            f"chunk_index: {source.chunk_index}\n"
            f"chunk_id: {source.chunk_id}\n"
            f"retrieval_type: {source.retrieval_type}\n"
            f"match_count: {source.match_count}\n"
            f"similarity: {similarity_text}\n"
            f"content:\n{content}"
        )

    return "\n\n".join(lines), sources


def read_code_file_tool(
    *,
    session,
    knowledge_base_id,
    document_id=None,
    filename_keyword: str | None = None,
    max_chunks: int = 50,
    max_chars: int = 20000,
) -> tuple[str, list[RagChatSource]]:
    max_chunks = max(1, min(int(max_chunks), 200))
    max_chars = max(1000, min(int(max_chars), 50000))

    document = None

    if document_id is not None:
        statement = (
            select(Document)
            .where(Document.id == document_id)
            .where(Document.knowledge_base_id == knowledge_base_id)
        )

        document = session.exec(statement).first()

        if document is not None and not is_code_file(document.original_filename):
            return (
                f"document_id={document_id} 对应的文件不是代码文件：{document.original_filename}",
                [],
            )

    if document is None and filename_keyword:
        keyword = filename_keyword.strip().lower()

        statement = (
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(col(Document.original_filename))
        )

        documents = session.exec(statement).all()

        matched_documents = [
            item
            for item in documents
            if is_code_file(item.original_filename)
            and keyword in item.original_filename.lower()
        ]

        if not matched_documents:
            return (
                f"没有找到文件名包含 '{filename_keyword}' 的代码文件。",
                [],
            )

        if len(matched_documents) > 1:
            lines = [
                f"找到多个文件名包含 '{filename_keyword}' 的代码文件，请进一步指定：",
                "",
            ]

            for index, item in enumerate(matched_documents[:20], start=1):
                lines.append(
                    f"{index}. {item.original_filename}\n"
                    f"   document_id: {item.id}\n"
                    f"   status: {item.status}\n"
                    f"   size: {item.file_size or 0} bytes"
                )

            return "\n".join(lines), []

        document = matched_documents[0]

    if document is None:
        return (
            "没有指定可读取的代码文件。请提供 document_id 或 filename_keyword，"
            "或者先使用 search_code 检索到相关代码片段。",
            [],
        )

    chunk_statement = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(col(DocumentChunk.chunk_index))
        .limit(max_chunks)
    )

    chunks = session.exec(chunk_statement).all()

    if not chunks:
        return (
            f"代码文件 {document.original_filename} 暂无 chunk，可能还未解析成功。",
            [],
        )

    sources: list[RagChatSource] = []

    for chunk in chunks:
        sources.append(
            RagChatSource(
                document_id=document.id,
                original_filename=document.original_filename,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                content_length=chunk.content_length,
                match_count=0,
                similarity=None,
                retrieval_type="code_file_read",
            )
        )

    lines = [
        f"已读取代码文件：{document.original_filename}",
        f"document_id: {document.id}",
        f"status: {document.status}",
        f"file_size: {document.file_size or 0} bytes",
        f"chunk_count_read: {len(chunks)}",
        "",
    ]

    current_chars = 0

    for index, chunk in enumerate(chunks, start=1):
        content = chunk.content

        remaining_chars = max_chars - current_chars

        if remaining_chars <= 0:
            lines.append("...（文件内容过长，后续 chunk 已截断）")
            break

        if len(content) > remaining_chars:
            content = content[:remaining_chars] + "\n...（当前 chunk 内容已截断）"

        lines.append(
            f"[Chunk {index}]\n"
            f"chunk_index: {chunk.chunk_index}\n"
            f"chunk_id: {chunk.id}\n"
            f"content:\n{content}"
        )

        current_chars += len(content)

    return "\n\n".join(lines), sources


def extract_code_chunk_metadata(content: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    for line in content.splitlines()[:8]:
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key in {
            "file_path",
            "language",
            "symbol_name",
            "symbol_type",
            "line_range",
        }:
            metadata[key] = value

    return metadata


def classify_code_reference(
    *,
    symbol_name: str,
    chunk_content: str,
) -> str:
    metadata = extract_code_chunk_metadata(chunk_content)

    metadata_symbol_name = metadata.get("symbol_name", "")

    if metadata_symbol_name == symbol_name:
        return "definition_or_symbol_chunk"

    definition_patterns = [
        rf"\bdef\s+{re.escape(symbol_name)}\s*\(",
        rf"\bclass\s+{re.escape(symbol_name)}\b",
        rf"\bfunction\s+{re.escape(symbol_name)}\s*\(",
        rf"\bconst\s+{re.escape(symbol_name)}\s*=",
        rf"\bexport\s+function\s+{re.escape(symbol_name)}\s*\(",
        rf"\bexport\s+const\s+{re.escape(symbol_name)}\s*=",
        rf"\bfunc\s+{re.escape(symbol_name)}\s*\(",
    ]

    for pattern in definition_patterns:
        if re.search(pattern, chunk_content):
            return "possible_definition"

    return "reference"


def find_code_references_tool(
    *,
    session,
    knowledge_base_id,
    symbol_name: str,
    language: str | None = None,
    filename_keyword: str | None = None,
    limit: int = 50,
) -> tuple[str, list[RagChatSource]]:
    symbol_name = symbol_name.strip()

    if not symbol_name:
        return "要查找的 symbol_name 不能为空。", []

    limit = max(1, min(int(limit), 100))

    pattern = f"%{symbol_name}%"

    statement = (
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.knowledge_base_id == knowledge_base_id)
        .where(
            or_(
                col(DocumentChunk.content).ilike(pattern),
                col(Document.original_filename).ilike(pattern),
            )
        )
        .order_by(col(Document.original_filename), col(DocumentChunk.chunk_index))
        .limit(limit * 5)
    )

    rows = session.exec(statement).all()

    sources: list[RagChatSource] = []
    seen_chunk_ids = set()

    suffixes = get_code_language_suffixes(language)

    for chunk, document in rows:
        filename = document.original_filename

        if not is_code_file(filename):
            continue

        if suffixes is not None:
            suffix = Path(filename).suffix.lower()

            if suffix not in suffixes:
                continue

        if filename_keyword:
            keyword = filename_keyword.lower().strip()

            if keyword and keyword not in filename.lower():
                continue

        if chunk.id in seen_chunk_ids:
            continue

        content_lower = chunk.content.lower()
        symbol_lower = symbol_name.lower()

        occurrence_count = content_lower.count(symbol_lower)

        if occurrence_count <= 0 and symbol_lower not in filename.lower():
            continue

        sources.append(
            RagChatSource(
                document_id=document.id,
                original_filename=document.original_filename,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                content_length=chunk.content_length,
                match_count=occurrence_count,
                similarity=None,
                retrieval_type="code_reference",
            )
        )

        seen_chunk_ids.add(chunk.id)

        if len(sources) >= limit:
            break

    if not sources:
        filters = []

        if language:
            filters.append(f"language={language}")

        if filename_keyword:
            filters.append(f"filename_keyword={filename_keyword}")

        filter_text = f"筛选条件：{', '.join(filters)}。" if filters else ""

        return (
            f"没有找到 symbol_name='{symbol_name}' 的代码引用。{filter_text}",
            [],
        )

    lines = [
        f"代码引用查找完成。symbol_name='{symbol_name}'，共找到 {len(sources)} 个相关片段。",
        "",
    ]

    for index, source in enumerate(sources, start=1):
        metadata = extract_code_chunk_metadata(source.content)

        reference_type = classify_code_reference(
            symbol_name=symbol_name,
            chunk_content=source.content,
        )

        content = source.content

        if len(content) > 1200:
            content = content[:1200] + "\n...（代码片段过长，已截断）"

        lines.append(
            f"[引用片段 {index}]\n"
            f"file: {source.original_filename}\n"
            f"chunk_index: {source.chunk_index}\n"
            f"chunk_id: {source.chunk_id}\n"
            f"reference_type: {reference_type}\n"
            f"symbol_name_in_chunk: {metadata.get('symbol_name', '-')}\n"
            f"symbol_type_in_chunk: {metadata.get('symbol_type', '-')}\n"
            f"line_range: {metadata.get('line_range', '-')}\n"
            f"match_count: {source.match_count}\n"
            f"content:\n{content}"
        )

    return "\n\n".join(lines), sources