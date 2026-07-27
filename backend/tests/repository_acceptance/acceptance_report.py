from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tests.repository_acceptance.acceptance_matrix_runner import (
    AcceptanceMatrixResult,
)
from tests.repository_acceptance.acceptance_models import (
    AcceptanceRunResult,
)


@dataclass(frozen=True, slots=True)
class AcceptanceReportPaths:
    json_path: Path
    markdown_path: Path
    latest_json_path: Path
    latest_markdown_path: Path


def write_acceptance_reports(
    *,
    result: AcceptanceMatrixResult,
    output_dir: str | Path,
    run_name: str | None = None,
) -> AcceptanceReportPaths:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    resolved_name = run_name or result.started_at.strftime(
        "repository-acceptance-%Y%m%d-%H%M%S"
    )
    json_path = directory / f"{resolved_name}.json"
    markdown_path = directory / f"{resolved_name}.md"
    latest_json_path = directory / "latest.json"
    latest_markdown_path = directory / "latest.md"

    payload = _to_json_value(result)
    json_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_markdown_report(result),
        encoding="utf-8",
    )

    shutil.copyfile(json_path, latest_json_path)
    shutil.copyfile(markdown_path, latest_markdown_path)

    return AcceptanceReportPaths(
        json_path=json_path,
        markdown_path=markdown_path,
        latest_json_path=latest_json_path,
        latest_markdown_path=latest_markdown_path,
    )


def render_markdown_report(result: AcceptanceMatrixResult) -> str:
    lines = [
        "# Repository Acceptance Report",
        "",
        f"- Status: **{result.status.value.upper()}**",
        f"- Started: `{result.started_at.isoformat()}`",
        f"- Finished: `{result.finished_at.isoformat()}`",
        f"- Duration: `{result.duration_seconds:.2f}s`",
        f"- Repositories: `{len(result.runs)}`",
        f"- Passed: `{result.passed_count}`",
        f"- Failed: `{result.failed_count}`",
        "",
        "## Repository Runs",
        "",
        "| Repository | Category | Status | Commit | Documents | Duration |",
        "|---|---|---:|---|---:|---:|",
    ]

    for run in result.runs:
        lines.append(
            "| "
            + " | ".join(
                [
                    _repository_full_name(run.repository_url),
                    run.category.value,
                    run.status.value,
                    _short_commit(run.resolved_commit_sha),
                    str(run.metadata.get("document_count", 0)),
                    f"{_run_duration_seconds(run):.2f}s",
                ]
            )
            + " |"
        )

    for run in result.runs:
        lines.extend(_render_run_details(run))

    lines.extend(
        [
            "",
            "## Cross-Repository Isolation",
            "",
        ]
    )
    if not result.isolation_assertions:
        lines.append("Only one repository was executed; pairwise isolation was not applicable.")
    else:
        for assertion in result.isolation_assertions:
            code = f" (`{assertion.code}`)" if assertion.code else ""
            lines.append(
                f"- **{assertion.status.value.upper()}**{code}: "
                f"{assertion.message}"
            )

    return "\n".join(lines).rstrip() + "\n"


def _render_run_details(run: AcceptanceRunResult) -> list[str]:
    lines = [
        "",
        f"## {_repository_full_name(run.repository_url)}",
        "",
        f"- Status: **{run.status.value.upper()}**",
        f"- Default branch: `{run.default_branch or '<missing>'}`",
        f"- Commit: `{run.resolved_commit_sha or '<missing>'}`",
        f"- Task: `{run.repository_analysis_task_id or '<missing>'}`",
        f"- Knowledge base: `{run.knowledge_base_id or '<missing>'}`",
        f"- Documents: `{run.metadata.get('document_count', 0)}`",
        "",
        "### Stage Timings",
        "",
    ]

    if run.stage_timings:
        for stage in run.stage_timings:
            duration = stage.duration_seconds
            rendered_duration = (
                f"{duration:.2f}s" if duration is not None else "running"
            )
            lines.append(f"- `{stage.name}`: {rendered_duration}")
    else:
        lines.append("- No stage timing was recorded.")

    lines.extend(["", "### Failures", ""])
    if run.failures:
        for failure in run.failures:
            stage = f" at `{failure.stage}`" if failure.stage else ""
            lines.append(
                f"- `{failure.code.value}`{stage}: {failure.message}"
            )
    else:
        lines.append("- None.")

    return lines


def _run_duration_seconds(run: AcceptanceRunResult) -> float:
    return sum(
        stage.duration_seconds or 0.0 for stage in run.stage_timings
    )


def _repository_full_name(repository_url: str) -> str:
    path = urlparse(repository_url).path.strip("/")
    return path or repository_url


def _short_commit(commit_sha: str | None) -> str:
    return commit_sha[:12] if commit_sha else "<missing>"


def _to_json_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_json_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _to_json_value(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
