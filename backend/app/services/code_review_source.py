from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

from app.models import CodeReviewSourceProvider


_ALLOWED_HOSTS: dict[
    str,
    CodeReviewSourceProvider,
] = {
    "github.com": "github",
    "www.github.com": "github",
    "gitlab.com": "gitlab",
    "www.gitlab.com": "gitlab",
}


_REPOSITORY_SEGMENT_PATTERN = re.compile(
    r"^[A-Za-z0-9._-]+$",
)


_CHANGE_NUMBER_PATTERN = re.compile(
    r"^[0-9]+$",
)


class CodeReviewSourceUrlError(
    ValueError,
):
    """
    表示用户提交的 PR/MR URL 不受支持
    或者不满足安全要求。
    """


@dataclass(
    frozen=True,
    slots=True,
)
class ParsedCodeReviewSourceUrl:
    """
    PR/MR URL 解析完成后的统一结果。

    GitHub 和 GitLab 的地址格式不同，
    但后续 Provider 只依赖这个统一结构。
    """

    provider: CodeReviewSourceProvider

    source_url: str

    repository: str

    change_number: int


def parse_code_review_source_url(
    source_url: str,
) -> ParsedCodeReviewSourceUrl:
    """
    解析并规范化公开 GitHub PR
    或 GitLab MR 地址。

    允许：
    - URL 末尾斜杠
    - 查询参数
    - 页面锚点
    - www.github.com
    - www.gitlab.com

    拒绝：
    - 非 HTTPS
    - 任意其他域名
    - 自定义端口
    - URL 用户名或密码
    - 编码路径分隔符
    - 非标准 PR/MR 路径
    """

    normalized_input = source_url.strip()

    if not normalized_input:
        raise CodeReviewSourceUrlError(
            "PR/MR 地址不能为空",
        )

    parsed = _split_source_url(
        normalized_input,
    )

    provider = _validate_url_origin(
        parsed,
    )

    path_segments = _parse_path_segments(
        parsed,
    )

    if provider == "github":
        return _parse_github_url(
            path_segments,
        )

    return _parse_gitlab_url(
        path_segments,
    )


def _split_source_url(
    source_url: str,
) -> SplitResult:
    """
    使用标准库拆分 URL。

    urlsplit 不会主动发起网络请求，
    这里只进行字符串结构解析。
    """

    try:
        parsed = urlsplit(
            source_url,
        )
    except ValueError as exc:
        raise CodeReviewSourceUrlError(
            "PR/MR 地址格式不合法",
        ) from exc

    if not parsed.scheme or not parsed.netloc:
        raise CodeReviewSourceUrlError(
            "PR/MR 地址必须是完整的 HTTPS URL",
        )

    return parsed


def _validate_url_origin(
    parsed: SplitResult,
) -> CodeReviewSourceProvider:
    """
    校验 URL 的协议、域名、端口和凭据。

    这一层只决定是否允许连接这个来源，
    不负责解析仓库路径。
    """

    if parsed.scheme.lower() != "https":
        raise CodeReviewSourceUrlError(
            "PR/MR 地址必须使用 HTTPS",
        )

    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise CodeReviewSourceUrlError(
            "PR/MR 地址不能包含用户名或密码",
        )

    try:
        port = parsed.port
    except ValueError as exc:
        raise CodeReviewSourceUrlError(
            "PR/MR 地址端口不合法",
        ) from exc

    if port is not None:
        raise CodeReviewSourceUrlError(
            "PR/MR 地址不能包含自定义端口",
        )

    hostname = (
        parsed.hostname
        or ""
    ).lower()

    provider = _ALLOWED_HOSTS.get(
        hostname,
    )

    if provider is None:
        raise CodeReviewSourceUrlError(
            "只支持 github.com 和 gitlab.com",
        )

    return provider


