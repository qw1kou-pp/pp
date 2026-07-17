import pytest
from pydantic import ValidationError

from app.models import (
    CodeSkillGenerateReviewReportRequest,
    CodeSkillGeneratedFindingPublic,
    CodeSkillGeneratedManualReviewItemPublic,
    CodeSkillGeneratedOverallAssessmentPublic,
    CodeSkillGeneratedReviewReportPublic,
    CodeSkillGeneratedTestPlanItemPublic,
)


def test_generate_review_report_request_uses_expected_defaults() -> None:
    request = CodeSkillGenerateReviewReportRequest(
        diff_text=(
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
        )
    )

    assert request.max_references_per_symbol == 20
    assert request.max_test_files == 20
    assert request.min_test_confidence == 0.2
    assert request.include_file_level_fallback is True
    assert request.include_definition_chunk is False
    assert request.language == "zh-CN"


def test_generate_review_report_request_rejects_empty_diff() -> None:
    with pytest.raises(ValidationError):
        CodeSkillGenerateReviewReportRequest(
            diff_text="",
        )


def test_generate_review_report_request_rejects_unsupported_language() -> None:
    with pytest.raises(ValidationError):
        CodeSkillGenerateReviewReportRequest(
            diff_text="diff --git a/a.py b/a.py",
            language="fr-FR",  # type: ignore[arg-type]
        )


def test_generated_finding_requires_evidence_ids() -> None:
    with pytest.raises(ValidationError):
        CodeSkillGeneratedFindingPublic(
            finding_id="F-001",
            severity="high",
            category="testing",
            title="缺少测试证据",
            description="没有找到与变更直接关联的测试文件。",
            recommendation="补充相关单元测试。",
            evidence_ids=[],
        )


def test_generated_review_report_accepts_valid_structure() -> None:
    report = CodeSkillGeneratedReviewReportPublic(
        executive_summary="本次修改涉及文件上传逻辑，需要重点复核异常处理。",
        overall_assessment=CodeSkillGeneratedOverallAssessmentPublic(
            risk_level="medium",
            conclusion="存在需要人工确认的文件上传与测试风险。",
            merge_recommendation="needs_review",
        ),
        findings=[
            CodeSkillGeneratedFindingPublic(
                finding_id="F-001",
                severity="medium",
                category="testing",
                title="部分变更缺少测试关联证据",
                description="当前静态分析没有找到直接关联测试。",
                recommendation="补充并运行文件上传相关测试。",
                evidence_ids=["RS-001", "CF-001"],
            )
        ],
        test_plan=[
            CodeSkillGeneratedTestPlanItemPublic(
                test_file="backend/tests/test_documents.py",
                reason="该文件与变更路径和符号匹配。",
                priority="high",
                evidence_ids=["RT-001"],
            )
        ],
        manual_review_items=[
            CodeSkillGeneratedManualReviewItemPublic(
                description="检查异常路径下临时文件是否清理。",
                priority="high",
                evidence_ids=["RC-001"],
            )
        ],
        uncertainties=[
            "动态调用关系无法通过当前静态文本匹配完全确认。",
        ],
    )

    assert report.overall_assessment.risk_level == "medium"
    assert report.overall_assessment.merge_recommendation == "needs_review"
    assert len(report.findings) == 1
    assert report.findings[0].evidence_ids == ["RS-001", "CF-001"]
    assert len(report.test_plan) == 1
    assert len(report.manual_review_items) == 1