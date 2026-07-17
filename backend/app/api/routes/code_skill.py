from typing import Any, Annotated
import uuid
import logging
from fastapi import APIRouter, HTTPException, Query, status

from sqlmodel import col, select
from time import perf_counter

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    CodeSkillChangedFilePublic,
    CodeSkillChangedSymbolPublic,
    CodeSkillDiffHunkPublic,
    CodeSkillLocateChangedSymbolsRequest,
    CodeSkillLocateChangedSymbolsResponse,
    CodeSkillParseDiffRequest,
    CodeSkillParseDiffResponse,
    Document,
    DocumentChunk,
    KnowledgeBase,
    CodeSkillChangedSymbolInput,
    CodeSkillFindImpactsRequest,
    CodeSkillFindImpactsResponse,
    CodeSkillImpactReferencePublic,
    CodeSkillImpactedFilePublic,
    CodeSkillSymbolImpactPublic,
    CodeSkillImpactedFileInput,
    CodeSkillRecommendTestsRequest,
    CodeSkillRecommendTestsResponse,
    CodeSkillRecommendedTestPublic,
    CodeSkillBuildReviewEvidenceRequest,
    CodeSkillChangeSummaryPublic,
    CodeSkillEvidenceTraceStepPublic,
    CodeSkillReviewEvidenceResponse,
    CodeSkillGenerateReviewReportRequest,
    CodeSkillGenerateReviewReportResponse,
    CodeReviewGenerationStatus,
    CodeReviewRiskLevel,
    CodeReviewRunDetailPublic,
    CodeReviewRunsPublic,
    Message,
    CodeReviewCompareRequest,
    CodeReviewCompareResponse,
    CodeReviewSourceResolvedPublic,
    CodeReviewSourceResolveRequest,
    CodeReviewPublication,
    CodeReviewPublicationPublic,
    CodeReviewPublicationsPublic,
    GitHubReviewPublicationPreviewPublic,
    GitHubReviewPublicationRequest,
    GitHubReviewPublicationResultPublic,
)
from app.services.code_skill import (
    build_changed_symbol_reason,
    build_file_level_fallback_symbol,
    calculate_range_overlap,
    calculate_symbol_confidence,
    extract_code_chunk_metadata,
    get_hunk_new_line_range,
    parse_git_diff,
    parse_line_range,
    repo_paths_match,
    build_impact_reference_reason,
    build_reference_preview,
    calculate_reference_confidence,
    count_symbol_occurrences,
    is_definition_chunk_for_symbol,
    build_test_candidate_preview,
    build_test_gap_notes,
    calculate_test_path_match,
    calculate_test_recommendation_confidence,
    deduplicate_strings,
    find_symbol_occurrences_in_content,
    is_test_file_path,
    resolve_code_file_path,
)
from app.services.code_skill_review import (
    build_review_checklist,
    build_review_limitations,
    build_review_risk_signals,
    calculate_overall_risk_level,
)

from app.services.code_skill_pipeline import (
    locate_changed_symbols_for_knowledge_base,
    find_impacts_for_knowledge_base,
    recommend_tests_for_knowledge_base,
)

from app.services.code_skill_pipeline import build_review_evidence_for_knowledge_base
from app.services.code_review_run import (
    save_code_review_generation_result,
    delete_code_review_run as delete_code_review_run_record,
    get_code_review_run_detail,
    list_code_review_runs,
    CodeReviewRunDeleteBlockedError,
)
from app.services.code_review_report import generate_review_report_from_evidence
from app.services.code_review_compare import (
    compare_code_review_runs
    as compare_code_review_run_details,
)
from app.services.code_review_providers.errors import (
    CodeReviewSourceInvalidResponseError,
    CodeReviewSourceNotFoundError,
    CodeReviewSourceProviderError,
    CodeReviewSourceRateLimitError,
    CodeReviewSourceTimeoutError,
    CodeReviewSourceTooLargeError,
    CodeReviewSourceUpstreamError,
)
from app.services.code_review_source import (
    CodeReviewSourceUrlError,
)
from app.services.code_review_source_resolver import (
    resolve_code_review_source
    as resolve_code_review_source_service,
)

from app.services.code_review_source_snapshot import (
    CodeReviewSourceDiffMismatchError,
    calculate_code_review_diff_hash,
    validate_and_build_code_review_source_fields,
)

from app.services.code_review_publication import (
    CodeReviewPublicationCommand,
    CodeReviewPublicationServiceError,
    preview_code_review_github_publication,
    publish_code_review_to_github,
    read_code_review_publications,
)

