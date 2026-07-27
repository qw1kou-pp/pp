import uuid
import json
import re
from typing import Any

from sqlmodel import Session

from app.models import AgentToolCallPublic, RagChatSource
from app.services.agent_tools import (
    build_sources_context,
    list_documents_tool,
    read_document_chunks_tool,
    search_knowledge_base_tool,
    search_rag_history_tool,
)
from app.services.llm import LLMError, call_llm
from app.services.agent_tool_registry import (
    AgentToolContext,
    build_agent_tools_prompt_section,
    execute_registered_agent_tool,
    get_agent_tool_names,
    merge_sources_without_duplicates,
)


def normalize_agent_weights(
    *,
    semantic_weight: float,
    keyword_weight: float,
) -> tuple[float, float]:
    total = semantic_weight + keyword_weight

    if total <= 0:
        return 0.75, 0.25

    return semantic_weight / total, keyword_weight / total


def should_list_documents(question: str) -> bool:
    question_lower = question.lower()

    keywords = [
        "有哪些文档",
        "有什么文档",
        "文档列表",
        "文件列表",
        "知识库里有什么",
        "知识库有哪些",
        "list documents",
        "documents",
    ]

    return any(keyword in question_lower for keyword in keywords)


def should_list_code_files(question: str) -> bool:
    question_lower = question.lower()

    keywords = [
        "代码文件",
        "源码文件",
        "项目文件",
        "仓库文件",
        "代码仓库",
        "项目结构",
        "目录结构",
        "有哪些代码",
        "有哪些源码",
        "有哪些 py",
        "有哪些 python",
        "有哪些 ts",
        "有哪些 tsx",
        "有哪些 js",
        "有哪些 java",
        "有哪些 go",
        "list code files",
        "code files",
        "source files",
        "repository files",
        "project structure",
    ]

    return any(keyword in question_lower for keyword in keywords)


def should_search_code(question: str) -> bool:
    question_lower = question.lower()

    keywords = [
        "代码",
        "源码",
        "函数",
        "方法",
        "类",
        "组件",
        "接口",
        "变量",
        "调用",
        "定义",
        "实现",
        "逻辑",
        "流程",
        "报错",
        "错误",
        "异常",
        "bug",
        "api",
        "router",
        "service",
        "controller",
        "component",
        "hook",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".java",
        ".go",
        "code",
        "source",
        "function",
        "class",
        "method",
        "component",
        "variable",
        "reference",
        "definition",
        "implementation",
        "logic",
        "flow",
        "error",
        "exception",
        "stack trace",
        "bug",
    ]

    return any(keyword in question_lower for keyword in keywords)


def should_read_code_file(question: str) -> bool:
    question_lower = question.lower()

    keywords = [
        "完整代码",
        "完整文件",
        "整个文件",
        "读取文件",
        "看看这个文件",
        "分析这个文件",
        "这个文件整体",
        "完整逻辑",
        "主要逻辑",
        "执行逻辑",
        "完整流程",
        "实现流程",
        "执行流程",
        "上下文",
        "所在文件",
        "完整实现",
        "整体作用",
        "整体流程",
        "详细解释",
        "详细分析",
        "read code file",
        "read file",
        "entire file",
        "whole file",
        "complete code",
        "full code",
        "full file",
        "full logic",
        "implementation flow",
    ]

    return any(keyword in question_lower for keyword in keywords)


def should_find_code_references(question: str) -> bool:
    question_lower = question.lower()

    keywords = [
        "在哪里被调用",
        "哪里调用了",
        "哪些地方调用",
        "谁调用了",
        "调用关系",
        "在哪里使用",
        "哪里使用了",
        "哪些地方使用",
        "在哪里出现",
        "哪些文件出现",
        "在哪些文件",
        "引用",
        "被引用",
        "定义在哪里",
        "在哪里定义",
        "在哪定义",
        "出现在哪里",
        "使用位置",
        "调用位置",
        "references",
        "reference",
        "usage",
        "used by",
        "where is used",
        "where used",
        "where defined",
        "definition",
        "call sites",
        "callsite",
    ]

    return any(keyword in question_lower for keyword in keywords)


