from __future__ import annotations

import pytest

from app.services.github_repository_reference import (
    InvalidGitHubRepositoryUrlError,
    parse_public_github_repository_url,
)


@pytest.mark.parametrize(
    (
        "repository_url",
        "expected_repository",
        "expected_url",
    ),
    [
        (
            (
                "https://github.com/"
                "fastapi/"
                "full-stack-fastapi-template"
            ),
            (
                "fastapi/"
                "full-stack-fastapi-template"
            ),
            (
                "https://github.com/"
                "fastapi/"
                "full-stack-fastapi-template"
            ),
        ),
        (
            (
                "https://github.com/"
                "fastapi/"
                "full-stack-fastapi-template/"
            ),
            (
                "fastapi/"
                "full-stack-fastapi-template"
            ),
            (
                "https://github.com/"
                "fastapi/"
                "full-stack-fastapi-template"
            ),
        ),
        (
            (
                "https://github.com/"
                "fastapi/"
                "full-stack-fastapi-template.git"
            ),
            (
                "fastapi/"
                "full-stack-fastapi-template"
            ),
            (
                "https://github.com/"
                "fastapi/"
                "full-stack-fastapi-template"
            ),
        ),
        (
            (
                "git@github.com:"
                "fastapi/"
                "full-stack-fastapi-template.git"
            ),
            (
                "fastapi/"
                "full-stack-fastapi-template"
            ),
            (
                "https://github.com/"
                "fastapi/"
                "full-stack-fastapi-template"
            ),
        ),
    ],
)
def test_parse_supported_github_repository_urls(
    repository_url: str,
    expected_repository: str,
    expected_url: str,
) -> None:
    reference = (
        parse_public_github_repository_url(
            repository_url,
        )
    )

    assert reference.owner == "fastapi"

    assert reference.name == (
        "full-stack-fastapi-template"
    )

    assert (
        reference.repository
        == expected_repository
    )

    assert (
        reference.canonical_url
        == expected_url
    )


@pytest.mark.parametrize(
    "repository_url",
    [
        "",
        "   ",
        (
            "https://gitlab.com/"
            "fastapi/"
            "full-stack-fastapi-template"
        ),
        "https://github.com/fastapi",
        (
            "https://github.com/"
            "fastapi/"
            "full-stack-fastapi-template/"
            "issues/1"
        ),
        (
            "https://github.com/"
            "fastapi/"
            "full-stack-fastapi-template/"
            "tree/main"
        ),
        (
            "https://user:token@github.com/"
            "fastapi/"
            "full-stack-fastapi-template"
        ),
        (
            "http://github.com/"
            "fastapi/"
            "full-stack-fastapi-template"
        ),
        (
            "https://evil.example/"
            "github.com/fastapi/project"
        ),
        (
            "git@evil.example:"
            "fastapi/project.git"
        ),
    ],
)
def test_reject_unsupported_or_unsafe_repository_urls(
    repository_url: str,
) -> None:
    with pytest.raises(
        InvalidGitHubRepositoryUrlError,
    ):
        parse_public_github_repository_url(
            repository_url,
        )


@pytest.mark.parametrize(
    "repository_url",
    [
        (
            "https://github.com/"
            "-invalid/repo"
        ),
        (
            "https://github.com/"
            "invalid-/repo"
        ),
        (
            "https://github.com/"
            "owner/.git"
        ),
        (
            "https://github.com/"
            "owner/repo name"
        ),
        "git@github.com:owner",
    ],
)
def test_reject_invalid_owner_or_repository_names(
    repository_url: str,
) -> None:
    with pytest.raises(
        InvalidGitHubRepositoryUrlError,
    ):
        parse_public_github_repository_url(
            repository_url,
        )