import uuid

from app.models import CodeReviewRun


def build_code_review_run() -> CodeReviewRun:
    return CodeReviewRun(
        knowledge_base_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        title="Review backend authentication changes",
        diff_text=(
            "diff --git a/backend/app/api/routes/login.py "
            "b/backend/app/api/routes/login.py\n"
            "--- a/backend/app/api/routes/login.py\n"
            "+++ b/backend/app/api/routes/login.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-old_line\n"
            "+new_line\n"
        ),
        diff_hash="a" * 64,
        generation_status="completed",
        language="zh-CN",
        risk_level="medium",
        merge_recommendation="needs_review",
        changed_file_count=1,
        changed_symbol_count=2,
        finding_count=1,
        recommended_test_count=3,
        request_parameters_json={
            "max_references_per_symbol": 20,
            "max_test_files": 20,
            "min_test_confidence": 0.2,
            "include_file_level_fallback": True,
            "include_definition_chunk": False,
        },
        review_report_json={
            "executive_summary": "Authentication behavior changed.",
        },
        review_markdown="# RepoGuard Review",
        evidence_json={
            "change_summary": {
                "total_changed_files": 1,
            },
        },
        generation_trace_json={
            "model": "deepseek-chat",
            "duration_ms": 1200,
        },
    )


def test_code_review_run_has_generated_uuid() -> None:
    review_run = build_code_review_run()

    assert isinstance(review_run.id, uuid.UUID)


def test_code_review_run_preserves_review_snapshot() -> None:
    review_run = build_code_review_run()

    assert review_run.generation_status == "completed"
    assert review_run.risk_level == "medium"
    assert review_run.merge_recommendation == "needs_review"
    assert review_run.changed_file_count == 1
    assert review_run.finding_count == 1

    assert review_run.review_report_json == {
        "executive_summary": "Authentication behavior changed.",
    }

    assert review_run.evidence_json["change_summary"]["total_changed_files"] == 1


def test_code_review_run_json_defaults_are_not_shared() -> None:
    first_run = build_code_review_run()
    second_run = build_code_review_run()

    first_run.evidence_json["extra"] = "first-run-only"

    assert "extra" not in second_run.evidence_json


def test_code_review_run_uses_expected_table_name() -> None:
    assert CodeReviewRun.__tablename__ == "code_review_run"


def test_code_review_run_contains_required_columns() -> None:
    column_names = set(CodeReviewRun.__table__.columns.keys())

    assert {
        "id",
        "knowledge_base_id",
        "owner_id",
        "title",
        "diff_text",
        "diff_hash",
        "generation_status",
        "language",
        "risk_level",
        "merge_recommendation",
        "changed_file_count",
        "changed_symbol_count",
        "finding_count",
        "recommended_test_count",
        "request_parameters_json",
        "review_report_json",
        "review_markdown",
        "evidence_json",
        "generation_trace_json",
        "generation_error",
        "created_at",
    }.issubset(column_names)