def extract_possible_symbol_name(question: str) -> str:
    code_like_patterns = [
        r"`([^`]+)`",
        r"([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)",
        r"([A-Za-z_][A-Za-z0-9_]{2,})",
    ]

    ignored_words = {
        "where",
        "used",
        "defined",
        "reference",
        "references",
        "usage",
        "function",
        "class",
        "method",
        "variable",
        "component",
        "python",
        "typescript",
        "javascript",
        "java",
        "code",
        "source",
        "file",
        "logic",
        "flow",
        "implementation",
        "代码",
        "源码",
        "函数",
        "方法",
        "变量",
        "组件",
        "引用",
        "调用",
        "定义",
        "哪里",
        "哪些",
        "文件",
        "出现",
        "使用",
        "逻辑",
        "流程",
        "实现",
    }

    for pattern in code_like_patterns:
        matches = re.findall(pattern, question)

        for match in matches:
            candidate = str(match).strip()

            if not candidate:
                continue

            if candidate.lower() in ignored_words:
                continue

            if len(candidate) < 3:
                continue

            return candidate

    return question


def should_summarize_knowledge_base(question: str) -> bool:
    question_lower = question.lower()

    keywords = [
        "总结",
        "概括",
        "主要内容",
        "讲了什么",
        "知识库内容",
        "summarize",
        "summary",
    ]

    return any(keyword in question_lower for keyword in keywords)


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


def should_read_document_chunks(question: str) -> bool:
    question_lower = question.lower()

    keywords = [
        "详细",
        "完整",
        "具体",
        "流程",
        "步骤",
        "原理",
        "怎么实现",
        "如何实现",
        "为什么",
        "总结",
        "概括",
        "主要内容",
        "讲了什么",
        "detail",
        "complete",
        "process",
        "step",
        "summarize",
        "summary",
    ]

    return any(keyword in question_lower for keyword in keywords)


def should_search_rag_history(question: str) -> bool:
    question_lower = question.lower()

    keywords = [
        "历史",
        "之前",
        "上次",
        "最近问过",
        "问答记录",
        "回答过",
        "问过",
        "rag 历史",
        "rag历史",
        "history",
        "previous",
        "past question",
    ]

    return any(keyword in question_lower for keyword in keywords)


def should_summarize_document(question: str) -> bool:
    question_lower = question.lower()

    keywords = [
        "总结文档",
        "总结一下文档",
        "这个文档讲了什么",
        "这个文件讲了什么",
        "最近上传的文档",
        "最近上传的文件",
        "pdf 主要讲了什么",
        "pdf主要讲了什么",
        "word 主要讲了什么",
        "word主要讲了什么",
        "docx",
        ".docx",
        ".pdf",
        "summarize document",
        "summarize file",
    ]

    return any(keyword in question_lower for keyword in keywords)


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    cleaned_text = text.strip()

    if cleaned_text.startswith("```"):
        cleaned_text = re.sub(r"^```json", "", cleaned_text, flags=re.IGNORECASE).strip()
        cleaned_text = re.sub(r"^```", "", cleaned_text).strip()
        cleaned_text = re.sub(r"```$", "", cleaned_text).strip()

    try:
        parsed = json.loads(cleaned_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned_text)

    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None

    return None


def format_tool_calls_for_react(
    *,
    tool_calls: list[AgentToolCallPublic],
) -> str:
    if not tool_calls:
        return "暂无工具调用。"

    parts: list[str] = []

    for index, tool_call in enumerate(tool_calls, start=1):
        observation = tool_call.observation

        if len(observation) > 1500:
            observation = observation[:1500] + "\n...（内容过长，已截断）"

        parts.append(
            f"[Step {index}]\n"
            f"tool_name: {tool_call.tool_name}\n"
            f"arguments: {tool_call.arguments}\n"
            f"success: {tool_call.success}\n"
            f"observation:\n{observation}"
        )

    return "\n\n".join(parts)


