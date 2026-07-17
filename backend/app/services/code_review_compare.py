from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from app.models import (
    CodeReviewCompareFindingPublic,
    CodeReviewCompareResponse,
    CodeReviewCompareTestPublic,
    CodeReviewFindingChangesPublic,
    CodeReviewMetricChangePublic,
    CodeReviewMetricChangesPublic,
    CodeReviewOverallChangePublic,
    CodeReviewRunCompareReferencePublic,
    CodeReviewRunDetailPublic,
    CodeReviewTestChangesPublic,
    CodeReviewTraceChangesPublic,
    CodeReviewValueChangePublic,
)


RISK_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


def _read_value(
    item: Any,
    *names: str,
    default: Any = None,
) -> Any:
    """
    同时兼容字典、Pydantic 模型和测试对象。
    """

    if item is None:
        return default

    if isinstance(item, dict):
        for name in names:
            if (
                name in item
                and item[name] is not None
            ):
                return item[name]

        return default

    for name in names:
        value = getattr(
            item,
            name,
            None,
        )

        if value is not None:
            return value

    return default


def _read_list(
    item: Any,
    *names: str,
) -> list[Any]:
    value = _read_value(
        item,
        *names,
        default=[],
    )

    if isinstance(
        value,
        list,
    ):
        return value

    if isinstance(
        value,
        tuple,
    ):
        return list(value)

    return []


def _read_text(
    item: Any,
    *names: str,
) -> str | None:
    value = _read_value(
        item,
        *names,
    )

    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _read_int(
    item: Any,
    *names: str,
) -> int | None:
    value = _read_value(
        item,
        *names,
    )

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _read_int_or_zero(
    item: Any,
    *names: str,
) -> int:
    value = _read_int(
        item,
        *names,
    )

    return (
        value
        if value is not None
        else 0
    )


def normalize_compare_text(
    value: Any,
) -> str:
    """
    对参与指纹计算的文本进行稳定化。

    统一 Unicode、大小写和连续空白，
    但不进行语义改写。
    """

    if value is None:
        return ""

    normalized = (
        unicodedata.normalize(
            "NFKC",
            str(value),
        )
        .strip()
        .lower()
    )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    )


def _build_fingerprint(
    *parts: Any,
) -> str:
    normalized_parts = [
        normalize_compare_text(
            part,
        )
        for part in parts
    ]

    canonical_value = "\x1f".join(
        normalized_parts,
    )

    return hashlib.sha256(
        canonical_value.encode(
            "utf-8",
        ),
    ).hexdigest()


def build_finding_fingerprint(
    finding: Any,
) -> str:
    """
    Finding 指纹不使用 finding_id。

    因为同一个问题在两次 LLM 生成中，
    可能分别被编号为 F-001 和 F-005。
    """

    title = _read_text(
        finding,
        "title",
        "name",
    )

    category = _read_text(
        finding,
        "category",
        "finding_category",
    )

    severity = _read_text(
        finding,
        "severity",
        "risk_level",
    )

    description = _read_text(
        finding,
        "description",
        "detail",
        "summary",
    )

    if not any(
        [
            title,
            category,
            severity,
            description,
        ],
    ):
        fallback_id = _read_text(
            finding,
            "finding_id",
            "id",
        )

        return _build_fingerprint(
            "finding",
            fallback_id
            or "unnamed-finding",
        )

    return _build_fingerprint(
        category,
        severity,
        title,
        description,
    )


def build_test_fingerprint(
    test_item: Any,
) -> str:
    file_path = _read_text(
        test_item,
        "file_path",
        "test_file_path",
        "target_file",
        "path",
    )

    test_type = _read_text(
        test_item,
        "test_type",
        "type",
        "category",
    )

    title = _read_text(
        test_item,
        "title",
        "test_name",
        "name",
    )

    reason = _read_text(
        test_item,
        "reason",
        "description",
        "rationale",
    )

    if not any(
        [
            file_path,
            test_type,
            title,
            reason,
        ],
    ):
        fallback_id = _read_text(
            test_item,
            "test_id",
            "id",
        )

        return _build_fingerprint(
            "test",
            fallback_id
            or "unnamed-test",
        )

    return _build_fingerprint(
        file_path,
        test_type,
        title,
        reason,
    )


def _to_compare_finding(
    finding: Any,
) -> CodeReviewCompareFindingPublic:
    title = _read_text(
        finding,
        "title",
        "name",
    )

    return CodeReviewCompareFindingPublic(
        fingerprint=(
            build_finding_fingerprint(
                finding,
            )
        ),
        title=(
            title
            or "未命名 Finding"
        ),
        severity=_read_text(
            finding,
            "severity",
            "risk_level",
        ),
        category=_read_text(
            finding,
            "category",
            "finding_category",
        ),
        description=_read_text(
            finding,
            "description",
            "detail",
            "summary",
        ),
        recommendation=_read_text(
            finding,
            "recommendation",
            "suggestion",
            "remediation",
        ),
    )


