from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any


DEFAULT_MAX_RESULT_JSON_BYTES = 1_500_000
DEFAULT_MAX_EVIDENCE_JSON_BYTES = 2_000_000
DEFAULT_MAX_REPORT_CHARACTERS = 80_000

DEFAULT_MAX_STRING_CHARACTERS = 4_000

_JSON_BUDGET_RESERVE_BYTES = 8_192

_COMPACTION_SCALES = (
    1.0,
    0.75,
    0.5,
    0.25,
    0.1,
)

_EVIDENCE_HIGH_CONFIDENCE_SOURCES = {
    "github_rest_api",
    "github_zip",
    "repository_filesystem",
    "repository_file",
    "file_extensions",
    "python_ast",
}

_EVIDENCE_MEDIUM_CONFIDENCE_SOURCES = {
    "repository_scanner",
    "deterministic_path_matching",
    "python_ast_call_graph",
    "javascript_typescript_static_scan",
    "javascript_typescript_static_call_graph",
}

_LIST_LIMITS = {
    # 仓库结构
    "tree": 400,
    "module_paths": 250,
    "manifests": 150,
    "dependency_names": 300,
    "dependencies": 300,
    "entry_points": 120,
    "deployment_files": 120,
    "ci_files": 120,
    "migration_paths": 200,
    "test_paths": 300,

    # 普通代码结构
    "symbols": 700,
    "backend_routes": 400,
    "frontend_routes": 400,
    "frontend_api_calls": 400,
    "call_edges": 1_000,
    "data_models": 400,
    "business_flows": 300,

    # FastAPI Router 图
    "router_definitions": 400,
    "registrations": 500,
    "resolved_routes": 500,
    "routes": 500,
    "registration_chain": 20,

    # 后端调用链
    "internal_calls": 1_000,
    "unresolved_calls": 600,
    "model_usages": 600,
    "database_operations": 600,
    "route_flows": 250,
    "call_paths": 20,
    "steps": 12,

    # 前端调用链
    "pages": 250,
    "http_operations": 500,
    "page_operations": 400,
    "full_stack_flows": 250,
    "frontend_call_chain": 12,
    "backend_call_paths": 20,

    # Evidence
    "items": 100,
    "flows": 250,
    "edges": 1_000,
    "models": 500,
    "calls": 600,
    "paths": 500,
}

_STRING_LIMITS = {
    "description": 2_000,
    "project_summary": 3_000,
    "excerpt": 5_000,
    "readme_excerpt": 5_000,
    "message": 2_000,
    "error_message": 4_000,
    "notice": 2_000,
}

_EVIDENCE_TYPE_PRIORITY = {
    "github_repository_metadata": 10,
    "github_resolved_commit": 20,
    "github_repository_snapshot": 30,
    "readme": 40,
    "repository_tree": 50,
    "language_distribution": 60,
    "dependency_manifests": 70,
    "entry_points": 80,
    "deployment_configuration": 90,
    "continuous_integration": 100,
    "database_migrations": 110,
    "test_structure": 120,
    "backend_routes": 130,
    "data_models": 140,
    "fastapi_router_registration_graph": 150,
    "backend_business_flows": 160,
    "frontend_routes": 170,
    "frontend_api_calls": 180,
    "possible_business_flows": 190,
    "frontend_and_full_stack_flows": 200,
    "python_call_edges": 210,
    "scan_statistics": 220,
}


@dataclass(frozen=True, slots=True)
class RepositoryAnalysisCompactedPayload:
    """
    完成压缩后的仓库分析结果。

    RepositoryAnalysisProcessor 最终只需要把这三个字段
    交给 Worker 保存到数据库。
    """

    result_json: dict[str, Any]
    evidence_json: dict[str, Any]
    report_markdown: str