def _parse_path_segments(
    parsed: SplitResult,
) -> list[str]:
    """
    把 URL 路径拆成安全的非空片段。

    查询参数和页面锚点由 urlsplit
    单独保存，因此不会进入路径解析。
    """

    raw_path = parsed.path

    lowered_path = raw_path.lower()

    if (
        "%2f" in lowered_path
        or "%5c" in lowered_path
    ):
        raise CodeReviewSourceUrlError(
            "PR/MR 地址不能包含编码路径分隔符",
        )

    if "\\" in raw_path:
        raise CodeReviewSourceUrlError(
            "PR/MR 地址不能包含反斜杠",
        )

    if "//" in raw_path:
        raise CodeReviewSourceUrlError(
            "PR/MR 地址不能包含重复路径分隔符",
        )

    path_without_trailing_slash = (
        raw_path[:-1]
        if raw_path.endswith("/")
        else raw_path
    )

    normalized_path = (
        path_without_trailing_slash
        .strip("/")
    )

    if not normalized_path:
        raise CodeReviewSourceUrlError(
            "PR/MR 地址缺少仓库路径",
        )

    path_segments = (
        normalized_path.split("/")
    )

    if any(
        not segment
        for segment in path_segments
    ):
        raise CodeReviewSourceUrlError(
            "PR/MR 地址路径不完整",
        )

    return path_segments


def _parse_github_url(
    path_segments: list[str],
) -> ParsedCodeReviewSourceUrl:
    """
    解析 GitHub 地址：

    /{owner}/{repository}/pull/{number}
    """

    if (
        len(path_segments) != 4
        or path_segments[2] != "pull"
    ):
        raise CodeReviewSourceUrlError(
            "GitHub 地址必须符合 "
            "/owner/repository/pull/number",
        )

    owner = path_segments[0]
    repository_name = path_segments[1]

    _validate_repository_segment(
        owner,
    )

    _validate_repository_segment(
        repository_name,
    )

    change_number = _parse_change_number(
        path_segments[3],
    )

    repository = (
        f"{owner}/{repository_name}"
    )

    normalized_url = (
        "https://github.com/"
        f"{repository}/pull/"
        f"{change_number}"
    )

    return ParsedCodeReviewSourceUrl(
        provider="github",
        source_url=normalized_url,
        repository=repository,
        change_number=change_number,
    )


def _parse_gitlab_url(
    path_segments: list[str],
) -> ParsedCodeReviewSourceUrl:
    """
    解析 GitLab 地址：

    /{namespace}/{project}/-/merge_requests/{iid}

    namespace 可以包含多个层级。
    """

    if len(path_segments) < 5:
        raise CodeReviewSourceUrlError(
            "GitLab MR 地址路径不完整",
        )

    if (
        path_segments[-3] != "-"
        or path_segments[-2]
        != "merge_requests"
    ):
        raise CodeReviewSourceUrlError(
            "GitLab 地址必须符合 "
            "/namespace/project/"
            "-/merge_requests/iid",
        )

    repository_segments = (
        path_segments[:-3]
    )

    if len(repository_segments) < 2:
        raise CodeReviewSourceUrlError(
            "GitLab 地址必须包含命名空间和项目",
        )

    for segment in repository_segments:
        _validate_repository_segment(
            segment,
        )

    change_number = _parse_change_number(
        path_segments[-1],
    )

    repository = "/".join(
        repository_segments,
    )

    normalized_url = (
        "https://gitlab.com/"
        f"{repository}/-/merge_requests/"
        f"{change_number}"
    )

    return ParsedCodeReviewSourceUrl(
        provider="gitlab",
        source_url=normalized_url,
        repository=repository,
        change_number=change_number,
    )


def _validate_repository_segment(
    segment: str,
) -> None:
    """
    校验仓库路径中的单个名称。

    当前公开版只允许常见仓库路径字符，
    避免百分号编码和路径歧义。
    """

    if not _REPOSITORY_SEGMENT_PATTERN.fullmatch(
        segment,
    ):
        raise CodeReviewSourceUrlError(
            "仓库路径包含不支持的字符",
        )

    if segment in {".", ".."}:
        raise CodeReviewSourceUrlError(
            "仓库路径不能包含相对路径片段",
        )


def _parse_change_number(
    raw_change_number: str,
) -> int:
    """
    把 GitHub PR Number 或 GitLab MR IID
    转换为正整数。
    """

    if not _CHANGE_NUMBER_PATTERN.fullmatch(
        raw_change_number,
    ):
        raise CodeReviewSourceUrlError(
            "PR/MR 编号必须是正整数",
        )

    change_number = int(
        raw_change_number,
    )

    if change_number < 1:
        raise CodeReviewSourceUrlError(
            "PR/MR 编号必须大于 0",
        )

    return change_number