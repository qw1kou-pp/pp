from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    Literal,
    TypeAlias,
)
from urllib.parse import quote

import httpx

from app.services.github_app_installation import (
    GITHUB_API_BASE_URL,
    GITHUB_REQUEST_TIMEOUT_SECONDS,
    build_github_api_headers,
    parse_github_repository,
)


GitHubReviewEvent: TypeAlias = Literal[
    "COMMENT",
    "APPROVE",
    "REQUEST_CHANGES",
]


VALID_GITHUB_REVIEW_EVENTS = frozenset(
    {
        "COMMENT",
        "APPROVE",
        "REQUEST_CHANGES",
    },
)


class GitHubReviewClientError(
    RuntimeError,
):
    """GitHub PR Review 客户端基础异常。"""


class GitHubReviewAuthenticationError(
    GitHubReviewClientError,
):
    """GitHub 拒绝 Installation Token。"""


class GitHubReviewPermissionDeniedError(
    GitHubReviewClientError,
):
    """GitHub App 缺少 PR 权限。"""


class GitHubPullRequestNotFoundError(
    GitHubReviewClientError,
):
    """目标 PR 不存在或不可见。"""


class GitHubReviewRateLimitedError(
    GitHubReviewClientError,
):
    """GitHub API 触发限流。"""


class GitHubReviewRejectedError(
    GitHubReviewClientError,
):
    """GitHub 拒绝创建 Review。"""


class GitHubReviewRequestTimeoutError(
    GitHubReviewClientError,
):
    """GitHub API 请求超时。"""


class GitHubReviewUpstreamError(
    GitHubReviewClientError,
):
    """GitHub API 返回上游错误。"""


class GitHubReviewInvalidResponseError(
    GitHubReviewClientError,
):
    """GitHub 响应结构不完整。"""


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubPullRequestSnapshot:
    repository: str
    number: int
    title: str
    state: str
    merged: bool
    draft: bool
    html_url: str

    head_sha: str
    head_ref: str

    base_sha: str
    base_ref: str

    author_login: str | None


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubPublishedReview:
    review_id: int
    state: str
    html_url: str
    body: str | None
    commit_id: str
    submitted_at: datetime | None
    actor_login: str | None


