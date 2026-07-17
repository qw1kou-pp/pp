from __future__ import annotations

import hmac
import logging
import uuid
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, cast

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.models import (
    CodeReviewPublication,
    CodeReviewRun,
)
from app.services.code_review_publication_repository import (
    CodeReviewAlreadyPublishedError,
    CodeReviewPublicationAttemptInput,
    CodeReviewPublicationInProgressError,
    CodeReviewPublicationReviewRunNotFoundError,
    begin_code_review_publication,
    count_successful_code_review_publications,
    mark_code_review_publication_failed,
    mark_code_review_publication_succeeded,
)
from app.services.code_review_publication_repository import list_code_review_publications as list_code_review_publication_records
from app.services.github_app_auth import (
    GitHubAppAuthConfig,
    GitHubAppNotConfiguredError,
    GitHubAppPrivateKeyError,
    load_github_app_auth_config,
)
from app.services.github_app_installation import (
    GitHubAppAuthenticationRejectedError,
    GitHubAppInvalidResponseError,
    GitHubAppNotInstalledError,
    GitHubAppPermissionDeniedError,
    GitHubAppRateLimitedError,
    GitHubAppRequestTimeoutError,
    GitHubAppUpstreamError,
    GitHubRepositoryAccess,
    create_repository_installation_access,
)
from app.services.github_review_body import (
    GitHubReviewBodyContext,
    GitHubReviewBodyError,
    build_github_review_body,
    compute_github_review_body_hash,
)
from app.services.github_review_client import (
    GitHubPullRequestNotFoundError,
    GitHubPullRequestSnapshot,
    GitHubReviewAuthenticationError,
    GitHubReviewEvent,
    GitHubReviewInvalidResponseError,
    GitHubReviewPermissionDeniedError,
    GitHubReviewRateLimitedError,
    GitHubReviewRejectedError,
    GitHubReviewRequestTimeoutError,
    GitHubReviewUpstreamError,
    create_github_review_client,
    create_pull_request_review,
    get_pull_request,
)


logger = logging.getLogger(
    __name__,
)


@dataclass(
    frozen=True,
    slots=True,
)
class CodeReviewPublicationCommand:
    knowledge_base_id: uuid.UUID
    review_run_id: uuid.UUID
    owner_id: uuid.UUID

    requested_event: (
        str | None
    ) = None

    force_republish: bool = False


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubReviewTarget:
    repository: str
    pull_number: int
    source_url: str
    reviewed_head_sha: str


@dataclass(
    frozen=True,
    slots=True,
)
class CodeReviewPublicationResult:
    publication: (
        CodeReviewPublication
    )

    pull_request: (
        GitHubPullRequestSnapshot
    )

    requested_event: (
        GitHubReviewEvent
    )


@dataclass(
    frozen=True,
    slots=True,
)
class CodeReviewPublicationPreviewResult:
    review_run_id: uuid.UUID

    target: GitHubReviewTarget

    default_event: (
        GitHubReviewEvent
    )

    allowed_events: tuple[
        GitHubReviewEvent,
        ...,
    ]

    body_markdown: str
    body_hash: str

    successful_publication_count: int

    publications: tuple[
        CodeReviewPublication,
        ...,
    ]

    @property
    def already_published(
        self,
    ) -> bool:
        return (
            self
            .successful_publication_count
            > 0
        )

    @property
    def latest_publication(
        self,
    ) -> (
        CodeReviewPublication | None
    ):
        if not self.publications:
            return None

        return self.publications[0]


class CodeReviewPublicationServiceError(
    RuntimeError,
):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        retryable: bool = False,
        context: (
            dict[str, Any] | None
        ) = None,
    ) -> None:
        super().__init__(
            message,
        )

        self.code = code
        self.message = message
        self.retryable = retryable
        self.context = context or {}


def recommend_github_review_event(
    *,
    risk_level: str | None,
    merge_recommendation: (
        str | None
    ),
) -> GitHubReviewEvent:
    normalized_risk = str(
        risk_level or "",
    ).strip().lower()

    normalized_recommendation = str(
        merge_recommendation or "",
    ).strip().lower()

    if (
        normalized_risk == "low"
        and normalized_recommendation
        == "approve"
    ):
        return "APPROVE"

    if (
        normalized_risk == "high"
        or normalized_recommendation
        == "request_changes"
    ):
        return "REQUEST_CHANGES"

    return "COMMENT"


