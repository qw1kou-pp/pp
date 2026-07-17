import uuid

from app.models import (
    CodeSkillChangeSummaryPublic,
    CodeSkillChangedFilePublic,
    CodeSkillChangedSymbolInput,
    CodeSkillChangedSymbolPublic,
    CodeSkillImpactedFilePublic,
    CodeSkillImpactReferencePublic,
    CodeSkillRecommendedTestPublic,
    CodeSkillReviewChecklistItemPublic,
    CodeSkillReviewEvidenceResponse,
    CodeSkillRiskSignalPublic,
    CodeSkillSymbolImpactPublic,
)
from app.services.code_review_report import (
    REVIEW_PROMPT_VERSION,
    build_review_evidence_catalog,
    build_review_llm_context,
    build_review_prompt_package,
)


DOCUMENT_ID = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)

CHUNK_ID = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)


def build_test_review_evidence(
    *,
    reference_preview: str = "await upload_repository(file)",
) -> CodeSkillReviewEvidenceResponse:
    changed_symbol_input = CodeSkillChangedSymbolInput(
        document_id=DOCUMENT_ID,
        chunk_id=CHUNK_ID,
        file_path="backend/app/api/routes/documents.py",
        symbol_name="upload_code_repository_zip",
        symbol_type="function",
        line_range="100-180",
    )

    impact_reference = CodeSkillImpactReferencePublic(
        document_id=DOCUMENT_ID,
        chunk_id=CHUNK_ID,
        chunk_index=3,
        document_filename="test_documents.py",
        file_path="backend/tests/api/routes/test_documents.py",
        changed_symbol_name="upload_code_repository_zip",
        changed_symbol_type="function",
        containing_symbol_name="test_upload_repository",
        containing_symbol_type="function",
        containing_line_range="40-75",
        occurrence_count=1,
        preview=reference_preview,
        confidence=0.92,
        reason="测试代码中直接调用了变更函数。",
    )

    impacted_file = CodeSkillImpactedFilePublic(
        file_path="backend/tests/api/routes/test_documents.py",
        document_filename="test_documents.py",
        reference_count=1,
        impacted_symbol_names=[
            "upload_code_repository_zip",
        ],
        confidence=0.92,
        reason="该文件包含对变更函数的直接引用。",
    )

    recommended_test = CodeSkillRecommendedTestPublic(
        document_id=DOCUMENT_ID,
        document_filename="test_documents.py",
        test_file_path=(
            "backend/tests/api/routes/test_documents.py"
        ),
        confidence=0.91,
        path_match_score=0.85,
        symbol_match_count=1,
        related_changed_files=[
            "backend/app/api/routes/documents.py",
        ],
        related_impacted_files=[
            "backend/tests/api/routes/test_documents.py",
        ],
        related_symbols=[
            "upload_code_repository_zip",
        ],
        matched_reasons=[
            "测试文件路径与变更文件匹配。",
            "测试中出现了变更函数名称。",
        ],
        preview="def test_upload_repository(): ...",
    )

    risk_signal = CodeSkillRiskSignalPublic(
        risk_type="important_module_change",
        risk_level="medium",
        title="变更涉及文件上传模块",
        message="需要检查上传限制和异常处理。",
        evidence=[
            "upload",
            "archive",
        ],
        related_files=[
            "backend/app/api/routes/documents.py",
        ],
        related_symbols=[
            "upload_code_repository_zip",
        ],
    )

    checklist_item = CodeSkillReviewChecklistItemPublic(
        item_id="check-upload-size-limit",
        category="file_upload",
        priority="high",
        description="检查 ZIP 和 RAR 大小限制是否一致。",
        reason="本次变更涉及压缩包上传。",
        related_files=[
            "backend/app/api/routes/documents.py",
        ],
        related_symbols=[
            "upload_code_repository_zip",
        ],
    )

    return CodeSkillReviewEvidenceResponse(
        change_summary=CodeSkillChangeSummaryPublic(
            total_changed_files=1,
            total_added_lines=12,
            total_deleted_lines=3,
            total_changed_symbols=1,
            total_unresolved_files=0,
            total_references=1,
            total_impacted_files=1,
            total_test_candidates=2,
            total_recommended_tests=1,
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
            )
        ],
        changed_symbols=[
            CodeSkillChangedSymbolPublic(
                document_id=DOCUMENT_ID,
                chunk_id=CHUNK_ID,
                chunk_index=2,
                document_filename="documents.py",
                file_path=(
                    "backend/app/api/routes/documents.py"
                ),
                symbol_name="upload_code_repository_zip",
                symbol_type="function",
                line_range="100-180",
                symbol_start_line=100,
                symbol_end_line=180,
                changed_hunk_new_start=125,
                changed_hunk_new_end=140,
                overlap_start_line=125,
                overlap_end_line=140,
                overlap_line_count=16,
                confidence=0.95,
                reason="Diff 行号与函数范围发生重叠。",
            )
        ],
        symbol_impacts=[
            CodeSkillSymbolImpactPublic(
                changed_symbol=changed_symbol_input,
                references=[
                    impact_reference,
                ],
                impacted_files=[
                    impacted_file,
                ],
                total_references=1,
                total_impacted_files=1,
            )
        ],
        impacted_files_summary=[
            impacted_file,
        ],
        recommended_tests=[
            recommended_test,
        ],
        test_gap_notes=[
            "仍需人工确认损坏压缩包测试。",
        ],
        uncovered_changed_files=[],
        uncovered_symbols=[],
        risk_signals=[
            risk_signal,
        ],
        review_checklist=[
            checklist_item,
        ],
        limitations=[
            "当前影响分析不是编译器级调用图。",
        ],
    )


