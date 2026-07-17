from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.services.github_app_auth import (
    GitHubAppAuthConfig,
    build_github_app_jwt,
)


GITHUB_API_BASE_URL = (
    "https://api.github.com"
)

GITHUB_API_VERSION = (
    "2026-03-10"
)

GITHUB_ACCEPT_HEADER = (
    "application/vnd.github+json"
)

GITHUB_REQUEST_TIMEOUT_SECONDS = 15.0


class GitHubAppInstallationError(
    RuntimeError,
):
    """Installation 认证链基础异常。"""


class GitHubAppNotInstalledError(
    GitHubAppInstallationError,
):
    """GitHub App 未安装到目标仓库。"""


class GitHubAppAuthenticationRejectedError(
    GitHubAppInstallationError,
):
    """GitHub 拒绝 App JWT。"""


class GitHubAppPermissionDeniedError(
    GitHubAppInstallationError,
):
    """GitHub App 权限不足。"""


class GitHubAppRateLimitedError(
    GitHubAppInstallationError,
):
    """GitHub API 触发限流。"""


class GitHubAppRequestTimeoutError(
    GitHubAppInstallationError,
):
    """GitHub API 请求超时。"""


class GitHubAppUpstreamError(
    GitHubAppInstallationError,
):
    """GitHub API 返回上游错误。"""


class GitHubAppInvalidResponseError(
    GitHubAppInstallationError,
):
    """GitHub 返回的响应结构不合法。"""


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubRepositoryRef:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return (
            f"{self.owner}/{self.name}"
        )


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubRepositoryInstallation:
    installation_id: int

    account_login: str | None

    repository_selection: (
        str | None
    )

    permissions: dict[str, str]


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubInstallationAccessToken:
    # 避免 dataclass repr 泄露 Token。
    token: str = field(
        repr=False,
    )

    expires_at: datetime

    installation_id: int

    repository: str

    permissions: dict[str, str]


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubRepositoryAccess:
    installation: (
        GitHubRepositoryInstallation
    )

    access_token: (
        GitHubInstallationAccessToken
    )


def parse_github_repository(
    repository: str,
) -> GitHubRepositoryRef:
    normalized_repository = (
        str(repository or "")
        .strip()
    )

    repository_parts = (
        normalized_repository.split(
            "/",
        )
    )

    if len(repository_parts) != 2:
        raise ValueError(
            "GitHub repository must use "
            "the owner/repository format",
        )

    owner = (
        repository_parts[0]
        .strip()
    )

    repository_name = (
        repository_parts[1]
        .strip()
    )

    if repository_name.lower().endswith(
        ".git",
    ):
        repository_name = (
            repository_name[:-4]
        )

    if (
        not owner
        or not repository_name
        or owner in {".", ".."}
        or repository_name
        in {".", ".."}
    ):
        raise ValueError(
            "GitHub repository owner "
            "and name are required",
        )

    forbidden_characters = {
        "\\",
        "?",
        "#",
        "%",
        ":",
    }

    if any(
        character.isspace()
        or character
        in forbidden_characters
        for character in (
            owner
            + repository_name
        )
    ):
        raise ValueError(
            "GitHub repository contains "
            "invalid characters",
        )

    return GitHubRepositoryRef(
        owner=owner,
        name=repository_name,
    )


def build_github_api_headers(
    bearer_token: str,
) -> dict[str, str]:
    normalized_token = (
        str(bearer_token or "")
        .strip()
    )

    if not normalized_token:
        raise ValueError(
            "GitHub bearer token "
            "is required",
        )

    return {
        "Accept":
            GITHUB_ACCEPT_HEADER,

        "Authorization":
            f"Bearer {normalized_token}",

        "X-GitHub-Api-Version":
            GITHUB_API_VERSION,

        "User-Agent":
            "RepoGuard",
    }


def parse_permissions(
    value: object,
) -> dict[str, str]:
    if not isinstance(
        value,
        dict,
    ):
        return {}

    permissions: dict[str, str] = {}

    for key, permission in (
        value.items()
    ):
        if (
            isinstance(key, str)
            and isinstance(
                permission,
                str,
            )
        ):
            permissions[key] = (
                permission
            )

    return permissions