def _to_compare_test(
    test_item: Any,
) -> CodeReviewCompareTestPublic:
    file_path = _read_text(
        test_item,
        "file_path",
        "test_file_path",
        "target_file",
        "path",
    )

    reason = _read_text(
        test_item,
        "reason",
        "description",
        "rationale",
    )

    title = _read_text(
        test_item,
        "title",
        "test_name",
        "name",
    )

    return CodeReviewCompareTestPublic(
        fingerprint=(
            build_test_fingerprint(
                test_item,
            )
        ),
        title=(
            title
            or reason
            or file_path
            or "未命名测试建议"
        ),
        test_type=_read_text(
            test_item,
            "test_type",
            "type",
            "category",
        ),
        file_path=file_path,
        reason=reason,
    )


def compare_finding_items(
    *,
    base_items: list[Any],
    target_items: list[Any],
) -> CodeReviewFindingChangesPublic:
    base_lookup = {
        build_finding_fingerprint(
            item,
        ): item
        for item in base_items
    }

    target_lookup = {
        build_finding_fingerprint(
            item,
        ): item
        for item in target_items
    }

    base_fingerprints = set(
        base_lookup,
    )

    target_fingerprints = set(
        target_lookup,
    )

    added_fingerprints = sorted(
        target_fingerprints
        - base_fingerprints,
    )

    resolved_fingerprints = sorted(
        base_fingerprints
        - target_fingerprints,
    )

    persisting_fingerprints = sorted(
        base_fingerprints
        & target_fingerprints,
    )

    return CodeReviewFindingChangesPublic(
        added=[
            _to_compare_finding(
                target_lookup[
                    fingerprint
                ],
            )
            for fingerprint
            in added_fingerprints
        ],
        resolved=[
            _to_compare_finding(
                base_lookup[
                    fingerprint
                ],
            )
            for fingerprint
            in resolved_fingerprints
        ],
        persisting=[
            _to_compare_finding(
                target_lookup[
                    fingerprint
                ],
            )
            for fingerprint
            in persisting_fingerprints
        ],
    )


def compare_test_items(
    *,
    base_items: list[Any],
    target_items: list[Any],
) -> CodeReviewTestChangesPublic:
    base_lookup = {
        build_test_fingerprint(
            item,
        ): item
        for item in base_items
    }

    target_lookup = {
        build_test_fingerprint(
            item,
        ): item
        for item in target_items
    }

    base_fingerprints = set(
        base_lookup,
    )

    target_fingerprints = set(
        target_lookup,
    )

    added_fingerprints = sorted(
        target_fingerprints
        - base_fingerprints,
    )

    removed_fingerprints = sorted(
        base_fingerprints
        - target_fingerprints,
    )

    persisting_fingerprints = sorted(
        base_fingerprints
        & target_fingerprints,
    )

    return CodeReviewTestChangesPublic(
        added=[
            _to_compare_test(
                target_lookup[
                    fingerprint
                ],
            )
            for fingerprint
            in added_fingerprints
        ],
        removed=[
            _to_compare_test(
                base_lookup[
                    fingerprint
                ],
            )
            for fingerprint
            in removed_fingerprints
        ],
        persisting=[
            _to_compare_test(
                target_lookup[
                    fingerprint
                ],
            )
            for fingerprint
            in persisting_fingerprints
        ],
    )


def build_metric_change(
    *,
    base_value: int,
    target_value: int,
) -> CodeReviewMetricChangePublic:
    delta = (
        target_value
        - base_value
    )

    if delta > 0:
        trend = "increased"
    elif delta < 0:
        trend = "decreased"
    else:
        trend = "unchanged"

    return CodeReviewMetricChangePublic(
        base_value=base_value,
        target_value=target_value,
        delta=delta,
        trend=trend,
    )


def build_value_change(
    *,
    base_value: str | None,
    target_value: str | None,
) -> CodeReviewValueChangePublic:
    normalized_base = (
        normalize_compare_text(
            base_value,
        )
        or None
    )

    normalized_target = (
        normalize_compare_text(
            target_value,
        )
        or None
    )

    if (
        normalized_base is None
        or normalized_target is None
    ):
        trend = "unavailable"
    elif (
        normalized_base
        == normalized_target
    ):
        trend = "unchanged"
    else:
        trend = "changed"

    return CodeReviewValueChangePublic(
        base_value=normalized_base,
        target_value=normalized_target,
        trend=trend,
    )


