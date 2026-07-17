from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from app.models import (
    CodeReviewSourceResolvedPublic,
)
from app.services.code_review_providers.errors import (
    CodeReviewSourceInvalidResponseError,
    CodeReviewSourceNotFoundError,
    CodeReviewSourceRateLimitError,
    CodeReviewSourceTimeoutError,
    CodeReviewSourceTooLargeError,
    CodeReviewSourceUpstreamError,
)
from app.services.code_review_source import (
    ParsedCodeReviewSourceUrl,
)


GITHUB_API_BASE_URL = (
    "https://api.github.com"
)

GITHUB_API_VERSION = "2026-03-10"

DEFAULT_GITHUB_TIMEOUT_SECONDS = 15.0

DEFAULT_MAX_DIFF_BYTES = (
    1024 * 1024 * 1024
)

_GITHUB_USER_AGENT = "RepoGuard"

_GITHUB_JSON_MEDIA_TYPE = (
    "application/vnd.github+json"
)

_GITHUB_DIFF_MEDIA_TYPE = (
    "application/vnd.github.diff"
)


async def resolve_github_pull_request(
    source: ParsedCodeReviewSourceUrl,
    *,
    client: httpx.AsyncClient
    | None = None,
    token: str | None = None,
    max_diff_bytes: int = (
        DEFAULT_MAX_DIFF_BYTES
    ),
) -> CodeReviewSourceResolvedPublic:
    """
    获取公开 GitHub Pull Request
    的元数据和标准 Git Diff。

    token 是内部预留参数。
    当前 API 和前端不会接收用户 Token。
    """

    if source.provider != "github":
        raise ValueError(
            "GitHub Provider 只能处理 "
            "provider='github' 的来源",
        )

    if max_diff_bytes < 1:
        raise ValueError(
            "max_diff_bytes 必须大于 0",
        )

    endpoint = _build_pull_request_endpoint(
        source,
    )

    owns_client = client is None

    if client is None:
        client = httpx.AsyncClient(
            timeout=(
                DEFAULT_GITHUB_TIMEOUT_SECONDS
            ),
            follow_redirects=False,
            trust_env=False,
        )

    try:
        metadata = await _fetch_metadata(
            client,
            endpoint=endpoint,
            token=token,
        )

        diff_bytes = await _fetch_diff(
            client,
            endpoint=endpoint,
            token=token,
            max_diff_bytes=max_diff_bytes,
        )
    except httpx.TimeoutException as exc:
        raise CodeReviewSourceTimeoutError(
            "连接 GitHub 超时",
        ) from exc
    except httpx.RequestError as exc:
        raise CodeReviewSourceUpstreamError(
            "无法连接 GitHub",
        ) from exc
    finally:
        if owns_client:
            await client.aclose()

    diff_text = _decode_diff(
        diff_bytes,
    )

    return _build_resolved_source(
        source=source,
        metadata=metadata,
        diff_text=diff_text,
        diff_bytes=diff_bytes,
    )


def _build_pull_request_endpoint(
    source: ParsedCodeReviewSourceUrl,
) -> str:
    """
    根据已解析仓库名称构造固定 API URL。

    不使用用户提供的完整 URL 发起请求。
    """

    repository_parts = (
        source.repository.split("/")
    )

    if (
        len(repository_parts) != 2
        or not all(repository_parts)
    ):
        raise ValueError(
            "GitHub 仓库名称必须符合 "
            "owner/repository",
        )

    owner = quote(
        repository_parts[0],
        safe="._-",
    )

    repository = quote(
        repository_parts[1],
        safe="._-",
    )

    return (
        f"{GITHUB_API_BASE_URL}/repos/"
        f"{owner}/{repository}/pulls/"
        f"{source.change_number}"
    )


def _build_headers(
    *,
    accept: str,
    token: str | None,
) -> dict[str, str]:
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": (
            GITHUB_API_VERSION
        ),
        "User-Agent": _GITHUB_USER_AGENT,
    }

    if token:
        headers["Authorization"] = (
            f"Bearer {token}"
        )

    return headers


