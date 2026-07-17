from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_GITHUB_API_VERSION = "2022-11-28"


class GitHubRepositoryClientError(RuntimeError):
    """GitHub 仓库访问基础异常。"""


class GitHubRepositoryNotFoundError(
    GitHubRepositoryClientError,
):
    """仓库不存在，或者不是公开仓库。"""


class GitHubPrivateRepositoryNotSupportedError(
    GitHubRepositoryClientError,
):
    """当前功能不支持私有仓库。"""


class GitHubRepositoryRateLimitError(
    GitHubRepositoryClientError,
):
    """GitHub API 请求频率受限。"""


class GitHubRepositoryEmptyError(
    GitHubRepositoryClientError,
):
    """仓库没有可以解析的提交。"""


class GitHubRepositoryUnavailableError(
    GitHubRepositoryClientError,
):
    """GitHub API 暂时无法访问。"""


class GitHubRepositoryResponseError(
    GitHubRepositoryClientError,
):
    """GitHub 返回了无法解析的响应。"""


@dataclass(frozen=True, slots=True)
class GitHubRepositoryMetadata:
    """GitHub 仓库基础元数据。"""

    owner: str
    name: str
    full_name: str
    html_url: str
    description: str | None

    default_branch: str
    primary_language: str | None
    topics: tuple[str, ...]

    archived: bool
    fork: bool
    size_kb: int

    stargazers_count: int
    forks_count: int
    open_issues_count: int

    license_spdx_id: str | None

    created_at: str | None
    updated_at: str | None
    pushed_at: str | None


@dataclass(frozen=True, slots=True)
class GitHubResolvedCommit:
    """固定后的 GitHub Commit 信息。"""

    requested_ref: str
    sha: str
    html_url: str

    message: str
    author_name: str | None
    authored_at: str | None
    committed_at: str | None


@dataclass(frozen=True, slots=True)
class GitHubRepositoryAcquisition:
    """一次仓库元数据获取的完整结果。"""

    metadata: GitHubRepositoryMetadata
    commit: GitHubResolvedCommit