router = APIRouter(prefix="/code-skill", tags=["code-skill"])
logger = logging.getLogger(__name__)


def elapsed_milliseconds(start_time: float) -> int:
    return int((perf_counter() - start_time) * 1000)


def get_knowledge_base_or_404(
    *,
    session: SessionDep,
    knowledge_base_id: uuid.UUID,
) -> KnowledgeBase:
    knowledge_base = session.get(KnowledgeBase, knowledge_base_id)

    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    return knowledge_base


def check_knowledge_base_permission(
    *,
    knowledge_base: KnowledgeBase,
    current_user: CurrentUser,
) -> None:
    if not current_user.is_superuser and knowledge_base.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")


def build_changed_file_public(changed_file: Any) -> CodeSkillChangedFilePublic:
    return CodeSkillChangedFilePublic(
        old_path=changed_file.old_path,
        new_path=changed_file.new_path,
        file_path=changed_file.file_path,
        change_type=changed_file.change_type,
        added_lines=changed_file.added_lines,
        deleted_lines=changed_file.deleted_lines,
        hunks=[
            CodeSkillDiffHunkPublic(
                old_start=hunk.old_start,
                old_count=hunk.old_count,
                new_start=hunk.new_start,
                new_count=hunk.new_count,
                added_lines=hunk.added_lines,
                deleted_lines=hunk.deleted_lines,
                context_lines=hunk.context_lines,
            )
            for hunk in changed_file.hunks
        ],
    )


def serialize_code_review_publication(
    publication: (
        CodeReviewPublication
    ),
) -> CodeReviewPublicationPublic:
    return CodeReviewPublicationPublic(
        id=publication.id,

        knowledge_base_id=(
            publication
            .knowledge_base_id
        ),

        review_run_id=(
            publication.review_run_id
        ),

        provider=publication.provider,

        publication_type=(
            publication
            .publication_type
        ),

        requested_event=(
            publication
            .requested_event
        ),

        status=publication.status,

        target_repository=(
            publication
            .target_repository
        ),

        target_change_number=(
            publication
            .target_change_number
        ),

        target_head_sha=(
            publication
            .target_head_sha
        ),

        target_source_url=(
            publication
            .target_source_url
        ),

        attempt_number=(
            publication
            .attempt_number
        ),

        force_republish=(
            publication
            .force_republish
        ),

        body_hash=(
            publication.body_hash
        ),

        external_review_id=(
            publication
            .external_review_id
        ),

        external_review_url=(
            publication
            .external_review_url
        ),

        external_review_state=(
            publication
            .external_review_state
        ),

        external_actor=(
            publication
            .external_actor
        ),

        error_code=(
            publication.error_code
        ),

        error_message=(
            publication.error_message
        ),

        created_at=(
            publication.created_at
        ),

        updated_at=(
            publication.updated_at
        ),

        published_at=(
            publication.published_at
        ),
    )