async def _fetch_metadata(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    token: str | None,
) -> dict[str, Any]:
    response = await client.get(
        endpoint,
        headers=_build_headers(
            accept=(
                _GITHUB_JSON_MEDIA_TYPE
            ),
            token=token,
        ),
        timeout=(
            DEFAULT_GITHUB_TIMEOUT_SECONDS
        ),
        follow_redirects=False,
    )

    _raise_for_github_status(
        response,
    )

    try:
        payload = response.json()
    except ValueError as exc:
        raise (
            CodeReviewSourceInvalidResponseError(
                "GitHub PR 元数据不是合法 JSON",
            )
        ) from exc

    if not isinstance(payload, dict):
        raise CodeReviewSourceInvalidResponseError(
            "GitHub PR 元数据结构不合法",
        )

    return payload


async def _fetch_diff(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    token: str | None,
    max_diff_bytes: int,
) -> bytes:
    """
    流式读取 Diff。

    同时检查 Content-Length 和实际读取大小，
    防止上游未提供或伪造长度。
    """

    async with client.stream(
        "GET",
        endpoint,
        headers=_build_headers(
            accept=(
                _GITHUB_DIFF_MEDIA_TYPE
            ),
            token=token,
        ),
        timeout=(
            DEFAULT_GITHUB_TIMEOUT_SECONDS
        ),
        follow_redirects=False,
    ) as response:
        if not (
            200
            <= response.status_code
            < 300
        ):
            await response.aread()

            _raise_for_github_status(
                response,
            )

        _validate_content_length(
            response,
            max_diff_bytes=max_diff_bytes,
        )

        chunks: list[bytes] = []
        total_bytes = 0

        async for chunk in (
            response.aiter_bytes()
        ):
            total_bytes += len(chunk)

            if total_bytes > max_diff_bytes:
                raise (
                    CodeReviewSourceTooLargeError(
                        "GitHub PR Diff "
                        "超过大小限制",
                        max_bytes=(
                            max_diff_bytes
                        ),
                    )
                )

            chunks.append(chunk)

    return b"".join(chunks)


def _validate_content_length(
    response: httpx.Response,
    *,
    max_diff_bytes: int,
) -> None:
    raw_content_length = (
        response.headers.get(
            "content-length",
        )
    )

    if raw_content_length is None:
        return

    try:
        content_length = int(
            raw_content_length,
        )
    except ValueError:
        return

    if content_length > max_diff_bytes:
        raise CodeReviewSourceTooLargeError(
            "GitHub PR Diff 超过大小限制",
            max_bytes=max_diff_bytes,
        )


def _decode_diff(
    diff_bytes: bytes,
) -> str:
    if not diff_bytes:
        raise CodeReviewSourceInvalidResponseError(
            "GitHub PR Diff 为空",
        )

    try:
        diff_text = diff_bytes.decode(
            "utf-8",
        )
    except UnicodeDecodeError as exc:
        raise (
            CodeReviewSourceInvalidResponseError(
                "GitHub PR Diff "
                "不是有效 UTF-8 文本",
            )
        ) from exc

    normalized_start = diff_text.lstrip(
        "\ufeff \t\r\n",
    )

    if not normalized_start.startswith(
        "diff --git ",
    ):
        raise CodeReviewSourceInvalidResponseError(
            "GitHub 返回内容不是标准 Git Diff",
        )

    return diff_text


