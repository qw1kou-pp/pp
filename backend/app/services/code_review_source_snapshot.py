from __future__ import annotations

import hashlib
import hmac
from typing import Any

from app.models import (
    CodeReviewSourceSnapshot,
)


class CodeReviewSourceDiffMismatchError(
    ValueError,
):
    """
    表示请求携带的来源快照
    与实际参与审查的 Diff 不一致。
    """


def calculate_code_review_diff_hash(
    diff_text: str,
) -> str:
    """
    对实际 Diff 文本计算 SHA-256。

    必须使用原始字符串，不执行 strip、
    换行转换或其他内容规范化。
    """

    return hashlib.sha256(
        diff_text.encode("utf-8"),
    ).hexdigest()


def validate_and_build_code_review_source_fields(
    *,
    diff_text: str,
    source: (
        CodeReviewSourceSnapshot
        | None
    ),
) -> dict[str, Any]:
    """
    验证来源快照中的 Diff Hash，
    并转换为 CodeReviewRun 数据库字段。

    手动 Diff 模式 source=None，
    返回空字典。
    """

    if source is None:
        return {}

    actual_diff_hash = (
        calculate_code_review_diff_hash(
            diff_text,
        )
    )

    expected_diff_hash = (
        source.diff_hash
        .strip()
        .lower()
    )

    if not hmac.compare_digest(
        actual_diff_hash,
        expected_diff_hash,
    ):
        raise (
            CodeReviewSourceDiffMismatchError(
                "Diff 内容与 PR/MR 来源不一致。"
                "请重新导入来源，或者清除来源后"
                "按手动 Diff 模式生成审查。"
            )
        )

    return {
        "source_provider": (
            source.provider
        ),
        "source_url": (
            source.source_url
        ),
        "source_repository": (
            source.repository
        ),
        "source_change_number": (
            source.change_number
        ),
        "source_title": (
            source.title
        ),
        "source_author": (
            source.author
        ),
        "source_base_ref": (
            source.base_ref
        ),
        "source_head_ref": (
            source.head_ref
        ),
        "source_base_sha": (
            source.base_sha
        ),
        "source_head_sha": (
            source.head_sha
        ),
        "source_diff_hash": (
            expected_diff_hash
        ),
        "source_fetched_at": (
            source.fetched_at
        ),
    }