def build_risk_change(
    *,
    base_value: str | None,
    target_value: str | None,
) -> CodeReviewValueChangePublic:
    normalized_base = (
        normalize_compare_text(
            base_value,
        )
        or None
    )

    normalized_target = (
        normalize_compare_text(
            target_value,
        )
        or None
    )

    if (
        normalized_base is None
        or normalized_target is None
    ):
        trend = "unavailable"
    elif (
        normalized_base
        == normalized_target
    ):
        trend = "unchanged"
    elif (
        normalized_base
        in RISK_RANK
        and normalized_target
        in RISK_RANK
    ):
        if (
            RISK_RANK[
                normalized_target
            ]
            >
            RISK_RANK[
                normalized_base
            ]
        ):
            trend = "increased"
        else:
            trend = "decreased"
    else:
        trend = "changed"

    return CodeReviewValueChangePublic(
        base_value=normalized_base,
        target_value=normalized_target,
        trend=trend,
    )


def _get_findings(
    review: Any,
) -> list[Any]:
    review_report = _read_value(
        review,
        "review_report",
    )

    return _read_list(
        review_report,
        "findings",
    )


def _get_tests(
    review: Any,
) -> list[Any]:
    review_report = _read_value(
        review,
        "review_report",
    )

    report_tests = _read_list(
        review_report,
        "test_plan",
        "tests",
    )

    if report_tests:
        return report_tests

    evidence = _read_value(
        review,
        "evidence",
    )

    return _read_list(
        evidence,
        "recommended_tests",
        "test_recommendations",
    )


def _build_review_reference(
    review: CodeReviewRunDetailPublic,
) -> CodeReviewRunCompareReferencePublic:
    return CodeReviewRunCompareReferencePublic(
        id=_read_value(
            review,
            "id",
        ),
        title=(
            _read_text(
                review,
                "title",
            )
            or "RepoGuard Review"
        ),
        created_at=_read_value(
            review,
            "created_at",
        ),
        generation_status=_read_text(
            review,
            "generation_status",
        )
        or "evidence_only",
        risk_level=_read_text(
            review,
            "risk_level",
        ),
        merge_recommendation=_read_text(
            review,
            "merge_recommendation",
        ),
        diff_hash=_read_text(
            review,
            "diff_hash",
        )
        or "",
    )


def _build_optional_trace_metric(
    *,
    base_trace: Any,
    target_trace: Any,
    field_name: str,
) -> CodeReviewMetricChangePublic | None:
    base_value = _read_int(
        base_trace,
        field_name,
    )

    target_value = _read_int(
        target_trace,
        field_name,
    )

    if (
        base_value is None
        or target_value is None
    ):
        return None

    return build_metric_change(
        base_value=base_value,
        target_value=target_value,
    )


def _build_summary(
    *,
    same_diff: bool,
    risk_change: CodeReviewValueChangePublic,
    merge_change: CodeReviewValueChangePublic,
    finding_change: CodeReviewMetricChangePublic,
    test_change: CodeReviewMetricChangePublic,
) -> str:
    summary_parts: list[str] = []

    if same_diff:
        summary_parts.append(
            "两次审查基于相同的 Diff。"
        )
    else:
        summary_parts.append(
            "两次审查的 Diff 已发生变化。"
        )

    risk_summary_map = {
        "increased": (
            "目标版本的风险等级上升。"
        ),
        "decreased": (
            "目标版本的风险等级下降。"
        ),
        "unchanged": (
            "目标版本的风险等级保持不变。"
        ),
        "changed": (
            "目标版本的风险状态发生变化。"
        ),
        "unavailable": (
            "当前缺少完整的风险等级，"
            "无法判断风险趋势。"
        ),
    }

    summary_parts.append(
        risk_summary_map[
            risk_change.trend
        ],
    )

    if finding_change.delta > 0:
        summary_parts.append(
            "目标版本新增了 "
            f"{finding_change.delta} 个 Finding。"
        )
    elif finding_change.delta < 0:
        summary_parts.append(
            "目标版本的 Finding "
            f"减少了 {abs(finding_change.delta)} 个。"
        )
    else:
        summary_parts.append(
            "Finding 总数保持不变。"
        )

    if test_change.delta > 0:
        summary_parts.append(
            "推荐测试增加了 "
            f"{test_change.delta} 项。"
        )
    elif test_change.delta < 0:
        summary_parts.append(
            "推荐测试减少了 "
            f"{abs(test_change.delta)} 项。"
        )
    else:
        summary_parts.append(
            "推荐测试数量保持不变。"
        )

    if merge_change.trend == "changed":
        summary_parts.append(
            "合并建议发生了变化。"
        )
    elif (
        merge_change.trend
        == "unavailable"
    ):
        summary_parts.append(
            "至少一条记录缺少合并建议。"
        )

    return "".join(
        summary_parts,
    )


