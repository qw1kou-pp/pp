from __future__ import annotations

import httpx

from app.models import (
    CodeReviewSourceResolvedPublic,
)
from app.services.code_review_providers.github import (
    resolve_github_pull_request,
)
from app.services.code_review_providers.gitlab import (
    resolve_gitlab_merge_request,
)
from app.services.code_review_source import (
    parse_code_review_source_url,
)


DEFAULT_MAX_SOURCE_DIFF_BYTES = (
    1024 * 1024 * 1024
)


async def resolve_code_review_source(
    source_url: str,
    *,
    client: httpx.AsyncClient
    | None = None,
    github_token: str | None = None,
    gitlab_token: str | None = None,
    max_diff_bytes: int = (
        DEFAULT_MAX_SOURCE_DIFF_BYTES
    ),
) -> CodeReviewSourceResolvedPublic:
    """
    解析并获取公开 GitHub PR
    或 GitLab MR 的来源信息和 Diff。

    这是 API Route 后续调用的统一入口。
    Route 不需要直接依赖具体 Provider。
    """

    if max_diff_bytes < 1:
        raise ValueError(
            "max_diff_bytes 必须大于 0",
        )

    parsed_source = (
        parse_code_review_source_url(
            source_url,
        )
    )

    if parsed_source.provider == "github":
        return await (
            resolve_github_pull_request(
                parsed_source,
                client=client,
                token=github_token,
                max_diff_bytes=max_diff_bytes,
            )
        )

    if parsed_source.provider == "gitlab":
        return await (
            resolve_gitlab_merge_request(
                parsed_source,
                client=client,
                token=gitlab_token,
                max_diff_bytes=max_diff_bytes,
            )
        )

    raise RuntimeError(
        "URL 解析器返回了"
        "不支持的代码托管平台",
    )