def _load_review_run(
    *,
    session: Session,
    command: (
        CodeReviewPublicationCommand
    ),
) -> CodeReviewRun:
    statement = (
        select(
            CodeReviewRun,
        )
        .where(
            CodeReviewRun.id
            == command.review_run_id,

            CodeReviewRun
            .knowledge_base_id
            == command
            .knowledge_base_id,

            CodeReviewRun.owner_id
            == command.owner_id,
        )
    )

    review_run = session.exec(
        statement,
    ).first()

    if review_run is None:
        raise (
            CodeReviewPublicationServiceError(
                code=(
                    "REVIEW_RUN_NOT_FOUND"
                ),

                message=(
                    "代码审查历史不存在，"
                    "或者当前用户无权访问。"
                ),
            )
        )

    return review_run


def _extract_github_target(
    review_run: CodeReviewRun,
) -> GitHubReviewTarget:
    if (
        review_run.generation_status
        != "completed"
    ):
        raise (
            CodeReviewPublicationServiceError(
                code=(
                    "REVIEW_NOT_COMPLETED"
                ),

                message=(
                    "该审查没有完整的 "
                    "AI Review 报告。"
                ),
            )
        )

    if (
        not isinstance(
            review_run
            .review_report_json,
            dict,
        )
        or not review_run
        .review_report_json
    ):
        raise (
            CodeReviewPublicationServiceError(
                code=(
                    "REVIEW_NOT_COMPLETED"
                ),

                message=(
                    "该审查没有可发布的"
                    "结构化报告。"
                ),
            )
        )

    provider = str(
        review_run.source_provider
        or "",
    ).strip().lower()

    if provider != "github":
        raise (
            CodeReviewPublicationServiceError(
                code=(
                    "REVIEW_SOURCE_NOT_GITHUB"
                ),

                message=(
                    "当前 Review 不是来自 "
                    "GitHub Pull Request。"
                ),
            )
        )

    repository = str(
        review_run.source_repository
        or "",
    ).strip()

    source_url = str(
        review_run.source_url
        or "",
    ).strip()

    reviewed_head_sha = str(
        review_run.source_head_sha
        or "",
    ).strip()

    pull_number = (
        review_run.source_change_number
    )

    if (
        not repository
        or not source_url
        or not reviewed_head_sha
        or not isinstance(
            pull_number,
            int,
        )
        or pull_number <= 0
    ):
        raise (
            CodeReviewPublicationServiceError(
                code=(
                    "REVIEW_SOURCE_INCOMPLETE"
                ),

                message=(
                    "GitHub 来源快照不完整，"
                    "请重新导入 PR 并生成 Review。"
                ),
            )
        )

    return GitHubReviewTarget(
        repository=repository,
        pull_number=pull_number,
        source_url=source_url,
        reviewed_head_sha=(
            reviewed_head_sha
        ),
    )


def _resolve_requested_event(
    *,
    review_run: CodeReviewRun,
    requested_event: (
        str | None
    ),
) -> GitHubReviewEvent:
    if requested_event is None:
        return (
            recommend_github_review_event(
                risk_level=(
                    review_run.risk_level
                ),

                merge_recommendation=(
                    review_run
                    .merge_recommendation
                ),
            )
        )

    normalized_event = str(
        requested_event,
    ).strip().upper()

    if normalized_event not in {
        "COMMENT",
        "APPROVE",
        "REQUEST_CHANGES",
    }:
        raise (
            CodeReviewPublicationServiceError(
                code=(
                    "INVALID_REVIEW_EVENT"
                ),

                message=(
                    "Review 状态必须是 "
                    "COMMENT、APPROVE 或 "
                    "REQUEST_CHANGES。"
                ),
            )
        )

    return cast(
        GitHubReviewEvent,
        normalized_event,
    )


def _build_publication_body(
    *,
    review_run: CodeReviewRun,
    target: GitHubReviewTarget,
) -> tuple[str, str]:
    try:
        body_markdown = (
            build_github_review_body(
                GitHubReviewBodyContext(
                    review_run_id=str(
                        review_run.id,
                    ),

                    review_title=(
                        review_run.title
                    ),

                    repository=(
                        target.repository
                    ),

                    pull_number=(
                        target.pull_number
                    ),

                    head_sha=(
                        target
                        .reviewed_head_sha
                    ),

                    language=(
                        review_run.language
                    ),

                    risk_level=(
                        review_run.risk_level
                    ),

                    merge_recommendation=(
                        review_run
                        .merge_recommendation
                    ),

                    review_report=(
                        review_run
                        .review_report_json
                        or {}
                    ),
                )
            )
        )

        body_hash = (
            compute_github_review_body_hash(
                body_markdown,
            )
        )

    except GitHubReviewBodyError as exc:
        raise (
            CodeReviewPublicationServiceError(
                code=(
                    "REVIEW_BODY_INVALID"
                ),

                message=(
                    "无法根据历史报告生成 "
                    "GitHub Review 正文。"
                ),
            )
        ) from exc

    return (
        body_markdown,
        body_hash,
    )


