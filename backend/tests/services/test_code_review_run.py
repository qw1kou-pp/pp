from __future__ import annotations

import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


from app.services.code_review_run import (
    build_code_review_run,
    build_review_title,
    compute_diff_hash,
    create_code_review_run,
    delete_code_review_run,
    normalize_diff_text,
    save_code_review_generation_result,
    serialize_code_review_run_detail,
    serialize_code_review_run_summary,
)


def build_fake_request() -> SimpleNamespace:
    request_payload = {
        "diff_text": (
            "diff --git a/backend/app/main.py b/backend/app/main.py\r\n"
            "--- a/backend/app/main.py\r\n"
            "+++ b/backend/app/main.py\r\n"
            "@@ -1 +1 @@\r\n"
            "-old_line\r\n"
            "+new_line\r\n"
        ),
        "max_references_per_symbol": 20,
        "max_test_files": 20,
        "min_test_confidence": 0.2,
        "include_file_level_fallback": True,
        "include_definition_chunk": False,
        "language": "zh-CN",
    }

    return SimpleNamespace(
        **request_payload,
        model_dump=lambda **_: request_payload.copy(),
    )


def build_fake_response(
    *,
    generation_status: str = "completed",
    with_report: bool = True,
) -> SimpleNamespace:
    change_summary = SimpleNamespace(
        total_changed_files=2,
        total_changed_symbols=3,
        total_recommended_tests=4,
        risk_level="medium",
    )

    changed_files = [
        SimpleNamespace(
            file_path="backend/app/main.py",
            change_type="modified",
        ),
        SimpleNamespace(
            file_path="backend/app/api/routes/items.py",
            change_type="modified",
        ),
    ]

    evidence_payload = {
        "change_summary": {
            "total_changed_files": 2,
            "total_changed_symbols": 3,
            "total_recommended_tests": 4,
            "risk_level": "medium",
        },
        "changed_files": [
            {
                "file_path": "backend/app/main.py",
                "change_type": "modified",
            },
            {
                "file_path": "backend/app/api/routes/items.py",
                "change_type": "modified",
            },
        ],
    }

    evidence = SimpleNamespace(
        change_summary=change_summary,
        changed_files=changed_files,
        model_dump=lambda **_: evidence_payload.copy(),
    )

    generation_trace_payload = {
        "model": "deepseek-chat",
        "duration_ms": 1250,
        "evidence_item_count": 12,
        "output_characters": 2048,
    }

    generation_trace = SimpleNamespace(
        model_dump=lambda **_: generation_trace_payload.copy(),
    )

    review_report = None

    if with_report:
        report_payload = {
            "executive_summary": "本次变更影响两个后端文件。",
            "overall_assessment": {
                "risk_level": "high",
                "merge_recommendation": "request_changes",
                "conclusion": "建议补充测试后再合并。",
            },
            "findings": [
                {
                    "finding_id": "F-001",
                    "title": "认证流程发生变化",
                    "severity": "high",
                    "category": "security",
                    "description": "登录行为发生变化。",
                    "recommendation": "补充鉴权回归测试。",
                    "evidence_ids": ["CF-001"],
                },
            ],
            "test_plan": [],
            "manual_review_items": [],
            "uncertainties": [],
        }

        review_report = SimpleNamespace(
            overall_assessment=SimpleNamespace(
                risk_level="high",
                merge_recommendation="request_changes",
            ),
            findings=[
                SimpleNamespace(
                    finding_id="F-001",
                ),
            ],
            model_dump=lambda **_: report_payload.copy(),
        )

    response = SimpleNamespace(
        generation_status=generation_status,
        review_report=review_report,
        review_markdown=("# RepoGuard Review" if with_report else None),
        evidence=evidence,
        generation_trace=generation_trace,
        generation_error=(None if with_report else "LLM output validation failed"),
    )

    def model_copy(
        *,
        update: dict[str, object],
    ) -> SimpleNamespace:
        response_payload = {
            key: value for key, value in vars(response).items() if key != "model_copy"
        }

        response_payload.update(update)

        return SimpleNamespace(
            **response_payload,
        )

    response.model_copy = model_copy

    return response


def test_normalize_diff_text_unifies_line_endings() -> None:
    source = "line-1\r\nline-2\rline-3\n\n"

    result = normalize_diff_text(source)

    assert result == "line-1\nline-2\nline-3"


def test_normalize_diff_text_preserves_line_whitespace() -> None:
    source = " line-1  \r\n\tline-2\t\r\n"

    result = normalize_diff_text(source)

    assert result == " line-1  \n\tline-2\t"


def test_compute_diff_hash_is_stable_across_line_endings() -> None:
    windows_diff = "line-1\r\nline-2\r\n"
    unix_diff = "line-1\nline-2\n"

    windows_hash = compute_diff_hash(windows_diff)
    unix_hash = compute_diff_hash(unix_diff)

    assert windows_hash == unix_hash
    assert len(windows_hash) == 64


def test_compute_diff_hash_matches_sha256() -> None:
    diff_text = "line-1\nline-2\n"

    expected = hashlib.sha256(
        b"line-1\nline-2",
    ).hexdigest()

    assert compute_diff_hash(diff_text) == expected


def test_compute_diff_hash_rejects_empty_diff() -> None:
    with pytest.raises(
        ValueError,
        match="diff_text must not be empty",
    ):
        compute_diff_hash("\r\n\n")


def test_build_review_title_uses_changed_file_paths() -> None:
    response = build_fake_response()

    title = build_review_title(response.evidence)

    assert title == ("RepoGuard · backend/app/main.py · +1 file")