def _read_json_object(
    response: httpx.Response,
    *,
    operation: str,
) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise (
            GitHubReviewInvalidResponseError(
                "GitHub returned invalid "
                f"JSON while {operation}",
            )
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise (
            GitHubReviewInvalidResponseError(
                "GitHub returned an invalid "
                f"response while {operation}",
            )
        )

    return payload


def _require_string(
    value: object,
    *,
    field_name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
    ):
        raise (
            GitHubReviewInvalidResponseError(
                "GitHub response is "
                f"missing {field_name}",
            )
        )

    return value.strip()


def _optional_string(
    value: object,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    normalized_value = value.strip()

    return (
        normalized_value
        if normalized_value
        else None
    )


def _require_positive_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if (
        not isinstance(
            value,
            int,
        )
        or isinstance(
            value,
            bool,
        )
        or value <= 0
    ):
        raise (
            GitHubReviewInvalidResponseError(
                "GitHub response is "
                f"missing {field_name}",
            )
        )

    return value


def _read_nested_string(
    payload: dict[str, Any],
    *,
    object_name: str,
    field_name: str,
) -> str:
    nested_object = payload.get(
        object_name,
    )

    if not isinstance(
        nested_object,
        dict,
    ):
        raise (
            GitHubReviewInvalidResponseError(
                "GitHub response is "
                f"missing {object_name}",
            )
        )

    return _require_string(
        nested_object.get(
            field_name,
        ),
        field_name=(
            f"{object_name}.{field_name}"
        ),
    )


def _read_actor_login(
    payload: dict[str, Any],
) -> str | None:
    user = payload.get(
        "user",
    )

    if not isinstance(
        user,
        dict,
    ):
        return None

    return _optional_string(
        user.get(
            "login",
        ),
    )


def _parse_optional_datetime(
    value: object,
    *,
    field_name: str,
) -> datetime | None:
    if value is None:
        return None

    normalized_value = _require_string(
        value,
        field_name=field_name,
    ).replace(
        "Z",
        "+00:00",
    )

    try:
        parsed_datetime = (
            datetime.fromisoformat(
                normalized_value,
            )
        )
    except ValueError as exc:
        raise (
            GitHubReviewInvalidResponseError(
                "GitHub response contains "
                f"an invalid {field_name}",
            )
        ) from exc

    if parsed_datetime.tzinfo is None:
        raise (
            GitHubReviewInvalidResponseError(
                "GitHub response contains "
                "a timezone-free "
                f"{field_name}",
            )
        )

    return parsed_datetime


def _perform_request(
    *,
    client: httpx.Client,
    method: str,
    path: str,
    access_token: str,
    json_payload: (
        dict[str, Any] | None
    ) = None,
) -> httpx.Response:
    request_arguments: dict[
        str,
        Any,
    ] = {
        "headers":
            build_github_api_headers(
                access_token,
            ),
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
            GitHubReviewRequestTimeoutError(
                "GitHub PR request "
                "timed out",
            )
        ) from exc
    except httpx.HTTPError as exc:
        raise GitHubReviewUpstreamError(
            "GitHub PR request failed",
        ) from exc


def _raise_for_response(
    response: httpx.Response,
    *,
    operation: str,
) -> None:
    if 200 <= response.status_code < 300:
        return

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
        raise GitHubReviewRateLimitedError(
            "GitHub API rate limit "
            "was reached",
        )

    if response.status_code == 401:
        raise (
            GitHubReviewAuthenticationError(
                "GitHub rejected the "
                "installation token",
            )
        )

    if response.status_code == 403:
        raise (
            GitHubReviewPermissionDeniedError(
                "GitHub App does not have "
                "the required pull request "
                "permission",
            )
        )

    if response.status_code == 404:
        raise (
            GitHubPullRequestNotFoundError(
                "GitHub pull request "
                "was not found",
            )
        )

    if response.status_code == 422:
        raise GitHubReviewRejectedError(
            "GitHub rejected the "
            f"pull request {operation}",
        )

    if response.status_code >= 500:
        raise GitHubReviewUpstreamError(
            "GitHub returned an upstream "
            f"error while {operation}",
        )

    raise GitHubReviewUpstreamError(
        "GitHub request failed while "
        f"{operation}; status="
        f"{response.status_code}",
    )


def get_pull_request(
    *,
    client: httpx.Client,
    access_token: str,
    repository: str,
    pull_number: int,
) -> GitHubPullRequestSnapshot:
    if (
        not isinstance(
            pull_number,
            int,
        )
        or isinstance(
            pull_number,
            bool,
        )
        or pull_number <= 0
    ):
        raise ValueError(
            "GitHub pull number "
            "must be positive",
        )

    repository_ref = (
        parse_github_repository(
            repository,
        )
    )

    encoded_owner = quote(
        repository_ref.owner,
        safe="",
    )

    encoded_repository = quote(
        repository_ref.name,
        safe="",
    )

    response = _perform_request(
        client=client,
        method="GET",
        path=(
            f"/repos/{encoded_owner}/"
            f"{encoded_repository}/"
            f"pulls/{pull_number}"
        ),
        access_token=access_token,
    )

    _raise_for_response(
        response,
        operation=(
            "pull request lookup"
        ),
    )

    payload = _read_json_object(
        response,
        operation=(
            "reading pull request"
        ),
    )

    response_pull_number = (
        _require_positive_integer(
            payload.get(
                "number",
            ),
            field_name="number",
        )
    )

    return GitHubPullRequestSnapshot(
        repository=(
            repository_ref.full_name
        ),

        number=response_pull_number,

        title=_require_string(
            payload.get(
                "title",
            ),
            field_name="title",
        ),

        state=_require_string(
            payload.get(
                "state",
            ),
            field_name="state",
        ).lower(),

        merged=(
            payload.get(
                "merged",
            )
            is True
        ),

        draft=(
            payload.get(
                "draft",
            )
            is True
        ),

        html_url=_require_string(
            payload.get(
                "html_url",
            ),
            field_name="html_url",
        ),

        head_sha=(
            _read_nested_string(
                payload,
                object_name="head",
                field_name="sha",
            )
        ),

        head_ref=(
            _read_nested_string(
                payload,
                object_name="head",
                field_name="ref",
            )
        ),

        base_sha=(
            _read_nested_string(
                payload,
                object_name="base",
                field_name="sha",
            )
        ),

        base_ref=(
            _read_nested_string(
                payload,
                object_name="base",
                field_name="ref",
            )
        ),

        author_login=(
            _read_actor_login(
                payload,
            )
        ),
    )


def create_pull_request_review(
    *,
    client: httpx.Client,
    access_token: str,
    repository: str,
    pull_number: int,
    commit_id: str,
    event: str,
    body: str,
) -> GitHubPublishedReview:
    if (
        not isinstance(
            pull_number,
            int,
        )
        or isinstance(
            pull_number,
            bool,
        )
        or pull_number <= 0
    ):
        raise ValueError(
            "GitHub pull number "
            "must be positive",
        )

    normalized_commit_id = (
        str(commit_id or "")
        .strip()
    )

    if not normalized_commit_id:
        raise ValueError(
            "GitHub review commit_id "
            "is required",
        )

    normalized_event = (
        str(event or "")
        .strip()
        .upper()
    )

    if (
        normalized_event
        not in
        VALID_GITHUB_REVIEW_EVENTS
    ):
        raise ValueError(
            "GitHub review event "
            "must be COMMENT, APPROVE, "
            "or REQUEST_CHANGES",
        )

    normalized_body = str(
        body or "",
    )

    if (
        normalized_event
        in {
            "COMMENT",
            "REQUEST_CHANGES",
        }
        and not normalized_body.strip()
    ):
        raise ValueError(
            "GitHub review body "
            "is required for COMMENT "
            "and REQUEST_CHANGES",
        )

    repository_ref = (
        parse_github_repository(
            repository,
        )
    )

    encoded_owner = quote(
        repository_ref.owner,
        safe="",
    )

    encoded_repository = quote(
        repository_ref.name,
        safe="",
    )

    request_payload: dict[
        str,
        Any,
    ] = {
        "commit_id":
            normalized_commit_id,

        "event":
            normalized_event,
    }

    if normalized_body.strip():
        request_payload["body"] = (
            normalized_body
        )

    response = _perform_request(
        client=client,
        method="POST",
        path=(
            f"/repos/{encoded_owner}/"
            f"{encoded_repository}/"
            f"pulls/{pull_number}/reviews"
        ),
        access_token=access_token,
        json_payload=request_payload,
    )

    _raise_for_response(
        response,
        operation=(
            "review creation"
        ),
    )

    payload = _read_json_object(
        response,
        operation=(
            "creating pull request "
            "review"
        ),
    )

    return GitHubPublishedReview(
        review_id=(
            _require_positive_integer(
                payload.get(
                    "id",
                ),
                field_name="id",
            )
        ),

        state=_require_string(
            payload.get(
                "state",
            ),
            field_name="state",
        ),

        html_url=_require_string(
            payload.get(
                "html_url",
            ),
            field_name="html_url",
        ),

        body=_optional_string(
            payload.get(
                "body",
            ),
        ),

        commit_id=_require_string(
            payload.get(
                "commit_id",
            ),
            field_name="commit_id",
        ),

        submitted_at=(
            _parse_optional_datetime(
                payload.get(
                    "submitted_at",
                ),
                field_name=(
                    "submitted_at"
                ),
            )
        ),

        actor_login=(
            _read_actor_login(
                payload,
            )
        ),
    )


def create_github_review_client() -> (
    httpx.Client
):
    return httpx.Client(
        base_url=GITHUB_API_BASE_URL,
        timeout=(
            GITHUB_REQUEST_TIMEOUT_SECONDS
        ),
        follow_redirects=False,
    )