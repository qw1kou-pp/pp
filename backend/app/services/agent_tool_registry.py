import json
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from sqlmodel import Session

from app.models import AgentToolCallPublic, RagChatSource
from app.services.agent_tools import (
    list_documents_tool,
    list_code_files_tool,
    search_code_tool,
    read_code_file_tool,
    find_code_references_tool,
    read_document_chunks_tool,
    search_knowledge_base_tool,
    search_rag_history_tool,
    summarize_document_tool,
)


@dataclass
class AgentToolContext:
    session: Session
    knowledge_base_id: uuid.UUID
    repository_analysis_task_id: uuid.UUID | None

    question: str
    top_k: int
    semantic_weight: float
    keyword_weight: float
    all_sources: list[RagChatSource]


@dataclass
class AgentToolResult:
    tool_call: AgentToolCallPublic | None
    sources: list[RagChatSource]
    stop: bool = False


@dataclass
class AgentTool:
    name: str
    description: str
    arguments_schema: dict[str, Any]
    handler: Callable[[AgentToolContext, dict[str, Any]], AgentToolResult]


def merge_sources_without_duplicates(
    *,
    existing_sources: list[RagChatSource],
    new_sources: list[RagChatSource],
) -> list[RagChatSource]:
    existing_chunk_ids = {source.chunk_id for source in existing_sources}

    merged_sources = list(existing_sources)

    for source in new_sources:
        if source.chunk_id in existing_chunk_ids:
            continue

        merged_sources.append(source)
        existing_chunk_ids.add(source.chunk_id)

    return merged_sources


