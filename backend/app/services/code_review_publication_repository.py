from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import (
    CodeReviewPublication,
    CodeReviewRun,
)
PUBLICATION_ATTEMPT_TIMEOUT = (
    timedelta(
        minutes=10,
    )
)


class CodeReviewPublicationRepositoryError(
    RuntimeError,
):
    """发布记录 Repository 基础异常。"""


class CodeReviewPublicationReviewRunNotFoundError(
    CodeReviewPublicationRepositoryError,
):
    """目标 Review Run 不存在或无权访问。"""


class CodeReviewPublicationNotFoundError(
    CodeReviewPublicationRepositoryError,
):
    """目标发布记录不存在。"""


class CodeReviewPublicationInProgressError(
    CodeReviewPublicationRepositoryError,
):
    """当前 Review Run 已有发布任务进行中。"""


class CodeReviewAlreadyPublishedError(
    CodeReviewPublicationRepositoryError,
):
    """当前 Review Run 已成功发布过。"""


class CodeReviewPublicationInvalidStateError(
    CodeReviewPublicationRepositoryError,
):
    """当前发布记录状态不允许执行目标操作。"""


@dataclass(
    frozen=True,
    slots=True,
)
class CodeReviewPublicationAttemptInput:
    knowledge_base_id: uuid.UUID
    review_run_id: uuid.UUID
    owner_id: uuid.UUID

    requested_event: str

    target_repository: str
    target_change_number: int
    target_head_sha: str
    target_source_url: str

    body_markdown: str
    body_hash: str

    force_republish: bool = False


def _normalize_datetime(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=UTC,
        )

    return value.astimezone(
        UTC,
    )


def _resolve_now(
    value: datetime | None,
) -> datetime:
    if value is None:
        return datetime.now(
            UTC,
        )

    return _normalize_datetime(
        value,
    )


def _require_text(
    value: object,
    *,
    field_name: str,
    max_length: int | None = None,
) -> str:
    normalized_value = str(
        value or "",
    ).strip()

    if not normalized_value:
        raise ValueError(
            f"{field_name} is required",
        )

    if (
        max_length is not None
        and len(normalized_value)
        > max_length
    ):
        raise ValueError(
            f"{field_name} exceeds "
            f"{max_length} characters",
        )

    return normalized_value


def _lock_review_run(
    *,
    session: Session,
    attempt: (
        CodeReviewPublicationAttemptInput
    ),
) -> CodeReviewRun:
    statement = (
        select(
            CodeReviewRun,
        )
        .where(
            CodeReviewRun.id
            == attempt.review_run_id,

            CodeReviewRun
            .knowledge_base_id
            == attempt.knowledge_base_id,

            CodeReviewRun.owner_id
            == attempt.owner_id,
        )
        .with_for_update()
    )

    review_run = session.exec(
        statement,
    ).first()

    if review_run is None:
        raise (
            CodeReviewPublicationReviewRunNotFoundError(
                "Code review run was "
                "not found",
            )
        )

    return review_run


def _get_active_publication(
    *,
    session: Session,
    review_run_id: uuid.UUID,
) -> CodeReviewPublication | None:
    statement = (
        select(
            CodeReviewPublication,
        )
        .where(
            CodeReviewPublication
            .review_run_id
            == review_run_id,

            CodeReviewPublication.status
            == "publishing",
        )
        .order_by(
            CodeReviewPublication
            .attempt_number
            .desc(),
        )
        .with_for_update()
    )

    return session.exec(
        statement,
    ).first()


def _publication_reference_time(
    publication: (
        CodeReviewPublication
    ),
) -> datetime:
    reference_time = (
        publication.updated_at
        or publication.created_at
    )

    if reference_time is None:
        return datetime.min.replace(
            tzinfo=UTC,
        )

    return _normalize_datetime(
        reference_time,
    )


def _expire_stale_publication(
    *,
    session: Session,
    publication: (
        CodeReviewPublication
    ),
    now: datetime,
) -> bool:
    expiration_time = (
        _publication_reference_time(
            publication,
        )
        + PUBLICATION_ATTEMPT_TIMEOUT
    )

    if expiration_time > now:
        return False

    publication.status = "failed"

    publication.error_code = (
        "PUBLICATION_ATTEMPT_EXPIRED"
    )

    publication.error_message = (
        "The publication attempt "
        "remained in publishing state "
        "for more than 10 minutes"
    )

    publication.updated_at = now

    session.add(
        publication,
    )

    session.flush()

    return True