@dataclass(slots=True)
class _CompactionStatistics:
    """
    单个 JSON 数据的内部压缩统计。
    """

    original_bytes: int = 0
    final_bytes: int = 0

    original_sha256: str = ""

    removed_duplicate_items: int = 0
    truncated_list_items: int = 0
    truncated_string_characters: int = 0

    applied_scale: float = 1.0

    truncated_paths: dict[str, int] = field(
        default_factory=dict,
    )

    def to_dict(self) -> dict[str, Any]:
        """
        转换成可以保存到 JSONB 的结构。
        """

        return {
            "original_bytes": self.original_bytes,
            "final_bytes": self.final_bytes,
            "original_sha256": self.original_sha256,
            "removed_duplicate_items": (
                self.removed_duplicate_items
            ),
            "truncated_list_items": (
                self.truncated_list_items
            ),
            "truncated_string_characters": (
                self.truncated_string_characters
            ),
            "applied_scale": self.applied_scale,
            "truncated_paths": dict(
                sorted(
                    self.truncated_paths.items(),
                ),
            ),
        }


@dataclass(frozen=True, slots=True)
class _MarkdownCompactionResult:
    """
    Markdown 压缩结果。
    """

    markdown: str

    original_characters: int
    final_characters: int

    truncated: bool


def compact_repository_analysis_payload(
    *,
    result_json: dict[str, Any],
    evidence_json: dict[str, Any],
    report_markdown: str,
    max_result_json_bytes: int = (
        DEFAULT_MAX_RESULT_JSON_BYTES
    ),
    max_evidence_json_bytes: int = (
        DEFAULT_MAX_EVIDENCE_JSON_BYTES
    ),
    max_report_characters: int = (
        DEFAULT_MAX_REPORT_CHARACTERS
    ),
) -> RepositoryAnalysisCompactedPayload:
    """
    对一次仓库分析的全部输出进行统一压缩。

    处理顺序：

    1. Evidence 置信度和顺序标准化；
    2. 对 JSON 递归去重和截断；
    3. 按字节预算逐级收紧；
    4. 按 Markdown 章节限制报告长度；
    5. 保存压缩统计信息。
    """

    if max_result_json_bytes <= 0:
        raise ValueError(
            "max_result_json_bytes must be greater than zero",
        )

    if max_evidence_json_bytes <= 0:
        raise ValueError(
            "max_evidence_json_bytes must be greater than zero",
        )

    if max_report_characters <= 0:
        raise ValueError(
            "max_report_characters must be greater than zero",
        )

    normalized_result = copy.deepcopy(
        result_json,
    )

    normalized_evidence = (
        _prepare_evidence_payload(
            copy.deepcopy(
                evidence_json,
            ),
        )
    )

    compacted_result, result_statistics = (
        _fit_json_to_budget(
            payload=normalized_result,
            max_bytes=max_result_json_bytes,
        )
    )

    compacted_evidence, evidence_statistics = (
        _fit_json_to_budget(
            payload=normalized_evidence,
            max_bytes=max_evidence_json_bytes,
        )
    )

    markdown_result = _compact_markdown_report(
        report_markdown,
        max_characters=max_report_characters,
    )

    compacted_result["compaction"] = {
        **result_statistics.to_dict(),
        "report": {
            "original_characters": (
                markdown_result
                .original_characters
            ),
            "final_characters": (
                markdown_result
                .final_characters
            ),
            "truncated": (
                markdown_result.truncated
            ),
        },
    }

    compacted_evidence["compaction"] = (
        evidence_statistics.to_dict()
    )

    return RepositoryAnalysisCompactedPayload(
        result_json=compacted_result,
        evidence_json=compacted_evidence,
        report_markdown=markdown_result.markdown,
    )