def _resolve_repository_access(
    *,
    target: GitHubReviewTarget,
    repository_access: (
        GitHubRepositoryAccess
        | None
    ),
    auth_config: (
        GitHubAppAuthConfig | None
    ),
) -> GitHubRepositoryAccess:
    if repository_access is not None:
        token_repository = (
            repository_access
            .access_token
            .repository
        )

        if (
            token_repository.lower()
            != target.repository.lower()
        ):
            raise (
                CodeReviewPublicationServiceError(
                    code=(
                        "GITHUB_ACCESS_"
                        "REPOSITORY_MISMATCH"
                    ),

                    message=(
                        "Installation Token "
                        "与目标仓库不一致。"
                    ),
                )
            )

        return repository_access

    resolved_config = auth_config

    if resolved_config is None:
        resolved_config = (
            load_github_app_auth_config(
                app_id=(
                    settings.GITHUB_APP_ID
                ),

                private_key_path=(
                    settings
                    .GITHUB_APP_PRIVATE_KEY_PATH
                ),
            )
        )

    return (
        create_repository_installation_access(
            config=resolved_config,
            repository=(
                target.repository
            ),
        )
    )


def _map_dependency_error(
    error: Exception,
) -> CodeReviewPublicationServiceError:
    if isinstance(
        error,
        CodeReviewAlreadyPublishedError,
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "REVIEW_ALREADY_PUBLISHED"
                ),

                message=(
                    "该 Review 已经成功"
                    "发布到 GitHub。"
                ),
            )
        )

    if isinstance(
        error,
        CodeReviewPublicationInProgressError,
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "REVIEW_PUBLICATION_"
                    "IN_PROGRESS"
                ),

                message=(
                    "该 Review 当前正在发布。"
                ),

                retryable=True,
            )
        )

    if isinstance(
        error,
        CodeReviewPublicationReviewRunNotFoundError,
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "REVIEW_RUN_NOT_FOUND"
                ),

                message=(
                    "代码审查历史不存在，"
                    "或者当前用户无权访问。"
                ),
            )
        )

    if isinstance(
        error,
        GitHubAppNotConfiguredError,
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_APP_NOT_CONFIGURED"
                ),

                message=(
                    "后端尚未完成 "
                    "GitHub App 配置。"
                ),
            )
        )

    if isinstance(
        error,
        GitHubAppPrivateKeyError,
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_APP_"
                    "PRIVATE_KEY_INVALID"
                ),

                message=(
                    "GitHub App 私钥"
                    "无法读取或格式无效。"
                ),
            )
        )

    if isinstance(
        error,
        GitHubAppNotInstalledError,
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_APP_NOT_INSTALLED"
                ),

                message=(
                    "GitHub App 尚未安装到"
                    "目标仓库。"
                ),
            )
        )

    if isinstance(
        error,
        (
            GitHubAppPermissionDeniedError,
            GitHubReviewPermissionDeniedError,
        ),
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_APP_"
                    "PERMISSION_DENIED"
                ),

                message=(
                    "GitHub App 缺少 "
                    "Pull requests: write 权限。"
                ),
            )
        )

    if isinstance(
        error,
        (
            GitHubAppAuthenticationRejectedError,
            GitHubReviewAuthenticationError,
        ),
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_APP_"
                    "AUTHENTICATION_REJECTED"
                ),

                message=(
                    "GitHub 拒绝了 App 认证。"
                ),
            )
        )

    if isinstance(
        error,
        GitHubPullRequestNotFoundError,
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_PR_NOT_FOUND"
                ),

                message=(
                    "GitHub 上找不到目标 PR。"
                ),
            )
        )

    if isinstance(
        error,
        (
            GitHubAppRateLimitedError,
            GitHubReviewRateLimitedError,
        ),
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_RATE_LIMITED"
                ),

                message=(
                    "GitHub API 当前受到"
                    "速率限制，请稍后重试。"
                ),

                retryable=True,
            )
        )

    if isinstance(
        error,
        (
            GitHubAppRequestTimeoutError,
            GitHubReviewRequestTimeoutError,
        ),
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_REQUEST_TIMEOUT"
                ),

                message=(
                    "GitHub 请求超时，"
                    "可以稍后重试。"
                ),

                retryable=True,
            )
        )

    if isinstance(
        error,
        GitHubReviewRejectedError,
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_REVIEW_REJECTED"
                ),

                message=(
                    "GitHub 拒绝创建该 "
                    "Pull Request Review。"
                ),
            )
        )

    if isinstance(
        error,
        (
            GitHubAppInvalidResponseError,
            GitHubReviewInvalidResponseError,
        ),
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_INVALID_RESPONSE"
                ),

                message=(
                    "GitHub 返回了无法识别的"
                    "响应数据。"
                ),

                retryable=True,
            )
        )

    if isinstance(
        error,
        (
            GitHubAppUpstreamError,
            GitHubReviewUpstreamError,
        ),
    ):
        return (
            CodeReviewPublicationServiceError(
                code=(
                    "GITHUB_UPSTREAM_ERROR"
                ),

                message=(
                    "GitHub 服务暂时异常，"
                    "请稍后重试。"
                ),

                retryable=True,
            )
        )

    return (
        CodeReviewPublicationServiceError(
            code=(
                "REVIEW_PUBLICATION_FAILED"
            ),

            message=(
                "发布 GitHub Review 失败。"
            ),

            retryable=False,
        )
    )


