from __future__ import annotations
import os
import json
from dataclasses import dataclass
from typing import Any, Literal
from pydantic import ValidationError
from collections.abc import Callable
from time import perf_counter

from app.models import (
    CodeSkillGenerateReviewReportResponse,
    CodeSkillGeneratedReviewReportPublic,
    CodeSkillReportGenerationTracePublic,
    CodeSkillReviewEvidenceResponse,
)

from app.services.llm import (
    LLMError,
    call_llm,
)


REVIEW_PROMPT_VERSION = "repoguard-review-v1"

MAX_PREVIEW_CHARACTERS = 800
MAX_REASON_CHARACTERS = 600
MAX_MESSAGE_CHARACTERS = 600
MAX_GENERATION_ERROR_CHARACTERS = 1500


ReviewLanguage = Literal[
    "zh-CN",
    "en-US",
]

ReviewLLMCall = Callable[
    [str],
    str,
]


class CodeReviewReportError(Exception):
    """RepoGuard Review Report 基础异常。"""


class ReviewReportParseError(CodeReviewReportError):
    """模型返回内容无法解析成合法报告。"""


class ReviewEvidenceValidationError(CodeReviewReportError):
    """报告引用了不存在的 Evidence ID。"""


@dataclass(frozen=True)
class ReviewEvidenceItem:
    evidence_id: str
    evidence_type: str
    data: dict[str, Any]

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            **self.data,
        }


@dataclass(frozen=True)
class ReviewPromptPackage:
    system_prompt: str
    user_prompt: str
    prompt_version: str

    evidence_catalog: dict[
        str,
        ReviewEvidenceItem,
    ]

    evidence_item_count: int


def number_or_zero(
    value: int | float | None,
) -> int | float:
    if value is None:
        return 0

    return value


def truncate_review_text(
    value: str | None,
    *,
    max_characters: int,
) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip()

    if not normalized_value:
        return None

    if len(normalized_value) <= max_characters:
        return normalized_value

    return normalized_value[:max_characters].rstrip() + "..."


def build_changed_file_evidence_data(
    changed_file: Any,
) -> dict[str, Any]:
    return {
        "file_path": changed_file.file_path,
        "old_path": changed_file.old_path,
        "new_path": changed_file.new_path,
        "change_type": changed_file.change_type,
        "added_lines": number_or_zero(changed_file.added_lines),
        "deleted_lines": number_or_zero(changed_file.deleted_lines),
        "hunk_count": len(changed_file.hunks or []),
    }


def build_changed_symbol_evidence_data(
    changed_symbol: Any,
) -> dict[str, Any]:
    return {
        "file_path": changed_symbol.file_path,
        "symbol_name": changed_symbol.symbol_name,
        "symbol_type": changed_symbol.symbol_type,
        "line_range": changed_symbol.line_range,
        "confidence": number_or_zero(changed_symbol.confidence),
        "changed_hunk_new_start": (changed_symbol.changed_hunk_new_start),
        "changed_hunk_new_end": (changed_symbol.changed_hunk_new_end),
        "overlap_line_count": number_or_zero(changed_symbol.overlap_line_count),
        "reason": truncate_review_text(
            changed_symbol.reason,
            max_characters=MAX_REASON_CHARACTERS,
        ),
    }


def build_impact_reference_evidence_data(
    impact_reference: Any,
) -> dict[str, Any]:
    return {
        "file_path": impact_reference.file_path,
        "changed_symbol_name": (impact_reference.changed_symbol_name),
        "changed_symbol_type": (impact_reference.changed_symbol_type),
        "containing_symbol_name": (impact_reference.containing_symbol_name),
        "containing_symbol_type": (impact_reference.containing_symbol_type),
        "containing_line_range": (impact_reference.containing_line_range),
        "occurrence_count": number_or_zero(impact_reference.occurrence_count),
        "confidence": number_or_zero(impact_reference.confidence),
        "reason": truncate_review_text(
            impact_reference.reason,
            max_characters=MAX_REASON_CHARACTERS,
        ),
        "preview": truncate_review_text(
            impact_reference.preview,
            max_characters=MAX_PREVIEW_CHARACTERS,
        ),
    }