def build_react_step_prompt(
    *,
    question: str,
    tool_calls: list[
        AgentToolCallPublic
    ],
    used_steps: int,
    max_steps: int,
    repository_analysis_task_id:
        uuid.UUID | None = None,
) -> str:
    previous_steps = (
        format_tool_calls_for_react(
            tool_calls=tool_calls,
        )
    )

    repository_scoped = (
        repository_analysis_task_id
        is not None
    )

    tools_section = (
        build_agent_tools_prompt_section(
            repository_scoped=(
                repository_scoped
            ),
        )
    )

    if repository_scoped:
        scope_instruction = (
            "当前是仓库范围 Agent。\n"
            "你只能使用当前仓库分析任务导入的"
            "固定 Commit 代码资料。\n"
            "不得请求、推断或引用当前任务范围"
            "之外的文档。\n"
            "当前仓库分析任务 ID："
            f"{repository_analysis_task_id}"
        )

        history_rule = (
            "1. 如果用户询问之前、历史、"
            "上次、问过或回答过，使用 "
            "search_rag_history。"
            "该工具只会搜索当前仓库分析"
            "任务对应的历史。"
        )
    else:
        scope_instruction = (
            "当前是普通知识库 Agent，"
            "可以使用当前知识库范围内的工具。"
        )
        history_rule = (
            "1. 如果用户询问之前、历史、"
            "上次、问过或回答过，使用 "
            "search_rag_history。"
            "该工具只会搜索普通知识库历史。"
        )

    return f"""
你是一个知识库 Agent 的工具决策器。

你需要根据用户问题和已经获得的工具观察结果，决定下一步调用哪个工具。

当前已经使用步骤数：{used_steps}
最大步骤数：{max_steps}

当前工作范围：

{scope_instruction}

可用工具：

{tools_section}

选择原则：
{history_rule}
2. 如果用户问“有哪些文档、知识库里有什么文件”，使用 list_documents。
3. 如果用户问代码文件列表、项目模块或代码仓库结构，优先使用 list_code_files。
4. 如果用户问具体知识内容，使用 search_knowledge_base。
5. 如果用户问函数、类、变量或代码实现位置，优先使用 search_code。
6. 如果用户问某个符号在哪里调用、引用或使用，优先使用 find_code_references。
7. 如果用户要求读取完整代码文件，或者检索结果上下文不足，可以使用 read_code_file。
8. 如果用户要求“详细、完整、流程、步骤、总结、原理”，并且已经有检索结果，可以继续使用 read_document_chunks。
9. 如果用户要求总结某个文档、Word、PDF、docx 或最近上传的文件，优先使用 summarize_document。
10. 不要重复调用同一个工具，除非查询条件明显不同且确实有必要。
11. 如果已经获得足够信息，请选择 final_answer。
12. 你必须只返回 JSON，不要使用 markdown，不要解释。

返回 JSON 格式：

{{
  "action": "search_knowledge_base",
  "arguments": {{
    "query": "用户问题"
  }},
  "reason": "一句话说明为什么选择这个工具"
}}

用户问题：
{question}

已有工具调用和观察结果：
{previous_steps}

请决定下一步 action：
""".strip()

def normalize_react_action(
    raw_action:
        dict[str, Any] | None,
    *,
    repository_scoped:
        bool = False,
) -> tuple[
    str,
    dict[str, Any],
    str,
]:
    if not raw_action:
        return "search_knowledge_base", {}, "LLM action 解析失败，使用默认检索工具。"

    action = str(raw_action.get("action", "")).strip()

    arguments = raw_action.get("arguments", {})

    if not isinstance(arguments, dict):
        arguments = {}

    reason = str(raw_action.get("reason", "")).strip()

    allowed_actions = (
        get_agent_tool_names(
            repository_scoped=
            repository_scoped,
        )
    )

    if action not in allowed_actions:
        return "search_knowledge_base", {}, "LLM 返回了未知 action，使用默认检索工具。"

    return action, arguments, reason