def _mark_publication_failed_safely(
    *,
    session: Session,
    publication: (
        CodeReviewPublication
    ),
    error: (
        CodeReviewPublicationServiceError
    ),
) -> None:
    try:
        mark_code_review_publication_failed(
            session=session,

            publication_id=(
                publication.id
            ),

            error_code=error.code,

            error_message=(
                error.message
            ),
        )

    except Exception:
        session.rollback()

        logger.exception(
            "Failed to mark code review "
            "publication as failed: "
            "publication_id=%s",
            publication.id,
        )


def preview_code_review_github_publication(
    *,
    session: Session,
    command: (
        CodeReviewPublicationCommand
    ),
) -> CodeReviewPublicationPreviewResult:
    review_run = _load_review_run(
        session=session,
        command=command,
    )

    target = _extract_github_target(
        review_run,
    )

    default_event = (
        recommend_github_review_event(
            risk_level=(
                review_run.risk_level
            ),

            merge_recommendation=(
                review_run
                .merge_recommendation
            ),
        )
    )

    (
        body_markdown,
        body_hash,
    ) = _build_publication_body(
        review_run=review_run,
        target=target,
    )

    publications = (
        list_code_review_publication_records(
            session=session,

            review_run_id=(
                review_run.id
            ),
        )
    )

    successful_count = (
        count_successful_code_review_publications(
            session=session,

            review_run_id=(
                review_run.id
            ),
        )
    )

    return (
        CodeReviewPublicationPreviewResult(
            review_run_id=(
                review_run.id
            ),

            target=target,

            default_event=(
                default_event
            ),

            allowed_events=(
                "COMMENT",
                "APPROVE",
                "REQUEST_CHANGES",
            ),

            body_markdown=(
                body_markdown
            ),

            body_hash=body_hash,

            successful_publication_count=(
                successful_count
            ),

            publications=tuple(
                publications,
            ),
        )
    )


def read_code_review_publications(
    *,
    session: Session,
    command: (
        CodeReviewPublicationCommand
    ),
) -> list[CodeReviewPublication]:
    review_run = _load_review_run(
        session=session,
        command=command,
    )

    return (
        list_code_review_publication_records(
            session=session,

            review_run_id=(
                review_run.id
            ),
        )
    )


