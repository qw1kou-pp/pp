from __future__ import annotations

import pytest

from app.services.code_review_source import (
    CodeReviewSourceUrlError,
    parse_code_review_source_url,
)


@pytest.mark.parametrize(
    (
        "source_url",
        "expected_provider",
        "expected_repository",
        "expected_change_number",
        "expected_normalized_url",
    ),
    [
        (
            "https://github.com/example/project/pull/12",
            "github",
            "example/project",
            12,
            "https://github.com/example/project/pull/12",
        ),
        (
            (
                "https://github.com/example/project/"
                "pull/12/?diff=split#discussion_r1"
            ),
            "github",
            "example/project",
            12,
            "https://github.com/example/project/pull/12",
        ),
        (
            "https://www.github.com/example/project/pull/8",
            "github",
            "example/project",
            8,
            "https://github.com/example/project/pull/8",
        ),
        (
            (
                "https://gitlab.com/example/project/"
                "-/merge_requests/15"
            ),
            "gitlab",
            "example/project",
            15,
            (
                "https://gitlab.com/example/project/"
                "-/merge_requests/15"
            ),
        ),
        (
            (
                "https://gitlab.com/group/subgroup/project/"
                "-/merge_requests/27/"
                "?view=parallel#note_1"
            ),
            "gitlab",
            "group/subgroup/project",
            27,
            (
                "https://gitlab.com/group/subgroup/project/"
                "-/merge_requests/27"
            ),
        ),
        (
            (
                "https://www.gitlab.com/group/project/"
                "-/merge_requests/6"
            ),
            "gitlab",
            "group/project",
            6,
            (
                "https://gitlab.com/group/project/"
                "-/merge_requests/6"
            ),
        ),
    ],
)
def test_parse_supported_source_urls(
    source_url: str,
    expected_provider: str,
    expected_repository: str,
    expected_change_number: int,
    expected_normalized_url: str,
) -> None:
    result = parse_code_review_source_url(
        source_url,
    )

    assert result.provider == expected_provider

    assert (
        result.repository
        == expected_repository
    )

    assert (
        result.change_number
        == expected_change_number
    )

    assert (
        result.source_url
        == expected_normalized_url
    )


@pytest.mark.parametrize(
    "source_url",
    [
        # 只允许 HTTPS。
        "http://github.com/example/project/pull/12",

        # 不允许其他平台。
        (
            "https://bitbucket.org/example/project/"
            "pull-requests/12"
        ),

        # 不允许 localhost。
        "https://localhost/example/project/pull/12",

        # 不允许直接访问 IP。
        "https://127.0.0.1/example/project/pull/12",

        # 即使是 443，也不允许自定义端口。
        (
            "https://github.com:443/"
            "example/project/pull/12"
        ),

        # 不允许 URL 凭据。
        (
            "https://user:password@github.com/"
            "example/project/pull/12"
        ),

        # GitHub 路径不完整。
        "https://github.com/example/project/pull",

        # GitHub PR 编号不能是 0。
        "https://github.com/example/project/pull/0",

        # GitHub PR 编号必须是数字。
        (
            "https://github.com/example/project/"
            "pull/abc"
        ),

        # GitHub 地址不能多出路径。
        (
            "https://github.com/example/project/"
            "pull/12/files/extra"
        ),

        # GitLab 必须包含 /-/merge_requests/。
        (
            "https://gitlab.com/example/project/"
            "merge_requests/12"
        ),

        # GitLab 必须至少包含命名空间和项目。
        (
            "https://gitlab.com/project/"
            "-/merge_requests/12"
        ),

        # GitLab MR 编号必须大于 0。
        (
            "https://gitlab.com/example/project/"
            "-/merge_requests/0"
        ),

        # 拒绝编码后的路径分隔符。
        (
            "https://github.com/example%2Fother/"
            "project/pull/12"
        ),

        # 拒绝反斜杠。
        (
            "https://github.com/example\\other/"
            "project/pull/12"
        ),

        # 拒绝重复路径分隔符。
        (
            "https://github.com/example//"
            "project/pull/12"
        ),
    ],
)
def test_reject_unsupported_or_unsafe_urls(
    source_url: str,
) -> None:
    with pytest.raises(
        CodeReviewSourceUrlError,
    ):
        parse_code_review_source_url(
            source_url,
        )


@pytest.mark.parametrize(
    "source_url",
    [
        "",
        "   ",
        "github.com/example/project/pull/12",
        "not-a-url",
    ],
)
def test_reject_empty_or_incomplete_urls(
    source_url: str,
) -> None:
    with pytest.raises(
        CodeReviewSourceUrlError,
    ):
        parse_code_review_source_url(
            source_url,
        )