def parse_uuid_or_none(value: Any) -> uuid.UUID | None:
    if not value:
        return None

    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def handle_list_documents(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    observation = list_documents_tool(
        session=context.session,
        knowledge_base_id=context.knowledge_base_id,
        repository_analysis_task_id= context.repository_analysis_task_id,
    )

    tool_call = AgentToolCallPublic(
        tool_name="list_documents",
        arguments={
            "knowledge_base_id": str(context.knowledge_base_id),
            "limit": 20,
        },
        observation=observation,
        success=True,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=context.all_sources,
    )


def handle_list_code_files(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    raw_limit = arguments.get("limit", 200)

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 200

    limit = max(1, min(limit, 500))

    language = arguments.get("language")

    if language is not None:
        language = str(language).strip() or None

    observation = list_code_files_tool(
        session=context.session,
        knowledge_base_id=context.knowledge_base_id,
        repository_analysis_task_id= context.repository_analysis_task_id,
        limit=limit,
        language=language,
    )

    tool_call = AgentToolCallPublic(
        tool_name="list_code_files",
        arguments={
            "knowledge_base_id": str(context.knowledge_base_id),
            "language": language,
            "limit": limit,
        },
        observation=observation,
        success=True,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=context.all_sources,
    )


def handle_search_code(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    query = str(arguments.get("query") or context.question).strip()

    raw_top_k = arguments.get("top_k", context.top_k)

    try:
        top_k = int(raw_top_k)
    except (TypeError, ValueError):
        top_k = context.top_k

    top_k = max(1, min(top_k, 20))

    language = arguments.get("language")

    if language is not None:
        language = str(language).strip() or None

    filename_keyword = arguments.get("filename_keyword")

    if filename_keyword is not None:
        filename_keyword = str(filename_keyword).strip() or None

    observation, sources = search_code_tool(
        session=context.session,
        knowledge_base_id=context.knowledge_base_id,
        repository_analysis_task_id=context.repository_analysis_task_id,
        query=query,
        top_k=top_k,
        semantic_weight=context.semantic_weight,
        keyword_weight=context.keyword_weight,
        language=language,
        filename_keyword=filename_keyword,
    )

    tool_call = AgentToolCallPublic(
        tool_name="search_code",
        arguments={
            "query": query,
            "top_k": top_k,
            "semantic_weight": context.semantic_weight,
            "keyword_weight": context.keyword_weight,
            "language": language,
            "filename_keyword": filename_keyword,
        },
        observation=observation,
        success=len(sources) > 0,
    )

    merged_sources = merge_sources_without_duplicates(
        existing_sources=context.all_sources,
        new_sources=sources,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=merged_sources,
    )


def handle_read_code_file(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    document_id = parse_uuid_or_none(arguments.get("document_id"))

    if document_id is None and context.all_sources:
        first_source = context.all_sources[0]
        document_id = first_source.document_id

    filename_keyword = arguments.get("filename_keyword")

    if filename_keyword is not None:
        filename_keyword = str(filename_keyword).strip() or None

    raw_max_chunks = arguments.get("max_chunks", 50)

    try:
        max_chunks = int(raw_max_chunks)
    except (TypeError, ValueError):
        max_chunks = 50

    raw_max_chars = arguments.get("max_chars", 20000)

    try:
        max_chars = int(raw_max_chars)
    except (TypeError, ValueError):
        max_chars = 20000

    observation, sources = read_code_file_tool(
        session=context.session,
        knowledge_base_id=context.knowledge_base_id,
        repository_analysis_task_id=context.repository_analysis_task_id,
        document_id=document_id,
        filename_keyword=filename_keyword,
        max_chunks=max_chunks,
        max_chars=max_chars,
    )

    tool_call = AgentToolCallPublic(
        tool_name="read_code_file",
        arguments={
            "document_id": str(document_id) if document_id else None,
            "filename_keyword": filename_keyword,
            "max_chunks": max_chunks,
            "max_chars": max_chars,
        },
        observation=observation,
        success=len(sources) > 0,
    )

    merged_sources = merge_sources_without_duplicates(
        existing_sources=context.all_sources,
        new_sources=sources,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=merged_sources,
    )


def handle_find_code_references(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    symbol_name = (
        arguments.get("symbol_name")
        or arguments.get("name")
        or arguments.get("query")
        or ""
    )

    symbol_name = str(symbol_name).strip()

    language = arguments.get("language")

    if language is not None:
        language = str(language).strip() or None

    filename_keyword = arguments.get("filename_keyword")

    if filename_keyword is not None:
        filename_keyword = str(filename_keyword).strip() or None

    raw_limit = arguments.get("limit", 50)

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 50

    limit = max(1, min(limit, 100))

    observation, sources = find_code_references_tool(
        session=context.session,
        knowledge_base_id=context.knowledge_base_id,
        repository_analysis_task_id=context.repository_analysis_task_id,
        symbol_name=symbol_name,
        language=language,
        filename_keyword=filename_keyword,
        limit=limit,
    )

    tool_call = AgentToolCallPublic(
        tool_name="find_code_references",
        arguments={
            "symbol_name": symbol_name,
            "language": language,
            "filename_keyword": filename_keyword,
            "limit": limit,
        },
        observation=observation,
        success=len(sources) > 0,
    )

    merged_sources = merge_sources_without_duplicates(
        existing_sources=context.all_sources,
        new_sources=sources,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=merged_sources,
    )


def handle_search_knowledge_base(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    query = str(arguments.get("query") or context.question)

    observation, sources = search_knowledge_base_tool(
        session=context.session,
        knowledge_base_id=context.knowledge_base_id,
        repository_analysis_task_id=context.repository_analysis_task_id,
        query=query,
        top_k=context.top_k,
        semantic_weight=context.semantic_weight,
        keyword_weight=context.keyword_weight,
    )

    tool_call = AgentToolCallPublic(
        tool_name="search_knowledge_base",
        arguments={
            "query": query,
            "top_k": context.top_k,
            "semantic_weight": context.semantic_weight,
            "keyword_weight": context.keyword_weight,
        },
        observation=observation,
        success=True,
    )

    merged_sources = merge_sources_without_duplicates(
        existing_sources=context.all_sources,
        new_sources=sources,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=merged_sources,
    )


def handle_read_document_chunks(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    if not context.all_sources:
        tool_call = AgentToolCallPublic(
            tool_name="read_document_chunks",
            arguments=arguments,
            observation="当前还没有 sources，无法读取相邻 chunk。请先调用 search_knowledge_base。",
            success=False,
        )

        return AgentToolResult(
            tool_call=tool_call,
            sources=context.all_sources,
        )

    first_source = context.all_sources[0]

    document_id = parse_uuid_or_none(arguments.get("document_id"))

    if document_id is None:
        document_id = first_source.document_id

    raw_center_chunk_index = arguments.get("center_chunk_index")

    try:
        center_chunk_index = int(raw_center_chunk_index)
    except (TypeError, ValueError):
        center_chunk_index = first_source.chunk_index

    raw_window = arguments.get("window", 1)

    try:
        window = int(raw_window)
    except (TypeError, ValueError):
        window = 1

    observation, window_sources = read_document_chunks_tool(
        session=context.session,
        knowledge_base_id=context.knowledge_base_id,
        repository_analysis_task_id=context.repository_analysis_task_id,
        document_id=document_id,
        center_chunk_index=center_chunk_index,
        window=window,
    )

    tool_call = AgentToolCallPublic(
        tool_name="read_document_chunks",
        arguments={
            "document_id": str(document_id),
            "center_chunk_index": center_chunk_index,
            "window": window,
        },
        observation=observation,
        success=True,
    )

    merged_sources = merge_sources_without_duplicates(
        existing_sources=context.all_sources,
        new_sources=window_sources,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=merged_sources,
    )


def handle_search_rag_history(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    query = str(arguments.get("query") or context.question)

    observation = search_rag_history_tool(
        session=context.session,
        knowledge_base_id=context.knowledge_base_id,
        repository_analysis_task_id=context.repository_analysis_task_id,
        query=query,
        limit=10,
    )

    tool_call = AgentToolCallPublic(
        tool_name="search_rag_history",
        arguments={
            "knowledge_base_id": str(context.knowledge_base_id),
            "query": query,
            "limit": 10,
        },
        observation=observation,
        success=True,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=context.all_sources,
    )


def handle_summarize_document(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    document_id = parse_uuid_or_none(arguments.get("document_id"))

    filename_keyword = arguments.get("filename_keyword")

    if filename_keyword is not None:
        filename_keyword = str(filename_keyword).strip() or None

    raw_max_chunks = arguments.get("max_chunks", 5)

    try:
        max_chunks = int(raw_max_chunks)
    except (TypeError, ValueError):
        max_chunks = 5

    observation, sources = summarize_document_tool(
        session=context.session,
        knowledge_base_id=context.knowledge_base_id,
        repository_analysis_task_id=context.repository_analysis_task_id,
        document_id=document_id,
        filename_keyword=filename_keyword,
        max_chunks=max_chunks,
    )

    tool_call = AgentToolCallPublic(
        tool_name="summarize_document",
        arguments={
            "document_id": str(document_id) if document_id else None,
            "filename_keyword": filename_keyword,
            "max_chunks": max_chunks,
        },
        observation=observation,
        success=len(sources) > 0,
    )

    merged_sources = merge_sources_without_duplicates(
        existing_sources=context.all_sources,
        new_sources=sources,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=merged_sources,
    )


def handle_final_answer(
    context: AgentToolContext,
    arguments: dict[str, Any],
) -> AgentToolResult:
    return AgentToolResult(
        tool_call=None,
        sources=context.all_sources,
        stop=True,
    )


def get_agent_tools(
    *,
    repository_scoped:
        bool = False,
) -> dict[str, AgentTool]:
    tools = {
        "list_documents": AgentTool(
            name="list_documents",
            description="查看当前知识库有哪些文档。适合用户询问知识库里有哪些文件、有哪些资料。",
            arguments_schema={},
            handler=handle_list_documents,
        ),
        "list_code_files": AgentTool(
            name="list_code_files",
            description=(
                "列出当前知识库中的代码文件。适合用于代码仓库问答，例如："
                "这个项目有哪些代码文件、有哪些 Python 文件、有哪些 TSX 文件、"
                "当前仓库包含哪些模块。"
            ),
            arguments_schema={
                "language": "可选。按语言过滤，例如 python、py、typescript、ts、tsx、javascript、js、java、go。",
                "limit": "可选。最多返回多少个代码文件，默认 200。",
            },
            handler=handle_list_code_files,
        ),
        "search_code": AgentTool(
            name="search_code",
            description=(
                "专门检索当前知识库中的代码文件和代码片段。适合用于代码仓库问答，"
                "例如查找函数、类、组件、接口、变量、调用关系、报错相关代码、"
                "某个逻辑在哪个文件中实现。"
            ),
            arguments_schema={
                "query": "要检索的代码问题、函数名、类名、变量名或报错信息。通常可以直接使用用户原问题。",
                "top_k": "可选。返回多少个代码片段，默认使用当前 Agent top_k。",
                "language": "可选。按语言过滤，例如 python、py、typescript、ts、tsx、javascript、js、java、go。",
                "filename_keyword": "可选。按文件名关键词过滤，例如 service、router、api、component。",
            },
            handler=handle_search_code,
        ),
        "read_code_file": AgentTool(
            name="read_code_file",
            description=(
                "读取某个代码文件的完整 chunk 内容。适合在 search_code 找到相关代码后，"
                "继续分析整个文件的结构、完整逻辑、上下文、函数之间关系。"
                "可以根据 document_id 读取，也可以根据 filename_keyword 按文件名读取。"
            ),
            arguments_schema={
                "document_id": "可选。要读取的代码文件 document_id。如果前一步 search_code 已经得到 sources，可以不填。",
                "filename_keyword": "可选。文件名关键词，例如 documents.py、agent、service、tsx。",
                "max_chunks": "可选。最多读取多少个 chunk，默认 50。",
                "max_chars": "可选。最多返回多少字符，默认 20000。",
            },
            handler=handle_read_code_file,
        ),
        "find_code_references": AgentTool(
            name="find_code_references",
            description=(
                "查找某个函数、类、方法、变量、组件或接口在代码仓库中的定义和引用位置。"
                "适合回答：某个函数在哪里定义、在哪里被调用、某个变量在哪些文件中出现、"
                "某个组件被哪些代码引用、某个报错相关符号出现在哪里。"
            ),
            arguments_schema={
                "symbol_name": "要查找的函数名、类名、变量名、组件名或方法名，例如 create_document_chunks。",
                "language": "可选。按语言过滤，例如 python、py、typescript、ts、tsx、javascript、js、java、go。",
                "filename_keyword": "可选。按文件名关键词过滤，例如 service、router、documents、agent。",
                "limit": "可选。最多返回多少个引用片段，默认 50。",
            },
            handler=handle_find_code_references,
        ),
        "search_knowledge_base": AgentTool(
            name="search_knowledge_base",
            description="检索当前知识库内容。适合回答具体知识问题、解释概念、查询文档内容。",
            arguments_schema={
                "query": "要检索的问题或关键词。通常可以直接使用用户原问题。",
            },
            handler=handle_search_knowledge_base,
        ),
        "read_document_chunks": AgentTool(
            name="read_document_chunks",
            description="在已经有 sources 后，读取某个文档某个 chunk 附近的上下文。适合详细说明、完整流程、步骤、原理、总结类问题。",
            arguments_schema={
                "document_id": "可选。文档 ID。如果不知道，可以不填。",
                "center_chunk_index": "可选。中心 chunk 序号。如果不知道，可以不填。",
                "window": "可选。读取前后多少个 chunk，默认 1。",
            },
            handler=handle_read_document_chunks,
        ),
        "search_rag_history": AgentTool(
            name="search_rag_history",
            description="查询当前知识库下之前的 RAG 问答历史。适合用户询问之前问过什么、上次回答是什么、历史记录里有没有某个问题。",
            arguments_schema={
                "query": "要搜索的历史问答关键词。",
            },
            handler=handle_search_rag_history,
        ),
        "summarize_document": AgentTool(
            name="summarize_document",
            description=(
                "总结某个文档的主要内容。适合用户询问某个 Word、PDF、docx、"
                "最近上传的文档、指定文件主要讲了什么。"
            ),
            arguments_schema={
                "document_id": "可选。要总结的文档 ID。如果不知道，可以不填。",
                "filename_keyword": "可选。文件名关键词，例如 report、论文、xxx.docx。",
                "max_chunks": "可选。最多读取多少个 chunk 用于总结，默认 5。",
            },
            handler=handle_summarize_document,
        ),
        "final_answer": AgentTool(
            name="final_answer",
            description="如果已有信息足够回答用户问题，就选择该 action，结束工具调用并进入最终回答阶段。",
            arguments_schema={},
            handler=handle_final_answer,
        ),
    }
    return tools


def get_agent_tool_names(
    *,
    repository_scoped:
        bool = False,
) -> set[str]:
    return set(
        get_agent_tools(
            repository_scoped=
                repository_scoped,
        ).keys(),
    )


def build_agent_tools_prompt_section(
    *,
    repository_scoped: bool = False,
) -> str:
    tools = get_agent_tools(
        repository_scoped=repository_scoped,
    )

    parts: list[str] = []

    for index, tool in enumerate(
        tools.values(),
        start=1,
    ):
        arguments_schema_text = (
            json.dumps(
                tool.arguments_schema,
                ensure_ascii=False,
                indent=2,
            )
        )

        parts.append(
            f"{index}. {tool.name}\n"
            f"用途：{tool.description}\n"
            "参数：\n"
            f"{arguments_schema_text}"
        )

    return "\n\n".join(parts)


def build_failed_tool_result(
    *,
    action: str,
    arguments: dict[str, Any],
    context: AgentToolContext,
    message: str,
) -> AgentToolResult:
    tool_call = AgentToolCallPublic(
        tool_name=action,
        arguments=arguments,
        observation=message,
        success=False,
    )

    return AgentToolResult(
        tool_call=tool_call,
        sources=context.all_sources,
    )


def format_tool_error_message(error: Exception) -> str:
    error_type = error.__class__.__name__
    error_message = str(error)

    if not error_message:
        error_message = "未知错误"

    return f"工具执行失败：{error_type}: {error_message}"


def execute_registered_agent_tool(
    *,
    action: str,
    arguments: dict[str, Any],
    context: AgentToolContext,
) -> AgentToolResult:
    repository_scoped = (
            context
            .repository_analysis_task_id
            is not None
    )

    tools = get_agent_tools(
        repository_scoped=
        repository_scoped,
    )

    tool = tools.get(action)

    if not tool:
        return build_failed_tool_result(
            action=action,
            arguments=arguments,
            context=context,
            message=f"未知工具 action：{action}",
        )

    try:
        result = tool.handler(context, arguments)
    except Exception as error:
        print(f"Agent tool failed: action={action}, error={error}")

        return build_failed_tool_result(
            action=action,
            arguments=arguments,
            context=context,
            message=format_tool_error_message(error),
        )

    if result.sources is None:
        result.sources = context.all_sources

    validate_repository_scoped_sources(
        context=context,
        sources=result.sources,
    )

    return result


def validate_repository_scoped_sources(
    *,
    context: AgentToolContext,
    sources: list[RagChatSource],
) -> None:
    task_id = (
        context
        .repository_analysis_task_id
    )

    if task_id is None:
        return

    invalid_sources = [
        source
        for source in sources
        if (
            source
            .repository_analysis_task_id
            != task_id
        )
    ]

    if invalid_sources:
        raise RuntimeError(
            "Repository-scoped Agent "
            "tool returned sources outside "
            "the requested repository task",
        )