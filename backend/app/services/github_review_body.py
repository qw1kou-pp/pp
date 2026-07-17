from __future__ import annotations

import hashlib
from collections.abc import (
    Mapping,
    Sequence,
)
from dataclasses import dataclass
from typing import Any


SUMMARY_FINDING_LIMIT = 3
SUMMARY_TEST_LIMIT = 5


class GitHubReviewBodyError(
    ValueError,
):
    """无法根据 RepoGuard 报告构建正文。"""


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubReviewBodyContext:
    review_run_id: str
    review_title: str

    repository: str
    pull_number: int
    head_sha: str

    language: str

    risk_level: str | None

    merge_recommendation: (
        str | None
    )

    review_report: Mapping[
        str,
        Any,
    ]


ZH_LABELS = {
    "summary":
        "执行摘要",

    "key_findings":
        "主要发现",

    "recommended_tests":
        "推荐测试",

    "details_summary":
        "查看完整 RepoGuard Review",

    "overall_assessment":
        "总体评估",

    "all_findings":
        "完整审查发现",

    "test_plan":
        "完整测试计划",

    "manual_review":
        "人工复核事项",

    "uncertainties":
        "不确定性与限制",

    "audit":
        "审计信息",

    "risk":
        "风险等级",

    "merge_recommendation":
        "合并建议",

    "reviewed_commit":
        "审查提交",

    "target":
        "目标",

    "conclusion":
        "结论",

    "category":
        "类别",

    "severity":
        "严重程度",

    "recommendation":
        "建议",

    "evidence":
        "Evidence",

    "priority":
        "优先级",

    "reason":
        "原因",

    "review_run_id":
        "RepoGuard Review Run ID",

    "no_findings":
        "没有生成明确的审查发现。",

    "no_tests":
        "没有生成明确的测试计划。",

    "no_manual_items":
        "没有额外的人工复核事项。",

    "no_uncertainties":
        "没有额外的不确定性说明。",
}


EN_LABELS = {
    "summary":
        "Executive Summary",

    "key_findings":
        "Key Findings",

    "recommended_tests":
        "Recommended Tests",

    "details_summary":
        "View full RepoGuard review",

    "overall_assessment":
        "Overall Assessment",

    "all_findings":
        "All Findings",

    "test_plan":
        "Full Test Plan",

    "manual_review":
        "Manual Review Items",

    "uncertainties":
        "Uncertainties and Limitations",

    "audit":
        "Audit Information",

    "risk":
        "Risk Level",

    "merge_recommendation":
        "Merge Recommendation",

    "reviewed_commit":
        "Reviewed Commit",

    "target":
        "Target",

    "conclusion":
        "Conclusion",

    "category":
        "Category",

    "severity":
        "Severity",

    "recommendation":
        "Recommendation",

    "evidence":
        "Evidence",

    "priority":
        "Priority",

    "reason":
        "Reason",

    "review_run_id":
        "RepoGuard Review Run ID",

    "no_findings":
        "No explicit findings were generated.",

    "no_tests":
        "No explicit test plan was generated.",

    "no_manual_items":
        "No additional manual review items.",

    "no_uncertainties":
        "No additional uncertainty notes.",
}


ZH_RISK_LABELS = {
    "low": "低风险",
    "medium": "中风险",
    "high": "高风险",
}


EN_RISK_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}


ZH_MERGE_LABELS = {
    "approve":
        "可以合并",

    "needs_review":
        "需要进一步审查",

    "request_changes":
        "建议修改后再合并",
}


EN_MERGE_LABELS = {
    "approve":
        "Approve",

    "needs_review":
        "Needs further review",

    "request_changes":
        "Request changes",
}


def _labels(
    language: str,
) -> Mapping[str, str]:
    if language == "en-US":
        return EN_LABELS

    return ZH_LABELS


def _normalize_text(
    value: object,
) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


def _require_text(
    value: object,
    *,
    field_name: str,
) -> str:
    normalized_value = (
        _normalize_text(
            value,
        )
    )

    if not normalized_value:
        raise GitHubReviewBodyError(
            "Review report is missing "
            f"{field_name}",
        )

    return normalized_value


def _read_mapping(
    value: object,
) -> Mapping[str, Any]:
    if isinstance(
        value,
        Mapping,
    ):
        return value

    return {}


def _read_object_list(
    value: object,
) -> list[Mapping[str, Any]]:
    if (
        not isinstance(
            value,
            Sequence,
        )
        or isinstance(
            value,
            (
                str,
                bytes,
                bytearray,
            ),
        )
    ):
        return []

    items: list[
        Mapping[str, Any]
    ] = []

    for item in value:
        if isinstance(
            item,
            Mapping,
        ):
            items.append(
                item,
            )

    return items