def publish_code_review_to_github(
    *,
    session: Session,
    command: (
        CodeReviewPublicationCommand
    ),
    auth_config: (
        GitHubAppAuthConfig | None
    ) = None,
    repository_access: (
        GitHubRepositoryAccess
        | None
    ) = None,
    github_client: (
        httpx.Client | None
    ) = None,
) -> CodeReviewPublicationResult:
    review_run = _load_review_run(
        session=session,
        command=command,
    )

    target = _extract_github_target(
        review_run,
    )

    requested_event = (
        _resolve_requested_event(
            review_run=review_run,

            requested_event=(
                command.requested_event
            ),
        )
    )

    (
        body_markdown,
        body_hash,
    ) = _build_publication_body(
        review_run=review_run,
        target=target,
    )

    attempt = (
        CodeReviewPublicationAttemptInput(
            knowledge_base_id=(
                command.knowledge_base_id
            ),

            review_run_id=(
                command.review_run_id
            ),

            owner_id=(
                command.owner_id
            ),

            requested_event=(
                requested_event
            ),

            target_repository=(
                target.repository
            ),

            target_change_number=(
                target.pull_number
            ),

            target_head_sha=(
                target.reviewed_head_sha
            ),

            target_source_url=(
                target.source_url
            ),

            body_markdown=(
                body_markdown
            ),

            body_hash=body_hash,

            force_republish=(
                command.force_republish
            ),
        )
    )

    try:
        publication = (
            begin_code_review_publication(
                session=session,
                attempt=attempt,
            )
        )

    except Exception as error:
        raise (
            _map_dependency_error(
                error,
            )
        ) from error

    try:
        resolved_access = (
            _resolve_repository_access(
                target=target,

                repository_access=(
                    repository_access
                ),

                auth_config=auth_config,
            )
        )

        client_context = (
            nullcontext(
                github_client,
            )
            if github_client is not None
            else create_github_review_client()
        )

        with client_context as client:
            if client is None:
                raise RuntimeError(
                    "GitHub client is missing",
                )

            pull_request = (
                get_pull_request(
                    client=client,

                    access_token=(
                        resolved_access
                        .access_token
                        .token
                    ),

                    repository=(
                        target.repository
                    ),

                    pull_number=(
                        target.pull_number
                    ),
                )
            )

            if (
                pull_request.state
                != "open"
                or pull_request.merged
            ):
                raise (
                    CodeReviewPublicationServiceError(
                        code=(
                            "GITHUB_PR_NOT_OPEN"
                        ),

                        message=(
                            "目标 PR 已关闭或已合并，"
                            "不能再发布正式 Review。"
                        ),

                        context={
                            "state":
                                pull_request.state,

                            "merged":
                                pull_request.merged,
                        },
                    )
                )

            if not hmac.compare_digest(
                pull_request.head_sha,
                target.reviewed_head_sha,
            ):
                raise (
                    CodeReviewPublicationServiceError(
                        code=(
                            "GITHUB_PR_HEAD_CHANGED"
                        ),

                        message=(
                            "该 PR 已产生新提交，"
                            "请重新导入并生成 Review。"
                        ),

                        context={
                            "reviewed_head_sha": (
                                target
                                .reviewed_head_sha
                            ),

                            "current_head_sha": (
                                pull_request
                                .head_sha
                            ),
                        },
                    )
                )

            published_review = (
                create_pull_request_review(
                    client=client,

                    access_token=(
                        resolved_access
                        .access_token
                        .token
                    ),

                    repository=(
                        target.repository
                    ),

                    pull_number=(
                        target.pull_number
                    ),

                    commit_id=(
                        target
                        .reviewed_head_sha
                    ),

                    event=(
                        requested_event
                    ),

                    body=body_markdown,
                )
            )

    except CodeReviewPublicationServiceError as error:
        _mark_publication_failed_safely(
            session=session,
            publication=publication,
            error=error,
        )

        raise

    except Exception as error:
        mapped_error = (
            _map_dependency_error(
                error,
            )
        )

        _mark_publication_failed_safely(
            session=session,
            publication=publication,
            error=mapped_error,
        )

        raise mapped_error from error

    try:
        succeeded_publication = (
            mark_code_review_publication_succeeded(
                session=session,

                publication_id=(
                    publication.id
                ),

                external_review_id=(
                    published_review.review_id
                ),

                external_review_url=(
                    published_review.html_url
                ),

                external_review_state=(
                    published_review.state
                ),

                external_actor=(
                    published_review.actor_login
                ),

                published_at=(
                    published_review
                    .submitted_at
                ),
            )
        )

    except Exception as error:
        session.rollback()

        raise (
            CodeReviewPublicationServiceError(
                code=(
                    "PUBLICATION_PERSISTENCE_FAILED"
                ),

                message=(
                    "GitHub Review 已创建，"
                    "但本地发布记录未能"
                    "正确保存。"
                ),

                context={
                    "external_review_url": (
                        published_review
                        .html_url
                    ),

                    "external_review_id": (
                        str(
                            published_review
                            .review_id
                        )
                    ),
                },
            )
        ) from error

    return CodeReviewPublicationResult(
        publication=(
            succeeded_publication
        ),

        pull_request=(
            pull_request
        ),

        requested_event=(
            requested_event
        ),
    )