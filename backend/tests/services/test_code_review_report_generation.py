import json
import uuid
from collections.abc import Callable

from app.models import (
    CodeSkillChangeSummaryPublic,
    CodeSkillChangedFilePublic,
    CodeSkillGenerateReviewReportResponse,
    CodeSkillReviewChecklistItemPublic,
    CodeSkillReviewEvidenceResponse,
    CodeSkillRiskSignalPublic,
)
from app.services.code_review_report import (
    build_combined_review_prompt,
    generate_review_report_from_evidence,
)
from app.services.llm import LLMError


DOCUMENT_ID = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)


def build_minimal_review_evidence(
) -> CodeSkillReviewEvidenceResponse:
    return CodeSkillReviewEvidenceResponse(
        change_summary=CodeSkillChangeSummaryPublic(
            total_changed_files=1,
            total_added_lines=12,
            total_deleted_lines=3,
            total_changed_symbols=0,
            total_unresolved_files=0,
            total_references=0,
            total_impacted_files=0,
            total_test_candidates=0,
            total_recommended_tests=0,
            total_risk_signals=1,
            risk_level="medium",
        ),
        changed_files=[
            CodeSkillChangedFilePublic(
                old_path=(
                    "backend/app/api/routes/documents.py"
                ),
                new_path=(
                    "backend/app/api/routes/documents.py"
                ),
                file_path=(
                    "backend/app/api/routes/documents.py"
                ),
                change_type="modified",
                added_lines=12,
                deleted_lines=3,
                hunks=[],
            )
        ],
        changed_symbols=[],
        unresolved_files=[],
        symbol_impacts=[],
        impacted_files_summary=[],
        recommended_tests=[],
        test_gap_notes=[
            "没有找到明确相关的自动化测试文件。",
        ],
        uncovered_changed_files=[
            "backend/app/api/routes/documents.py",
        ],
        uncovered_symbols=[],
        risk_signals=[
            CodeSkillRiskSignalPublic(
                risk_type="missing_test_evidence",
                risk_level="medium",
                title="当前缺少明确测试证据",
                message=(
                    "没有找到与本次变更直接关联的"
                    "自动化测试文件。"
                ),
                evidence=[
                    "recommended_tests=0",
                ],
                related_files=[
                    "backend/app/api/routes/documents.py",
                ],
                related_symbols=[],
            )
        ],
        review_checklist=[
            CodeSkillReviewChecklistItemPublic(
                item_id="add-missing-tests",
                category="testing",
                priority="high",
                description=(
                    "人工确认测试范围并补充相关测试。"
                ),
                reason=(
                    "当前没有找到明确相关的测试文件。"
                ),
                related_files=[
                    "backend/app/api/routes/documents.py",
                ],
                related_symbols=[],
            )
        ],
        evidence_trace=[],
        limitations=[
            "测试推荐不是实际代码覆盖率证明。",
        ],
    )


def build_valid_llm_response_text() -> str:
    return json.dumps(
        {
            "executive_summary": (
                "本次修改涉及文件上传相关代码，"
                "当前缺少明确测试证据。"
            ),
            "overall_assessment": {
                "risk_level": "medium",
                "conclusion": (
                    "建议在合并前人工确认测试范围。"
                ),
                "merge_recommendation": "needs_review",
            },
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": "medium",
                    "category": "testing",
                    "title": "当前缺少明确测试证据",
                    "description": (
                        "RepoGuard 未找到与变更文件"
                        "直接关联的自动化测试。"
                    ),
                    "recommendation": (
                        "补充并运行文件上传相关测试。"
                    ),
                    "evidence_ids": [
                        "RS-001",
                        "CF-001",
                    ],
                }
            ],
            "test_plan": [],
            "manual_review_items": [
                {
                    "description": (
                        "人工确认测试范围并补充相关测试。"
                    ),
                    "priority": "high",
                    "evidence_ids": [
                        "RC-001",
                    ],
                }
            ],
            "uncertainties": [
                "当前测试推荐不等同于真实覆盖率。",
            ],
        },
        ensure_ascii=False,
    )