def parse_response_json(
    response: httpx.Response,
    *,
    operation: str,
) -> dict[str, Any]:
    try:
        response_payload = (
            response.json()
        )
    except ValueError as exc:
        raise (
            GitHubAppInvalidResponseError(
                f"GitHub returned invalid "
                f"JSON while {operation}",
            )
        ) from exc

    if not isinstance(
        response_payload,
        dict,
    ):
        raise (
            GitHubAppInvalidResponseError(
                f"GitHub returned an invalid "
                f"response while {operation}",
            )
        )

    return response_payload


def raise_for_github_response(
    response: httpx.Response,
    *,
    operation: str,
    not_found_means_not_installed: (
        bool
    ) = False,
) -> None:
    if 200 <= response.status_code < 300:
        return

    if (
        response.status_code == 404
        and not_found_means_not_installed
    ):
        raise GitHubAppNotInstalledError(
            "GitHub App is not installed "
            "for the target repository",
        )

    if response.status_code == 401:
        raise (
            GitHubAppAuthenticationRejectedError(
                "GitHub rejected the "
                "GitHub App authentication",
            )
        )

    is_rate_limited = (
        response.status_code == 429
        or response.headers.get(
            "X-RateLimit-Remaining",
        )
        == "0"
        or "Retry-After"
        in response.headers
    )

    if is_rate_limited:
        raise GitHubAppRateLimitedError(
            "GitHub API rate limit "
            "was reached",
        )

    if response.status_code == 403:
        raise (
            GitHubAppPermissionDeniedError(
                "GitHub App does not have "
                "the required permission",
            )
        )

    if response.status_code >= 500:
        raise GitHubAppUpstreamError(
            "GitHub returned an "
            "upstream server error",
        )

    raise GitHubAppUpstreamError(
        "GitHub request failed while "
        f"{operation}; status="
        f"{response.status_code}",
    )


def perform_github_request(
    *,
    client: httpx.Client,
    method: str,
    path: str,
    headers: dict[str, str],
    json_payload: (
        dict[str, Any] | None
    ) = None,
) -> httpx.Response:
    request_arguments: dict[
        str,
        Any,
    ] = {
        "headers": headers,
    }

    if json_payload is not None:
        request_arguments["json"] = (
            json_payload
        )

    try:
        return client.request(
            method,
            path,
            **request_arguments,
        )
    except httpx.TimeoutException as exc:
        raise (
            GitHubAppRequestTimeoutError(
                "GitHub API request "
                "timed out",
            )
        ) from exc
    except httpx.HTTPError as exc:
        raise GitHubAppUpstreamError(
            "GitHub API request failed",
        ) from exc


def get_repository_installation(
    *,
    client: httpx.Client,
    app_jwt: str,
    repository: str,
) -> GitHubRepositoryInstallation:
    repository_ref = (
        parse_github_repository(
            repository,
        )
    )

    encoded_owner = quote(
        repository_ref.owner,
        safe="",
    )

    encoded_repository_name = quote(
        repository_ref.name,
        safe="",
    )

    response = perform_github_request(
        client=client,
        method="GET",
        path=(
            f"/repos/{encoded_owner}/"
            f"{encoded_repository_name}/"
            "installation"
        ),
        headers=(
            build_github_api_headers(
                app_jwt,
            )
        ),
    )

    raise_for_github_response(
        response,
        operation=(
            "resolving repository "
            "installation"
        ),
        not_found_means_not_installed=True,
    )

    payload = parse_response_json(
        response,
        operation=(
            "resolving repository "
            "installation"
        ),
    )

    installation_id = payload.get(
        "id",
    )

    if (
        not isinstance(
            installation_id,
            int,
        )
        or isinstance(
            installation_id,
            bool,
        )
        or installation_id <= 0
    ):
        raise (
            GitHubAppInvalidResponseError(
                "GitHub installation "
                "response is missing "
                "a valid installation id",
            )
        )

    account_login: str | None = None

    account = payload.get(
        "account",
    )

    if isinstance(
        account,
        dict,
    ):
        account_login_value = (
            account.get(
                "login",
            )
        )

        if isinstance(
            account_login_value,
            str,
        ):
            account_login = (
                account_login_value
            )

    repository_selection_value = (
        payload.get(
            "repository_selection",
        )
    )

    repository_selection = (
        repository_selection_value
        if isinstance(
            repository_selection_value,
            str,
        )
        else None
    )

    return GitHubRepositoryInstallation(
        installation_id=(
            installation_id
        ),

        account_login=account_login,

        repository_selection=(
            repository_selection
        ),

        permissions=parse_permissions(
            payload.get(
                "permissions",
            )
        ),
    )


