from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import (
    CodeReviewSourceResolvedPublic,
    CodeReviewSourceResolveRequest,
    CodeReviewSourceSnapshot,
    CodeSkillGenerateReviewReportRequest,
)


def build_source_snapshot() -> CodeReviewSourceSnapshot:
    """
    构造一个合法的 GitHub PR 来源快照。

    多个测试都需要相同的来源数据，
    使用辅助函数避免重复构造。
    """

    return CodeReviewSourceSnapshot(
        provider="github",
        source_url=(
            "https://github.com/"
            "example/project/pull/12"
        ),
        repository="example/project",
        change_number=12,
        title="Fix authentication validation",
        author="example-user",
        base_ref="main",
        head_ref="fix/auth-validation",
        base_sha="a" * 40,
        head_sha="b" * 40,
        diff_hash="c" * 64,
        fetched_at=datetime.now(
            timezone.utc,
        ),
    )


def build_diff_text() -> str:
    """
    构造一份能够被 RepoGuard 解析的
    最小标准 Git Diff。
    """

    return (
        "diff --git a/app.py b/app.py\n"
        "index 1111111..2222222 100644\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )


def test_source_resolve_request_accepts_url() -> None:
    request = CodeReviewSourceResolveRequest(
        source_url=(
            "https://github.com/"
            "example/project/pull/12"
        ),
    )

    assert request.source_url == (
        "https://github.com/"
        "example/project/pull/12"
    )


def test_source_snapshot_does_not_contain_diff_text() -> None:
    source = build_source_snapshot()

    payload = source.model_dump(
        mode="json",
    )

    assert payload["provider"] == "github"

    assert (
        payload["repository"]
        == "example/project"
    )

    assert "diff_text" not in payload


def test_resolved_source_contains_diff_text() -> None:
    source = build_source_snapshot()

    resolved = CodeReviewSourceResolvedPublic(
        **source.model_dump(),
        diff_text=build_diff_text(),
    )

    assert resolved.provider == "github"
    assert resolved.change_number == 12

    assert resolved.diff_text.startswith(
        "diff --git ",
    )


def test_generate_review_request_accepts_source_snapshot() -> None:
    source = build_source_snapshot()

    request = CodeSkillGenerateReviewReportRequest(
        diff_text=build_diff_text(),
        max_references_per_symbol=20,
        max_test_files=20,
        min_test_confidence=0.2,
        include_file_level_fallback=True,
        include_definition_chunk=False,
        language="zh-CN",
        source=source,
    )

    assert request.source is not None

    assert (
        request.source.source_url
        == source.source_url
    )

    assert (
        request.source.diff_hash
        == "c" * 64
    )


def test_generate_review_request_keeps_manual_diff_mode() -> None:
    request = CodeSkillGenerateReviewReportRequest(
        diff_text=build_diff_text(),
        max_references_per_symbol=20,
        max_test_files=20,
        min_test_confidence=0.2,
        include_file_level_fallback=True,
        include_definition_chunk=False,
        language="zh-CN",
    )

    assert request.source is None


def test_source_provider_rejects_unknown_platform() -> None:
    with pytest.raises(
        ValidationError,
    ):
        CodeReviewSourceSnapshot(
            provider="bitbucket",
            source_url=(
                "https://bitbucket.org/"
                "example/project/"
                "pull-requests/12"
            ),
            repository="example/project",
            change_number=12,
            title="Unsupported provider",
            author=None,
            base_ref="main",
            head_ref="feature",
            base_sha="a" * 40,
            head_sha="b" * 40,
            diff_hash="c" * 64,
            fetched_at=datetime.now(
                timezone.utc,
            ),
        )


def test_source_change_number_must_be_positive() -> None:
    with pytest.raises(
        ValidationError,
    ):
        CodeReviewSourceSnapshot(
            provider="gitlab",
            source_url=(
                "https://gitlab.com/"
                "example/project/-/"
                "merge_requests/0"
            ),
            repository="example/project",
            change_number=0,
            title="Invalid merge request",
            author=None,
            base_ref="main",
            head_ref="feature",
            base_sha="a" * 40,
            head_sha="b" * 40,
            diff_hash="c" * 64,
            fetched_at=datetime.now(
                timezone.utc,
            ),
        )