def build_fallback_react_action(
    *,
    question: str,
    tool_calls: list[AgentToolCallPublic],
    sources: list[RagChatSource],
    repository_scoped: bool = False,
) -> tuple[str, dict[str, Any], str]:
    used_tool_names = {tool_call.tool_name for tool_call in tool_calls}

    if not tool_calls:
        if (
            not repository_scoped
            and should_search_rag_history(
                question,
            )
        ):
            return (
                "search_rag_history",
                {"query": question},
                "规则兜底：用户问题看起来是在查询历史记录。",
            )

        if should_list_code_files(question):
            return (
                "list_code_files",
                {"limit": 200},
                "规则兜底：用户问题看起来是在询问代码文件或项目结构。",
            )

        if should_find_code_references(question):
            symbol_name = extract_possible_symbol_name(question)

            return (
                "find_code_references",
                {
                    "symbol_name": symbol_name,
                    "limit": 50,
                },
                "规则兜底：用户问题看起来是在询问代码引用或定义位置。",
            )

        if should_search_code(question):
            return (
                "search_code",
                {"query": question},
                "规则兜底：用户问题看起来是在询问具体代码逻辑。",
            )

        if should_summarize_document(question):
            return (
                "summarize_document",
                {"max_chunks": 5},
                "规则兜底：用户问题看起来是在请求总结某个文档。",
            )

        if should_list_documents(question) or should_summarize_knowledge_base(question):
            return (
                "list_documents",
                {},
                "规则兜底：用户问题需要先查看知识库文档。",
            )

        return (
            "search_knowledge_base",
            {"query": question},
            "规则兜底：默认先检索知识库。",
        )

    if (
        "list_documents" in used_tool_names
        and "summarize_document" not in used_tool_names
        and should_summarize_document(question)
    ):
        return (
            "summarize_document",
            {"max_chunks": 5},
            "规则兜底：已经查看过文档列表，继续总结文档。",
        )

    if (
        "search_knowledge_base" not in used_tool_names
        and "search_rag_history" not in used_tool_names
    ):
        return (
            "search_knowledge_base",
            {"query": question},
            "规则兜底：还没有检索知识库，继续检索。",
        )

    if (
        sources
        and "read_code_file" not in used_tool_names
        and should_read_code_file(question)
    ):
        first_source = sources[0]

        return (
            "read_code_file",
            {
                "document_id": str(first_source.document_id),
                "max_chunks": 50,
                "max_chars": 20000,
            },
            "规则兜底：问题需要读取完整代码文件。",
        )

    if (
        sources
        and "read_document_chunks" not in used_tool_names
        and should_read_document_chunks(question)
    ):
        return (
            "read_document_chunks",
            {"window": 1},
            "规则兜底：问题需要更完整上下文，读取相邻 chunk。",
        )

    return (
        "final_answer",
        {},
        "规则兜底：已有信息足够，进入最终回答。",
    )


def parse_uuid_or_none(value: Any) -> uuid.UUID | None:
    if not value:
        return None

    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def execute_react_action(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    question: str,
    action: str,
    arguments: dict[str, Any],
    top_k: int,
    semantic_weight: float,
    keyword_weight: float,
    all_sources: list[RagChatSource],
) -> tuple[AgentToolCallPublic | None, list[RagChatSource]]:
    if action == "final_answer":
        return None, all_sources

    if action == "list_documents":
        observation = list_documents_tool(
            session=session,
            knowledge_base_id=knowledge_base_id,
        )

        tool_call = AgentToolCallPublic(
            tool_name="list_documents",
            arguments={
                "knowledge_base_id": str(knowledge_base_id),
                "limit": 20,
            },
            observation=observation,
            success=True,
        )

        return tool_call, all_sources

    if action == "search_rag_history":
        query = str(arguments.get("query") or question)

        observation = search_rag_history_tool(
            session=session,
            knowledge_base_id=knowledge_base_id,
            query=query,
            limit=10,
        )

        tool_call = AgentToolCallPublic(
            tool_name="search_rag_history",
            arguments={
                "knowledge_base_id": str(knowledge_base_id),
                "query": query,
                "limit": 10,
            },
            observation=observation,
            success=True,
        )

        return tool_call, all_sources

    if action == "search_knowledge_base":
        query = str(arguments.get("query") or question)

        observation, sources = search_knowledge_base_tool(
            session=session,
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=top_k,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
        )

        tool_call = AgentToolCallPublic(
            tool_name="search_knowledge_base",
            arguments={
                "query": query,
                "top_k": top_k,
                "semantic_weight": semantic_weight,
                "keyword_weight": keyword_weight,
            },
            observation=observation,
            success=True,
        )

        merged_sources = merge_sources_without_duplicates(
            existing_sources=all_sources,
            new_sources=sources,
        )

        return tool_call, merged_sources

    if action == "read_document_chunks":
        if not all_sources:
            tool_call = AgentToolCallPublic(
                tool_name="read_document_chunks",
                arguments=arguments,
                observation="当前还没有 sources，无法读取相邻 chunk。请先调用 search_knowledge_base。",
                success=False,
            )

            return tool_call, all_sources

        first_source = all_sources[0]

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

        read_observation, window_sources = read_document_chunks_tool(
            session=session,
            knowledge_base_id=knowledge_base_id,
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
            observation=read_observation,
            success=True,
        )

        merged_sources = merge_sources_without_duplicates(
            existing_sources=all_sources,
            new_sources=window_sources,
        )

        return tool_call, merged_sources

    tool_call = AgentToolCallPublic(
        tool_name=action,
        arguments=arguments,
        observation=f"未知工具 action：{action}",
        success=False,
    )

    return tool_call, all_sources