def test_build_review_title_has_fallback() -> None:
    evidence = SimpleNamespace(
        changed_files=[],
    )

    assert build_review_title(evidence) == "RepoGuard Review"


def test_build_code_review_run_creates_completed_snapshot() -> None:
    knowledge_base_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    review_run = build_code_review_run(
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
        request=build_fake_request(),
        response=build_fake_response(),
    )

    assert review_run.knowledge_base_id == knowledge_base_id
    assert review_run.owner_id == owner_id
    assert review_run.generation_status == "completed"
    assert review_run.language == "zh-CN"

    assert review_run.risk_level == "high"
    assert review_run.merge_recommendation == "request_changes"

    assert review_run.changed_file_count == 2
    assert review_run.changed_symbol_count == 3
    assert review_run.finding_count == 1
    assert review_run.recommended_test_count == 4

    assert review_run.review_report_json is not None
    assert review_run.review_markdown == "# RepoGuard Review"
    assert review_run.generation_error is None

    assert "diff_text" not in (review_run.request_parameters_json)


def test_build_code_review_run_creates_evidence_only_snapshot() -> None:
    review_run = build_code_review_run(
        knowledge_base_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        request=build_fake_request(),
        response=build_fake_response(
            generation_status="evidence_only",
            with_report=False,
        ),
    )

    assert review_run.generation_status == "evidence_only"
    assert review_run.review_report_json is None
    assert review_run.review_markdown is None

    assert review_run.risk_level == "medium"
    assert review_run.merge_recommendation is None
    assert review_run.finding_count == 0

    assert review_run.generation_error == ("LLM output validation failed")


def test_create_code_review_run_commits_and_refreshes() -> None:
    session = MagicMock()

    review_run = create_code_review_run(
        session=session,
        knowledge_base_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        request=build_fake_request(),
        response=build_fake_response(),
    )

    session.add.assert_called_once_with(review_run)
    session.commit.assert_called_once_with()
    session.refresh.assert_called_once_with(review_run)
    session.rollback.assert_not_called()


def test_create_code_review_run_rolls_back_on_failure() -> None:
    session = MagicMock()
    session.commit.side_effect = RuntimeError(
        "database commit failed",
    )

    with pytest.raises(
        RuntimeError,
        match="database commit failed",
    ):
        create_code_review_run(
            session=session,
            knowledge_base_id=uuid.uuid4(),
            owner_id=uuid.uuid4(),
            request=build_fake_request(),
            response=build_fake_response(),
        )

    session.rollback.assert_called_once_with()


def test_serialize_code_review_run_summary() -> None:
    review_run = build_code_review_run(
        knowledge_base_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        request=build_fake_request(),
        response=build_fake_response(),
    )

    summary = serialize_code_review_run_summary(
        review_run,
    )

    assert summary.id == review_run.id
    assert summary.title == review_run.title
    assert summary.generation_status == "completed"
    assert summary.finding_count == 1


def test_serialize_code_review_run_detail() -> None:
    review_run = build_code_review_run(
        knowledge_base_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        request=build_fake_request(),
        response=build_fake_response(),
    )

    detail = serialize_code_review_run_detail(
        review_run,
    )

    assert detail.id == review_run.id
    assert detail.diff_text == review_run.diff_text

    assert detail.review_report is not None
    assert detail.review_report.overall_assessment.risk_level == "high"

    assert detail.evidence.change_summary.total_changed_files == 2

    assert detail.generation_trace.model == "deepseek-chat"


def test_delete_code_review_run_returns_false_when_missing() -> None:
    session = MagicMock()
    query_result = MagicMock()
    query_result.first.return_value = None
    session.exec.return_value = query_result

    deleted = delete_code_review_run(
        session=session,
        knowledge_base_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        review_run_id=uuid.uuid4(),
    )

    assert deleted is False
    session.delete.assert_not_called()
    session.commit.assert_not_called()


def test_save_code_review_generation_result_returns_saved_metadata() -> None:
    session = MagicMock()
    knowledge_base_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    result = save_code_review_generation_result(
        session=session,
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
        request=build_fake_request(),
        response=build_fake_response(),
    )

    assert result.generation_status == "completed"
    assert isinstance(
        result.review_run_id,
        uuid.UUID,
    )
    assert result.saved_at is not None

    session.add.assert_called_once()
    session.commit.assert_called_once_with()
    session.refresh.assert_called_once()


def test_save_code_review_generation_result_saves_evidence_only() -> None:
    session = MagicMock()

    result = save_code_review_generation_result(
        session=session,
        knowledge_base_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        request=build_fake_request(),
        response=build_fake_response(
            generation_status="evidence_only",
            with_report=False,
        ),
    )

    assert result.generation_status == "evidence_only"
    assert result.review_report is None
    assert isinstance(
        result.review_run_id,
        uuid.UUID,
    )
    assert result.saved_at is not None

    saved_review_run = session.add.call_args.args[0]

    assert saved_review_run.generation_status == "evidence_only"
    assert saved_review_run.review_report_json is None
    assert saved_review_run.evidence_json
    assert saved_review_run.generation_error == "LLM output validation failed"


def test_save_code_review_generation_result_propagates_database_error() -> None:
    session = MagicMock()
    session.commit.side_effect = RuntimeError(
        "database unavailable",
    )

    with pytest.raises(
        RuntimeError,
        match="database unavailable",
    ):
        save_code_review_generation_result(
            session=session,
            knowledge_base_id=uuid.uuid4(),
            owner_id=uuid.uuid4(),
            request=build_fake_request(),
            response=build_fake_response(),
        )

    session.rollback.assert_called_once_with()
