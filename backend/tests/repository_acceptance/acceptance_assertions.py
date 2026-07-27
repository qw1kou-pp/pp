from __future__ import annotations

from collections.abc import Sequence

from tests.repository_acceptance.acceptance_models import (
    AssertionResult,
    AssertionStatus,
    SourceEvidence,
)


def assert_commit_present(
    resolved_commit_sha: str | None,
) -> AssertionResult:
    normalized_sha = (resolved_commit_sha or "").strip()

    if not normalized_sha:
        return AssertionResult(
            name="commit_present",
            status=AssertionStatus.FAILED,
            code="COMMIT_MISSING",
            message="仓库分析任务没有记录 resolved_commit_sha",
        )

    return AssertionResult(
        name="commit_present",
        status=AssertionStatus.PASSED,
        message=f"仓库分析任务已固定 Commit：{normalized_sha}",
    )


def assert_sources_match_scope(
    *,
    sources: Sequence[SourceEvidence],
    expected_task_id: str,
    expected_commit_sha: str,
    assertion_name: str,
) -> AssertionResult:
    if not sources:
        return AssertionResult(
            name=assertion_name,
            status=AssertionStatus.FAILED,
            code="SOURCE_EMPTY",
            message="本次运行没有返回任何来源",
        )

    task_mismatches = [
        source
        for source in sources
        if source.repository_analysis_task_id != expected_task_id
    ]

    if task_mismatches:
        return AssertionResult(
            name=assertion_name,
            status=AssertionStatus.FAILED,
            code="SOURCE_TASK_SCOPE_MISMATCH",
            message="来源中出现不属于当前仓库分析任务的数据",
            details={
                "expected_task_id": expected_task_id,
                "mismatched_paths": [
                    source.repository_relative_path
                    or source.original_filename
                    or "<unknown>"
                    for source in task_mismatches
                ],
            },
        )

    commit_mismatches = [
        source
        for source in sources
        if source.source_commit_sha != expected_commit_sha
    ]

    if commit_mismatches:
        return AssertionResult(
            name=assertion_name,
            status=AssertionStatus.FAILED,
            code="SOURCE_COMMIT_MISMATCH",
            message="来源 Commit 与仓库分析任务 Commit 不一致",
            details={
                "expected_commit_sha": expected_commit_sha,
                "actual_commits": sorted(
                    {
                        source.source_commit_sha or "<missing>"
                        for source in commit_mismatches
                    }
                ),
            },
        )

    missing_paths = [
        source
        for source in sources
        if not (
            source.repository_relative_path
            or source.original_filename
        )
    ]

    if missing_paths:
        return AssertionResult(
            name=assertion_name,
            status=AssertionStatus.FAILED,
            code="SOURCE_PATH_MISSING",
            message="来源缺少仓库相对路径和原始文件名",
        )

    return AssertionResult(
        name=assertion_name,
        status=AssertionStatus.PASSED,
        message=(
            f"{len(sources)} 条来源全部属于任务 {expected_task_id}，"
            f"且 Commit 一致"
        ),
    )