def test_build_combined_review_prompt_contains_both_prompts() -> None:
    combined_prompt = build_combined_review_prompt(
        system_prompt="SYSTEM RULES",
        user_prompt="USER EVIDENCE",
    )

    assert "SYSTEM RULES" in combined_prompt
    assert "USER EVIDENCE" in combined_prompt
    assert "SYSTEM INSTRUCTIONS" in combined_prompt
    assert "USER EVIDENCE CONTEXT" in combined_prompt


def test_generate_review_report_returns_completed() -> None:
    captured_prompt: dict[str, str] = {}

    def fake_llm_call(prompt: str) -> str:
        captured_prompt["value"] = prompt
        return build_valid_llm_response_text()

    evidence = build_minimal_review_evidence()

    result = generate_review_report_from_evidence(
        evidence=evidence,
        language="zh-CN",
        llm_call=fake_llm_call,
        model_name="mock-review-model",
    )

    assert isinstance(
        result,
        CodeSkillGenerateReviewReportResponse,
    )

    assert result.generation_status == "completed"
    assert result.review_report is not None
    assert result.review_markdown is not None
    assert result.generation_error is None

    assert (
        result.review_report
        .overall_assessment
        .risk_level
        == "medium"
    )

    assert "# RepoGuard 代码审查报告" in (
        result.review_markdown
    )

    assert "`RS-001`" in result.review_markdown
    assert result.evidence is evidence

    assert result.generation_trace.model == (
        "mock-review-model"
    )

    assert (
        result.generation_trace.prompt_version
        == "repoguard-review-v1"
    )

    assert (
        result.generation_trace.evidence_item_count
        == 3
    )

    assert (
        result.generation_trace.output_characters
        > 0
    )

    assert "不得编造" in captured_prompt["value"]
    assert "RS-001" in captured_prompt["value"]


def test_generate_review_report_returns_evidence_only_on_llm_error(
) -> None:
    def failing_llm_call(prompt: str) -> str:
        raise LLMError("mock upstream failure")

    evidence = build_minimal_review_evidence()

    result = generate_review_report_from_evidence(
        evidence=evidence,
        language="zh-CN",
        llm_call=failing_llm_call,
        model_name="mock-review-model",
    )

    assert result.generation_status == (
        "evidence_only"
    )

    assert result.review_report is None
    assert result.review_markdown is None
    assert result.evidence is evidence

    assert result.generation_error is not None
    assert "mock upstream failure" in (
        result.generation_error
    )


def test_generate_review_report_returns_evidence_only_on_invalid_json(
) -> None:
    def invalid_json_llm_call(prompt: str) -> str:
        return "模型没有返回 JSON"

    result = generate_review_report_from_evidence(
        evidence=build_minimal_review_evidence(),
        language="zh-CN",
        llm_call=invalid_json_llm_call,
        model_name="mock-review-model",
    )

    assert result.generation_status == (
        "evidence_only"
    )

    assert result.review_report is None
    assert result.review_markdown is None
    assert result.generation_error is not None
    assert "合法 JSON" in result.generation_error

    assert (
        result.generation_trace.output_characters
        == len("模型没有返回 JSON")
    )


def test_generate_review_report_returns_evidence_only_on_unknown_id(
) -> None:
    invalid_payload = json.loads(
        build_valid_llm_response_text()
    )

    invalid_payload["findings"][0][
        "evidence_ids"
    ] = [
        "RS-999",
    ]

    def unknown_id_llm_call(prompt: str) -> str:
        return json.dumps(
            invalid_payload,
            ensure_ascii=False,
        )

    result = generate_review_report_from_evidence(
        evidence=build_minimal_review_evidence(),
        language="zh-CN",
        llm_call=unknown_id_llm_call,
        model_name="mock-review-model",
    )

    assert result.generation_status == (
        "evidence_only"
    )

    assert result.review_report is None
    assert result.review_markdown is None
    assert result.generation_error is not None
    assert "RS-999" in result.generation_error