def _prepare_evidence_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    对 Evidence 顶层结构进行标准化。

    主要处理：

    - Evidence ID 去重；
    - 按 Evidence 优先级排序；
    - 增加 confidence；
    - 增加 confidence_reason；
    - 生成置信度数量统计。
    """

    raw_items = payload.get("items")

    if not isinstance(raw_items, list):
        payload["items"] = []
        payload["confidence_summary"] = {
            "high": 0,
            "medium": 0,
            "low": 0,
        }
        return payload

    normalized_items: list[
        dict[str, Any]
    ] = []

    seen_ids: set[str] = set()

    duplicate_ids: list[str] = []

    confidence_summary = {
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    for index, raw_item in enumerate(
        raw_items,
        start=1,
    ):
        if not isinstance(raw_item, dict):
            continue

        item = copy.deepcopy(raw_item)

        evidence_id = str(
            item.get("id")
            or f"E-AUTO-{index:04d}",
        ).strip()

        if evidence_id in seen_ids:
            duplicate_ids.append(evidence_id)
            continue

        seen_ids.add(evidence_id)

        item["id"] = evidence_id

        confidence, reason = (
            _determine_evidence_confidence(
                item,
            )
        )

        item["confidence"] = confidence

        item["confidence_reason"] = reason

        confidence_summary[confidence] += 1

        normalized_items.append(item)

    normalized_items.sort(
        key=_evidence_sort_key,
    )

    payload["items"] = normalized_items

    payload["confidence_summary"] = (
        confidence_summary
    )

    payload["duplicate_evidence_ids_removed"] = (
        sorted(set(duplicate_ids))
    )

    return payload


def _determine_evidence_confidence(
    item: dict[str, Any],
) -> tuple[str, str]:
    """
    根据 Evidence 来源给出置信度。

    high：
    来源于 GitHub API、固定快照、文件系统或 Python AST。

    medium：
    来源真实，但包含路径匹配、调用图恢复等静态推断。

    low：
    来源未知，或不是确定性扫描结果。
    """

    source = str(
        item.get("source") or "",
    ).strip()

    evidence_type = str(
        item.get("type") or "",
    ).strip()

    if source in _EVIDENCE_HIGH_CONFIDENCE_SOURCES:
        return (
            "high",
            (
                "Evidence comes directly from a "
                "deterministic source"
            ),
        )

    if (
        source
        in _EVIDENCE_MEDIUM_CONFIDENCE_SOURCES
    ):
        return (
            "medium",
            (
                "Evidence is based on deterministic "
                "static analysis with inference"
            ),
        )

    if evidence_type in {
        "backend_business_flows",
        "possible_business_flows",
        "frontend_and_full_stack_flows",
    }:
        return (
            "medium",
            (
                "The source data is deterministic, "
                "but flow reconstruction is static"
            ),
        )

    return (
        "low",
        (
            "Evidence source confidence could not "
            "be determined"
        ),
    )


def _evidence_sort_key(
    item: dict[str, Any],
) -> tuple[int, int, str]:
    """
    确保 Evidence 顺序稳定。

    第一排序依据是业务优先级；
    第二排序依据是 E-001、E-002 等数字编号。
    """

    evidence_type = str(
        item.get("type") or "",
    )

    priority = _EVIDENCE_TYPE_PRIORITY.get(
        evidence_type,
        10_000,
    )

    evidence_id = str(
        item.get("id") or "",
    )

    identifier_number = (
        _extract_identifier_number(
            evidence_id,
        )
    )

    return (
        priority,
        identifier_number,
        evidence_id,
    )


def _extract_identifier_number(
    value: str,
) -> int:
    """
    从 E-021 中提取 21。
    """

    match = re.search(
        r"(\d+)",
        value,
    )

    if match is None:
        return 1_000_000

    return int(match.group(1))


def _fit_json_to_budget(
    *,
    payload: dict[str, Any],
    max_bytes: int,
) -> tuple[
    dict[str, Any],
    _CompactionStatistics,
]:
    """
    将 JSON 限制在指定字节预算内。

    每次从原始 payload 重新压缩，逐步降低数组数量限制。
    """

    original_bytes = _json_size_bytes(
        payload,
    )

    original_sha256 = _json_sha256(
        payload,
    )

    target_bytes = max(
        max_bytes
        - _JSON_BUDGET_RESERVE_BYTES,
        max_bytes // 2,
    )

    last_payload: dict[str, Any] = {}
    last_statistics = _CompactionStatistics()

    for scale in _COMPACTION_SCALES:
        statistics = _CompactionStatistics(
            original_bytes=original_bytes,
            original_sha256=original_sha256,
            applied_scale=scale,
        )

        compacted_value = _compact_value(
            payload,
            path=(),
            scale=scale,
            statistics=statistics,
        )

        if not isinstance(
            compacted_value,
            dict,
        ):
            raise TypeError(
                "Compacted root JSON value must be an object",
            )

        final_bytes = _json_size_bytes(
            compacted_value,
        )

        statistics.final_bytes = final_bytes

        last_payload = compacted_value
        last_statistics = statistics

        if final_bytes <= target_bytes:
            return compacted_value, statistics

    emergency_statistics = (
        _CompactionStatistics(
            original_bytes=original_bytes,
            original_sha256=original_sha256,
            applied_scale=0.05,
        )
    )

    emergency_payload = _compact_value(
        payload,
        path=(),
        scale=0.05,
        statistics=emergency_statistics,
        emergency=True,
    )

    if not isinstance(
        emergency_payload,
        dict,
    ):
        raise TypeError(
            "Emergency compacted JSON must be an object",
        )

    emergency_statistics.final_bytes = (
        _json_size_bytes(
            emergency_payload,
        )
    )

    if (
        emergency_statistics.final_bytes
        < last_statistics.final_bytes
    ):
        return (
            emergency_payload,
            emergency_statistics,
        )

    return last_payload, last_statistics


def _compact_value(
    value: Any,
    *,
    path: tuple[str, ...],
    scale: float,
    statistics: _CompactionStatistics,
    emergency: bool = False,
) -> Any:
    """
    递归压缩 JSON 兼容值。
    """

    if isinstance(value, dict):
        return {
            str(key): _compact_value(
                child_value,
                path=(
                    *path,
                    str(key),
                ),
                scale=scale,
                statistics=statistics,
                emergency=emergency,
            )
            for key, child_value
            in value.items()
        }

    if isinstance(value, (list, tuple)):
        compacted_items = [
            _compact_value(
                item,
                path=(
                    *path,
                    "[]",
                ),
                scale=scale,
                statistics=statistics,
                emergency=emergency,
            )
            for item in value
        ]

        unique_items = _stable_deduplicate(
            compacted_items,
        )

        duplicate_count = (
            len(compacted_items)
            - len(unique_items)
        )

        statistics.removed_duplicate_items += (
            duplicate_count
        )

        limit = _get_list_limit(
            path,
            scale=scale,
            emergency=emergency,
        )

        if len(unique_items) > limit:
            removed_count = (
                len(unique_items) - limit
            )

            statistics.truncated_list_items += (
                removed_count
            )

            path_text = _format_path(path)

            statistics.truncated_paths[
                path_text
            ] = (
                statistics.truncated_paths.get(
                    path_text,
                    0,
                )
                + removed_count
            )

            unique_items = unique_items[:limit]

        return unique_items

    if isinstance(value, str):
        limit = _get_string_limit(
            path,
            scale=scale,
            emergency=emergency,
        )

        if len(value) <= limit:
            return value

        removed_characters = (
            len(value) - limit
        )

        statistics.truncated_string_characters += (
            removed_characters
        )

        path_text = _format_path(path)

        statistics.truncated_paths[
            path_text
        ] = (
            statistics.truncated_paths.get(
                path_text,
                0,
            )
            + removed_characters
        )

        suffix = (
            "\n...[truncated]"
        )

        visible_characters = max(
            limit - len(suffix),
            0,
        )

        return (
            value[:visible_characters]
            + suffix
        )

    if value is None:
        return None

    if isinstance(
        value,
        (
            bool,
            int,
            float,
        ),
    ):
        return value

    return str(value)


def _get_list_limit(
    path: tuple[str, ...],
    *,
    scale: float,
    emergency: bool,
) -> int:
    """
    根据字段名称获取数组数量限制。
    """

    field_name = _last_real_path_part(
        path,
    )

    base_limit = _LIST_LIMITS.get(
        field_name,
        200,
    )

    if emergency:
        base_limit = min(
            base_limit,
            20,
        )

    return max(
        int(base_limit * scale),
        1,
    )


def _get_string_limit(
    path: tuple[str, ...],
    *,
    scale: float,
    emergency: bool,
) -> int:
    """
    根据字段名称获取字符串长度限制。
    """

    field_name = _last_real_path_part(
        path,
    )

    base_limit = _STRING_LIMITS.get(
        field_name,
        DEFAULT_MAX_STRING_CHARACTERS,
    )

    if field_name in {
        "file_path",
        "path",
        "source",
        "handler",
        "symbol",
        "caller",
        "callee",
        "qualified_name",
    }:
        base_limit = min(
            base_limit,
            1_000,
        )

    if emergency:
        base_limit = min(
            base_limit,
            500,
        )

    return max(
        int(base_limit * max(scale, 0.1)),
        100,
    )


def _last_real_path_part(
    path: tuple[str, ...],
) -> str:
    for part in reversed(path):
        if part != "[]":
            return part

    return ""


def _stable_deduplicate(
    items: list[Any],
) -> list[Any]:
    """
    使用稳定 JSON 表示去重，同时保持第一次出现顺序。
    """

    results: list[Any] = []
    seen_tokens: set[str] = set()

    for item in items:
        token = json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        if token in seen_tokens:
            continue

        seen_tokens.add(token)
        results.append(item)

    return results


def _compact_markdown_report(
    report_markdown: str,
    *,
    max_characters: int,
) -> _MarkdownCompactionResult:
    """
    按 Markdown 二级章节压缩报告。

    尽量保留完整章节，不在可以避免时直接从字符中间截断。
    """

    normalized_report = str(
        report_markdown or "",
    ).strip()

    original_characters = len(
        normalized_report,
    )

    if original_characters <= max_characters:
        return _MarkdownCompactionResult(
            markdown=normalized_report,
            original_characters=(
                original_characters
            ),
            final_characters=(
                original_characters
            ),
            truncated=False,
        )

    footer = (
        "\n\n---\n\n"
        "> 本报告已根据快速概览的存储预算进行压缩。"
        "部分重复调用路径、文件清单和次要证据未在"
        " Markdown 中完全展开。"
    )

    available_characters = max(
        max_characters - len(footer),
        1,
    )

    sections = _split_markdown_sections(
        normalized_report,
    )

    retained_sections: list[str] = []

    current_length = 0
    truncated = False

    for section in sections:
        separator_length = (
            2 if retained_sections else 0
        )

        projected_length = (
            current_length
            + separator_length
            + len(section)
        )

        if projected_length <= available_characters:
            retained_sections.append(section)
            current_length = projected_length
            continue

        remaining = (
            available_characters
            - current_length
            - separator_length
        )

        if remaining > 300:
            truncated_section = section[
                :remaining
            ]

            newline_index = (
                truncated_section.rfind(
                    "\n",
                )
            )

            if newline_index >= 100:
                truncated_section = (
                    truncated_section[
                        :newline_index
                    ]
                )

            retained_sections.append(
                (
                    truncated_section.rstrip()
                    + "\n\n"
                    + "> 本章节后续内容已压缩。"
                ),
            )

        truncated = True
        break

    compacted_report = (
        "\n\n".join(
            retained_sections,
        ).rstrip()
        + footer
    )

    if len(compacted_report) > max_characters:
        compacted_report = (
            compacted_report[
                :max_characters
                - len(footer)
            ].rstrip()
            + footer
        )

    return _MarkdownCompactionResult(
        markdown=compacted_report,
        original_characters=(
            original_characters
        ),
        final_characters=len(
            compacted_report,
        ),
        truncated=truncated,
    )


def _split_markdown_sections(
    markdown: str,
) -> list[str]:
    """
    使用二级标题拆分 Markdown。

    开头的一级标题和简介会作为第一个章节保留。
    """

    sections = re.split(
        r"(?=\n##\s+)",
        markdown,
    )

    return [
        section.strip()
        for section in sections
        if section.strip()
    ]


def _format_path(
    path: tuple[str, ...],
) -> str:
    """
    把递归路径转换成可读形式。
    """

    if not path:
        return "$"

    parts: list[str] = ["$"]

    for part in path:
        if part == "[]":
            parts.append("[]")
        else:
            parts.append(
                f".{part}",
            )

    return "".join(parts)


def _json_size_bytes(
    payload: Any,
) -> int:
    """
    计算 UTF-8 JSON 字节数。
    """

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return len(
        serialized.encode("utf-8"),
    )


def _json_sha256(
    payload: Any,
) -> str:
    """
    计算压缩前 JSON 的 SHA-256。

    用于确认两次分析是否基于相同原始输出，
    不保存原始未压缩内容。
    """

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        serialized.encode("utf-8"),
    ).hexdigest()