PUBLICATION_ERROR_STATUS_CODES = {
    "INVALID_REVIEW_EVENT":
        status.HTTP_400_BAD_REQUEST,

    "REVIEW_RUN_NOT_FOUND":
        status.HTTP_404_NOT_FOUND,

    "GITHUB_PR_NOT_FOUND":
        status.HTTP_404_NOT_FOUND,

    "REVIEW_NOT_COMPLETED":
        status.HTTP_409_CONFLICT,

    "REVIEW_SOURCE_NOT_GITHUB":
        status.HTTP_409_CONFLICT,

    "REVIEW_SOURCE_INCOMPLETE":
        status.HTTP_409_CONFLICT,

    "REVIEW_ALREADY_PUBLISHED":
        status.HTTP_409_CONFLICT,

    "REVIEW_PUBLICATION_IN_PROGRESS":
        status.HTTP_409_CONFLICT,

    "GITHUB_PR_HEAD_CHANGED":
        status.HTTP_409_CONFLICT,

    "GITHUB_PR_NOT_OPEN":
        status.HTTP_409_CONFLICT,

    "GITHUB_ACCESS_REPOSITORY_MISMATCH":
        status.HTTP_409_CONFLICT,

    "REVIEW_BODY_INVALID":
        status.HTTP_422_UNPROCESSABLE_CONTENT,

    "GITHUB_REVIEW_REJECTED":
        status.HTTP_422_UNPROCESSABLE_CONTENT,

    "GITHUB_APP_NOT_INSTALLED":
        status.HTTP_424_FAILED_DEPENDENCY,

    "GITHUB_APP_PERMISSION_DENIED":
        status.HTTP_424_FAILED_DEPENDENCY,

    "GITHUB_APP_AUTHENTICATION_REJECTED":
        status.HTTP_424_FAILED_DEPENDENCY,

    "GITHUB_RATE_LIMITED":
        status.HTTP_429_TOO_MANY_REQUESTS,

    "GITHUB_INVALID_RESPONSE":
        status.HTTP_502_BAD_GATEWAY,

    "GITHUB_UPSTREAM_ERROR":
        status.HTTP_502_BAD_GATEWAY,

    "GITHUB_APP_NOT_CONFIGURED":
        status.HTTP_503_SERVICE_UNAVAILABLE,

    "GITHUB_APP_PRIVATE_KEY_INVALID":
        status.HTTP_503_SERVICE_UNAVAILABLE,

    "GITHUB_REQUEST_TIMEOUT":
        status.HTTP_504_GATEWAY_TIMEOUT,

    "PUBLICATION_PERSISTENCE_FAILED":
        status.HTTP_500_INTERNAL_SERVER_ERROR,

    "REVIEW_PUBLICATION_FAILED":
        status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def publication_error_status_code(
    error: (
        CodeReviewPublicationServiceError
    ),
) -> int:
    return (
        PUBLICATION_ERROR_STATUS_CODES
        .get(
            error.code,
            status
            .HTTP_500_INTERNAL_SERVER_ERROR,
        )
    )


def raise_publication_http_error(
    error: (
        CodeReviewPublicationServiceError
    ),
) -> None:
    raise HTTPException(
        status_code=(
            publication_error_status_code(
                error,
            )
        ),

        detail={
            "code": error.code,
            "message": error.message,
            "retryable":
                error.retryable,
            "context":
                error.context,
        },
    ) from error


@router.post(
    "/parse-diff",
    response_model=CodeSkillParseDiffResponse,
    operation_id="parse_code_skill_diff",
)
def parse_code_skill_diff(
    *,
    request: CodeSkillParseDiffRequest,
) -> Any:
    changed_files = parse_git_diff(request.diff_text)

    public_files = [
        build_changed_file_public(changed_file) for changed_file in changed_files
    ]

    return CodeSkillParseDiffResponse(
        changed_files=public_files,
        total_files=len(public_files),
        total_added_lines=sum(item.added_lines for item in public_files),
        total_deleted_lines=sum(item.deleted_lines for item in public_files),
    )


@router.post(
    "/knowledge-bases/{knowledge_base_id}/locate-changed-symbols",
    response_model=CodeSkillLocateChangedSymbolsResponse,
    operation_id="locate_code_skill_changed_symbols",
)
def locate_code_skill_changed_symbols(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    request: CodeSkillLocateChangedSymbolsRequest,
) -> Any:
    knowledge_base = get_knowledge_base_or_404(
        session=session,
        knowledge_base_id=knowledge_base_id,
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    try:
        return locate_changed_symbols_for_knowledge_base(
            session=session,
            knowledge_base_id=knowledge_base_id,
            request=request,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@router.post(
    "/knowledge-bases/{knowledge_base_id}/find-impacts",
    response_model=CodeSkillFindImpactsResponse,
    operation_id="find_code_skill_impacts",
)
def find_code_skill_impacts(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    request: CodeSkillFindImpactsRequest,
) -> Any:
    knowledge_base = get_knowledge_base_or_404(
        session=session,
        knowledge_base_id=knowledge_base_id,
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    try:
        return find_impacts_for_knowledge_base(
            session=session,
            knowledge_base_id=knowledge_base_id,
            request=request,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@router.post(
    "/knowledge-bases/{knowledge_base_id}/recommend-tests",
    response_model=CodeSkillRecommendTestsResponse,
    operation_id="recommend_code_skill_tests",
)
def recommend_code_skill_tests(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    request: CodeSkillRecommendTestsRequest,
) -> Any:
    knowledge_base = get_knowledge_base_or_404(
        session=session,
        knowledge_base_id=knowledge_base_id,
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    try:
        return recommend_tests_for_knowledge_base(
            session=session,
            knowledge_base_id=knowledge_base_id,
            request=request,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@router.post(
    "/knowledge-bases/{knowledge_base_id}/build-review-evidence",
    response_model=CodeSkillReviewEvidenceResponse,
    operation_id="build_code_skill_review_evidence",
)
def build_code_skill_review_evidence(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    request: CodeSkillBuildReviewEvidenceRequest,
) -> Any:
    knowledge_base = get_knowledge_base_or_404(
        session=session,
        knowledge_base_id=knowledge_base_id,
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    try:
        return build_review_evidence_for_knowledge_base(
            session=session,
            knowledge_base_id=knowledge_base_id,
            request=request,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@router.post(
    (
        "/knowledge-bases/"
        "{knowledge_base_id}/"
        "review-sources/resolve"
    ),
    response_model=(
        CodeReviewSourceResolvedPublic
    ),
    operation_id=(
        "resolve_code_review_source"
    ),
)
async def resolve_code_review_source_endpoint(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    request: (
        CodeReviewSourceResolveRequest
    ),
) -> CodeReviewSourceResolvedPublic:
    """
    获取公开 GitHub Pull Request
    或 GitLab Merge Request 的来源信息
    及标准 Git Diff。
    """

    knowledge_base = (
        get_knowledge_base_or_404(
            session=session,
            knowledge_base_id=(
                knowledge_base_id
            ),
        )
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    try:
        return await (
            resolve_code_review_source_service(
                request.source_url,
            )
        )

    except CodeReviewSourceUrlError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except (
        CodeReviewSourceNotFoundError
    ) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (
        CodeReviewSourceTooLargeError
    ) as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc

    except (
        CodeReviewSourceRateLimitError
    ) as exc:
        headers: dict[str, str] | None = (
            None
        )

        if (
            exc.retry_after_seconds
            is not None
        ):
            headers = {
                "Retry-After": str(
                    exc.retry_after_seconds,
                ),
            }

        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers=headers,
        ) from exc

    except (
        CodeReviewSourceTimeoutError
    ) as exc:
        raise HTTPException(
            status_code=504,
            detail=str(exc),
        ) from exc

    except (
        CodeReviewSourceInvalidResponseError
    ) as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except (
        CodeReviewSourceUpstreamError
    ) as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except (
        CodeReviewSourceProviderError
    ) as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "代码托管平台暂时无法处理该请求"
            ),
        ) from exc


@router.post(
    "/knowledge-bases/{knowledge_base_id}/generate-review-report",
    response_model=CodeSkillGenerateReviewReportResponse,
    operation_id="generate_code_skill_review_report",
)
def generate_code_skill_review_report(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    request: CodeSkillGenerateReviewReportRequest,
) -> Any:
    knowledge_base = get_knowledge_base_or_404(
        session=session,
        knowledge_base_id=knowledge_base_id,
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    if not request.diff_text.strip():
        raise HTTPException(
            status_code=400,
            detail="diff_text cannot be empty",
        )
    try:
        source_fields = (
            validate_and_build_code_review_source_fields(
                diff_text=request.diff_text,
                source=request.source,
            )
        )
    except (
            CodeReviewSourceDiffMismatchError
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    evidence_request = CodeSkillBuildReviewEvidenceRequest(
        diff_text=request.diff_text,
        max_references_per_symbol=(request.max_references_per_symbol),
        max_test_files=(request.max_test_files),
        min_test_confidence=(request.min_test_confidence),
        include_file_level_fallback=(request.include_file_level_fallback),
        include_definition_chunk=(request.include_definition_chunk),
    )

    try:
        evidence = build_review_evidence_for_knowledge_base(
            session=session,
            knowledge_base_id=knowledge_base_id,
            request=evidence_request,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    generated_response = generate_review_report_from_evidence(
        evidence=evidence,
        language=request.language,
    )

    try:
        return save_code_review_generation_result(
            session=session,
            knowledge_base_id=knowledge_base_id,
            owner_id=current_user.id,
            request=request,
            response=generated_response,
        )
    except Exception as error:
        logger.exception(
            (
                "Failed to persist code review run: "
                "knowledge_base_id=%s, owner_id=%s, "
                "generation_status=%s"
            ),
            knowledge_base_id,
            current_user.id,
            generated_response.generation_status,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Code review report was generated, "
                "but its history record could not be saved"
            ),
        ) from error


@router.get(
    "/knowledge-bases/{knowledge_base_id}/review-runs",
    response_model=CodeReviewRunsPublic,
    operation_id="read_code_review_runs",
)
def read_code_review_runs(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    skip: Annotated[
        int,
        Query(
            ge=0,
            description="跳过的历史记录数量",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="单页返回数量，最大 100",
        ),
    ] = 20,
    generation_status: CodeReviewGenerationStatus | None = None,
    risk_level: CodeReviewRiskLevel | None = None,
) -> CodeReviewRunsPublic:
    """
    查询当前用户在指定知识库中的 Review 历史。

    列表只返回摘要字段，不返回大型 Diff、
    Evidence、Markdown 和完整 Review JSON。
    """

    knowledge_base = get_knowledge_base_or_404(
        session=session,
        knowledge_base_id=knowledge_base_id,
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    return list_code_review_runs(
        session=session,
        knowledge_base_id=knowledge_base_id,
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
        generation_status=generation_status,
        risk_level=risk_level,
    )


@router.post(
    (
        "/knowledge-bases/{knowledge_base_id}"
        "/review-runs/compare"
    ),
    response_model=CodeReviewCompareResponse,
    operation_id="compare_code_review_runs",
)
def compare_code_review_run_history(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    request: CodeReviewCompareRequest,
) -> CodeReviewCompareResponse:
    """
    比较两条属于当前用户和知识库的
    Review 历史快照。

    A 为基准版本，B 为目标版本；
    所有变化均按照 A → B 解释。
    """

    knowledge_base = get_knowledge_base_or_404(
        session=session,
        knowledge_base_id=knowledge_base_id,
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    if (
        request.base_review_run_id
        == request.target_review_run_id
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Base and target review runs "
                "must be different"
            ),
        )

    base_review = get_code_review_run_detail(
        session=session,
        knowledge_base_id=knowledge_base_id,
        owner_id=current_user.id,
        review_run_id=(
            request.base_review_run_id
        ),
    )

    if base_review is None:
        raise HTTPException(
            status_code=404,
            detail="Code review run not found",
        )

    target_review = get_code_review_run_detail(
        session=session,
        knowledge_base_id=knowledge_base_id,
        owner_id=current_user.id,
        review_run_id=(
            request.target_review_run_id
        ),
    )

    if target_review is None:
        raise HTTPException(
            status_code=404,
            detail="Code review run not found",
        )

    return compare_code_review_run_details(
        base_review=base_review,
        target_review=target_review,
    )


@router.get(
    (
        "/knowledge-bases/{knowledge_base_id}"
        "/review-runs/{review_run_id}"
    ),
    response_model=CodeReviewRunDetailPublic,
    operation_id="read_code_review_run_detail",
)
def read_code_review_run_detail(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    review_run_id: uuid.UUID,
) -> CodeReviewRunDetailPublic:
    """
    查询一条完整 Review 历史快照。
    """

    knowledge_base = get_knowledge_base_or_404(
        session=session,
        knowledge_base_id=knowledge_base_id,
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    review_run_detail = get_code_review_run_detail(
        session=session,
        knowledge_base_id=knowledge_base_id,
        owner_id=current_user.id,
        review_run_id=review_run_id,
    )

    if review_run_detail is None:
        raise HTTPException(
            status_code=404,
            detail="Code review run not found",
        )

    return review_run_detail


@router.delete(
    (
        "/knowledge-bases/{knowledge_base_id}"
        "/review-runs/{review_run_id}"
    ),
    response_model=Message,
    operation_id="delete_code_review_run",
)
def delete_code_review_run_history(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    knowledge_base_id: uuid.UUID,
    review_run_id: uuid.UUID,
) -> Message:
    """
    删除一条属于当前用户的 Review 历史。
    """

    knowledge_base = get_knowledge_base_or_404(
        session=session,
        knowledge_base_id=knowledge_base_id,
    )

    check_knowledge_base_permission(
        knowledge_base=knowledge_base,
        current_user=current_user,
    )

    try:
        deleted = delete_code_review_run(
            session=session,

            knowledge_base_id=(
                knowledge_base_id
            ),

            owner_id=(
                current_user.id
            ),

            review_run_id=(
                review_run_id
            ),
        )

    except (
            CodeReviewRunDeleteBlockedError
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),

            detail={
                "code": error.code,
                "message": error.message,
                "retryable":
                    error.retryable,
                "context":
                    error.context,
            },
        ) from error

    if not deleted:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Code review run not found"
            ),
        )

    return Message(
        message=(
            "Code review run "
            "deleted successfully"
        ),
    )


@router.get(
    (
        "/knowledge-bases/"
        "{knowledge_base_id}/"
        "review-runs/"
        "{review_run_id}/"
        "github-publication-preview"
    ),

    response_model=(
        GitHubReviewPublicationPreviewPublic
    ),

    operation_id=(
        "preview_github_code_review_"
        "publication"
    ),
)
def preview_github_code_review_publication(
    *,
    session: SessionDep,
    current_user: CurrentUser,

    knowledge_base_id: uuid.UUID,
    review_run_id: uuid.UUID,
) -> (
    GitHubReviewPublicationPreviewPublic
):
    try:
        preview = (
            preview_code_review_github_publication(
                session=session,

                command=(
                    CodeReviewPublicationCommand(
                        knowledge_base_id=(
                            knowledge_base_id
                        ),

                        review_run_id=(
                            review_run_id
                        ),

                        owner_id=(
                            current_user.id
                        ),
                    )
                ),
            )
        )

    except (
        CodeReviewPublicationServiceError
    ) as error:
        raise_publication_http_error(
            error,
        )

    latest_publication = None

    if (
        preview.latest_publication
        is not None
    ):
        latest_publication = (
            serialize_code_review_publication(
                preview.latest_publication,
            )
        )

    return (
        GitHubReviewPublicationPreviewPublic(
            review_run_id=(
                preview.review_run_id
            ),

            target_repository=(
                preview
                .target
                .repository
            ),

            target_change_number=(
                preview
                .target
                .pull_number
            ),

            target_source_url=(
                preview
                .target
                .source_url
            ),

            reviewed_head_sha=(
                preview
                .target
                .reviewed_head_sha
            ),

            default_event=(
                preview.default_event
            ),

            allowed_events=list(
                preview.allowed_events,
            ),

            already_published=(
                preview.already_published
            ),

            successful_publication_count=(
                preview
                .successful_publication_count
            ),

            latest_publication=(
                latest_publication
            ),

            body_markdown=(
                preview.body_markdown
            ),

            body_hash=(
                preview.body_hash
            ),

            body_character_count=len(
                preview.body_markdown,
            ),
        )
    )


@router.post(
    (
        "/knowledge-bases/"
        "{knowledge_base_id}/"
        "review-runs/"
        "{review_run_id}/"
        "github-publications"
    ),

    response_model=(
        GitHubReviewPublicationResultPublic
    ),

    operation_id=(
        "publish_github_code_review"
    ),
)
def publish_github_code_review(
    *,
    session: SessionDep,
    current_user: CurrentUser,

    knowledge_base_id: uuid.UUID,
    review_run_id: uuid.UUID,

    request: (
        GitHubReviewPublicationRequest
    ),
) -> GitHubReviewPublicationResultPublic:
    try:
        result = (
            publish_code_review_to_github(
                session=session,

                command=(
                    CodeReviewPublicationCommand(
                        knowledge_base_id=(
                            knowledge_base_id
                        ),

                        review_run_id=(
                            review_run_id
                        ),

                        owner_id=(
                            current_user.id
                        ),

                        requested_event=(
                            request.event
                        ),

                        force_republish=(
                            request
                            .force_republish
                        ),
                    )
                ),
            )
        )

    except (
        CodeReviewPublicationServiceError
    ) as error:
        raise_publication_http_error(
            error,
        )

    return (
        GitHubReviewPublicationResultPublic(
            publication=(
                serialize_code_review_publication(
                    result.publication,
                )
            ),

            requested_event=(
                result.requested_event
            ),

            current_head_sha=(
                result
                .pull_request
                .head_sha
            ),

            pull_request_url=(
                result
                .pull_request
                .html_url
            ),
        )
    )


@router.get(
    (
        "/knowledge-bases/"
        "{knowledge_base_id}/"
        "review-runs/"
        "{review_run_id}/"
        "publications"
    ),

    response_model=(
        CodeReviewPublicationsPublic
    ),

    operation_id=(
        "read_code_review_publications"
    ),
)
def read_code_review_publication_history(
    *,
    session: SessionDep,
    current_user: CurrentUser,

    knowledge_base_id: uuid.UUID,
    review_run_id: uuid.UUID,
) -> CodeReviewPublicationsPublic:
    try:
        publications = (
            read_code_review_publications(
                session=session,

                command=(
                    CodeReviewPublicationCommand(
                        knowledge_base_id=(
                            knowledge_base_id
                        ),

                        review_run_id=(
                            review_run_id
                        ),

                        owner_id=(
                            current_user.id
                        ),
                    )
                ),
            )
        )

    except (
        CodeReviewPublicationServiceError
    ) as error:
        raise_publication_http_error(
            error,
        )

    publication_rows = [
        serialize_code_review_publication(
            publication,
        )
        for publication
        in publications
    ]

    return CodeReviewPublicationsPublic(
        data=publication_rows,
        count=len(
            publication_rows,
        ),
    )