def _read_text_list(
    value: object,
) -> list[str]:
    if (
        not isinstance(
            value,
            Sequence,
        )
        or isinstance(
            value,
            (
                str,
                bytes,
                bytearray,
            ),
        )
    ):
        return []

    values: list[str] = []

    for item in value:
        normalized_item = (
            _normalize_text(
                item,
            )
        )

        if normalized_item:
            values.append(
                normalized_item,
            )

    return values


def _table_cell(
    value: object,
) -> str:
    normalized_value = (
        _normalize_text(
            value,
        )
    )

    if not normalized_value:
        return "-"

    return (
        normalized_value
        .replace("|", r"\|")
        .replace("\n", "<br>")
    )


def _inline_code(
    value: object,
) -> str:
    normalized_value = (
        _normalize_text(
            value,
        )
        .replace("`", "'")
    )

    return (
        f"`{normalized_value}`"
        if normalized_value
        else "`-`"
    )


def _risk_label(
    value: object,
    *,
    language: str,
) -> str:
    normalized_value = (
        _normalize_text(
            value,
        )
        .lower()
    )

    label_map = (
        EN_RISK_LABELS
        if language == "en-US"
        else ZH_RISK_LABELS
    )

    return label_map.get(
        normalized_value,
        normalized_value or "-",
    )


def _merge_label(
    value: object,
    *,
    language: str,
) -> str:
    normalized_value = (
        _normalize_text(
            value,
        )
        .lower()
    )

    label_map = (
        EN_MERGE_LABELS
        if language == "en-US"
        else ZH_MERGE_LABELS
    )

    return label_map.get(
        normalized_value,
        normalized_value or "-",
    )


def _severity_badge(
    value: object,
) -> str:
    normalized_value = (
        _normalize_text(
            value,
        )
        .upper()
    )

    return (
        f"[{normalized_value}]"
        if normalized_value
        else "[UNKNOWN]"
    )


def _build_summary_findings(
    *,
    findings: list[
        Mapping[str, Any]
    ],
    labels: Mapping[str, str],
) -> list[str]:
    lines = [
        f"### {labels['key_findings']}",
        "",
    ]

    if not findings:
        lines.append(
            labels["no_findings"],
        )
        return lines

    for index, finding in enumerate(
        findings[
            :SUMMARY_FINDING_LIMIT
        ],
        start=1,
    ):
        title = _require_text(
            finding.get(
                "title",
            ),
            field_name=(
                "findings[].title"
            ),
        )

        description = _normalize_text(
            finding.get(
                "description",
            ),
        )

        severity = _severity_badge(
            finding.get(
                "severity",
            ),
        )

        finding_id = _normalize_text(
            finding.get(
                "finding_id",
            ),
        )

        identifier = (
            f"{finding_id} · "
            if finding_id
            else ""
        )

        lines.append(
            f"{index}. **{severity} "
            f"{identifier}{title}**",
        )

        if description:
            lines.append(
                f"   - {description}",
            )

    return lines


def _build_summary_tests(
    *,
    test_plan: list[
        Mapping[str, Any]
    ],
    labels: Mapping[str, str],
) -> list[str]:
    lines = [
        "",
        f"### {labels['recommended_tests']}",
        "",
    ]

    if not test_plan:
        lines.append(
            labels["no_tests"],
        )
        return lines

    for test_item in (
        test_plan[
            :SUMMARY_TEST_LIMIT
        ]
    ):
        test_file = _require_text(
            test_item.get(
                "test_file",
            ),
            field_name=(
                "test_plan[].test_file"
            ),
        )

        priority = _normalize_text(
            test_item.get(
                "priority",
            ),
        )

        reason = _normalize_text(
            test_item.get(
                "reason",
            ),
        )

        line = (
            f"- {_inline_code(test_file)}"
        )

        if priority:
            line += (
                f" — {labels['priority']}: "
                f"**{priority.upper()}**"
            )

        lines.append(
            line,
        )

        if reason:
            lines.append(
                f"  - {reason}",
            )

    return lines