def test_build_review_evidence_catalog_assigns_stable_ids() -> None:
    evidence = build_test_review_evidence()

    catalog = build_review_evidence_catalog(
        evidence
    )

    assert list(catalog.keys()) == [
        "CF-001",
        "CS-001",
        "IR-001",
        "IF-001",
        "RT-001",
        "RS-001",
        "RC-001",
    ]

    assert catalog["CF-001"].evidence_type == (
        "changed_file"
    )

    assert catalog["CS-001"].data["symbol_name"] == (
        "upload_code_repository_zip"
    )

    assert catalog["IR-001"].data["file_path"] == (
        "backend/tests/api/routes/test_documents.py"
    )


def test_build_review_evidence_catalog_ids_are_unique() -> None:
    evidence = build_test_review_evidence()

    catalog = build_review_evidence_catalog(
        evidence
    )

    evidence_ids = list(catalog.keys())

    assert len(evidence_ids) == len(
        set(evidence_ids)
    )


def test_build_review_llm_context_truncates_long_preview() -> None:
    long_preview = "x" * 2000

    evidence = build_test_review_evidence(
        reference_preview=long_preview,
    )

    context = build_review_llm_context(
        evidence
    )

    impact_reference = next(
        item
        for item in context["evidence_items"]
        if item["evidence_id"] == "IR-001"
    )

    assert len(impact_reference["preview"]) <= 803
    assert impact_reference["preview"].endswith("...")


def test_build_review_prompt_package_contains_constraints() -> None:
    evidence = build_test_review_evidence()

    prompt_package = build_review_prompt_package(
        evidence=evidence,
        language="zh-CN",
    )

    assert (
        prompt_package.prompt_version
        == REVIEW_PROMPT_VERSION
    )

    assert "不得编造" in (
        prompt_package.system_prompt
    )

    assert "每一条 finding" in (
        prompt_package.system_prompt.lower()
    )

    assert "evidence_ids" in (
        prompt_package.system_prompt
    )

    assert "RS-001" in prompt_package.user_prompt
    assert "CF-001" in prompt_package.user_prompt

    assert prompt_package.evidence_item_count == 7


def test_build_review_prompt_package_supports_english() -> None:
    evidence = build_test_review_evidence()

    prompt_package = build_review_prompt_package(
        evidence=evidence,
        language="en-US",
    )

    assert "Do not invent" in (
        prompt_package.system_prompt
    )

    assert "Return JSON only" in (
        prompt_package.system_prompt
    )