from __future__ import annotations

from app.models import CodeReviewRun


SOURCE_COLUMN_NAMES = {
    "source_provider",
    "source_url",
    "source_repository",
    "source_change_number",
    "source_title",
    "source_author",
    "source_base_ref",
    "source_head_ref",
    "source_base_sha",
    "source_head_sha",
    "source_fetched_at",
}


def test_code_review_run_declares_source_columns() -> None:
    """
    CodeReviewRun 数据库表必须声明全部来源字段。
    """

    actual_column_names = set(
        CodeReviewRun.__table__.columns.keys(),
    )

    assert SOURCE_COLUMN_NAMES.issubset(
        actual_column_names,
    )


def test_code_review_run_source_columns_are_nullable() -> None:
    """
    来源字段必须允许 NULL。

    旧 Review 和手动粘贴 Diff 生成的 Review
    都没有 GitHub/GitLab 来源信息。
    """

    columns = CodeReviewRun.__table__.columns

    for column_name in SOURCE_COLUMN_NAMES:
        assert columns[column_name].nullable is True


def test_code_review_run_source_fields_default_to_none() -> None:
    """
    Python 模型层的来源字段默认值必须是 None。
    """

    for field_name in SOURCE_COLUMN_NAMES:
        field = CodeReviewRun.model_fields[field_name]

        assert field.default is None


def test_source_lookup_columns_are_indexed() -> None:
    """
    后续需要根据平台、仓库和 PR/MR 编号
    查询同一变更的多次 Review。
    """

    columns = CodeReviewRun.__table__.columns

    indexed_column_names = {
        "source_provider",
        "source_repository",
        "source_change_number",
    }

    for column_name in indexed_column_names:
        assert columns[column_name].index is True