def get_bool_from_plan(
    *,
    plan: dict[str, Any],
    key: str,
    default: bool = False,
) -> bool:
    value = plan.get(key, default)

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.lower() in ["true", "yes", "1", "是", "需要"]

    if isinstance(value, int):
        return value != 0

    return default


def build_rule_based_agent_plan(question: str) -> dict[str, Any]:
    history_intent = should_search_rag_history(question)
    list_documents_intent = should_list_documents(question)
    summarize_intent = should_summarize_knowledge_base(question)
    read_more_context_intent = should_read_document_chunks(question)

    return {
        "need_search_rag_history": history_intent,
        "need_list_documents": (not history_intent)
        and (list_documents_intent or summarize_intent),
        "need_search_knowledge_base": not history_intent,
        "need_read_more_context": (not history_intent) and read_more_context_intent,
        "reason": "规则兜底生成的工具计划。",
    }


def build_agent_planning_prompt(question: str) -> str:
    return f"""
你是一个知识库 Agent 的工具规划器。

你需要根据用户问题，判断后端应该调用哪些工具。

当前可用工具如下：

1. list_documents
用途：查看当前知识库有哪些文档。
适合问题：
- 这个知识库有哪些文档？
- 知识库里有什么文件？
- 请先看看知识库包含什么资料。

2. search_knowledge_base
用途：检索当前知识库内容。
适合问题：
- 根据知识库回答某个具体问题。
- 解释某个概念。
- 总结知识库中的某个主题。
- 查询文档内容。

3. read_document_chunks
用途：在 search_knowledge_base 检索到相关 chunk 后，继续读取该文档附近的上下文。
适合问题：
- 详细说明
- 完整流程
- 步骤
- 原理
- 总结
- 需要更完整上下文的问题

注意：
read_document_chunks 不能单独使用，必须先使用 search_knowledge_base。

4. search_rag_history
用途：查询用户之前的 RAG 问答历史。
适合问题：
- 我之前问过什么？
- 上次关于 FastAPI 的回答是什么？
- 最近有哪些 RAG 问答记录？
- 历史记录里有没有 embedding 相关问题？

请只返回 JSON，不要返回解释文字。

JSON 格式必须是：

{{
  "need_list_documents": false,
  "need_search_knowledge_base": true,
  "need_read_more_context": false,
  "need_search_rag_history": false,
  "reason": "一句话说明为什么这样选"
}}

约束：
1. 如果用户问历史、之前、上次、问过、回答过，优先使用 search_rag_history。
2. 如果使用 search_rag_history，一般不需要 search_knowledge_base。
3. 如果用户问知识库有哪些文档，使用 list_documents。
4. 如果用户问具体知识内容，使用 search_knowledge_base。
5. 如果用户要求详细、完整、流程、步骤、总结，可以同时使用 search_knowledge_base 和 read_document_chunks。
6. read_document_chunks 只有在 need_search_knowledge_base 为 true 时才可以为 true。

用户问题：
{question}
""".strip()