def compare_code_review_runs(
    *,
    base_review: CodeReviewRunDetailPublic,
    target_review: CodeReviewRunDetailPublic,
) -> CodeReviewCompareResponse:
    """
    对两条 Review 历史快照进行确定性比较。

    A 为 base_review，B 为 target_review。
    所有 delta 均按照 B - A 计算。
    """

    base_diff_hash = (
        _read_text(
            base_review,
            "diff_hash",
        )
        or ""
    )

    target_diff_hash = (
        _read_text(
            target_review,
            "diff_hash",
        )
        or ""
    )

    same_diff = (
        bool(base_diff_hash)
        and base_diff_hash
        == target_diff_hash
    )

    risk_change = build_risk_change(
        base_value=_read_text(
            base_review,
            "risk_level",
        ),
        target_value=_read_text(
            target_review,
            "risk_level",
        ),
    )

    merge_change = build_value_change(
        base_value=_read_text(
            base_review,
            "merge_recommendation",
        ),
        target_value=_read_text(
            target_review,
            "merge_recommendation",
        ),
    )

    generation_status_change = (
        build_value_change(
            base_value=_read_text(
                base_review,
                "generation_status",
            ),
            target_value=_read_text(
                target_review,
                "generation_status",
            ),
        )
    )

    changed_file_change = (
        build_metric_change(
            base_value=(
                _read_int_or_zero(
                    base_review,
                    "changed_file_count",
                )
            ),
            target_value=(
                _read_int_or_zero(
                    target_review,
                    "changed_file_count",
                )
            ),
        )
    )

    changed_symbol_change = (
        build_metric_change(
            base_value=(
                _read_int_or_zero(
                    base_review,
                    "changed_symbol_count",
                )
            ),
            target_value=(
                _read_int_or_zero(
                    target_review,
                    "changed_symbol_count",
                )
            ),
        )
    )

    finding_count_change = (
        build_metric_change(
            base_value=(
                _read_int_or_zero(
                    base_review,
                    "finding_count",
                )
            ),
            target_value=(
                _read_int_or_zero(
                    target_review,
                    "finding_count",
                )
            ),
        )
    )

    test_count_change = (
        build_metric_change(
            base_value=(
                _read_int_or_zero(
                    base_review,
                    "recommended_test_count",
                )
            ),
            target_value=(
                _read_int_or_zero(
                    target_review,
                    "recommended_test_count",
                )
            ),
        )
    )

    finding_changes = (
        compare_finding_items(
            base_items=_get_findings(
                base_review,
            ),
            target_items=_get_findings(
                target_review,
            ),
        )
    )

    test_changes = compare_test_items(
        base_items=_get_tests(
            base_review,
        ),
        target_items=_get_tests(
            target_review,
        ),
    )

    base_trace = _read_value(
        base_review,
        "generation_trace",
    )

    target_trace = _read_value(
        target_review,
        "generation_trace",
    )

    trace_changes = (
        CodeReviewTraceChangesPublic(
            model=build_value_change(
                base_value=_read_text(
                    base_trace,
                    "model",
                ),
                target_value=_read_text(
                    target_trace,
                    "model",
                ),
            ),
            duration_ms=(
                _build_optional_trace_metric(
                    base_trace=base_trace,
                    target_trace=target_trace,
                    field_name="duration_ms",
                )
            ),
            evidence_item_count=(
                _build_optional_trace_metric(
                    base_trace=base_trace,
                    target_trace=target_trace,
                    field_name=(
                        "evidence_item_count"
                    ),
                )
            ),
            output_characters=(
                _build_optional_trace_metric(
                    base_trace=base_trace,
                    target_trace=target_trace,
                    field_name=(
                        "output_characters"
                    ),
                )
            ),
        )
    )

    return CodeReviewCompareResponse(
        base_review=(
            _build_review_reference(
                base_review,
            )
        ),
        target_review=(
            _build_review_reference(
                target_review,
            )
        ),
        overall_change=(
            CodeReviewOverallChangePublic(
                same_diff=same_diff,
                risk=risk_change,
                merge_recommendation=(
                    merge_change
                ),
                generation_status=(
                    generation_status_change
                ),
                summary=_build_summary(
                    same_diff=same_diff,
                    risk_change=(
                        risk_change
                    ),
                    merge_change=(
                        merge_change
                    ),
                    finding_change=(
                        finding_count_change
                    ),
                    test_change=(
                        test_count_change
                    ),
                ),
            )
        ),
        metric_changes=(
            CodeReviewMetricChangesPublic(
                changed_file_count=(
                    changed_file_change
                ),
                changed_symbol_count=(
                    changed_symbol_change
                ),
                finding_count=(
                    finding_count_change
                ),
                recommended_test_count=(
                    test_count_change
                ),
            )
        ),
        finding_changes=(
            finding_changes
        ),
        test_changes=test_changes,
        trace_changes=trace_changes,
    )