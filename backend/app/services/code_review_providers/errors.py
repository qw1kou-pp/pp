from __future__ import annotations


class CodeReviewSourceProviderError(
    RuntimeError,
):
    """
    所有 PR/MR Provider 异常的基类。
    """


class CodeReviewSourceNotFoundError(
    CodeReviewSourceProviderError,
):
    """
    PR/MR 不存在、不是公开资源，
    或当前凭据无权访问。
    """


class CodeReviewSourceRateLimitError(
    CodeReviewSourceProviderError,
):
    """
    上游平台拒绝请求，因为已经触发限流。
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int
        | None = None,
    ) -> None:
        super().__init__(message)

        self.retry_after_seconds = (
            retry_after_seconds
        )


class CodeReviewSourceTooLargeError(
    CodeReviewSourceProviderError,
):
    """
    上游返回的 Diff 超过允许大小。
    """

    def __init__(
        self,
        message: str,
        *,
        max_bytes: int,
    ) -> None:
        super().__init__(message)

        self.max_bytes = max_bytes


class CodeReviewSourceTimeoutError(
    CodeReviewSourceProviderError,
):
    """
    访问上游平台超时。
    """


class CodeReviewSourceInvalidResponseError(
    CodeReviewSourceProviderError,
):
    """
    上游返回成功状态，但内容结构不合法。
    """


class CodeReviewSourceUpstreamError(
    CodeReviewSourceProviderError,
):
    """
    上游返回其他无法处理的失败状态。
    """