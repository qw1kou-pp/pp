"""add retrieval tuning params

Revision ID: bfa66ba12a7b
Revises: c5ace850bf78
Create Date: 2026-07-07 02:31:01.175561

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'bfa66ba12a7b'
down_revision = 'c5ace850bf78'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "rag_run",
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "rag_run",
        sa.Column("semantic_weight", sa.Float(), nullable=False, server_default="0.75"),
    )
    op.add_column(
        "rag_run",
        sa.Column("keyword_weight", sa.Float(), nullable=False, server_default="0.25"),
    )

    op.add_column(
        "rag_eval_run",
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "rag_eval_run",
        sa.Column("semantic_weight", sa.Float(), nullable=False, server_default="0.75"),
    )
    op.add_column(
        "rag_eval_run",
        sa.Column("keyword_weight", sa.Float(), nullable=False, server_default="0.25"),
    )

    op.alter_column("rag_run", "top_k", server_default=None)
    op.alter_column("rag_run", "semantic_weight", server_default=None)
    op.alter_column("rag_run", "keyword_weight", server_default=None)

    op.alter_column("rag_eval_run", "top_k", server_default=None)
    op.alter_column("rag_eval_run", "semantic_weight", server_default=None)
    op.alter_column("rag_eval_run", "keyword_weight", server_default=None)
    # ### end Alembic commands ###


def downgrade():
    op.drop_column("rag_eval_run", "keyword_weight")
    op.drop_column("rag_eval_run", "semantic_weight")
    op.drop_column("rag_eval_run", "top_k")

    op.drop_column("rag_run", "keyword_weight")
    op.drop_column("rag_run", "semantic_weight")
    op.drop_column("rag_run", "top_k")
    # ### end Alembic commands ###
