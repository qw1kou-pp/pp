from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    CodeReviewRun,
    CodeReviewRunDetailPublic,
    CodeReviewRunsPublic,
    CodeReviewRunSummaryPublic,
    CodeSkillGenerateReviewReportRequest,
    CodeSkillGenerateReviewReportResponse,
    CodeSkillGeneratedReviewReportPublic,
    CodeSkillReportGenerationTracePublic,
    CodeSkillReviewEvidenceResponse,
    CodeReviewSourceSnapshot,
    CodeReviewPublication,
)
from app.services.code_review_source_snapshot import (
    validate_and_build_code_review_source_fields,
)

from app.utils import logger

VALID_GENERATION_STATUSES = {
    "completed",
    "evidence_only",
}

VALID_RISK_LEVELS = {
    "low",
    "medium",
    "high",
}


class CodeReviewRunDeleteBlockedError(
    RuntimeError,
):
    """
    Review Run 因发布审计要求
    暂时或永久不能删除。
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        retryable: bool,
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


def normalize_diff_text(diff_text: str) -> str:
    """
    对 Diff 做最小规范化，用于生成稳定指纹。

    只统一换行符和结尾多余换行，不删除每一行的空格，
    因为代码中的空白本身也可能是有效变更。
    """

    normalized_text = str(diff_text).replace("\r\n", "\n").replace("\r", "\n")

    return normalized_text.rstrip("\n")


def compute_diff_hash(diff_text: str) -> str:
    """
    使用规范化 Diff 计算 SHA-256。

    同一份 Diff 即使来自 Windows 和 Linux，
    也会得到相同的哈希值。
    """

    normalized_diff = normalize_diff_text(
        diff_text,
    )

    if not normalized_diff.strip():
        raise ValueError(
            "diff_text must not be empty",
        )

    return hashlib.sha256(
        normalized_diff.encode("utf-8"),
    ).hexdigest()


def build_review_title(
    evidence: CodeSkillReviewEvidenceResponse,
) -> str:
    """
    根据变更文件构造适合历史列表展示的标题。
    """

    changed_files = (
        getattr(
            evidence,
            "changed_files",
            [],
        )
        or []
    )

    file_paths: list[str] = []

    for changed_file in changed_files:
        file_path = str(
            getattr(
                changed_file,
                "file_path",
                "",
            )
            or ""
        ).strip()

        if file_path:
            file_paths.append(file_path)

    if not file_paths:
        return "RepoGuard Review"

    first_file_path = file_paths[0]

    if len(file_paths) == 1:
        title = f"RepoGuard · {first_file_path}"
    else:
        remaining_file_count = len(file_paths) - 1

        suffix = "file" if remaining_file_count == 1 else "files"

        title = f"RepoGuard · {first_file_path} · +{remaining_file_count} {suffix}"

    return title[:200]


def build_request_parameters_snapshot(
    request: CodeSkillGenerateReviewReportRequest,
) -> dict[str, Any]:
    """
    保存生成参数，但不重复保存体积较大的 diff_text。
    """

    request_payload = request.model_dump(
        mode="json",
    )

    request_payload.pop(
        "diff_text",
        None,
    )

    request_payload.pop(
        "source",
        None,
    )

    return request_payload


def _get_report_risk_level(
    response: CodeSkillGenerateReviewReportResponse,
) -> str | None:
    review_report = response.review_report

    if review_report is not None:
        risk_level = str(review_report.overall_assessment.risk_level or "").lower()

        if risk_level in VALID_RISK_LEVELS:
            return risk_level

    evidence_risk_level = str(response.evidence.change_summary.risk_level or "").lower()

    if evidence_risk_level in VALID_RISK_LEVELS:
        return evidence_risk_level

    return None


def _get_merge_recommendation(
    response: CodeSkillGenerateReviewReportResponse,
) -> str | None:
    review_report = response.review_report

    if review_report is None:
        return None

    recommendation = str(
        review_report.overall_assessment.merge_recommendation or ""
    ).lower()

    return recommendation or None


def build_code_review_run(
    *,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
    request: CodeSkillGenerateReviewReportRequest,
    response: CodeSkillGenerateReviewReportResponse,
) -> CodeReviewRun:
    """
    将一次报告生成结果转换成数据库不可变快照。

    此函数只构造模型，不执行数据库提交，
    因而可以独立进行单元测试。
    """

    generation_status = str(
        response.generation_status,
    ).lower()

    if generation_status not in VALID_GENERATION_STATUSES:
        raise ValueError(
            f"Unsupported generation status: {generation_status}",
        )
    source_fields = (
        validate_and_build_code_review_source_fields(
            diff_text=request.diff_text,
            source=request.source,
        )
    )
    evidence = response.evidence
    change_summary = evidence.change_summary
    review_report = response.review_report

    review_report_json = (
        review_report.model_dump(
            mode="json",
        )
        if review_report is not None
        else None
    )

    finding_count = (
        len(
            review_report.findings or [],
        )
        if review_report is not None
        else 0
    )

    return CodeReviewRun(
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
        title=build_review_title(
            evidence,
        ),
        diff_text=request.diff_text,
        diff_hash=compute_diff_hash(
            request.diff_text,
        ),
        generation_status=generation_status,
        **source_fields,
        language=request.language,
        risk_level=_get_report_risk_level(
            response,
        ),
        merge_recommendation=(
            _get_merge_recommendation(
                response,
            )
        ),
        changed_file_count=int(change_summary.total_changed_files or 0),
        changed_symbol_count=int(change_summary.total_changed_symbols or 0),
        finding_count=finding_count,
        recommended_test_count=int(change_summary.total_recommended_tests or 0),
        request_parameters_json=(
            build_request_parameters_snapshot(
                request,
            )
        ),
        review_report_json=(review_report_json),
        review_markdown=(response.review_markdown),
        evidence_json=(
            evidence.model_dump(
                mode="json",
            )
        ),
        generation_trace_json=(
            response.generation_trace.model_dump(
                mode="json",
            )
        ),
        generation_error=(response.generation_error),
    )


def create_code_review_run(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
    request: CodeSkillGenerateReviewReportRequest,
    response: CodeSkillGenerateReviewReportResponse,
) -> CodeReviewRun:
    """
    创建并提交一条审查历史记录。

    保存失败时回滚事务，并继续向上抛出异常，
    避免接口误报“生成成功但实际没有保存”。
    """

    review_run = build_code_review_run(
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
        request=request,
        response=response,
    )

    try:
        session.add(
            review_run,
        )

        session.commit()
        session.refresh(
            review_run,
        )
    except Exception:
        session.rollback()
        raise

    return review_run


def save_code_review_generation_result(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
    request: CodeSkillGenerateReviewReportRequest,
    response: CodeSkillGenerateReviewReportResponse,
) -> CodeSkillGenerateReviewReportResponse:
    """
    保存一次代码审查运行，并将数据库记录信息写回接口响应。

    completed 和 evidence_only 都会保存。
    数据库提交失败时，由 create_code_review_run 回滚并抛出异常。
    """

    review_run = create_code_review_run(
        session=session,
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
        request=request,
        response=response,
    )

    return response.model_copy(
        update={
            "review_run_id": review_run.id,
            "saved_at": review_run.created_at,
        },
    )


def serialize_code_review_run_source(
    review_run: CodeReviewRun,
) -> CodeReviewSourceSnapshot | None:
    """
    将 CodeReviewRun 中分散保存的
    source_* 字段恢复为来源快照。

    手动 Diff 的 source_provider 为 None，
    此时历史响应中的 source 也为 None。
    """

    if review_run.source_provider is None:
        return None

    required_fields = {
        "source_url":
            review_run.source_url,

        "source_repository":
            review_run.source_repository,

        "source_change_number":
            review_run.source_change_number,

        "source_title":
            review_run.source_title,

        "source_base_ref":
            review_run.source_base_ref,

        "source_head_ref":
            review_run.source_head_ref,

        "source_base_sha":
            review_run.source_base_sha,

        "source_head_sha":
            review_run.source_head_sha,

        "source_diff_hash":
            review_run.source_diff_hash,

        "source_fetched_at":
            review_run.source_fetched_at,
    }

    missing_fields = [
        field_name
        for (
            field_name,
            field_value,
        ) in required_fields.items()
        if field_value is None
        or (
            isinstance(
                field_value,
                str,
            )
            and not field_value.strip()
        )
    ]

    if missing_fields:
        # 改为记录警告并返回 None，不再抛出异常
        logger.warning(
            "Code review source snapshot incomplete for run %s, missing: %s",
            review_run.id,
            ", ".join(missing_fields),
        )
        return None

    return CodeReviewSourceSnapshot(
        provider=(
            review_run.source_provider
        ),

        source_url=(
            review_run.source_url
        ),

        repository=(
            review_run
            .source_repository
        ),

        change_number=(
            review_run
            .source_change_number
        ),

        title=(
            review_run.source_title
        ),

        author=(
            review_run.source_author
        ),

        base_ref=(
            review_run.source_base_ref
        ),

        head_ref=(
            review_run.source_head_ref
        ),

        base_sha=(
            review_run.source_base_sha
        ),

        head_sha=(
            review_run.source_head_sha
        ),

        diff_hash=(
            review_run.source_diff_hash
        ),

        fetched_at=(
            review_run.source_fetched_at
        ),
    )


def serialize_code_review_run_summary(
    review_run: CodeReviewRun,
) -> CodeReviewRunSummaryPublic:
    """
    将数据库记录转换为轻量级历史列表项。
    """

    return CodeReviewRunSummaryPublic(
        id=review_run.id,
        knowledge_base_id=(review_run.knowledge_base_id),
        title=review_run.title,
        generation_status=(review_run.generation_status),
        language=review_run.language,
        risk_level=review_run.risk_level,
        merge_recommendation=(review_run.merge_recommendation),
        changed_file_count=(review_run.changed_file_count),
        changed_symbol_count=(review_run.changed_symbol_count),
        finding_count=(review_run.finding_count),
        recommended_test_count=(review_run.recommended_test_count),
        created_at=review_run.created_at,
        source=serialize_code_review_run_source(
            review_run,
        ),
    )


def serialize_code_review_run_detail(
    review_run: CodeReviewRun,
) -> CodeReviewRunDetailPublic:
    """
    将 JSONB 快照恢复为强类型 API 响应。
    """

    review_report = None

    if review_run.review_report_json:
        review_report = CodeSkillGeneratedReviewReportPublic.model_validate(
            review_run.review_report_json,
        )

    evidence = CodeSkillReviewEvidenceResponse.model_validate(
        review_run.evidence_json,
    )

    generation_trace = CodeSkillReportGenerationTracePublic.model_validate(
        review_run.generation_trace_json,
    )

    return CodeReviewRunDetailPublic(
        id=review_run.id,
        knowledge_base_id=(review_run.knowledge_base_id),
        title=review_run.title,
        generation_status=(review_run.generation_status),
        language=review_run.language,
        risk_level=review_run.risk_level,
        merge_recommendation=(review_run.merge_recommendation),
        changed_file_count=(review_run.changed_file_count),
        changed_symbol_count=(review_run.changed_symbol_count),
        finding_count=(review_run.finding_count),
        recommended_test_count=(review_run.recommended_test_count),
        created_at=review_run.created_at,
        diff_text=review_run.diff_text,
        diff_hash=review_run.diff_hash,
        request_parameters=(review_run.request_parameters_json),
        review_report=review_report,
        review_markdown=(review_run.review_markdown),
        evidence=evidence,
        generation_trace=(generation_trace),
        generation_error=(review_run.generation_error),
        source=serialize_code_review_run_source(
            review_run,
        ),
    )


def list_code_review_runs(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    generation_status: str | None = None,
    risk_level: str | None = None,
) -> CodeReviewRunsPublic:
    """
    分页查询当前用户在指定知识库中的审查历史。
    """

    safe_skip = max(
        int(skip),
        0,
    )

    safe_limit = min(
        max(
            int(limit),
            1,
        ),
        100,
    )

    filters = [
        CodeReviewRun.knowledge_base_id == knowledge_base_id,
        CodeReviewRun.owner_id == owner_id,
    ]

    if generation_status:
        normalized_status = generation_status.strip().lower()

        if normalized_status not in VALID_GENERATION_STATUSES:
            raise ValueError(
                f"Unsupported generation status: {normalized_status}",
            )

        filters.append(
            CodeReviewRun.generation_status == normalized_status,
        )

    if risk_level:
        normalized_risk_level = risk_level.strip().lower()

        if normalized_risk_level not in VALID_RISK_LEVELS:
            raise ValueError(
                f"Unsupported risk level: {normalized_risk_level}",
            )

        filters.append(
            CodeReviewRun.risk_level == normalized_risk_level,
        )

    count_statement = select(
        func.count(
            CodeReviewRun.id,
        )
    ).where(
        *filters,
    )

    total_count = int(
        session.exec(
            count_statement,
        ).one()
    )

    query_statement = (
        select(
            CodeReviewRun,
        )
        .where(
            *filters,
        )
        .order_by(
            CodeReviewRun.created_at.desc(),
            CodeReviewRun.id.desc(),
        )
        .offset(
            safe_skip,
        )
        .limit(
            safe_limit,
        )
    )

    review_runs = list(
        session.exec(
            query_statement,
        ).all()
    )

    return CodeReviewRunsPublic(
        data=[
            serialize_code_review_run_summary(
                review_run,
            )
            for review_run in review_runs
        ],
        count=total_count,
    )


def get_code_review_run(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
    review_run_id: uuid.UUID,
) -> CodeReviewRun | None:
    """
    按记录 ID、知识库 ID 和用户 ID 联合查询。

    不单独按 review_run_id 查询，避免越权访问。
    """

    statement = select(
        CodeReviewRun,
    ).where(
        CodeReviewRun.id == review_run_id,
        CodeReviewRun.knowledge_base_id == knowledge_base_id,
        CodeReviewRun.owner_id == owner_id,
    )

    return session.exec(
        statement,
    ).first()


def get_code_review_run_detail(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
    review_run_id: uuid.UUID,
) -> CodeReviewRunDetailPublic | None:
    """
    查询并序列化一条完整 Review 历史。
    """

    review_run = get_code_review_run(
        session=session,
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
        review_run_id=review_run_id,
    )

    if review_run is None:
        return None

    return serialize_code_review_run_detail(
        review_run,
    )


VALID_PUBLICATION_STATUSES = {
    "publishing",
    "succeeded",
    "failed",
}


def _count_code_review_publications_by_status(
    *,
    session: Session,
    review_run_id: uuid.UUID,
    status: str,
) -> int:
    normalized_status = str(
        status or "",
    ).strip().lower()

    if (
        normalized_status
        not in VALID_PUBLICATION_STATUSES
    ):
        raise ValueError(
            "Unsupported publication "
            f"status: {normalized_status}",
        )

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
            == normalized_status,
        )
    )

    count_result = session.exec(
        statement,
    ).one()

    return int(
        count_result or 0,
    )


def delete_code_review_run(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
    review_run_id: uuid.UUID,
) -> bool:
    """
    删除属于当前用户和知识库的审查历史。

    删除规则：
    1. 记录不存在时返回 False。
    2. 存在成功发布时禁止删除。
    3. 存在正在发布的任务时禁止删除。
    4. 没有成功或正在发布记录时允许删除。
    """

    review_run = get_code_review_run(
        session=session,
        knowledge_base_id=(
            knowledge_base_id
        ),
        owner_id=owner_id,
        review_run_id=review_run_id,
    )

    if review_run is None:
        return False

    successful_publication_count = (
        _count_code_review_publications_by_status(
            session=session,

            review_run_id=(
                review_run.id
            ),

            status="succeeded",
        )
    )

    if successful_publication_count > 0:
        raise (
            CodeReviewRunDeleteBlockedError(
                code=(
                    "REVIEW_RUN_HAS_"
                    "SUCCESSFUL_PUBLICATION"
                ),

                message=(
                    "该 Review 已成功发布到 "
                    "GitHub，必须保留本地"
                    "审查和发布审计记录。"
                ),

                retryable=False,

                context={
                    (
                        "successful_"
                        "publication_count"
                    ):
                        successful_publication_count,
                },
            )
        )

    active_publication_count = (
        _count_code_review_publications_by_status(
            session=session,

            review_run_id=(
                review_run.id
            ),

            status="publishing",
        )
    )

    if active_publication_count > 0:
        raise (
            CodeReviewRunDeleteBlockedError(
                code=(
                    "REVIEW_PUBLICATION_"
                    "IN_PROGRESS"
                ),

                message=(
                    "该 Review 当前正在发布，"
                    "发布结束后再尝试删除。"
                ),

                retryable=True,

                context={
                    (
                        "active_"
                        "publication_count"
                    ):
                        active_publication_count,
                },
            )
        )

    try:
        session.delete(
            review_run,
        )

        session.commit()

    except Exception:
        session.rollback()
        raise

    return True