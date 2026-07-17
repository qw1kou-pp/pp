import json

import pytest

from app.services.code_review_report import (
    ReviewEvidenceItem,
    ReviewEvidenceValidationError,
    ReviewReportParseError,
    collect_review_report_evidence_ids,
    parse_and_validate_review_report,
    parse_review_report_text,
    render_review_report_markdown,
)


def build_test_evidence_catalog() -> dict[
    str,
    ReviewEvidenceItem,
]:
    return {
        "CF-001": ReviewEvidenceItem(
            evidence_id="CF-001",
            evidence_type="changed_file",
            data={
                "file_path": (
                    "backend/app/api/routes/documents.py"
                ),
                "change_type": "modified",
            },
        ),
        "RS-001": ReviewEvidenceItem(
            evidence_id="RS-001",
            evidence_type="risk_signal",
            data={
                "risk_type": "important_module_change",
                "risk_level": "medium",
                "title": "变更涉及文件上传模块",
                "message": "需要检查上传限制和异常处理。",
            },
        ),
        "RT-001": ReviewEvidenceItem(
            evidence_id="RT-001",
            evidence_type="recommended_test",
            data={
                "test_file_path": (
                    "backend/tests/api/routes/"
                    "test_documents.py"
                ),
                "confidence": 0.91,
            },
        ),
        "RC-001": ReviewEvidenceItem(
            evidence_id="RC-001",
            evidence_type="review_checklist",
            data={
                "description": (
                    "检查 ZIP 和 RAR 大小限制是否一致。"
                ),
                "priority": "high",
            },
        ),
    }


def build_valid_review_payload() -> dict:
    return {
        "executive_summary": (
            "本次修改涉及文件上传逻辑，"
            "建议重点检查异常处理和测试覆盖。"
        ),
        "overall_assessment": {
            "risk_level": "medium",
            "conclusion": (
                "当前证据显示存在需要人工确认的"
                "文件上传和测试风险。"
            ),
            "merge_recommendation": "needs_review",
        },
        "findings": [
            {
                "finding_id": "F-001",
                "severity": "medium",
                "category": "testing",
                "title": "需要复核文件上传相关测试",
                "description": (
                    "RepoGuard 找到了相关测试文件，"
                    "但仍需确认异常路径是否覆盖。"
                ),
                "recommendation": (
                    "运行推荐测试并补充损坏压缩包场景。"
                ),
                "evidence_ids": [
                    "RS-001",
                    "CF-001",
                ],
            }
        ],
        "test_plan": [
            {
                "test_file": (
                    "backend/tests/api/routes/"
                    "test_documents.py"
                ),
                "reason": (
                    "该测试文件与变更路径和符号相关。"
                ),
                "priority": "high",
                "evidence_ids": [
                    "RT-001",
                ],
            }
        ],
        "manual_review_items": [
            {
                "description": (
                    "检查 ZIP 和 RAR 上传大小限制"
                    "是否使用同一套约束。"
                ),
                "priority": "high",
                "evidence_ids": [
                    "RC-001",
                ],
            }
        ],
        "uncertainties": [
            "动态调用关系无法通过当前静态分析完全确认。",
        ],
    }


def test_parse_review_report_text_accepts_plain_json() -> None:
    raw_text = json.dumps(
        build_valid_review_payload(),
        ensure_ascii=False,
    )

    report = parse_review_report_text(raw_text)

    assert report.executive_summary.startswith(
        "本次修改涉及"
    )

    assert report.overall_assessment.risk_level == (
        "medium"
    )

    assert report.findings[0].finding_id == "F-001"


def test_parse_review_report_text_accepts_json_code_fence() -> None:
    serialized_payload = json.dumps(
        build_valid_review_payload(),
        ensure_ascii=False,
        indent=2,
    )

    raw_text = (
        "```json\n"
        f"{serialized_payload}\n"
        "```"
    )

    report = parse_review_report_text(raw_text)

    assert len(report.findings) == 1
    assert report.test_plan[0].evidence_ids == [
        "RT-001"
    ]


def test_parse_review_report_text_rejects_invalid_json() -> None:
    with pytest.raises(
        ReviewReportParseError,
        match="合法 JSON",
    ):
        parse_review_report_text(
            "这不是 JSON"
        )


def test_parse_review_report_text_rejects_invalid_structure() -> None:
    invalid_payload = {
        "executive_summary": "摘要",
    }

    with pytest.raises(
        ReviewReportParseError,
        match="结构校验失败",
    ):
        parse_review_report_text(
            json.dumps(
                invalid_payload,
                ensure_ascii=False,
            )
        )


def test_validate_review_report_rejects_unknown_evidence_id() -> None:
    payload = build_valid_review_payload()

    payload["findings"][0]["evidence_ids"] = [
        "RS-999"
    ]

    raw_text = json.dumps(
        payload,
        ensure_ascii=False,
    )

    with pytest.raises(
        ReviewEvidenceValidationError,
        match="RS-999",
    ):
        parse_and_validate_review_report(
            raw_text=raw_text,
            evidence_catalog=(
                build_test_evidence_catalog()
            ),
        )


def test_collect_review_report_evidence_ids_deduplicates_ids() -> None:
    payload = build_valid_review_payload()

    payload["findings"][0]["evidence_ids"] = [
        "RS-001",
        "CF-001",
        "RS-001",
    ]

    report = parse_review_report_text(
        json.dumps(
            payload,
            ensure_ascii=False,
        )
    )

    evidence_ids = (
        collect_review_report_evidence_ids(
            report
        )
    )

    assert evidence_ids == [
        "RS-001",
        "CF-001",
        "RT-001",
        "RC-001",
    ]


def test_render_review_report_markdown_contains_sections() -> None:
    report = parse_and_validate_review_report(
        raw_text=json.dumps(
            build_valid_review_payload(),
            ensure_ascii=False,
        ),
        evidence_catalog=(
            build_test_evidence_catalog()
        ),
    )

    markdown = render_review_report_markdown(
        report=report,
        evidence_catalog=(
            build_test_evidence_catalog()
        ),
        language="zh-CN",
    )

    assert "# RepoGuard 代码审查报告" in markdown
    assert "## 执行摘要" in markdown
    assert "## 总体评估" in markdown
    assert "## 审查发现" in markdown
    assert "## 测试计划" in markdown
    assert "## 人工复核事项" in markdown
    assert "## 不确定性与限制" in markdown
    assert "`RS-001`" in markdown
    assert "`RT-001`" in markdown
    assert "变更涉及文件上传模块" in markdown


def test_render_review_report_markdown_supports_english() -> None:
    report = parse_and_validate_review_report(
        raw_text=json.dumps(
            build_valid_review_payload(),
            ensure_ascii=False,
        ),
        evidence_catalog=(
            build_test_evidence_catalog()
        ),
    )

    markdown = render_review_report_markdown(
        report=report,
        evidence_catalog=(
            build_test_evidence_catalog()
        ),
        language="en-US",
    )

    assert "# RepoGuard Code Review Report" in markdown
    assert "## Executive Summary" in markdown
    assert "## Findings" in markdown
    assert "## Evidence References" in markdown