def _count_successful_publications(
    *,
    session: Session,
    review_run_id: uuid.UUID,
) -> int:
    statement = (
        select(
            func.count(
                CodeReviewPublication.id,
            )
        )
        .where(
            CodeReviewPublication
            .review_run_id
            == review_run_id,

            CodeReviewPublication.status
            == "succeeded",
        )
    )

    result = session.exec(
        statement,
    ).one()

    return int(
        result or 0,
    )


def _next_attempt_number(
    *,
    session: Session,
    review_run_id: uuid.UUID,
) -> int:
    statement = (
        select(
            func.max(
                CodeReviewPublication
                .attempt_number,
            )
        )
        .where(
            CodeReviewPublication
            .review_run_id
            == review_run_id,
        )
    )

    maximum_attempt = session.exec(
        statement,
    ).one()

    return int(
        maximum_attempt or 0,
    ) + 1


def begin_code_review_publication(
    *,
    session: Session,
    attempt: (
        CodeReviewPublicationAttemptInput
    ),
    now: datetime | None = None,
) -> CodeReviewPublication:
    current_time = _resolve_now(
        now,
    )

    normalized_event = (
        _require_text(
            attempt.requested_event,
            field_name=(
                "requested_event"
            ),
            max_length=50,
        )
        .upper()
    )

    if normalized_event not in {
        "COMMENT",
        "APPROVE",
        "REQUEST_CHANGES",
    }:
        raise ValueError(
            "requested_event must be "
            "COMMENT, APPROVE, or "
            "REQUEST_CHANGES",
        )

    target_repository = _require_text(
        attempt.target_repository,
        field_name=(
            "target_repository"
        ),
        max_length=255,
    )

    target_head_sha = _require_text(
        attempt.target_head_sha,
        field_name=(
            "target_head_sha"
        ),
        max_length=64,
    )

    target_source_url = _require_text(
        attempt.target_source_url,
        field_name=(
            "target_source_url"
        ),
        max_length=2048,
    )

    body_markdown = _require_text(
        attempt.body_markdown,
        field_name="body_markdown",
    )

    body_hash = _require_text(
        attempt.body_hash,
        field_name="body_hash",
        max_length=64,
    )

    if (
        attempt.target_change_number
        <= 0
    ):
        raise ValueError(
            "target_change_number "
            "must be positive",
        )

    try:
        _lock_review_run(
            session=session,
            attempt=attempt,
        )

        active_publication = (
            _get_active_publication(
                session=session,
                review_run_id=(
                    attempt.review_run_id
                ),
            )
        )

        if (
            active_publication
            is not None
        ):
            expired = (
                _expire_stale_publication(
                    session=session,
                    publication=(
                        active_publication
                    ),
                    now=current_time,
                )
            )

            if not expired:
                raise (
                    CodeReviewPublicationInProgressError(
                        "A code review "
                        "publication is "
                        "already in progress",
                    )
                )

        successful_count = (
            _count_successful_publications(
                session=session,
                review_run_id=(
                    attempt.review_run_id
                ),
            )
        )

        if (
            successful_count > 0
            and not attempt.force_republish
        ):
            raise (
                CodeReviewAlreadyPublishedError(
                    "This code review has "
                    "already been published",
                )
            )

        attempt_number = (
            _next_attempt_number(
                session=session,
                review_run_id=(
                    attempt.review_run_id
                ),
            )
        )

        publication = (
            CodeReviewPublication(
                knowledge_base_id=(
                    attempt
                    .knowledge_base_id
                ),

                review_run_id=(
                    attempt.review_run_id
                ),

                owner_id=(
                    attempt.owner_id
                ),

                provider="github",

                publication_type=(
                    "pull_request_review"
                ),

                requested_event=(
                    normalized_event
                ),

                status="publishing",

                target_repository=(
                    target_repository
                ),

                target_change_number=(
                    attempt
                    .target_change_number
                ),

                target_head_sha=(
                    target_head_sha
                ),

                target_source_url=(
                    target_source_url
                ),

                attempt_number=(
                    attempt_number
                ),

                force_republish=(
                    attempt.force_republish
                ),

                body_markdown=(
                    body_markdown
                ),

                body_hash=body_hash,

                created_at=(
                    current_time
                ),

                updated_at=(
                    current_time
                ),

                published_at=None,
            )
        )

        session.add(
            publication,
        )

        session.commit()

        session.refresh(
            publication,
        )

        return publication

    except IntegrityError as exc:
        session.rollback()

        error_text = str(
            exc.orig,
        )

        if (
            "uq_code_review_publication"
            "_active_attempt"
            in error_text
        ):
            raise (
                CodeReviewPublicationInProgressError(
                    "A code review "
                    "publication is already "
                    "in progress",
                )
            ) from exc

        if (
            "uq_code_review_publication"
            "_run_attempt"
            in error_text
        ):
            raise (
                CodeReviewPublicationInProgressError(
                    "A concurrent "
                    "publication attempt "
                    "was detected",
                )
            ) from exc

        raise