def build_impacted_file_evidence_data(
    impacted_file: Any,
) -> dict[str, Any]:
    return {
        "file_path": impacted_file.file_path,
        "reference_count": number_or_zero(impacted_file.reference_count),
        "impacted_symbol_names": (impacted_file.impacted_symbol_names or []),
        "confidence": number_or_zero(impacted_file.confidence),
        "reason": truncate_review_text(
            impacted_file.reason,
            max_characters=MAX_REASON_CHARACTERS,
        ),
    }


def build_recommended_test_evidence_data(
    recommended_test: Any,
) -> dict[str, Any]:
    return {
        "test_file_path": (recommended_test.test_file_path),
        "confidence": number_or_zero(recommended_test.confidence),
        "path_match_score": number_or_zero(recommended_test.path_match_score),
        "symbol_match_count": number_or_zero(recommended_test.symbol_match_count),
        "related_changed_files": (recommended_test.related_changed_files or []),
        "related_impacted_files": (recommended_test.related_impacted_files or []),
        "related_symbols": (recommended_test.related_symbols or []),
        "matched_reasons": [
            truncated_reason
            for reason in (recommended_test.matched_reasons or [])
            if (
                truncated_reason := truncate_review_text(
                    reason,
                    max_characters=(MAX_REASON_CHARACTERS),
                )
            )
        ],
        "preview": truncate_review_text(
            recommended_test.preview,
            max_characters=MAX_PREVIEW_CHARACTERS,
        ),
    }


def build_risk_signal_evidence_data(
    risk_signal: Any,
) -> dict[str, Any]:
    return {
        "risk_type": risk_signal.risk_type,
        "risk_level": risk_signal.risk_level,
        "title": risk_signal.title,
        "message": truncate_review_text(
            risk_signal.message,
            max_characters=MAX_MESSAGE_CHARACTERS,
        ),
        "evidence": risk_signal.evidence or [],
        "related_files": (risk_signal.related_files or []),
        "related_symbols": (risk_signal.related_symbols or []),
    }


def build_review_checklist_evidence_data(
    checklist_item: Any,
) -> dict[str, Any]:
    return {
        "item_id": checklist_item.item_id,
        "category": checklist_item.category,
        "priority": checklist_item.priority,
        "description": checklist_item.description,
        "reason": truncate_review_text(
            checklist_item.reason,
            max_characters=MAX_REASON_CHARACTERS,
        ),
        "related_files": (checklist_item.related_files or []),
        "related_symbols": (checklist_item.related_symbols or []),
    }


def build_review_evidence_catalog(
    evidence: CodeSkillReviewEvidenceResponse,
) -> dict[str, ReviewEvidenceItem]:
    catalog: dict[str, ReviewEvidenceItem] = {}

    for index, changed_file in enumerate(
        evidence.changed_files or [],
        start=1,
    ):
        evidence_id = f"CF-{index:03d}"

        catalog[evidence_id] = ReviewEvidenceItem(
            evidence_id=evidence_id,
            evidence_type="changed_file",
            data=build_changed_file_evidence_data(changed_file),
        )

    for index, changed_symbol in enumerate(
        evidence.changed_symbols or [],
        start=1,
    ):
        evidence_id = f"CS-{index:03d}"

        catalog[evidence_id] = ReviewEvidenceItem(
            evidence_id=evidence_id,
            evidence_type="changed_symbol",
            data=build_changed_symbol_evidence_data(changed_symbol),
        )

    impact_reference_index = 0

    for symbol_impact in evidence.symbol_impacts or []:
        for impact_reference in symbol_impact.references or []:
            impact_reference_index += 1

            evidence_id = f"IR-{impact_reference_index:03d}"

            catalog[evidence_id] = ReviewEvidenceItem(
                evidence_id=evidence_id,
                evidence_type=("impact_reference"),
                data=(build_impact_reference_evidence_data(impact_reference)),
            )

    for index, impacted_file in enumerate(
        evidence.impacted_files_summary or [],
        start=1,
    ):
        evidence_id = f"IF-{index:03d}"

        catalog[evidence_id] = ReviewEvidenceItem(
            evidence_id=evidence_id,
            evidence_type="impacted_file",
            data=build_impacted_file_evidence_data(impacted_file),
        )

    for index, recommended_test in enumerate(
        evidence.recommended_tests or [],
        start=1,
    ):
        evidence_id = f"RT-{index:03d}"

        catalog[evidence_id] = ReviewEvidenceItem(
            evidence_id=evidence_id,
            evidence_type="recommended_test",
            data=(build_recommended_test_evidence_data(recommended_test)),
        )

    for index, risk_signal in enumerate(
        evidence.risk_signals or [],
        start=1,
    ):
        evidence_id = f"RS-{index:03d}"

        catalog[evidence_id] = ReviewEvidenceItem(
            evidence_id=evidence_id,
            evidence_type="risk_signal",
            data=build_risk_signal_evidence_data(risk_signal),
        )

    for index, checklist_item in enumerate(
        evidence.review_checklist or [],
        start=1,
    ):
        evidence_id = f"RC-{index:03d}"

        catalog[evidence_id] = ReviewEvidenceItem(
            evidence_id=evidence_id,
            evidence_type="review_checklist",
            data=(build_review_checklist_evidence_data(checklist_item)),
        )

    return catalog