def _build_resolved_source(
    *,
    source: ParsedCodeReviewSourceUrl,
    metadata: dict[str, Any],
    diff_text: str,
    diff_bytes: bytes,
) -> CodeReviewSourceResolvedPublic:
    title = _required_string(
        metadata,
        "title",
    )

    base_ref = _required_string(
        metadata,
        "base",
        "ref",
    )

    base_sha = _required_string(
        metadata,
        "base",
        "sha",
    )

    head_ref = _required_string(
        metadata,
        "head",
        "ref",
    )

    head_sha = _required_string(
        metadata,
        "head",
        "sha",
    )

    author = _optional_string(
        metadata,
        "user",
        "login",
    )

    try:
        return (
            CodeReviewSourceResolvedPublic(
                provider="github",
                source_url=source.source_url,
                repository=source.repository,
                change_number=(
                    source.change_number
                ),
                title=title,
                author=author,
                base_ref=base_ref,
                head_ref=head_ref,
                base_sha=base_sha,
                head_sha=head_sha,
                diff_hash=hashlib.sha256(
                    diff_bytes,
                ).hexdigest(),
                fetched_at=datetime.now(
                    timezone.utc,
                ),
                diff_text=diff_text,
            )
        )
    except ValidationError as exc:
        raise (
            CodeReviewSourceInvalidResponseError(
                "GitHub PR 元数据字段不合法",
            )
        ) from exc


def _required_string(
    payload: dict[str, Any],
    *path: str,
) -> str:
    current: Any = payload

    for key in path:
        if not isinstance(
            current,
            dict,
        ):
            raise (
                CodeReviewSourceInvalidResponseError(
                    "GitHub PR 元数据缺少字段："
                    + ".".join(path)
                )
            )

        current = current.get(key)

    if (
        not isinstance(current, str)
        or not current.strip()
    ):
        raise CodeReviewSourceInvalidResponseError(
            "GitHub PR 元数据缺少字段："
            + ".".join(path),
        )

    return current.strip()


def _optional_string(
    payload: dict[str, Any],
    *path: str,
) -> str | None:
    current: Any = payload

    for key in path:
        if not isinstance(
            current,
            dict,
        ):
            return None

        current = current.get(key)

    if not isinstance(current, str):
        return None

    normalized = current.strip()

    return normalized or None


def _raise_for_github_status(
    response: httpx.Response,
) -> None:
    status_code = response.status_code

    if 200 <= status_code < 300:
        return

    if _is_rate_limited(response):
        raise CodeReviewSourceRateLimitError(
            "GitHub API 请求已达到限流上限",
            retry_after_seconds=(
                _parse_retry_after_seconds(
                    response,
                )
            ),
        )

    if status_code in {
        401,
        403,
        404,
    }:
        raise CodeReviewSourceNotFoundError(
            "无法访问该 GitHub Pull Request。"
            "请确认地址正确且仓库为公开仓库。",
        )

    if status_code >= 500:
        raise CodeReviewSourceUpstreamError(
            "GitHub 服务暂时不可用",
        )

    raise CodeReviewSourceUpstreamError(
        "GitHub 返回了无法处理的响应："
        f"{status_code}",
    )


def _is_rate_limited(
    response: httpx.Response,
) -> bool:
    if response.status_code == 429:
        return True

    if response.status_code != 403:
        return False

    if (
        response.headers.get(
            "x-ratelimit-remaining",
        )
        == "0"
    ):
        return True

    if (
        response.headers.get(
            "retry-after",
        )
        is not None
    ):
        return True

    try:
        response_text = (
            response.text.lower()
        )
    except httpx.ResponseNotRead:
        return False

    return (
        "rate limit" in response_text
        or "secondary rate" in response_text
        or "abuse detection" in response_text
    )


def _parse_retry_after_seconds(
    response: httpx.Response,
) -> int | None:
    raw_retry_after = (
        response.headers.get(
            "retry-after",
        )
    )

    if (
        raw_retry_after is not None
        and raw_retry_after.isdigit()
    ):
        return int(raw_retry_after)

    raw_reset_time = (
        response.headers.get(
            "x-ratelimit-reset",
        )
    )

    if (
        raw_reset_time is None
        or not raw_reset_time.isdigit()
    ):
        return None

    reset_timestamp = int(
        raw_reset_time,
    )

    return max(
        0,
        reset_timestamp
        - int(time.time()),
    )