def _build_full_findings(
    *,
    findings: list[
        Mapping[str, Any]
    ],
    labels: Mapping[str, str],
) -> list[str]:
    lines = [
        f"#### {labels['all_findings']}",
        "",
    ]

    if not findings:
        lines.append(
            labels["no_findings"],
        )
        return lines

    for index, finding in enumerate(
        findings,
        start=1,
    ):
        title = _require_text(
            finding.get(
                "title",
            ),
            field_name=(
                "findings[].title"
            ),
        )

        finding_id = _normalize_text(
            finding.get(
                "finding_id",
            ),
        )

        heading_prefix = (
            f"{finding_id} · "
            if finding_id
            else ""
        )

        lines.extend(
            [
                (
                    f"##### {index}. "
                    f"{heading_prefix}"
                    f"{title}"
                ),
                "",
                (
                    f"- **{labels['severity']}：** "
                    f"{_normalize_text(finding.get('severity')) or '-'}"
                ),
                (
                    f"- **{labels['category']}：** "
                    f"{_normalize_text(finding.get('category')) or '-'}"
                ),
            ]
        )

        description = _normalize_text(
            finding.get(
                "description",
            ),
        )

        if description:
            lines.extend(
                [
                    "",
                    description,
                ]
            )

        recommendation = (
            _normalize_text(
                finding.get(
                    "recommendation",
                ),
            )
        )

        if recommendation:
            lines.extend(
                [
                    "",
                    (
                        f"**{labels['recommendation']}：** "
                        f"{recommendation}"
                    ),
                ]
            )

        evidence_ids = (
            _read_text_list(
                finding.get(
                    "evidence_ids",
                ),
            )
        )

        if evidence_ids:
            evidence_text = "、".join(
                _inline_code(
                    evidence_id,
                )
                for evidence_id
                in evidence_ids
            )

            lines.extend(
                [
                    "",
                    (
                        f"**{labels['evidence']}：** "
                        f"{evidence_text}"
                    ),
                ]
            )

        lines.append("")

    return lines


def _build_full_test_plan(
    *,
    test_plan: list[
        Mapping[str, Any]
    ],
    labels: Mapping[str, str],
) -> list[str]:
    lines = [
        f"#### {labels['test_plan']}",
        "",
    ]

    if not test_plan:
        lines.append(
            labels["no_tests"],
        )
        return lines

    for index, test_item in enumerate(
        test_plan,
        start=1,
    ):
        test_file = _require_text(
            test_item.get(
                "test_file",
            ),
            field_name=(
                "test_plan[].test_file"
            ),
        )

        lines.append(
            f"{index}. "
            f"**{_inline_code(test_file)}**",
        )

        priority = _normalize_text(
            test_item.get(
                "priority",
            ),
        )

        reason = _normalize_text(
            test_item.get(
                "reason",
            ),
        )

        evidence_ids = (
            _read_text_list(
                test_item.get(
                    "evidence_ids",
                ),
            )
        )

        if priority:
            lines.append(
                f"   - {labels['priority']}："
                f"{priority}",
            )

        if reason:
            lines.append(
                f"   - {labels['reason']}："
                f"{reason}",
            )

        if evidence_ids:
            evidence_text = "、".join(
                _inline_code(
                    evidence_id,
                )
                for evidence_id
                in evidence_ids
            )

            lines.append(
                f"   - {labels['evidence']}："
                f"{evidence_text}",
            )

    return lines


def _build_manual_items(
    *,
    manual_items: list[
        Mapping[str, Any]
    ],
    labels: Mapping[str, str],
) -> list[str]:
    lines = [
        "",
        f"#### {labels['manual_review']}",
        "",
    ]

    if not manual_items:
        lines.append(
            labels["no_manual_items"],
        )
        return lines

    for item in manual_items:
        description = _require_text(
            item.get(
                "description",
            ),
            field_name=(
                "manual_review_items[]"
                ".description"
            ),
        )

        priority = _normalize_text(
            item.get(
                "priority",
            ),
        )

        line = f"- [ ] {description}"

        if priority:
            line += (
                f"（{labels['priority']}："
                f"{priority}）"
            )

        lines.append(
            line,
        )

    return lines


def _build_uncertainties(
    *,
    uncertainties: list[str],
    labels: Mapping[str, str],
) -> list[str]:
    lines = [
        "",
        f"#### {labels['uncertainties']}",
        "",
    ]

    if not uncertainties:
        lines.append(
            labels["no_uncertainties"],
        )
        return lines

    lines.extend(
        f"- {uncertainty}"
        for uncertainty
        in uncertainties
    )

    return lines


