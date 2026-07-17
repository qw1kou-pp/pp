from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit


_GITHUB_HOST = "github.com"

_OWNER_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")

_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class InvalidGitHubRepositoryUrlError(ValueError):
    """输入内容不是受支持的 GitHub 仓库地址。"""


@dataclass(frozen=True, slots=True)
class GitHubRepositoryReference:
    """标准化后的 GitHub 仓库信息。"""

    owner: str
    name: str
    repository: str
    canonical_url: str


def _validate_owner(owner: str) -> str:
    normalized_owner = owner.strip()

    if not _OWNER_PATTERN.fullmatch(normalized_owner):
        raise InvalidGitHubRepositoryUrlError(
            "GitHub repository owner is invalid",
        )

    return normalized_owner


def _normalize_repository_name(
    repository_name: str,
) -> str:
    normalized_name = repository_name.strip()

    if normalized_name.lower().endswith(".git"):
        normalized_name = normalized_name[:-4]

    if (
        not normalized_name
        or normalized_name in {".", ".."}
        or not _REPOSITORY_PATTERN.fullmatch(
            normalized_name,
        )
    ):
        raise InvalidGitHubRepositoryUrlError(
            "GitHub repository name is invalid",
        )

    return normalized_name


def _parse_https_url(
    repository_url: str,
) -> tuple[str, str]:
    parsed_url = urlsplit(repository_url)

    if parsed_url.scheme != "https":
        raise InvalidGitHubRepositoryUrlError(
            "Only HTTPS GitHub repository URLs are supported",
        )

    if parsed_url.hostname is None:
        raise InvalidGitHubRepositoryUrlError(
            "GitHub repository host is required",
        )

    if parsed_url.hostname.lower() != _GITHUB_HOST:
        raise InvalidGitHubRepositoryUrlError(
            "Only github.com repositories are supported",
        )

    if (
        parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.port is not None
    ):
        raise InvalidGitHubRepositoryUrlError(
            "Credentials and custom ports are not allowed",
        )

    if parsed_url.query or parsed_url.fragment:
        raise InvalidGitHubRepositoryUrlError(
            "Query parameters and fragments are not allowed",
        )

    path_parts = [part for part in parsed_url.path.strip("/").split("/") if part]

    if len(path_parts) != 2:
        raise InvalidGitHubRepositoryUrlError(
            "URL must point to a GitHub repository root",
        )

    return path_parts[0], path_parts[1]


def _parse_ssh_url(
    repository_url: str,
) -> tuple[str, str]:
    prefix = "git@github.com:"

    if not repository_url.startswith(prefix):
        raise InvalidGitHubRepositoryUrlError(
            "GitHub SSH repository URL is invalid",
        )

    repository_path = repository_url[len(prefix) :]

    path_parts = [part for part in repository_path.strip("/").split("/") if part]

    if len(path_parts) != 2:
        raise InvalidGitHubRepositoryUrlError(
            "SSH URL must point to a GitHub repository root",
        )

    return path_parts[0], path_parts[1]


def parse_public_github_repository_url(
    repository_url: str,
) -> GitHubRepositoryReference:
    """解析并标准化公开 GitHub 仓库地址。"""

    normalized_url = str(repository_url or "").strip()

    if not normalized_url:
        raise InvalidGitHubRepositoryUrlError(
            "GitHub repository URL is required",
        )

    if normalized_url.startswith("git@"):
        owner_value, repository_value = _parse_ssh_url(
            normalized_url,
        )
    else:
        owner_value, repository_value = _parse_https_url(
            normalized_url,
        )

    owner = _validate_owner(owner_value)

    repository_name = _normalize_repository_name(
        repository_value,
    )

    repository = f"{owner}/{repository_name}"

    canonical_url = f"https://github.com/{repository}"

    return GitHubRepositoryReference(
        owner=owner,
        name=repository_name,
        repository=repository,
        canonical_url=canonical_url,
    )
