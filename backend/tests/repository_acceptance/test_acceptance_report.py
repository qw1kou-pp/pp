from __future__ import annotations

import json
from datetime import datetime, timezone

from tests.repository_acceptance.acceptance_matrix_runner import (
    AcceptanceMatrixResult,
)
from tests.repository_acceptance.acceptance_models import (
    AcceptanceFailure,
    AcceptanceFailureCode,
    AcceptanceRunResult,
    AcceptanceStatus,
    RepositoryCategory,
    StageTiming,
)
from tests.repository_acceptance.acceptance_report import (
    write_acceptance_reports,
)


def test_report_writer_creates_timestamped_and_latest_reports(tmp_path) -> None:
    started = datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 7, 27, 8, 1, tzinfo=timezone.utc)
    run = AcceptanceRunResult(
        repository_key="requests",
        repository_url="https://github.com/psf/requests",
        category=RepositoryCategory.PYTHON,
        status=AcceptanceStatus.FAILED,
        default_branch="main",
        resolved_commit_sha="a" * 40,
        repository_analysis_task_id="task-1",
        knowledge_base_id="kb-1",
        stage_timings=[
            StageTiming(
                name="repository_overview",
                started_at=started,
                finished_at=finished,
            )
        ],
        failures=[
            AcceptanceFailure(
                code=AcceptanceFailureCode.RAG_SCOPE_VIOLATION,
                message="来源越界",
                stage="repository_rag",
            )
        ],
        metadata={"document_count": 8},
    )
    matrix = AcceptanceMatrixResult(
        status=AcceptanceStatus.FAILED,
        started_at=started,
        finished_at=finished,
        runs=[run],
    )

    paths = write_acceptance_reports(
        result=matrix,
        output_dir=tmp_path,
        run_name="acceptance-test",
    )

    assert paths.json_path.name == "acceptance-test.json"
    assert paths.markdown_path.name == "acceptance-test.md"
    assert paths.latest_json_path.exists()
    assert paths.latest_markdown_path.exists()

    payload = json.loads(paths.json_path.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["runs"][0]["category"] == "python"
    assert payload["runs"][0]["failures"][0]["code"] == (
        "RAG_SCOPE_VIOLATION"
    )

    markdown = paths.markdown_path.read_text(encoding="utf-8")
    assert "# Repository Acceptance Report" in markdown
    assert "psf/requests" in markdown
    assert "来源越界" in markdown
    assert "aaaaaaaaaaaa" in markdown