class GitHubRepositoryClient:
    """
    GitHub 公共仓库 REST API 客户端。

    当前负责：
    1. 获取仓库元数据；
    2. 获取默认分支；
    3. 将分支、标签或 SHA 解析为固定 Commit。
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        api_base_url: str = DEFAULT_GITHUB_API_URL,
        api_version: str = DEFAULT_GITHUB_API_VERSION,
        timeout_seconds: float = 20.0,
    ) -> None:
        normalized_token = str(
            token
            if token is not None
            else os.getenv("GITHUB_TOKEN", "")
        ).strip()

        self._api_base_url = api_base_url.rstrip("/")

        self._client = httpx.Client(
            base_url=self._api_base_url,
            timeout=timeout_seconds,
            follow_redirects=True,
            headers=self._build_headers(
                token=normalized_token or None,
                api_version=api_version,
            ),
        )

    def __enter__(
        self,
    ) -> GitHubRepositoryClient:
        return self

    def __exit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        """关闭 HTTP 连接池。"""

        self._client.close()

    def get_repository_metadata(
        self,
        *,
        owner: str,
        repository_name: str,
    ) -> GitHubRepositoryMetadata:
        """获取一个公开 GitHub 仓库的元数据。"""

        payload = self._get_json(
            path=(
                f"/repos/{quote(owner, safe='')}/"
                f"{quote(repository_name, safe='')}"
            ),
        )

        if payload.get("private") is True:
            raise GitHubPrivateRepositoryNotSupportedError(
                "Private GitHub repositories are not supported",
            )

        repository_owner = payload.get("owner")

        if not isinstance(repository_owner, dict):
            raise GitHubRepositoryResponseError(
                "GitHub repository owner is missing",
            )

        owner_login = self._require_string(
            repository_owner,
            "login",
        )

        default_branch = self._require_string(
            payload,
            "default_branch",
        )

        license_data = payload.get("license")

        license_spdx_id: str | None = None

        if isinstance(license_data, dict):
            raw_license = license_data.get("spdx_id")

            if isinstance(raw_license, str):
                normalized_license = raw_license.strip()

                if normalized_license:
                    license_spdx_id = normalized_license

        topics_value = payload.get("topics")

        topics: tuple[str, ...] = ()

        if isinstance(topics_value, list):
            topics = tuple(
                topic.strip()
                for topic in topics_value
                if isinstance(topic, str)
                and topic.strip()
            )

        return GitHubRepositoryMetadata(
            owner=owner_login,
            name=self._require_string(
                payload,
                "name",
            ),
            full_name=self._require_string(
                payload,
                "full_name",
            ),
            html_url=self._require_string(
                payload,
                "html_url",
            ),
            description=self._optional_string(
                payload.get("description"),
            ),
            default_branch=default_branch,
            primary_language=self._optional_string(
                payload.get("language"),
            ),
            topics=topics,
            archived=bool(
                payload.get("archived", False),
            ),
            fork=bool(
                payload.get("fork", False),
            ),
            size_kb=self._safe_integer(
                payload.get("size"),
            ),
            stargazers_count=self._safe_integer(
                payload.get("stargazers_count"),
            ),
            forks_count=self._safe_integer(
                payload.get("forks_count"),
            ),
            open_issues_count=self._safe_integer(
                payload.get("open_issues_count"),
            ),
            license_spdx_id=license_spdx_id,
            created_at=self._optional_string(
                payload.get("created_at"),
            ),
            updated_at=self._optional_string(
                payload.get("updated_at"),
            ),
            pushed_at=self._optional_string(
                payload.get("pushed_at"),
            ),
        )

    def get_commit(
        self,
        *,
        owner: str,
        repository_name: str,
        ref: str,
    ) -> GitHubResolvedCommit:
        """
        将分支、标签或 SHA 解析为一个固定 Commit。
        """

        normalized_ref = str(ref or "").strip()

        if not normalized_ref:
            raise ValueError(
                "GitHub commit ref must not be empty",
            )

        payload = self._get_json(
            path=(
                f"/repos/{quote(owner, safe='')}/"
                f"{quote(repository_name, safe='')}/"
                f"commits/{quote(normalized_ref, safe='')}"
            ),
        )

        commit_data = payload.get("commit")

        if not isinstance(commit_data, dict):
            raise GitHubRepositoryResponseError(
                "GitHub commit details are missing",
            )

        author_data = commit_data.get("author")
        committer_data = commit_data.get("committer")

        author_name: str | None = None
        authored_at: str | None = None
        committed_at: str | None = None

        if isinstance(author_data, dict):
            author_name = self._optional_string(
                author_data.get("name"),
            )
            authored_at = self._optional_string(
                author_data.get("date"),
            )

        if isinstance(committer_data, dict):
            committed_at = self._optional_string(
                committer_data.get("date"),
            )

        return GitHubResolvedCommit(
            requested_ref=normalized_ref,
            sha=self._require_string(
                payload,
                "sha",
            ),
            html_url=self._require_string(
                payload,
                "html_url",
            ),
            message=self._require_string(
                commit_data,
                "message",
            ),
            author_name=author_name,
            authored_at=authored_at,
            committed_at=committed_at,
        )

    def acquire_repository(
        self,
        *,
        owner: str,
        repository_name: str,
        requested_ref: str | None = None,
    ) -> GitHubRepositoryAcquisition:
        """
        获取仓库元数据并解析固定 Commit。

        未指定 requested_ref 时使用默认分支。
        """

        metadata = self.get_repository_metadata(
            owner=owner,
            repository_name=repository_name,
        )

        target_ref = str(
            requested_ref or metadata.default_branch,
        ).strip()

        commit = self.get_commit(
            owner=owner,
            repository_name=repository_name,
            ref=target_ref,
        )

        return GitHubRepositoryAcquisition(
            metadata=metadata,
            commit=commit,
        )

    def _get_json(
        self,
        *,
        path: str,
    ) -> dict[str, Any]:
        """发送 GET 请求并统一处理 GitHub 错误。"""

        try:
            response = self._client.get(path)
        except httpx.TimeoutException as exc:
            raise GitHubRepositoryUnavailableError(
                "GitHub API request timed out",
            ) from exc
        except httpx.RequestError as exc:
            raise GitHubRepositoryUnavailableError(
                "GitHub API could not be reached",
            ) from exc

        if response.status_code == 404:
            raise GitHubRepositoryNotFoundError(
                "Repository or Git reference was not found",
            )

        if response.status_code == 409:
            raise GitHubRepositoryEmptyError(
                "Repository does not contain a readable commit",
            )

        if response.status_code == 403:
            if (
                response.headers.get(
                    "x-ratelimit-remaining",
                )
                == "0"
            ):
                raise GitHubRepositoryRateLimitError(
                    "GitHub API rate limit was exceeded",
                )

            raise GitHubRepositoryClientError(
                "GitHub API rejected the request",
            )

        if response.status_code >= 500:
            raise GitHubRepositoryUnavailableError(
                "GitHub API is temporarily unavailable",
            )

        if not response.is_success:
            raise GitHubRepositoryResponseError(
                "Unexpected GitHub API response: "
                f"{response.status_code}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GitHubRepositoryResponseError(
                "GitHub API returned invalid JSON",
            ) from exc

        if not isinstance(payload, dict):
            raise GitHubRepositoryResponseError(
                "GitHub API returned an unexpected payload",
            )

        return payload

    @staticmethod
    def _build_headers(
        *,
        token: str | None,
        api_version: str,
    ) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version,
            "User-Agent": "RepoGuard-Repository-Analyzer",
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    @staticmethod
    def _require_string(
        payload: dict[str, Any],
        field_name: str,
    ) -> str:
        value = payload.get(field_name)

        if not isinstance(value, str):
            raise GitHubRepositoryResponseError(
                f"GitHub response field is missing: "
                f"{field_name}",
            )

        normalized_value = value.strip()

        if not normalized_value:
            raise GitHubRepositoryResponseError(
                f"GitHub response field is empty: "
                f"{field_name}",
            )

        return normalized_value

    @staticmethod
    def _optional_string(
        value: Any,
    ) -> str | None:
        if not isinstance(value, str):
            return None

        normalized_value = value.strip()

        return normalized_value or None

    @staticmethod
    def _safe_integer(
        value: Any,
    ) -> int:
        if isinstance(value, bool):
            return 0

        if isinstance(value, int):
            return max(value, 0)

        return 0