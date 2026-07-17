from __future__ import annotations

import hashlib
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


GITLAB_API_BASE_URL = (
    "https://gitlab.com/api/v4"
)

DEFAULT_GITLAB_TIMEOUT_SECONDS = 15.0

DEFAULT_MAX_DIFF_BYTES = (
    2 * 1024 * 1024
)

_GITLAB_USER_AGENT = "RepoGuard"

_GITLAB_JSON_MEDIA_TYPE = (
    "application/json"
)

_GITLAB_DIFF_MEDIA_TYPE = "text/plain"


async def resolve_gitlab_merge_request(
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
    获取公开 GitLab Merge Request
    的元数据和原始 Git Diff。

    token 是内部预留参数。
    当前 API 和前端不会接收用户 Token。
    """

    if source.provider != "gitlab":
        raise ValueError(
            "GitLab Provider 只能处理 "
            "provider='gitlab' 的来源",
        )

    if max_diff_bytes < 1:
        raise ValueError(
            "max_diff_bytes 必须大于 0",
        )

    (
        metadata_endpoint,
        diff_endpoint,
    ) = _build_merge_request_endpoints(
        source,
    )

    owns_client = client is None

    if client is None:
        client = httpx.AsyncClient(
            timeout=(
                DEFAULT_GITLAB_TIMEOUT_SECONDS
            ),
            follow_redirects=False,
            trust_env=False,
        )

    try:
        metadata = await _fetch_metadata(
            client,
            endpoint=metadata_endpoint,
            token=token,
        )

        diff_bytes = await _fetch_diff(
            client,
            endpoint=diff_endpoint,
            token=token,
            max_diff_bytes=max_diff_bytes,
        )

    except httpx.TimeoutException as exc:
        raise CodeReviewSourceTimeoutError(
            "连接 GitLab 超时",
        ) from exc

    except httpx.RequestError as exc:
        raise CodeReviewSourceUpstreamError(
            "无法连接 GitLab",
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


def _build_merge_request_endpoints(
    source: ParsedCodeReviewSourceUrl,
) -> tuple[str, str]:
    """
    根据已经校验过的仓库路径，
    构造固定 GitLab API 地址。

    整个 namespace/project 路径
    作为一个项目 ID 进行 URL 编码。
    """

    repository = (
        source.repository.strip("/")
    )

    if not repository:
        raise ValueError(
            "GitLab 仓库路径不能为空",
        )

    repository_segments = (
        repository.split("/")
    )

    if (
        len(repository_segments) < 2
        or not all(repository_segments)
    ):
        raise ValueError(
            "GitLab 仓库名称必须包含"
            "命名空间和项目名称",
        )

    encoded_repository = quote(
        repository,
        safe="",
    )

    metadata_endpoint = (
        f"{GITLAB_API_BASE_URL}/"
        f"projects/{encoded_repository}/"
        f"merge_requests/"
        f"{source.change_number}"
    )

    diff_endpoint = (
        f"{metadata_endpoint}/raw_diffs"
    )

    return (
        metadata_endpoint,
        diff_endpoint,
    )


def _build_headers(
    *,
    accept: str,
    token: str | None,
) -> dict[str, str]:
    """
    构造 GitLab API 请求头。

    Token 只通过 Header 发送，
    不放入 URL 查询参数。
    """

    headers = {
        "Accept": accept,
        "User-Agent": _GITLAB_USER_AGENT,
    }

    if token:
        headers["PRIVATE-TOKEN"] = token

    return headers


async def _fetch_metadata(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    token: str | None,
) -> dict[str, Any]:
    """
    获取 GitLab MR 元数据。
    """

    response = await client.get(
        endpoint,
        headers=_build_headers(
            accept=(
                _GITLAB_JSON_MEDIA_TYPE
            ),
            token=token,
        ),
        timeout=(
            DEFAULT_GITLAB_TIMEOUT_SECONDS
        ),
        follow_redirects=False,
    )

    _raise_for_gitlab_status(
        response,
    )

    try:
        payload = response.json()

    except ValueError as exc:
        raise (
            CodeReviewSourceInvalidResponseError(
                "GitLab MR 元数据"
                "不是合法 JSON",
            )
        ) from exc

    if not isinstance(payload, dict):
        raise CodeReviewSourceInvalidResponseError(
            "GitLab MR 元数据结构不合法",
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
    流式读取 GitLab raw diff。

    同时校验 Content-Length
    和实际读取字节数。
    """

    async with client.stream(
        "GET",
        endpoint,
        headers=_build_headers(
            accept=(
                _GITLAB_DIFF_MEDIA_TYPE
            ),
            token=token,
        ),
        timeout=(
            DEFAULT_GITLAB_TIMEOUT_SECONDS
        ),
        follow_redirects=False,
    ) as response:
        if not (
            200
            <= response.status_code
            < 300
        ):
            await response.aread()

            _raise_for_gitlab_status(
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
                        "GitLab MR Diff "
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
    """
    上游声明 Content-Length 时，
    在读取正文前先判断是否超限。
    """

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
            "GitLab MR Diff 超过大小限制",
            max_bytes=max_diff_bytes,
        )


def _decode_diff(
    diff_bytes: bytes,
) -> str:
    """
    将原始字节转为 UTF-8 Git Diff，
    并拒绝 HTML、JSON 和空响应。
    """

    if not diff_bytes:
        raise CodeReviewSourceInvalidResponseError(
            "GitLab MR Diff 为空",
        )

    try:
        diff_text = diff_bytes.decode(
            "utf-8",
        )

    except UnicodeDecodeError as exc:
        raise (
            CodeReviewSourceInvalidResponseError(
                "GitLab MR Diff "
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
            "GitLab 返回内容"
            "不是标准 Git Diff",
        )

    return diff_text


def _build_resolved_source(
    *,
    source: ParsedCodeReviewSourceUrl,
    metadata: dict[str, Any],
    diff_text: str,
    diff_bytes: bytes,
) -> CodeReviewSourceResolvedPublic:
    """
    从 GitLab 特有字段中提取信息，
    转换成统一的 RepoGuard 来源模型。
    """

    title = _required_string(
        metadata,
        "title",
    )

    base_ref = _required_string(
        metadata,
        "target_branch",
    )

    head_ref = _required_string(
        metadata,
        "source_branch",
    )

    base_sha = _required_string(
        metadata,
        "diff_refs",
        "base_sha",
    )

    head_sha = _required_string(
        metadata,
        "diff_refs",
        "head_sha",
    )

    author = _optional_string(
        metadata,
        "author",
        "username",
    )

    try:
        return (
            CodeReviewSourceResolvedPublic(
                provider="gitlab",
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
                "GitLab MR 元数据字段不合法",
            )
        ) from exc


def _required_string(
    payload: dict[str, Any],
    *path: str,
) -> str:
    """
    从嵌套 JSON 中读取必需字符串。
    """

    current: Any = payload

    for key in path:
        if not isinstance(
            current,
            dict,
        ):
            raise (
                CodeReviewSourceInvalidResponseError(
                    "GitLab MR 元数据"
                    "缺少字段："
                    + ".".join(path)
                )
            )

        current = current.get(key)

    if (
        not isinstance(current, str)
        or not current.strip()
    ):
        raise CodeReviewSourceInvalidResponseError(
            "GitLab MR 元数据缺少字段："
            + ".".join(path),
        )

    return current.strip()


def _optional_string(
    payload: dict[str, Any],
    *path: str,
) -> str | None:
    """
    从嵌套 JSON 中读取可选字符串。
    """

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


def _raise_for_gitlab_status(
    response: httpx.Response,
) -> None:
    """
    将 GitLab HTTP 状态映射成
    RepoGuard 统一 Provider 异常。
    """

    status_code = response.status_code

    if 200 <= status_code < 300:
        return

    if _is_rate_limited(
        response,
    ):
        raise CodeReviewSourceRateLimitError(
            "GitLab API 请求"
            "已达到限流上限",
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
            "无法访问该 GitLab "
            "Merge Request。"
            "请确认地址正确且仓库为公开仓库。",
        )

    if status_code == 408:
        raise CodeReviewSourceTimeoutError(
            "GitLab 处理请求超时",
        )

    if status_code >= 500:
        raise CodeReviewSourceUpstreamError(
            "GitLab 服务暂时不可用",
        )

    raise CodeReviewSourceUpstreamError(
        "GitLab 返回了"
        "无法处理的响应："
        f"{status_code}",
    )


def _is_rate_limited(
    response: httpx.Response,
) -> bool:
    """
    判断响应是否代表 GitLab 限流。
    """

    if response.status_code == 429:
        return True

    if response.status_code != 403:
        return False

    if (
        response.headers.get(
            "ratelimit-remaining",
        )
        == "0"
    ):
        return True

    return (
        response.headers.get(
            "retry-after",
        )
        is not None
    )


def _parse_retry_after_seconds(
    response: httpx.Response,
) -> int | None:
    """
    读取建议等待时间。

    只接受非负整数秒数。
    """

    raw_retry_after = (
        response.headers.get(
            "retry-after",
        )
    )

    if (
        raw_retry_after is None
        or not raw_retry_after.isdigit()
    ):
        return None

    return int(
        raw_retry_after,
    )