def build_review_llm_context(
    evidence: CodeSkillReviewEvidenceResponse,
) -> dict[str, Any]:
    catalog = build_review_evidence_catalog(evidence)

    summary = evidence.change_summary

    return {
        "change_summary": {
            "total_changed_files": number_or_zero(summary.total_changed_files),
            "total_added_lines": number_or_zero(summary.total_added_lines),
            "total_deleted_lines": number_or_zero(summary.total_deleted_lines),
            "total_changed_symbols": number_or_zero(summary.total_changed_symbols),
            "total_references": number_or_zero(summary.total_references),
            "total_impacted_files": number_or_zero(summary.total_impacted_files),
            "total_recommended_tests": (
                number_or_zero(summary.total_recommended_tests)
            ),
            "total_risk_signals": number_or_zero(summary.total_risk_signals),
            "risk_level": (summary.risk_level or "low"),
        },
        "evidence_items": [
            evidence_item.to_prompt_dict() for evidence_item in catalog.values()
        ],
        "test_gap_notes": (evidence.test_gap_notes or []),
        "uncovered_changed_files": (evidence.uncovered_changed_files or []),
        "uncovered_symbols": (evidence.uncovered_symbols or []),
        "limitations": (evidence.limitations or []),
    }


def build_review_output_schema_text() -> str:
    return json.dumps(
        {
            "executive_summary": "string",
            "overall_assessment": {
                "risk_level": ("low | medium | high"),
                "conclusion": "string",
                "merge_recommendation": ("approve | needs_review | request_changes"),
            },
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": ("low | medium | high"),
                    "category": "string",
                    "title": "string",
                    "description": "string",
                    "recommendation": "string",
                    "evidence_ids": [
                        "RS-001",
                    ],
                }
            ],
            "test_plan": [
                {
                    "test_file": "string",
                    "reason": "string",
                    "priority": ("low | medium | high"),
                    "evidence_ids": [
                        "RT-001",
                    ],
                }
            ],
            "manual_review_items": [
                {
                    "description": "string",
                    "priority": ("low | medium | high"),
                    "evidence_ids": [
                        "RC-001",
                    ],
                }
            ],
            "uncertainties": [
                "string",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def build_review_system_prompt(
    language: ReviewLanguage,
) -> str:
    output_schema = build_review_output_schema_text()

    if language == "en-US":
        return f"""
You are RepoGuard's evidence-grounded code review report generator.

Follow these rules strictly:

1. Use only the supplied RepoGuard Evidence.
2. Do not invent files, symbols, call relationships, runtime behavior, vulnerabilities, or test coverage.
3. Treat static matches and risk signals as indicators requiring verification, not confirmed bugs.
4. Every finding must contain at least one evidence_id that exists in the supplied evidence.
5. Test-plan items must cite relevant evidence_ids.
6. Manual-review items must cite relevant evidence_ids.
7. When evidence is insufficient, record the limitation in uncertainties instead of guessing.
8. Preserve uncertainty language such as "may", "possibly", and "requires verification".
9. Return JSON only. Do not wrap the response in Markdown code fences.
10. The JSON must conform to this structure:

{output_schema}
""".strip()

    return f"""
你是 RepoGuard 的证据约束代码审查报告生成器。

必须严格遵守以下规则：

1. 只能使用输入中提供的 RepoGuard Evidence。
2. 不得编造不存在的文件、符号、调用关系、运行时行为、安全漏洞或测试覆盖。
3. 静态匹配和风险信号只能作为需要复核的提示，不能直接表述为已经确认的 Bug。
4. 每一条 finding 必须至少引用一个真实存在的 evidence_id。
5. 测试计划必须引用与建议相关的 evidence_ids。
6. 人工检查项必须引用与检查内容相关的 evidence_ids。
7. Evidence 不足时，必须将不确定性写入 uncertainties，不能自行推测。
8. 对静态分析结果应使用“可能”“建议复核”“当前证据显示”等谨慎措辞。
9. 只能返回 JSON，不要使用 Markdown 代码块包裹。
10. 返回 JSON 必须符合以下结构：

{output_schema}
""".strip()


def build_review_user_prompt(
    *,
    evidence_context: dict[str, Any],
    language: ReviewLanguage,
) -> str:
    serialized_context = json.dumps(
        evidence_context,
        ensure_ascii=False,
        indent=2,
    )

    if language == "en-US":
        instruction = (
            "Generate a structured code review report "
            "from the following RepoGuard Evidence."
        )
    else:
        instruction = "请根据以下 RepoGuard Evidence 生成结构化代码审查报告。"

    return f"{instruction}\n\nRepoGuard Evidence:\n{serialized_context}"


def build_review_prompt_package(
    *,
    evidence: CodeSkillReviewEvidenceResponse,
    language: ReviewLanguage,
) -> ReviewPromptPackage:
    evidence_catalog = build_review_evidence_catalog(evidence)

    evidence_context = build_review_llm_context(evidence)

    return ReviewPromptPackage(
        system_prompt=build_review_system_prompt(language),
        user_prompt=build_review_user_prompt(
            evidence_context=evidence_context,
            language=language,
        ),
        prompt_version=REVIEW_PROMPT_VERSION,
        evidence_catalog=evidence_catalog,
        evidence_item_count=len(evidence_catalog),
    )


def build_combined_review_prompt(
    *,
    system_prompt: str,
    user_prompt: str,
) -> str:
    return (
        "=== SYSTEM INSTRUCTIONS ===\n"
        f"{system_prompt.strip()}\n\n"
        "=== USER EVIDENCE CONTEXT ===\n"
        f"{user_prompt.strip()}"
    )


def resolve_review_model_name(
    explicit_model_name: str | None = None,
) -> str:
    if explicit_model_name and explicit_model_name.strip():
        return explicit_model_name.strip()

    environment_model_names = [
        os.getenv("LLM_MODEL"),
        os.getenv("LLM_MODEL_NAME"),
        os.getenv("DEEPSEEK_MODEL"),
    ]

    for model_name in environment_model_names:
        if model_name and model_name.strip():
            return model_name.strip()

    return "configured-llm"


def format_review_generation_error(
    error: Exception,
) -> str:
    error_message = f"{type(error).__name__}: {error}"

    truncated_message = truncate_review_text(
        error_message,
        max_characters=(MAX_GENERATION_ERROR_CHARACTERS),
    )

    return truncated_message or type(error).__name__


def build_report_generation_trace(
    *,
    model_name: str,
    duration_ms: int,
    prompt_version: str,
    evidence_item_count: int,
    output_characters: int,
) -> CodeSkillReportGenerationTracePublic:
    return CodeSkillReportGenerationTracePublic(
        model=model_name,
        duration_ms=max(
            0,
            duration_ms,
        ),
        prompt_version=prompt_version,
        evidence_item_count=max(
            0,
            evidence_item_count,
        ),
        output_characters=max(
            0,
            output_characters,
        ),
    )


def strip_review_json_code_fence(
    raw_text: str,
) -> str:
    normalized_text = raw_text.strip()

    if not normalized_text:
        return ""

    lines = normalized_text.splitlines()

    if len(lines) < 2:
        return normalized_text

    first_line = lines[0].strip().lower()
    last_line = lines[-1].strip()

    if (
        first_line
        in {
            "```json",
            "```",
        }
        and last_line == "```"
    ):
        return "\n".join(lines[1:-1]).strip()

    return normalized_text


def parse_review_report_text(
    raw_text: str,
) -> CodeSkillGeneratedReviewReportPublic:
    normalized_text = strip_review_json_code_fence(raw_text)

    if not normalized_text:
        raise ReviewReportParseError("模型返回内容为空，无法生成 Review Report。")

    try:
        parsed_payload = json.loads(normalized_text)
    except json.JSONDecodeError as error:
        raise ReviewReportParseError(
            "模型返回内容不是合法 JSON："
            f"{error.msg}，"
            f"位置 line={error.lineno}, "
            f"column={error.colno}"
        ) from error

    if not isinstance(parsed_payload, dict):
        raise ReviewReportParseError("模型返回的 JSON 顶层必须是对象。")

    try:
        return CodeSkillGeneratedReviewReportPublic.model_validate(parsed_payload)
    except ValidationError as error:
        raise ReviewReportParseError(f"模型返回 JSON 结构校验失败：{error}") from error


def collect_review_report_evidence_ids(
    report: CodeSkillGeneratedReviewReportPublic,
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    def add_evidence_ids(
        evidence_ids: list[str],
    ) -> None:
        for evidence_id in evidence_ids:
            normalized_id = evidence_id.strip()

            if not normalized_id:
                continue

            if normalized_id in seen:
                continue

            seen.add(normalized_id)
            result.append(normalized_id)

    for finding in report.findings:
        add_evidence_ids(finding.evidence_ids)

    for test_plan_item in report.test_plan:
        add_evidence_ids(test_plan_item.evidence_ids)

    for manual_review_item in report.manual_review_items:
        add_evidence_ids(manual_review_item.evidence_ids)

    return result


def validate_review_report_evidence_ids(
    *,
    report: CodeSkillGeneratedReviewReportPublic,
    evidence_catalog: dict[
        str,
        ReviewEvidenceItem,
    ],
) -> None:
    referenced_ids = collect_review_report_evidence_ids(report)

    unknown_ids = [
        evidence_id
        for evidence_id in referenced_ids
        if evidence_id not in evidence_catalog
    ]

    if unknown_ids:
        formatted_unknown_ids = ", ".join(unknown_ids)

        raise ReviewEvidenceValidationError(
            f"模型报告引用了不存在的 Evidence ID：{formatted_unknown_ids}"
        )


def parse_and_validate_review_report(
    *,
    raw_text: str,
    evidence_catalog: dict[
        str,
        ReviewEvidenceItem,
    ],
) -> CodeSkillGeneratedReviewReportPublic:
    report = parse_review_report_text(raw_text)

    validate_review_report_evidence_ids(
        report=report,
        evidence_catalog=evidence_catalog,
    )

    return report


def normalize_markdown_inline(
    value: Any,
) -> str:
    normalized_value = str(value if value is not None else "")

    normalized_value = (
        normalized_value.replace("\r", " ")
        .replace("\n", " ")
        .replace("`", "\\`")
        .strip()
    )

    return normalized_value or "-"


def summarize_review_evidence_item(
    evidence_item: ReviewEvidenceItem,
) -> str:
    data = evidence_item.data
    evidence_type = evidence_item.evidence_type

    if evidence_type == "changed_file":
        return normalize_markdown_inline(data.get("file_path"))

    if evidence_type == "changed_symbol":
        symbol_name = normalize_markdown_inline(data.get("symbol_name"))

        file_path = normalize_markdown_inline(data.get("file_path"))

        return f"{symbol_name} @ {file_path}"

    if evidence_type == "impact_reference":
        containing_symbol = (
            data.get("containing_symbol_name")
            or data.get("changed_symbol_name")
            or "unknown symbol"
        )

        file_path = normalize_markdown_inline(data.get("file_path"))

        return f"{normalize_markdown_inline(containing_symbol)} @ {file_path}"

    if evidence_type == "impacted_file":
        return normalize_markdown_inline(data.get("file_path"))

    if evidence_type == "recommended_test":
        return normalize_markdown_inline(data.get("test_file_path"))

    if evidence_type == "risk_signal":
        return normalize_markdown_inline(data.get("title") or data.get("risk_type"))

    if evidence_type == "review_checklist":
        return normalize_markdown_inline(data.get("description") or data.get("item_id"))

    return normalize_markdown_inline(evidence_item.evidence_id)


def format_evidence_id_list(
    evidence_ids: list[str],
) -> str:
    if not evidence_ids:
        return "-"

    return ", ".join(
        f"`{normalize_markdown_inline(evidence_id)}`" for evidence_id in evidence_ids
    )


def get_risk_level_label(
    *,
    risk_level: str,
    language: ReviewLanguage,
) -> str:
    if language == "en-US":
        return risk_level

    return {
        "low": "低",
        "medium": "中",
        "high": "高",
    }.get(
        risk_level,
        risk_level,
    )


def get_merge_recommendation_label(
    *,
    merge_recommendation: str,
    language: ReviewLanguage,
) -> str:
    if language == "en-US":
        return merge_recommendation

    return {
        "approve": "可以合并",
        "needs_review": "需要进一步审查",
        "request_changes": "建议修改后再合并",
    }.get(
        merge_recommendation,
        merge_recommendation,
    )


def render_review_report_markdown(
    *,
    report: CodeSkillGeneratedReviewReportPublic,
    evidence_catalog: dict[str, ReviewEvidenceItem],
    language: ReviewLanguage,
) -> str:
    is_english = language == "en-US"
    lines: list[str] = []

    risk_label = get_risk_level_label(
        risk_level=report.overall_assessment.risk_level,
        language=language,
    )
    merge_label = get_merge_recommendation_label(
        merge_recommendation=(report.overall_assessment.merge_recommendation),
        language=language,
    )

    if is_english:
        lines.extend(
            [
                "# RepoGuard Code Review Report",
                "",
                "## Executive Summary",
                "",
                report.executive_summary,
                "",
                "## Overall Assessment",
                "",
                f"- Risk level: {risk_label}",
                f"- Merge recommendation: {merge_label}",
                (f"- Conclusion: {report.overall_assessment.conclusion}"),
                "",
                "## Findings",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "# RepoGuard 代码审查报告",
                "",
                "## 执行摘要",
                "",
                report.executive_summary,
                "",
                "## 总体评估",
                "",
                f"- 风险等级：{risk_label}",
                f"- 合并建议：{merge_label}",
                (f"- 结论：{report.overall_assessment.conclusion}"),
                "",
                "## 审查发现",
                "",
            ]
        )

    if not report.findings:
        lines.append(
            "- No explicit findings were generated."
            if is_english
            else "- 当前未生成明确的审查发现。"
        )
    else:
        for finding in report.findings:
            evidence_text = format_evidence_id_list(finding.evidence_ids)

            lines.extend(
                [
                    (
                        f"### {finding.finding_id} · "
                        f"[{finding.severity.upper()}] "
                        f"{finding.title}"
                    ),
                    "",
                ]
            )

            if is_english:
                lines.extend(
                    [
                        f"- Category: {finding.category}",
                        f"- Description: {finding.description}",
                        (f"- Recommendation: {finding.recommendation}"),
                        f"- Evidence: {evidence_text}",
                        "",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"- 类别：{finding.category}",
                        f"- 说明：{finding.description}",
                        f"- 建议：{finding.recommendation}",
                        f"- 证据：{evidence_text}",
                        "",
                    ]
                )

    lines.extend(
        [
            "## Test Plan" if is_english else "## 测试计划",
            "",
        ]
    )

    if not report.test_plan:
        lines.append(
            "- No test plan was generated."
            if is_english
            else "- 当前未生成明确的测试计划。"
        )
    else:
        for index, test_item in enumerate(
            report.test_plan,
            start=1,
        ):
            test_file = normalize_markdown_inline(test_item.test_file)
            evidence_text = format_evidence_id_list(test_item.evidence_ids)

            lines.append(f"{index}. `{test_file}`")

            if is_english:
                lines.extend(
                    [
                        f"   - Priority: {test_item.priority}",
                        f"   - Reason: {test_item.reason}",
                        f"   - Evidence: {evidence_text}",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"   - 优先级：{test_item.priority}",
                        f"   - 原因：{test_item.reason}",
                        f"   - 证据：{evidence_text}",
                    ]
                )

    lines.extend(
        [
            "",
            ("## Manual Review Items" if is_english else "## 人工复核事项"),
            "",
        ]
    )

    if not report.manual_review_items:
        lines.append(
            "- No manual review items were generated."
            if is_english
            else "- 当前未生成人工复核事项。"
        )
    else:
        for item in report.manual_review_items:
            evidence_text = format_evidence_id_list(item.evidence_ids)

            lines.append(f"- [ ] **{item.description}**")

            if is_english:
                lines.extend(
                    [
                        f"  - Priority: {item.priority}",
                        f"  - Evidence: {evidence_text}",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"  - 优先级：{item.priority}",
                        f"  - 证据：{evidence_text}",
                    ]
                )

    lines.extend(
        [
            "",
            ("## Uncertainties and Limitations" if is_english else "## 不确定性与限制"),
            "",
        ]
    )

    if not report.uncertainties:
        lines.append(
            "- No explicit uncertainties were reported."
            if is_english
            else "- 当前未报告额外不确定性。"
        )
    else:
        for uncertainty in report.uncertainties:
            lines.append(f"- {uncertainty}")

    referenced_ids = collect_review_report_evidence_ids(report)

    lines.extend(
        [
            "",
            ("## Evidence References" if is_english else "## Evidence 引用"),
            "",
        ]
    )

    if not referenced_ids:
        lines.append(
            "- No evidence references."
            if is_english
            else "- 当前报告没有 Evidence 引用。"
        )
    else:
        for evidence_id in referenced_ids:
            evidence_item = evidence_catalog.get(evidence_id)

            if evidence_item is None:
                # 正常流程中会在渲染前完成 Evidence ID 校验。
                # 这里保留防御性处理，避免单独调用渲染函数时 KeyError。
                lines.append(f"- `{evidence_id}` · unknown evidence")
                continue

            evidence_summary = summarize_review_evidence_item(evidence_item)

            lines.append(
                f"- `{evidence_id}` · "
                f"{evidence_item.evidence_type} · "
                f"{evidence_summary}"
            )

    return "\n".join(lines).strip() + "\n"


def generate_review_report_from_evidence(
    *,
    evidence: CodeSkillReviewEvidenceResponse,
    language: ReviewLanguage,
    llm_call: ReviewLLMCall = call_llm,
    model_name: str | None = None,
) -> CodeSkillGenerateReviewReportResponse:
    prompt_package = build_review_prompt_package(
        evidence=evidence,
        language=language,
    )

    combined_prompt = build_combined_review_prompt(
        system_prompt=(prompt_package.system_prompt),
        user_prompt=(prompt_package.user_prompt),
    )

    resolved_model_name = resolve_review_model_name(model_name)

    started_at = perf_counter()
    raw_output = ""

    try:
        raw_output = llm_call(combined_prompt)

        report = parse_and_validate_review_report(
            raw_text=raw_output,
            evidence_catalog=(prompt_package.evidence_catalog),
        )

        review_markdown = render_review_report_markdown(
            report=report,
            evidence_catalog=(prompt_package.evidence_catalog),
            language=language,
        )

        duration_ms = int((perf_counter() - started_at) * 1000)

        generation_trace = build_report_generation_trace(
            model_name=resolved_model_name,
            duration_ms=duration_ms,
            prompt_version=(prompt_package.prompt_version),
            evidence_item_count=(prompt_package.evidence_item_count),
            output_characters=len(raw_output),
        )

        return CodeSkillGenerateReviewReportResponse(
            generation_status="completed",
            review_report=report,
            review_markdown=(review_markdown),
            evidence=evidence,
            generation_trace=(generation_trace),
            generation_error=None,
        )

    except (
        LLMError,
        CodeReviewReportError,
    ) as error:
        duration_ms = int((perf_counter() - started_at) * 1000)

        generation_trace = build_report_generation_trace(
            model_name=resolved_model_name,
            duration_ms=duration_ms,
            prompt_version=(prompt_package.prompt_version),
            evidence_item_count=(prompt_package.evidence_item_count),
            output_characters=len(raw_output),
        )

        return CodeSkillGenerateReviewReportResponse(
            generation_status=("evidence_only"),
            review_report=None,
            review_markdown=None,
            evidence=evidence,
            generation_trace=(generation_trace),
            generation_error=(format_review_generation_error(error)),
        )