def _get_publication_for_update(
    *,
    session: Session,
    publication_id: uuid.UUID,
) -> CodeReviewPublication:
    statement = (
        select(
            CodeReviewPublication,
        )
        .where(
            CodeReviewPublication.id
            == publication_id,
        )
        .with_for_update()
    )

    publication = session.exec(
        statement,
    ).first()

    if publication is None:
        raise (
            CodeReviewPublicationNotFoundError(
                "Code review publication "
                "was not found",
            )
        )

    return publication


def mark_code_review_publication_succeeded(
    *,
    session: Session,
    publication_id: uuid.UUID,
    external_review_id: str | int,
    external_review_url: str,
    external_review_state: str,
    external_actor: str | None,
    published_at: datetime | None = None,
) -> CodeReviewPublication:
    success_time = _resolve_now(
        published_at,
    )

    normalized_review_id = (
        _require_text(
            external_review_id,
            field_name=(
                "external_review_id"
            ),
            max_length=128,
        )
    )

    normalized_review_url = (
        _require_text(
            external_review_url,
            field_name=(
                "external_review_url"
            ),
            max_length=2048,
        )
    )

    normalized_review_state = (
        _require_text(
            external_review_state,
            field_name=(
                "external_review_state"
            ),
            max_length=100,
        )
    )

    normalized_actor = (
        str(
            external_actor or "",
        ).strip()
        or None
    )

    if (
        normalized_actor is not None
        and len(normalized_actor) > 255
    ):
        raise ValueError(
            "external_actor exceeds "
            "255 characters",
        )

    try:
        publication = (
            _get_publication_for_update(
                session=session,
                publication_id=(
                    publication_id
                ),
            )
        )

        if (
            publication.status
            != "publishing"
        ):
            raise (
                CodeReviewPublicationInvalidStateError(
                    "Only a publishing "
                    "record can be marked "
                    "as succeeded",
                )
            )

        publication.status = (
            "succeeded"
        )

        publication.external_review_id = (
            normalized_review_id
        )

        publication.external_review_url = (
            normalized_review_url
        )

        publication.external_review_state = (
            normalized_review_state
        )

        publication.external_actor = (
            normalized_actor
        )

        publication.error_code = None
        publication.error_message = None

        publication.updated_at = (
            success_time
        )

        publication.published_at = (
            success_time
        )

        session.add(
            publication,
        )

        session.commit()

        session.refresh(
            publication,
        )

        return publication

    except IntegrityError:
        session.rollback()
        raise


def mark_code_review_publication_failed(
    *,
    session: Session,
    publication_id: uuid.UUID,
    error_code: str,
    error_message: str,
    failed_at: datetime | None = None,
) -> CodeReviewPublication:
    failure_time = _resolve_now(
        failed_at,
    )

    normalized_error_code = (
        _require_text(
            error_code,
            field_name="error_code",
            max_length=100,
        )
    )

    normalized_error_message = (
        _require_text(
            error_message,
            field_name=(
                "error_message"
            ),
        )
    )

    publication = (
        _get_publication_for_update(
            session=session,
            publication_id=(
                publication_id
            ),
        )
    )

    if publication.status != (
        "publishing"
    ):
        raise (
            CodeReviewPublicationInvalidStateError(
                "Only a publishing "
                "record can be marked "
                "as failed",
            )
        )

    publication.status = "failed"

    publication.error_code = (
        normalized_error_code
    )

    publication.error_message = (
        normalized_error_message
    )

    publication.updated_at = (
        failure_time
    )

    publication.published_at = None

    session.add(
        publication,
    )

    session.commit()

    session.refresh(
        publication,
    )

    return publication


def list_code_review_publications(
    *,
    session: Session,
    review_run_id: uuid.UUID,
) -> list[CodeReviewPublication]:
    statement = (
        select(
            CodeReviewPublication,
        )
        .where(
            CodeReviewPublication
            .review_run_id
            == review_run_id,
        )
        .order_by(
            CodeReviewPublication
            .attempt_number
            .desc(),
        )
    )

    return list(
        session.exec(
            statement,
        ).all(),
    )


def count_successful_code_review_publications(
    *,
    session: Session,
    review_run_id: uuid.UUID,
) -> int:
    return _count_successful_publications(
        session=session,
        review_run_id=(
            review_run_id
        ),
    )