def plan_agent_tools(question: str) -> tuple[dict[str, Any], list[str]]:
    trace: list[str] = []

    fallback_plan = build_rule_based_agent_plan(question)

    planning_prompt = build_agent_planning_prompt(question)

    try:
        raw_plan = call_llm(planning_prompt)
        trace.append("llm_tool_planner_called")
    except LLMError:
        trace.append("llm_tool_planner_failed_use_rule_fallback")
        return fallback_plan, trace

    parsed_plan = extract_json_object(raw_plan)

    if parsed_plan is None:
        trace.append("llm_tool_planner_parse_failed_use_rule_fallback")
        return fallback_plan, trace

    need_search_rag_history = get_bool_from_plan(
        plan=parsed_plan,
        key="need_search_rag_history",
        default=fallback_plan["need_search_rag_history"],
    )
    need_list_documents = get_bool_from_plan(
        plan=parsed_plan,
        key="need_list_documents",
        default=fallback_plan["need_list_documents"],
    )
    need_search_knowledge_base = get_bool_from_plan(
        plan=parsed_plan,
        key="need_search_knowledge_base",
        default=fallback_plan["need_search_knowledge_base"],
    )
    need_read_more_context = get_bool_from_plan(
        plan=parsed_plan,
        key="need_read_more_context",
        default=fallback_plan["need_read_more_context"],
    )

    if need_search_rag_history:
        need_search_knowledge_base = False
        need_read_more_context = False

    if need_read_more_context and not need_search_knowledge_base:
        need_read_more_context = False

    plan = {
        "need_search_rag_history": need_search_rag_history,
        "need_list_documents": need_list_documents,
        "need_search_knowledge_base": need_search_knowledge_base,
        "need_read_more_context": need_read_more_context,
        "reason": str(parsed_plan.get("reason", "")),
    }

    trace.append(
        "llm_tool_plan="
        f"history={need_search_rag_history},"
        f"list_documents={need_list_documents},"
        f"search_kb={need_search_knowledge_base},"
        f"read_more={need_read_more_context}"
    )

    return plan, trace





def build_agent_final_prompt(
    *,
    question: str,
    tool_calls: list[AgentToolCallPublic],
    sources: list[RagChatSource],
) -> str:
    tool_observations = []

    for index, tool_call in enumerate(tool_calls, start=1):
        tool_observations.append(
            f"[工具调用 {index}]\n"
            f"工具名称：{tool_call.tool_name}\n"
            f"参数：{tool_call.arguments}\n"
            f"观察结果：\n{tool_call.observation}"
        )

    sources_context = build_sources_context(sources=sources)

    return f"""
你是一个知识库 Agent 助手。

你可以根据已经调用过的工具结果，回答用户问题。

要求：
1. 优先根据知识库资料和代码检索结果回答。
2. 如果资料不足，要明确说明“当前知识库资料不足，无法可靠回答”。
3. 不要编造知识库中没有的信息。
4. 如果工具结果中包含来源文件、chunk 信息、file_path、symbol_name、line_range，回答时要尽量说明依据。
5. 如果用户问代码问题，回答时尽量指出相关文件、函数/类名、行号范围和核心逻辑。
6. 如果用户问“在哪里定义/哪里调用/引用位置”，回答时要区分“可能定义位置”和“可能引用位置”。
7. 如果用户问“完整逻辑/执行流程/实现流程”，回答时要结合完整文件上下文，按步骤说明流程。
8. 如果用户要求修改建议，只给出建议和可能修改位置，不要假装已经真实修改了代码。
9. 回答要清晰、有条理。

用户问题：
{question}

工具调用过程：
{chr(10).join(tool_observations)}

知识库资料：
{sources_context}

请根据以上信息给出最终回答：
""".strip()