def build_github_review_body(
    context: GitHubReviewBodyContext,
) -> str:
    labels = _labels(
        context.language,
    )

    if context.pull_number <= 0:
        raise GitHubReviewBodyError(
            "Pull request number "
            "must be positive",
        )

    repository = _require_text(
        context.repository,
        field_name="repository",
    )

    head_sha = _require_text(
        context.head_sha,
        field_name="head_sha",
    )

    review_run_id = _require_text(
        context.review_run_id,
        field_name="review_run_id",
    )

    report = _read_mapping(
        context.review_report,
    )

    executive_summary = (
        _require_text(
            report.get(
                "executive_summary",
            ),
            field_name=(
                "executive_summary"
            ),
        )
    )

    overall_assessment = (
        _read_mapping(
            report.get(
                "overall_assessment",
            )
        )
    )

    conclusion = _normalize_text(
        overall_assessment.get(
            "conclusion",
        ),
    )

    report_risk_level = (
        overall_assessment.get(
            "risk_level",
        )
        or context.risk_level
    )

    report_merge_recommendation = (
        overall_assessment.get(
            "merge_recommendation",
        )
        or context.merge_recommendation
    )

    findings = _read_object_list(
        report.get(
            "findings",
        )
    )

    test_plan = _read_object_list(
        report.get(
            "test_plan",
        )
    )

    manual_items = _read_object_list(
        report.get(
            "manual_review_items",
        )
    )

    uncertainties = _read_text_list(
        report.get(
            "uncertainties",
        )
    )

    lines: list[str] = [
        "## RepoGuard Review",
        "",
    ]

    review_title = _normalize_text(
        context.review_title,
    )

    if review_title:
        lines.extend(
            [
                f"**{review_title}**",
                "",
            ]
        )

    lines.extend(
        [
            "| 项目 | 结果 |"
            if context.language != "en-US"
            else "| Item | Result |",

            "|---|---|",

            (
                f"| {labels['risk']} | "
                f"{_table_cell(_risk_label(report_risk_level, language=context.language))} |"
            ),

            (
                f"| {labels['merge_recommendation']} | "
                f"{_table_cell(_merge_label(report_merge_recommendation, language=context.language))} |"
            ),

            (
                f"| {labels['target']} | "
                f"{_table_cell(repository)} PR #{context.pull_number} |"
            ),

            (
                f"| {labels['reviewed_commit']} | "
                f"{_inline_code(head_sha[:12])} |"
            ),

            "",
            f"### {labels['summary']}",
            "",
            executive_summary,
            "",
        ]
    )

    lines.extend(
        _build_summary_findings(
            findings=findings,
            labels=labels,
        )
    )

    lines.extend(
        _build_summary_tests(
            test_plan=test_plan,
            labels=labels,
        )
    )

    lines.extend(
        [
            "",
            "<details>",
            (
                f"<summary>"
                f"{labels['details_summary']}"
                f"</summary>"
            ),
            "",
            (
                f"#### "
                f"{labels['overall_assessment']}"
            ),
            "",
        ]
    )

    if conclusion:
        lines.extend(
            [
                (
                    f"**{labels['conclusion']}：** "
                    f"{conclusion}"
                ),
                "",
            ]
        )

    lines.extend(
        _build_full_findings(
            findings=findings,
            labels=labels,
        )
    )

    lines.extend(
        [
            "",
            *_build_full_test_plan(
                test_plan=test_plan,
                labels=labels,
            ),
        ]
    )

    lines.extend(
        _build_manual_items(
            manual_items=manual_items,
            labels=labels,
        )
    )

    lines.extend(
        _build_uncertainties(
            uncertainties=uncertainties,
            labels=labels,
        )
    )

    lines.extend(
        [
            "",
            f"#### {labels['audit']}",
            "",
            (
                f"- **{labels['review_run_id']}：** "
                f"{_inline_code(review_run_id)}"
            ),
            (
                f"- **{labels['target']}：** "
                f"{_inline_code(repository)} "
                f"PR #{context.pull_number}"
            ),
            (
                f"- **{labels['reviewed_commit']}：** "
                f"{_inline_code(head_sha)}"
            ),
            "",
            (
                "_Generated from RepoGuard "
                "evidence and stored review data._"
            ),
            "",
            "</details>",
        ]
    )

    return "\n".join(
        lines,
    ).strip()


def compute_github_review_body_hash(
    body_markdown: str,
) -> str:
    normalized_body = str(
        body_markdown or "",
    )

    if not normalized_body.strip():
        raise GitHubReviewBodyError(
            "GitHub review body "
            "cannot be empty",
        )

    return hashlib.sha256(
        normalized_body.encode(
            "utf-8",
        )
    ).hexdigest()