def parse_github_datetime(
    value: object,
    *,
    field_name: str,
) -> datetime:
    if not isinstance(
        value,
        str,
    ):
        raise (
            GitHubAppInvalidResponseError(
                f"GitHub response is "
                f"missing {field_name}",
            )
        )

    normalized_value = (
        value.strip()
        .replace(
            "Z",
            "+00:00",
        )
    )

    try:
        parsed_datetime = (
            datetime.fromisoformat(
                normalized_value,
            )
        )
    except ValueError as exc:
        raise (
            GitHubAppInvalidResponseError(
                f"GitHub response contains "
                f"an invalid {field_name}",
            )
        ) from exc

    if parsed_datetime.tzinfo is None:
        raise (
            GitHubAppInvalidResponseError(
                f"GitHub response contains "
                f"a timezone-free "
                f"{field_name}",
            )
        )

    return parsed_datetime


def create_installation_access_token(
    *,
    client: httpx.Client,
    app_jwt: str,
    installation_id: int,
    repository: str,
) -> GitHubInstallationAccessToken:
    if installation_id <= 0:
        raise ValueError(
            "GitHub installation id "
            "must be positive",
        )

    repository_ref = (
        parse_github_repository(
            repository,
        )
    )

    response = perform_github_request(
        client=client,
        method="POST",
        path=(
            "/app/installations/"
            f"{installation_id}/"
            "access_tokens"
        ),
        headers=(
            build_github_api_headers(
                app_jwt,
            )
        ),
        json_payload={
            # GitHub 这里只接收仓库名，
            # 不接收 owner/repository。
            "repositories": [
                repository_ref.name,
            ],

            "permissions": {
                "pull_requests":
                    "write",
            },
        },
    )

    raise_for_github_response(
        response,
        operation=(
            "creating installation "
            "access token"
        ),
    )

    payload = parse_response_json(
        response,
        operation=(
            "creating installation "
            "access token"
        ),
    )

    token = payload.get(
        "token",
    )

    if (
        not isinstance(
            token,
            str,
        )
        or not token.strip()
    ):
        raise (
            GitHubAppInvalidResponseError(
                "GitHub response is "
                "missing an installation "
                "access token",
            )
        )

    return GitHubInstallationAccessToken(
        token=token,

        expires_at=(
            parse_github_datetime(
                payload.get(
                    "expires_at",
                ),
                field_name=(
                    "expires_at"
                ),
            )
        ),

        installation_id=(
            installation_id
        ),

        repository=(
            repository_ref.full_name
        ),

        permissions=parse_permissions(
            payload.get(
                "permissions",
            )
        ),
    )


def create_repository_installation_access(
    *,
    config: GitHubAppAuthConfig,
    repository: str,
    client: httpx.Client | None = None,
) -> GitHubRepositoryAccess:
    app_jwt = build_github_app_jwt(
        config=config,
    )

    def resolve_access(
        github_client: httpx.Client,
    ) -> GitHubRepositoryAccess:
        installation = (
            get_repository_installation(
                client=github_client,
                app_jwt=app_jwt,
                repository=repository,
            )
        )

        access_token = (
            create_installation_access_token(
                client=github_client,
                app_jwt=app_jwt,
                installation_id=(
                    installation
                    .installation_id
                ),
                repository=repository,
            )
        )

        return GitHubRepositoryAccess(
            installation=installation,
            access_token=access_token,
        )

    if client is not None:
        return resolve_access(
            client,
        )

    with httpx.Client(
        base_url=(
            GITHUB_API_BASE_URL
        ),
        timeout=(
            GITHUB_REQUEST_TIMEOUT_SECONDS
        ),
        follow_redirects=False,
    ) as github_client:
        return resolve_access(
            github_client,
        )