def run_knowledge_base_agent(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    question: str,
    top_k: int,
    max_steps: int,
    semantic_weight: float,
    keyword_weight: float,
    repository_analysis_task_id: uuid.UUID | None = None,
) -> tuple[str, list[AgentToolCallPublic], list[RagChatSource], list[str]]:
    trace: list[str] = []
    tool_calls: list[AgentToolCallPublic] = []
    all_sources: list[RagChatSource] = []

    repository_scoped = (
            repository_analysis_task_id
            is not None
    )

    if repository_scoped:
        trace.append(
            "repository_scope="
            f"{repository_analysis_task_id}",
        )
    else:
        trace.append(
            "repository_scope=none",
        )

    semantic_weight, keyword_weight = normalize_agent_weights(
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
    )

    trace.append(
        f"agent_params_top_k={top_k},semantic_weight={semantic_weight:.2f},keyword_weight={keyword_weight:.2f}"
    )

    max_steps = max(1, min(max_steps, 10))

    for step_index in range(max_steps):
        used_tool_names = {tool_call.tool_name for tool_call in tool_calls}

        react_prompt = build_react_step_prompt(
            question=question,
            tool_calls=tool_calls,
            used_steps=step_index,
            max_steps=max_steps,
            repository_analysis_task_id=repository_analysis_task_id,
        )

        try:
            raw_action_text = call_llm(react_prompt)
            trace.append(f"react_step_{step_index + 1}_planner_called")
            raw_action = extract_json_object(raw_action_text)
            action, arguments, reason = (
                normalize_react_action(
                    raw_action,
                    repository_scoped=
                    repository_scoped,
                )
            )
        except LLMError:
            action, arguments, reason = build_fallback_react_action(
                question=question,
                tool_calls=tool_calls,
                sources=all_sources,
                repository_scoped=repository_scoped,
            )
            trace.append(f"react_step_{step_index + 1}_planner_failed_use_fallback")

        if action in used_tool_names and action not in {"search_knowledge_base", "search_code", "find_code_references"}:
            fallback_action, fallback_arguments, fallback_reason = (
                build_fallback_react_action(
                    question=question,
                    tool_calls=tool_calls,
                    sources=all_sources,
                    repository_scoped= repository_scoped,
                )
            )

            trace.append(
                f"react_step_{step_index + 1}_avoid_duplicate_action={action}"
            )

            action = fallback_action
            arguments = fallback_arguments
            reason = fallback_reason

        trace.append(
            f"react_step_{step_index + 1}_action={action},reason={reason}"
        )

        if action == "final_answer":
            trace.append(f"react_step_{step_index + 1}_final_answer_selected")
            break

        tool_context = AgentToolContext(
            session=session,
            knowledge_base_id=
            knowledge_base_id,
            repository_analysis_task_id=
            repository_analysis_task_id,
            question=question,
            top_k=top_k,
            semantic_weight=
            semantic_weight,
            keyword_weight=
            keyword_weight,
            all_sources=
            all_sources,
        )

        tool_result = execute_registered_agent_tool(
            action=action,
            arguments=arguments,
            context=tool_context,
        )

        tool_call = tool_result.tool_call
        all_sources = tool_result.sources

        if tool_result.stop:
            trace.append(f"react_step_{step_index + 1}_tool_registry_stop")
            break

        if tool_call is not None:
            tool_calls.append(tool_call)
            trace.append(
                f"react_step_{step_index + 1}_tool_call={tool_call.tool_name}"
            )

        if tool_call is not None and not tool_call.success:
            fallback_action, fallback_arguments, fallback_reason = (
                build_fallback_react_action(
                    question=question,
                    tool_calls=tool_calls,
                    sources=all_sources,
                    repository_scoped=repository_scoped,
                )
            )

            if fallback_action == "final_answer":
                trace.append(
                    f"react_step_{step_index + 1}_tool_failed_stop_loop"
                )
                break

    if not tool_calls:
        trace.append(
            "react_no_tool_called_use_"
            "registered_search_fallback",
        )

        fallback_context = (
            AgentToolContext(
                session=session,
                knowledge_base_id=
                knowledge_base_id,
                repository_analysis_task_id=
                repository_analysis_task_id,
                question=question,
                top_k=top_k,
                semantic_weight=
                semantic_weight,
                keyword_weight=
                keyword_weight,
                all_sources=
                all_sources,
            )
        )

        fallback_result = (
            execute_registered_agent_tool(
                action=
                "search_knowledge_base",
                arguments={
                    "query": question,
                },
                context=
                fallback_context,
            )
        )

        if (
                fallback_result.tool_call
                is not None
        ):
            tool_calls.append(
                fallback_result
                    .tool_call,
            )

        all_sources = (
            fallback_result.sources
        )

        tool_calls.append(
            AgentToolCallPublic(
                tool_name="search_knowledge_base",
                arguments={
                    "query": question,
                    "top_k": top_k,
                    "semantic_weight": semantic_weight,
                    "keyword_weight": keyword_weight,
                },
                observation=observation,
                success=True,
            )
        )

        all_sources = merge_sources_without_duplicates(
            existing_sources=all_sources,
            new_sources=sources,
        )

    final_prompt = build_agent_final_prompt(
        question=question,
        tool_calls=tool_calls,
        sources=all_sources,
    )

    try:
        answer = call_llm(final_prompt)
        trace.append("generate_agent_answer")
    except LLMError as error:
        answer = (
            "Agent 已完成工具调用，但大模型生成最终回答失败。\n\n"
            f"错误信息：{error}\n\n"
            "以下是工具调用结果：\n\n"
            + "\n\n".join(
                [
                    f"[{tool_call.tool_name}]\n{tool_call.observation}"
                    for tool_call in tool_calls
                ]
            )
        )
        trace.append("generate_agent_answer_failed")

    return answer, tool_calls, all_sources, trace