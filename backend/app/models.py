import uuid
from datetime import timezone, datetime, timedelta
from typing import Any, Literal
from pydantic import EmailStr
from sqlalchemy import (
    Column,
    DateTime,
    Text,
    UniqueConstraint,
    Index,
    text,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_repository_analysis_expiry() -> datetime:
    """返回临时仓库分析结果的默认过期时间。"""

    return get_datetime_utc() + timedelta(hours=24)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    knowledge_bases: list["KnowledgeBase"] = Relationship(
        back_populates="owner",
        cascade_delete=True,
    )
    documents: list["Document"] = Relationship(
        back_populates="owner",
        cascade_delete=True,
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Shared properties
class KnowledgeBaseBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on knowledge base creation
class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


# Properties to receive on knowledge base update
class KnowledgeBaseUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class KnowledgeBase(KnowledgeBaseBase, table=True):
    __tablename__ = "knowledge_base"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner: User | None = Relationship(back_populates="knowledge_bases")
    documents: list["Document"] = Relationship(
        back_populates="knowledge_base",
        cascade_delete=True,
    )


class DocumentBase(SQLModel):
    original_filename: str = Field(max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    file_size: int = Field(ge=0)
    status: str = Field(default="uploaded", max_length=50)
    error_message: str | None = Field(default=None, max_length=1024)


class DocumentCreate(DocumentBase):
    filename: str = Field(max_length=255)
    storage_path: str = Field(max_length=1024)
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID


class DocumentUpdate(SQLModel):
    status: str | None = Field(default=None, max_length=50)
    error_message: str | None = Field(default=None, max_length=1024)


class Document(DocumentBase, table=True):
    __tablename__ = "document"

    chunks: list["DocumentChunk"] = Relationship(
        back_populates="document",
        cascade_delete=True,
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    repository_analysis_task_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="repository_analysis_task.id",
        nullable=True,
        ondelete="SET NULL",
        index=True,
    )

    repository_relative_path: str | None = Field(
        default=None,
        max_length=2048,
    )

    source_commit_sha: str | None = Field(
        default=None,
        max_length=64,
        index=True,
    )
    filename: str = Field(max_length=255)
    storage_path: str = Field(max_length=1024)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    knowledge_base: KnowledgeBase | None = Relationship(back_populates="documents")
    owner: User | None = Relationship(back_populates="documents")


class DocumentPublic(DocumentBase):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID

    repository_analysis_task_id: uuid.UUID | None = None
    repository_relative_path: str | None = None
    source_commit_sha: str | None = None

    filename: str
    storage_path: str
    created_at: datetime | None = None


class DocumentsPublic(SQLModel):
    data: list[DocumentPublic]
    count: int


class DocumentChunkBase(SQLModel):
    chunk_index: int = Field(ge=0)
    content: str = Field(sa_column=Column(Text, nullable=False))
    content_length: int = Field(ge=0)


class DocumentChunk(DocumentChunkBase, table=True):
    __tablename__ = "document_chunk"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunk_document_id_chunk_index",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    document_id: uuid.UUID = Field(
        foreign_key="document.id",
        nullable=False,
        ondelete="CASCADE",
    )
    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    embedding: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    embedding_model: str | None = Field(default=None, max_length=255)
    embedding_status: str = Field(default="pending", max_length=50)
    embedding_error: str | None = Field(default=None, max_length=1024)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    document: Document | None = Relationship(back_populates="chunks")


class DocumentChunkPublic(DocumentChunkBase):
    id: uuid.UUID
    document_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID
    embedding_model: str | None = None
    embedding_status: str = "pending"
    embedding_error: str | None = None
    created_at: datetime | None = None
    created_at: datetime | None = None


class DocumentChunksPublic(SQLModel):
    data: list[DocumentChunkPublic]
    count: int


class KnowledgeBaseSearchRequest(SQLModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class KnowledgeBaseSearchResult(SQLModel):
    document_id: uuid.UUID
    original_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    content: str
    content_length: int
    match_count: int = 0


class KnowledgeBaseSearchResults(SQLModel):
    data: list[KnowledgeBaseSearchResult]
    count: int


class RagChatRequest(SQLModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)
    repository_analysis_task_id: (
        uuid.UUID | None
    ) = None


class RagChatSource(SQLModel):
    document_id: uuid.UUID
    original_filename: str
    repository_analysis_task_id: (
        uuid.UUID | None
    ) = None

    repository_relative_path: (
        str | None
    ) = None

    source_commit_sha: (
        str | None
    ) = None
    chunk_id: uuid.UUID
    chunk_index: int
    content: str
    content_length: int
    match_count: int = 0
    similarity: float | None = None
    retrieval_type: str = "keyword"


class RagChatResponse(SQLModel):
    answer: str
    sources: list[RagChatSource]
    trace: list[str]
    run_id: uuid.UUID | None = None
    latency_ms: int | None = None


class AgentToolCallPublic(SQLModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    observation: str
    success: bool = True


class AgentChatRequest(SQLModel):
  question: str = Field(
    min_length=1,
    max_length=1000,
  )

  top_k: int = Field(
    default=5,
    ge=1,
    le=20,
  )

  max_steps: int = Field(
    default=3,
    ge=1,
    le=10,
  )

  semantic_weight: float = Field(
    default=0.75,
    ge=0,
    le=1,
  )

  keyword_weight: float = Field(
    default=0.25,
    ge=0,
    le=1,
  )
  repository_analysis_task_id: uuid.UUID | None = None


class AgentChatResponse(SQLModel):
    agent_run_id: uuid.UUID | None = None
    answer: str
    tool_calls: list[AgentToolCallPublic]
    sources: list[RagChatSource]
    trace: list[str]
    latency_ms: int | None = None


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_run"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    repository_analysis_task_id: uuid.UUID | None = Field(
        default=None,
        foreign_key=(
            "repository_analysis_task.id"
        ),
        nullable=True,
        ondelete="SET NULL",
        index=True,
    )

    source_commit_sha: str | None = Field(
        default=None,
        max_length=64,
    )

    question: str = Field(sa_column=Column(Text, nullable=False))
    answer: str = Field(sa_column=Column(Text, nullable=False))

    top_k: int = Field(default=5, ge=1, le=20)
    max_steps: int = Field(default=3, ge=1, le=10)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)

    latency_ms: int | None = Field(default=None, ge=0)

    tool_calls_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )
    sources_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )
    trace_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )

    error_message: str | None = Field(default=None, max_length=1024)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class AgentRunPublic(SQLModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID

    repository_analysis_task_id: uuid.UUID | None = None

    source_commit_sha: str | None = None

    question: str
    answer: str

    top_k: int
    max_steps: int
    semantic_weight: float
    keyword_weight: float

    latency_ms: int | None = None

    tool_calls: list[
        AgentToolCallPublic
    ] = Field(
        default_factory=list,
    )

    sources: list[
        RagChatSource
    ] = Field(
        default_factory=list,
    )

    trace: list[str] = Field(
        default_factory=list,
    )

    error_message: str | None = None
    created_at: datetime | None = None


class AgentRunsPublic(SQLModel):
    data: list[AgentRunPublic]
    count: int


class KnowledgeBaseAgentSettings(SQLModel, table=True):
    __tablename__ = "knowledge_base_agent_settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
    )

    top_k: int = Field(default=5, ge=1, le=20)
    max_steps: int = Field(default=5, ge=1, le=10)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class CodeReviewRun(SQLModel, table=True):
    """
    RepoGuard 单次代码审查运行的不可变快照。

    每次完成 Evidence Pipeline 后创建一条记录。
    completed 和 evidence_only 两种执行结果都会保存。
    """

    __tablename__ = "code_review_run"

    __table_args__ = (
        Index(
            "ix_code_review_run_knowledge_base_created_at",
            "knowledge_base_id",
            "created_at",
        ),
        Index(
            "ix_code_review_run_owner_created_at",
            "owner_id",
            "created_at",
        ),
        Index(
            "ix_code_review_run_knowledge_base_status",
            "knowledge_base_id",
            "generation_status",
        ),
        Index(
            "ix_code_review_run_knowledge_base_risk",
            "knowledge_base_id",
            "risk_level",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )

    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        index=True,
    )

    owner_id: uuid.UUID = Field(
        nullable=False,
        index=True,
    )

    title: str = Field(
        default="RepoGuard Review",
        max_length=200,
        nullable=False,
    )

    diff_text: str = Field(
        sa_column=Column(
            Text,
            nullable=False,
        ),
    )

    diff_hash: str = Field(
        max_length=64,
        nullable=False,
        index=True,
    )

    source_provider: str | None = Field(
        default=None,
        max_length=16,
        index=True,
    )

    source_url: str | None = Field(
        default=None,
        max_length=2048,
    )

    source_repository: str | None = Field(
        default=None,
        max_length=512,
        index=True,
    )

    source_change_number: int | None = Field(
        default=None,
        ge=1,
        index=True,
    )

    source_title: str | None = Field(
        default=None,
        max_length=512,
    )

    source_author: str | None = Field(
        default=None,
        max_length=255,
    )

    source_base_ref: str | None = Field(
        default=None,
        max_length=255,
    )

    source_head_ref: str | None = Field(
        default=None,
        max_length=255,
    )

    source_base_sha: str | None = Field(
        default=None,
        max_length=64,
    )

    source_head_sha: str | None = Field(
        default=None,
        max_length=64,
    )

    source_diff_hash: str | None = Field(
        default=None,
        max_length=64,
    )

    source_fetched_at: datetime | None = Field(
        default=None,
    )

    generation_status: str = Field(
        max_length=32,
        nullable=False,
        index=True,
    )

    language: str = Field(
        default="zh-CN",
        max_length=16,
        nullable=False,
    )

    risk_level: str | None = Field(
        default=None,
        max_length=16,
        index=True,
    )

    merge_recommendation: str | None = Field(
        default=None,
        max_length=32,
    )

    changed_file_count: int = Field(
        default=0,
        ge=0,
        nullable=False,
    )

    changed_symbol_count: int = Field(
        default=0,
        ge=0,
        nullable=False,
    )

    finding_count: int = Field(
        default=0,
        ge=0,
        nullable=False,
    )

    recommended_test_count: int = Field(
        default=0,
        ge=0,
        nullable=False,
    )

    request_parameters_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
        ),
    )

    review_report_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            JSONB,
            nullable=True,
        ),
    )

    review_markdown: str | None = Field(
        default=None,
        sa_column=Column(
            Text,
            nullable=True,
        ),
    )

    evidence_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
        ),
    )

    generation_trace_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
        ),
    )

    generation_error: str | None = Field(
        default=None,
        sa_column=Column(
            Text,
            nullable=True,
        ),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
    )


class CodeReviewPublication(
    SQLModel,
    table=True,
):
    """
    一次 RepoGuard Review 向外部平台
    发布的审计记录。

    第一版只支持 GitHub 正式 PR Review，
    但表名和字段保持平台通用。
    """

    __tablename__ = "code_review_publication"

    __table_args__ = (
        UniqueConstraint(
            "review_run_id",
            "attempt_number",
            name=("uq_code_review_publication_run_attempt"),
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name=("ck_code_review_publication_attempt_positive"),
        ),
        CheckConstraint(
            "provider IN ('github')",
            name=("ck_code_review_publication_provider"),
        ),
        CheckConstraint(
            ("publication_type IN ('pull_request_review')"),
            name=("ck_code_review_publication_type"),
        ),
        CheckConstraint(
            ("requested_event IN ('COMMENT', 'APPROVE', 'REQUEST_CHANGES')"),
            name=("ck_code_review_publication_event"),
        ),
        CheckConstraint(
            ("status IN ('publishing', 'succeeded', 'failed')"),
            name=("ck_code_review_publication_status"),
        ),
        Index(
            ("ix_code_review_publication_run_status"),
            "review_run_id",
            "status",
        ),
        Index(
            ("ix_code_review_publication_run_created_at"),
            "review_run_id",
            "created_at",
        ),
        Index(
            ("ix_code_review_publication_owner_created_at"),
            "owner_id",
            "created_at",
        ),
        Index(
            ("ix_code_review_publication_knowledge_base_created_at"),
            "knowledge_base_id",
            "created_at",
        ),
        # 同一 Review Run 同一时刻只允许
        # 存在一个 publishing 尝试。
        Index(
            ("uq_code_review_publication_active_attempt"),
            "review_run_id",
            unique=True,
            postgresql_where=text(
                "status = 'publishing'",
            ),
        ),
        # 避免同一个外部 Review 被重复记录。
        Index(
            ("uq_code_review_publication_external_review"),
            "provider",
            "external_review_id",
            unique=True,
            postgresql_where=text(
                ("external_review_id IS NOT NULL"),
            ),
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )

    knowledge_base_id: uuid.UUID = Field(
        foreign_key=("knowledge_base.id"),
        nullable=False,
        ondelete="CASCADE",
    )

    review_run_id: uuid.UUID = Field(
        foreign_key=("code_review_run.id"),
        nullable=False,
        ondelete="CASCADE",
    )

    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    # 第一版固定为 github。
    provider: str = Field(
        default="github",
        max_length=50,
        nullable=False,
    )

    publication_type: str = Field(
        default="pull_request_review",
        max_length=50,
        nullable=False,
    )

    requested_event: str = Field(
        max_length=50,
        nullable=False,
    )

    status: str = Field(
        default="publishing",
        max_length=50,
        nullable=False,
    )

    # 发布目标快照
    target_repository: str = Field(
        max_length=255,
        nullable=False,
    )

    target_change_number: int = Field(
        ge=1,
        nullable=False,
    )

    # Git SHA-1 为 40 位；
    # 预留 SHA-256，使用 64 位。
    target_head_sha: str = Field(
        max_length=64,
        nullable=False,
    )

    target_source_url: str = Field(
        max_length=2048,
        nullable=False,
    )

    attempt_number: int = Field(
        default=1,
        ge=1,
        nullable=False,
    )

    force_republish: bool = Field(
        default=False,
        nullable=False,
    )

    # 实际发送正文快照
    body_markdown: str = Field(
        sa_column=Column(
            Text,
            nullable=False,
        ),
    )

    body_hash: str = Field(
        max_length=64,
        nullable=False,
    )

    # GitHub 成功响应
    external_review_id: str | None = Field(
        default=None,
        max_length=128,
    )

    external_review_url: str | None = Field(
        default=None,
        max_length=2048,
    )

    external_review_state: str | None = Field(
        default=None,
        max_length=100,
    )

    external_actor: str | None = Field(
        default=None,
        max_length=255,
    )

    # 清理敏感信息后的错误
    error_code: str | None = Field(
        default=None,
        max_length=100,
    )

    error_message: str | None = Field(
        default=None,
        sa_column=Column(
            Text,
            nullable=True,
        ),
    )

    created_at: datetime | None = Field(
        default_factory=(get_datetime_utc),
        sa_type=(
            DateTime(
                timezone=True,
            )
        ),
    )

    updated_at: datetime | None = Field(
        default_factory=(get_datetime_utc),
        sa_type=(
            DateTime(
                timezone=True,
            )
        ),
    )

    published_at: datetime | None = Field(
        default=None,
        sa_type=(
            DateTime(
                timezone=True,
            )
        ),
    )


class GitHubReviewPublicationRequest(
    SQLModel,
):
    """
    用户确认发布时允许提交的字段。

    仓库、PR、SHA 和正文全部从
    CodeReviewRun 中读取，前端不能覆盖。
    """

    event: str | None = Field(
        default=None,
        max_length=50,
    )

    force_republish: bool = False


class CodeReviewPublicationPublic(
    SQLModel,
):
    id: uuid.UUID

    knowledge_base_id: uuid.UUID
    review_run_id: uuid.UUID

    provider: str
    publication_type: str

    requested_event: str
    status: str

    target_repository: str
    target_change_number: int
    target_head_sha: str
    target_source_url: str

    attempt_number: int
    force_republish: bool

    body_hash: str

    external_review_id: str | None = None

    external_review_url: str | None = None

    external_review_state: str | None = None

    external_actor: str | None = None

    error_code: str | None = None

    error_message: str | None = None

    created_at: datetime | None = None

    updated_at: datetime | None = None

    published_at: datetime | None = None


class CodeReviewPublicationsPublic(
    SQLModel,
):
    data: list[CodeReviewPublicationPublic]

    count: int


class GitHubReviewPublicationPreviewPublic(
    SQLModel,
):
    review_run_id: uuid.UUID

    target_repository: str
    target_change_number: int
    target_source_url: str

    reviewed_head_sha: str

    default_event: str

    allowed_events: list[str]

    already_published: bool

    successful_publication_count: int

    latest_publication: CodeReviewPublicationPublic | None = None

    body_markdown: str

    body_hash: str

    body_character_count: int


class GitHubReviewPublicationResultPublic(
    SQLModel,
):
    publication: CodeReviewPublicationPublic

    requested_event: str

    current_head_sha: str

    pull_request_url: str


class KnowledgeBaseAgentSettingsPublic(SQLModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID

    top_k: int
    max_steps: int
    semantic_weight: float
    keyword_weight: float

    created_at: datetime | None = None
    updated_at: datetime | None = None


class KnowledgeBaseAgentSettingsUpdate(SQLModel):
    top_k: int | None = Field(default=None, ge=1, le=20)
    max_steps: int | None = Field(default=None, ge=1, le=10)
    semantic_weight: float | None = Field(default=None, ge=0, le=1)
    keyword_weight: float | None = Field(default=None, ge=0, le=1)


class RagRunBase(SQLModel):
    question: str = Field(sa_column=Column(Text, nullable=False))
    answer: str = Field(sa_column=Column(Text, nullable=False))
    retrieval_type: str = Field(default="unknown", max_length=50)
    top_k: int = Field(default=5, ge=1, le=20)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)
    latency_ms: int | None = Field(default=None, ge=0)
    sources_json: str = Field(default="[]", sa_column=Column(Text, nullable=False))
    trace_json: str = Field(default="[]", sa_column=Column(Text, nullable=False))
    error_message: str | None = Field(default=None, max_length=1024)


class RagRun(RagRunBase, table=True):
    __tablename__ = "rag_run"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    repository_analysis_task_id: uuid.UUID | None = Field(
        default=None,
        foreign_key=(
            "repository_analysis_task.id"
        ),
        nullable=True,
        ondelete="SET NULL",
        index=True,
    )

    source_commit_sha: str | None = Field(
        default=None,
        max_length=64,
    )

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class RagRunPublic(SQLModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID

    repository_analysis_task_id: uuid.UUID | None = None

    source_commit_sha: str | None = None

    question: str
    answer: str

    retrieval_type: str
    top_k: int = 5
    semantic_weight: float = 0.75
    keyword_weight: float = 0.25

    latency_ms: int | None = None

    sources: list[
        RagChatSource
    ] = Field(
        default_factory=list,
    )

    trace: list[str] = Field(
        default_factory=list,
    )

    error_message: str | None = None
    created_at: datetime | None = None


class RagRunsPublic(SQLModel):
    data: list[RagRunPublic]
    count: int


class RagEvalCaseCreate(SQLModel):
    question: str = Field(min_length=1, max_length=1000)
    expected_keywords: list[str] = Field(default_factory=list)
    expected_source_filename: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=1024)


class RagEvalCasePublic(SQLModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID
    question: str
    expected_keywords: list[str] = []
    expected_source_filename: str | None = None
    note: str | None = None
    created_at: datetime | None = None


class RagEvalCasesPublic(SQLModel):
    data: list[RagEvalCasePublic]
    count: int


class RagEvalCase(SQLModel, table=True):
    __tablename__ = "rag_eval_case"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    question: str = Field(sa_column=Column(Text, nullable=False))
    expected_keywords_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )
    expected_source_filename: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=1024)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class RagEvalRunRequest(SQLModel):
    top_k: int = Field(default=5, ge=1, le=20)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)


class RagEvalRun(SQLModel, table=True):
    __tablename__ = "rag_eval_run"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    eval_case_id: uuid.UUID = Field(
        foreign_key="rag_eval_case.id",
        nullable=False,
        ondelete="CASCADE",
    )
    batch_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="rag_eval_batch.id",
        nullable=True,
        ondelete="SET NULL",
    )
    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    question: str = Field(sa_column=Column(Text, nullable=False))
    answer: str = Field(sa_column=Column(Text, nullable=False))

    expected_keywords_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )
    expected_source_filename: str | None = Field(default=None, max_length=255)

    sources_json: str = Field(default="[]", sa_column=Column(Text, nullable=False))
    trace_json: str = Field(default="[]", sa_column=Column(Text, nullable=False))

    keyword_hit: bool | None = Field(default=None)
    source_hit: bool | None = Field(default=None)
    score: float | None = Field(default=None)

    retrieval_type: str = Field(default="hybrid", max_length=50)
    top_k: int = Field(default=5, ge=1, le=20)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)
    latency_ms: int | None = Field(default=None, ge=0)
    error_message: str | None = Field(default=None, max_length=1024)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class RagEvalRunPublic(SQLModel):
    id: uuid.UUID
    eval_case_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID
    question: str
    answer: str
    expected_keywords: list[str] = []
    expected_source_filename: str | None = None
    sources: list[RagChatSource] = []
    trace: list[str] = []
    keyword_hit: bool | None = None
    source_hit: bool | None = None
    score: float | None = None
    retrieval_type: str
    top_k: int = 5
    semantic_weight: float = 0.75
    keyword_weight: float = 0.25
    latency_ms: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    is_failed: bool = False
    failure_reasons: list[str] = []


class RagEvalRunsPublic(SQLModel):
    data: list[RagEvalRunPublic]
    count: int


class RagEvalBatchRunRequest(SQLModel):
    top_k: int = Field(default=5, ge=1, le=20)
    limit: int = Field(default=100, ge=1, le=500)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)
    batch_name: str | None = Field(default=None, max_length=100)
    batch_note: str | None = Field(default=None, max_length=1024)


class RagEvalBatch(SQLModel, table=True):
    __tablename__ = "rag_eval_batch"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    name: str = Field(max_length=100)
    note: str | None = Field(default=None, max_length=1024)

    top_k: int = Field(default=5, ge=1, le=20)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)

    total_cases: int = Field(default=0, ge=0)
    ran: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)

    average_score: float | None = Field(default=None)
    keyword_hit_rate: float | None = Field(default=None)
    source_hit_rate: float | None = Field(default=None)
    average_latency_ms: float | None = Field(default=None)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class RagEvalBatchPublic(SQLModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    note: str | None = None

    top_k: int
    semantic_weight: float
    keyword_weight: float

    total_cases: int
    ran: int
    failed: int

    average_score: float | None = None
    keyword_hit_rate: float | None = None
    source_hit_rate: float | None = None
    average_latency_ms: float | None = None

    created_at: datetime | None = None


class RagEvalBatchesPublic(SQLModel):
    data: list[RagEvalBatchPublic]
    count: int


class RagEvalBatchRunResult(SQLModel):
    total_cases: int
    ran: int
    failed: int
    top_k: int
    semantic_weight: float
    keyword_weight: float
    average_score: float | None = None
    keyword_hit_rate: float | None = None
    source_hit_rate: float | None = None
    average_latency_ms: float | None = None


class RagEvalSummary(SQLModel):
    total_runs: int
    average_score: float | None = None
    keyword_hit_rate: float | None = None
    source_hit_rate: float | None = None
    average_latency_ms: float | None = None
    max_score: float | None = None
    min_score: float | None = None
    latest_run_at: datetime | None = None


class RagEvalParamGroup(SQLModel):
    top_k: int
    semantic_weight: float
    keyword_weight: float

    preset_names: list[str] = Field(default_factory=list)

    total_runs: int
    average_score: float | None = None
    keyword_hit_rate: float | None = None
    source_hit_rate: float | None = None
    failure_rate: float | None = None
    average_latency_ms: float | None = None

    latest_run_at: datetime | None = None


class RagEvalParamGroups(SQLModel):
    data: list[RagEvalParamGroup]
    count: int


class RagEvalFailureAnalysis(SQLModel):
    total_runs: int
    failed_runs: int
    failure_rate: float | None = None

    keyword_miss_count: int
    source_miss_count: int
    error_count: int
    low_score_count: int
    zero_score_count: int

    average_failed_latency_ms: float | None = None
    recent_failed_runs: list[RagEvalRunPublic] = []


class CodeEvalTypeCompareStat(SQLModel):
    case_type: str
    case_type_label: str
    total_cases: int = 0
    compared_cases: int = 0

    rag_source_hit_rate: float = 0
    agent_source_hit_rate: float = 0

    rag_keyword_hit_rate: float = 0
    agent_keyword_hit_rate: float = 0

    rag_avg_latency_ms: float | None = None
    agent_avg_latency_ms: float | None = None

    agent_avg_tool_calls: float | None = None
    agent_tool_usage_json: str | None = None


class CodeEvalTypeCompareSummaryPublic(SQLModel):
    data: list[CodeEvalTypeCompareStat]
    count: int


class CodeAgentExperimentReportPublic(SQLModel):
    filename: str
    mime_type: str = "text/markdown"
    content: str


class RagAgentCompareFailureReasonStat(SQLModel):
    reason: str
    reason_label: str
    count: int = 0


class RagAgentCompareFailureCasePublic(SQLModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    eval_case_id: uuid.UUID | None = None

    question: str

    case_type: str = "unknown"
    case_type_label: str = "未分类"

    failure_reasons: list[str] = Field(default_factory=list)
    failure_reason_labels: list[str] = Field(default_factory=list)

    rag_source_hit: bool | None = None
    agent_source_hit: bool | None = None

    rag_keyword_hit_rate: float = 0
    agent_keyword_hit_rate: float = 0

    rag_latency_ms: int | None = None
    agent_latency_ms: int | None = None

    rag_sources_count: int = 0
    agent_sources_count: int = 0

    agent_tool_call_count: int = 0
    agent_failed_tool_count: int = 0
    agent_tool_names: list[str] = Field(default_factory=list)

    rag_error_message: str | None = None
    agent_error_message: str | None = None

    rag_answer: str | None = None
    agent_answer: str | None = None

    created_at: datetime | None = None


class RagAgentCompareFailureAnalysisPublic(SQLModel):
    total_items: int
    failed_items: int

    reason_stats: list[RagAgentCompareFailureReasonStat]
    data: list[RagAgentCompareFailureCasePublic]
    count: int


class RagAgentCompareEvalRequest(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    top_k: int = Field(default=5, ge=1, le=20)
    max_steps: int = Field(default=5, ge=1, le=10)
    limit: int = Field(default=10, ge=1, le=50)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)


class RagAgentCompareEvalItem(SQLModel):
    eval_case_id: uuid.UUID
    question: str
    expected_keywords: list[str] = Field(default_factory=list)
    expected_source_filename: str | None = None

    rag_answer: str | None = None
    agent_answer: str | None = None

    rag_latency_ms: int | None = None
    agent_latency_ms: int | None = None

    rag_sources_count: int = 0
    agent_sources_count: int = 0

    agent_tool_call_count: int = 0
    agent_failed_tool_count: int = 0
    agent_tool_names: list[str] = Field(default_factory=list)

    rag_sources: list[RagChatSource] = Field(default_factory=list)
    agent_sources: list[RagChatSource] = Field(default_factory=list)
    agent_tool_calls: list[AgentToolCallPublic] = Field(default_factory=list)

    rag_trace: list[str] = Field(default_factory=list)
    agent_trace: list[str] = Field(default_factory=list)

    rag_error_message: str | None = None
    agent_error_message: str | None = None

    is_failed: bool = False


class RagAgentCompareEvalSummary(SQLModel):
    total_cases: int = 0
    ran: int = 0
    failed: int = 0

    average_rag_latency_ms: float | None = None
    average_agent_latency_ms: float | None = None

    average_rag_sources_count: float | None = None
    average_agent_sources_count: float | None = None

    average_agent_tool_call_count: float | None = None
    total_agent_failed_tool_count: int = 0

    summarize_document_count: int = 0
    read_document_chunks_count: int = 0
    search_rag_history_count: int = 0


class RagAgentCompareEvalResponse(SQLModel):
    compare_batch_id: uuid.UUID | None = None
    summary: RagAgentCompareEvalSummary
    data: list[RagAgentCompareEvalItem]
    count: int

    # eval_case_id: uuid.UUID
    # question: str
    # expected_keywords: list[str] = Field(default_factory=list)
    # expected_source_filename: str | None = None
    #
    # rag_answer: str | None = None
    # agent_answer: str | None = None
    #
    # rag_latency_ms: int | None = None
    # agent_latency_ms: int | None = None
    #
    # rag_sources_count: int = 0
    # agent_sources_count: int = 0
    #
    # agent_tool_call_count: int = 0
    # agent_failed_tool_count: int = 0
    # agent_tool_names: list[str] = Field(default_factory=list)
    #
    # rag_sources: list[RagChatSource] = Field(default_factory=list)
    # agent_sources: list[RagChatSource] = Field(default_factory=list)
    # agent_tool_calls: list[AgentToolCallPublic] = Field(default_factory=list)
    #
    # rag_trace: list[str] = Field(default_factory=list)
    # agent_trace: list[str] = Field(default_factory=list)
    #
    # rag_error_message: str | None = None
    # agent_error_message: str | None = None
    #
    # is_failed: bool = False


class RagAgentCompareBatch(SQLModel, table=True):
    __tablename__ = "rag_agent_compare_batch"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    name: str = Field(default="RAG vs Agent Compare", max_length=255)

    top_k: int = Field(default=5, ge=1, le=20)
    max_steps: int = Field(default=5, ge=1, le=10)
    limit: int = Field(default=10, ge=1, le=50)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)

    total_cases: int = Field(default=0, ge=0)
    ran: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)

    average_rag_latency_ms: float | None = None
    average_agent_latency_ms: float | None = None
    average_rag_sources_count: float | None = None
    average_agent_sources_count: float | None = None
    average_agent_tool_call_count: float | None = None

    total_agent_failed_tool_count: int = Field(default=0, ge=0)

    summarize_document_count: int = Field(default=0, ge=0)
    read_document_chunks_count: int = Field(default=0, ge=0)
    search_rag_history_count: int = Field(default=0, ge=0)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class RagAgentCompareItem(SQLModel, table=True):
    __tablename__ = "rag_agent_compare_item"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    batch_id: uuid.UUID = Field(
        foreign_key="rag_agent_compare_batch.id",
        nullable=False,
        ondelete="CASCADE",
    )
    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    eval_case_id: uuid.UUID | None = Field(default=None)

    question: str = Field(sa_column=Column(Text, nullable=False))
    expected_keywords_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )
    expected_source_filename: str | None = Field(default=None, max_length=255)

    rag_answer: str | None = Field(default=None, sa_column=Column(Text))
    agent_answer: str | None = Field(default=None, sa_column=Column(Text))

    rag_latency_ms: int | None = None
    agent_latency_ms: int | None = None

    rag_sources_count: int = Field(default=0, ge=0)
    agent_sources_count: int = Field(default=0, ge=0)

    agent_tool_call_count: int = Field(default=0, ge=0)
    agent_failed_tool_count: int = Field(default=0, ge=0)

    agent_tool_names_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )

    rag_sources_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )
    agent_sources_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )
    agent_tool_calls_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )

    rag_trace_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )
    agent_trace_json: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
    )

    rag_error_message: str | None = Field(default=None, max_length=2048)
    agent_error_message: str | None = Field(default=None, max_length=2048)

    is_failed: bool = Field(default=False)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class RagAgentCompareBatchPublic(SQLModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID

    name: str

    top_k: int
    max_steps: int
    limit: int
    semantic_weight: float
    keyword_weight: float

    total_cases: int
    ran: int
    failed: int

    average_rag_latency_ms: float | None = None
    average_agent_latency_ms: float | None = None
    average_rag_sources_count: float | None = None
    average_agent_sources_count: float | None = None
    average_agent_tool_call_count: float | None = None

    total_agent_failed_tool_count: int

    summarize_document_count: int
    read_document_chunks_count: int
    search_rag_history_count: int

    created_at: datetime | None = None


class RagAgentCompareBatchesPublic(SQLModel):
    data: list[RagAgentCompareBatchPublic]
    count: int


class RagAgentCompareItemPublic(SQLModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID

    eval_case_id: uuid.UUID | None = None
    question: str

    expected_keywords: list[str] = Field(default_factory=list)
    expected_source_filename: str | None = None

    rag_answer: str | None = None
    agent_answer: str | None = None

    rag_latency_ms: int | None = None
    agent_latency_ms: int | None = None

    rag_sources_count: int = 0
    agent_sources_count: int = 0

    agent_tool_call_count: int = 0
    agent_failed_tool_count: int = 0
    agent_tool_names: list[str] = Field(default_factory=list)

    rag_sources: list[RagChatSource] = Field(default_factory=list)
    agent_sources: list[RagChatSource] = Field(default_factory=list)
    agent_tool_calls: list[AgentToolCallPublic] = Field(default_factory=list)

    rag_trace: list[str] = Field(default_factory=list)
    agent_trace: list[str] = Field(default_factory=list)

    rag_error_message: str | None = None
    agent_error_message: str | None = None

    is_failed: bool = False
    created_at: datetime | None = None


class RagAgentCompareBatchDetailPublic(SQLModel):
    batch: RagAgentCompareBatchPublic
    data: list[RagAgentCompareItemPublic]
    count: int


class RagAgentCompareReportResponse(SQLModel):
    filename: str
    content: str


class RagAgentCompareFileReportResponse(SQLModel):
    filename: str
    mime_type: str
    content_base64: str


class RagRetrievalPresetCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    top_k: int = Field(default=5, ge=1, le=20)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)
    note: str | None = Field(default=None, max_length=1024)


class RagRetrievalPresetPublic(SQLModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    top_k: int
    semantic_weight: float
    keyword_weight: float
    note: str | None = None
    created_at: datetime | None = None


class RagRetrievalPresetsPublic(SQLModel):
    data: list[RagRetrievalPresetPublic]
    count: int


class RagRetrievalPreset(SQLModel, table=True):
    __tablename__ = "rag_retrieval_preset"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    knowledge_base_id: uuid.UUID = Field(
        foreign_key="knowledge_base.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    name: str = Field(max_length=100)
    top_k: int = Field(default=5, ge=1, le=20)
    semantic_weight: float = Field(default=0.75, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)
    note: str | None = Field(default=None, max_length=1024)

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


class KnowledgeBaseSemanticSearchRequest(SQLModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeBaseSemanticSearchResult(SQLModel):
    document_id: uuid.UUID
    original_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    content: str
    content_length: int
    similarity: float


class KnowledgeBaseSemanticSearchResults(SQLModel):
    data: list[KnowledgeBaseSemanticSearchResult]
    count: int


class KnowledgeBaseEmbeddingBackfillRequest(SQLModel):
    limit: int = Field(default=50, ge=1, le=200)
    retry_failed: bool = Field(default=False)
    force: bool = Field(default=False)


class KnowledgeBaseEmbeddingBackfillResult(SQLModel):
    model: str
    processed: int
    embedded: int
    failed: int
    remaining: int


# Properties to return via API, id is always required
class KnowledgeBasePublic(KnowledgeBaseBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class KnowledgeBasesPublic(SQLModel):
    data: list[KnowledgeBasePublic]
    count: int


class RepositoryAnalysisTask(SQLModel, table=True):
    """
    GitHub 仓库分析后台任务。

    保存仓库身份、任务执行状态、分析结果、
    Worker 领取信息以及临时结果的过期时间。
    """

    __tablename__ = "repository_analysis_task"
    __table_args__ = (
        CheckConstraint(
            ("status IN ('queued', 'running', 'completed', 'failed', 'expired')"),
            name="ck_repository_analysis_task_status",
        ),
        CheckConstraint(
            ("progress_percent >= 0 AND progress_percent <= 100"),
            name="ck_repository_analysis_task_progress",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_repository_analysis_task_attempt_count",
        ),
        Index(
            "ix_repository_analysis_task_queue",
            "status",
            "created_at",
        ),
        Index(
            "ix_repository_analysis_task_owner_created",
            "owner_id",
            "created_at",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )

    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
    )

    knowledge_base_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="knowledge_base.id",
        nullable=True,
        ondelete="SET NULL",
        index=True,
    )

    source_url: str = Field(
        min_length=1,
        max_length=2048,
    )

    canonical_url: str = Field(
        min_length=1,
        max_length=2048,
    )

    repository_owner: str = Field(
        min_length=1,
        max_length=100,
    )

    repository_name: str = Field(
        min_length=1,
        max_length=255,
    )

    repository_full_name: str = Field(
        min_length=3,
        max_length=356,
        index=True,
    )

    requested_ref: str | None = Field(
        default=None,
        max_length=255,
    )

    default_branch: str | None = Field(
        default=None,
        max_length=255,
    )

    resolved_commit_sha: str | None = Field(
        default=None,
        max_length=64,
    )

    analysis_mode: str = Field(
        default="overview",
        max_length=30,
    )

    report_language: str = Field(
        default="zh-CN",
        max_length=20,
    )

    status: str = Field(
        default="queued",
        max_length=50,
        index=True,
    )

    stage: str = Field(
        default="queued",
        max_length=50,
    )

    progress_percent: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    attempt_count: int = Field(
        default=0,
        ge=0,
    )

    worker_id: str | None = Field(
        default=None,
        max_length=255,
    )

    snapshot_source: str | None = Field(
        default=None,
        max_length=50,
    )

    snapshot_storage_path: str | None = Field(
        default=None,
        max_length=1024,
    )

    result_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            JSONB,
            nullable=True,
        ),
    )

    evidence_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            JSONB,
            nullable=True,
        ),
    )

    report_markdown: str | None = Field(
        default=None,
        sa_column=Column(
            Text,
            nullable=True,
        ),
    )

    error_code: str | None = Field(
        default=None,
        max_length=100,
    )

    error_message: str | None = Field(
        default=None,
        sa_column=Column(
            Text,
            nullable=True,
        ),
    )

    is_saved: bool = Field(
        default=False,
    )

    claimed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )

    heartbeat_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )

    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )

    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )

    expires_at: datetime | None = Field(
        default_factory=get_repository_analysis_expiry,
        sa_type=DateTime(timezone=True),
        index=True,
    )

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    heartbeat_at: datetime | None = Field(
        default=None,
        index=True,
    )

    lease_expires_at: datetime | None = Field(
        default=None,
        index=True,
    )

    attempt_count: int = Field(
        default=0,
        ge=0,
    )

    max_attempts: int = Field(
        default=3,
        ge=1,
    )

    next_attempt_at: datetime | None = Field(
        default=None,
        index=True,
    )

    last_recovery_reason: str | None = Field(
        default=None,
        max_length=100,
    )


class RepositoryAnalysisTaskCreate(SQLModel):
    """创建快速仓库概览任务的请求参数。"""

    repository_url: str = Field(
        min_length=1,
        max_length=2048,
    )

    report_language: str = Field(
        default="zh-CN",
        max_length=20,
    )


class RepositoryAnalysisKnowledgeBaseRequest(SQLModel):
    """
    为仓库分析任务选择已有知识库，
    或者创建一个新的知识库。
    """

    knowledge_base_id: uuid.UUID | None = None

    knowledge_base_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    knowledge_base_description: str | None = Field(
        default=None,
        max_length=255,
    )


class RepositoryAnalysisTaskSummaryPublic(SQLModel):
    """任务列表使用的轻量响应。"""

    id: uuid.UUID
    repository_full_name: str
    canonical_url: str

    analysis_mode: str
    status: str
    stage: str
    progress_percent: int

    is_saved: bool
    knowledge_base_id: uuid.UUID | None = None

    error_code: str | None = None
    error_message: str | None = None

    expires_at: datetime | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RepositoryAnalysisTaskPublic(
    RepositoryAnalysisTaskSummaryPublic,
):
    """查询单个任务时返回的完整结果。"""

    source_url: str
    repository_owner: str
    repository_name: str

    requested_ref: str | None = None
    default_branch: str | None = None
    resolved_commit_sha: str | None = None

    report_language: str

    result_json: dict[str, Any] | None = None
    evidence_json: dict[str, Any] | None = None
    report_markdown: str | None = None

    updated_at: datetime | None = None


class RepositoryAnalysisKnowledgeBaseBindingPublic(
    SQLModel,
):
    """
    仓库分析任务绑定知识库后的响应。
    """

    task: RepositoryAnalysisTaskPublic
    knowledge_base: KnowledgeBasePublic

    created_new_knowledge_base: bool = False


class RepositoryAnalysisKnowledgeImportPublic(
    SQLModel,
):
    """
    固定 Commit 导入知识库后的结果。
    """

    task_id: uuid.UUID
    knowledge_base_id: uuid.UUID

    repository_full_name: str
    commit_sha: str

    document_count: int = 0
    chunk_count: int = 0
    imported_bytes: int = 0

    skipped_unsupported_file_count: int = 0
    skipped_large_file_count: int = 0
    skipped_unreadable_file_count: int = 0

    import_truncated: bool = False
    already_imported: bool = False


class RepositoryAnalysisEmbeddingBatchRequest(
    SQLModel,
):
    """
    一次仓库代码 Embedding 批处理请求。
    """

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
    )

    retry_failed: bool = Field(
        default=False,
    )


class RepositoryAnalysisEmbeddingStatusPublic(
    SQLModel,
):
    """
    当前仓库导入代码块的 Embedding 状态。
    """

    task_id: uuid.UUID
    knowledge_base_id: uuid.UUID

    embedding_model: str

    total_count: int = 0
    pending_count: int = 0
    embedded_count: int = 0
    failed_count: int = 0

    progress_percent: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    index_status: str
    ready_for_search: bool = False

    sample_error_message: str | None = None


class RepositoryAnalysisEmbeddingBatchPublic(
    RepositoryAnalysisEmbeddingStatusPublic,
):
    """
    一批 Embedding 处理结果。
    """

    processed_count: int = 0
    embedded_in_batch: int = 0
    failed_in_batch: int = 0


class RepositoryAnalysisTasksPublic(SQLModel):
    """仓库分析任务分页列表。"""

    data: list[RepositoryAnalysisTaskSummaryPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class CodeSkillParseDiffRequest(SQLModel):
    diff_text: str


class CodeSkillDiffHunkPublic(SQLModel):
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    added_lines: int = 0
    deleted_lines: int = 0
    context_lines: int = 0


class CodeSkillChangedFilePublic(SQLModel):
    old_path: str | None = None
    new_path: str | None = None
    file_path: str
    change_type: str
    added_lines: int = 0
    deleted_lines: int = 0
    hunks: list[CodeSkillDiffHunkPublic] = Field(default_factory=list)


class CodeSkillParseDiffResponse(SQLModel):
    changed_files: list[CodeSkillChangedFilePublic] = Field(default_factory=list)
    total_files: int = 0
    total_added_lines: int = 0
    total_deleted_lines: int = 0


class CodeSkillLocateChangedSymbolsRequest(SQLModel):
    diff_text: str
    include_file_level_fallback: bool = True


class CodeSkillChangedSymbolPublic(SQLModel):
    document_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    chunk_index: int | None = None

    document_filename: str | None = None
    file_path: str

    symbol_name: str
    symbol_type: str
    line_range: str | None = None

    symbol_start_line: int | None = None
    symbol_end_line: int | None = None

    changed_hunk_new_start: int
    changed_hunk_new_end: int

    overlap_start_line: int | None = None
    overlap_end_line: int | None = None
    overlap_line_count: int = 0

    confidence: float = 0
    reason: str


class CodeSkillLocateChangedSymbolsResponse(SQLModel):
    changed_files: list[CodeSkillChangedFilePublic] = Field(default_factory=list)
    changed_symbols: list[CodeSkillChangedSymbolPublic] = Field(default_factory=list)
    unresolved_files: list[str] = Field(default_factory=list)

    total_files: int = 0
    total_symbols: int = 0
    total_unresolved_files: int = 0


class CodeSkillChangedSymbolInput(SQLModel):
    document_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None

    file_path: str
    symbol_name: str
    symbol_type: str = "unknown"
    line_range: str | None = None


class CodeSkillFindImpactsRequest(SQLModel):
    changed_symbols: list[CodeSkillChangedSymbolInput] = Field(default_factory=list)
    max_references_per_symbol: int = 20
    include_definition_chunk: bool = False


class CodeSkillImpactReferencePublic(SQLModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int

    document_filename: str
    file_path: str

    changed_symbol_name: str
    changed_symbol_type: str

    containing_symbol_name: str | None = None
    containing_symbol_type: str | None = None
    containing_line_range: str | None = None

    occurrence_count: int = 0
    preview: str | None = None

    confidence: float = 0
    reason: str


class CodeSkillImpactedFilePublic(SQLModel):
    file_path: str
    document_filename: str | None = None

    reference_count: int = 0
    impacted_symbol_names: list[str] = Field(default_factory=list)

    confidence: float = 0
    reason: str


class CodeSkillSymbolImpactPublic(SQLModel):
    changed_symbol: CodeSkillChangedSymbolInput
    references: list[CodeSkillImpactReferencePublic] = Field(default_factory=list)
    impacted_files: list[CodeSkillImpactedFilePublic] = Field(default_factory=list)

    total_references: int = 0
    total_impacted_files: int = 0


class CodeSkillFindImpactsResponse(SQLModel):
    symbol_impacts: list[CodeSkillSymbolImpactPublic] = Field(default_factory=list)
    impacted_files_summary: list[CodeSkillImpactedFilePublic] = Field(
        default_factory=list
    )

    total_symbols: int = 0
    total_references: int = 0
    total_impacted_files: int = 0


class CodeSkillImpactedFileInput(SQLModel):
    file_path: str
    reference_count: int = 0
    impacted_symbol_names: list[str] = Field(default_factory=list)


class CodeSkillRecommendTestsRequest(SQLModel):
    changed_files: list[str] = Field(default_factory=list)
    changed_symbols: list[CodeSkillChangedSymbolInput] = Field(default_factory=list)
    impacted_files: list[CodeSkillImpactedFileInput] = Field(default_factory=list)

    max_test_files: int = 20
    min_confidence: float = 0.2


class CodeSkillRecommendedTestPublic(SQLModel):
    document_id: uuid.UUID
    document_filename: str
    test_file_path: str

    confidence: float = 0
    path_match_score: float = 0
    symbol_match_count: int = 0

    related_changed_files: list[str] = Field(default_factory=list)
    related_impacted_files: list[str] = Field(default_factory=list)
    related_symbols: list[str] = Field(default_factory=list)
    matched_reasons: list[str] = Field(default_factory=list)

    preview: str | None = None


class CodeSkillRecommendTestsResponse(SQLModel):
    recommended_tests: list[CodeSkillRecommendedTestPublic] = Field(
        default_factory=list
    )

    test_gap_notes: list[str] = Field(default_factory=list)
    uncovered_changed_files: list[str] = Field(default_factory=list)
    uncovered_symbols: list[str] = Field(default_factory=list)

    total_test_candidates: int = 0
    total_recommended_tests: int = 0

    analysis_method: str = "heuristic_path_and_symbol_matching"
    limitations: list[str] = Field(default_factory=list)


class CodeSkillBuildReviewEvidenceRequest(SQLModel):
    diff_text: str

    max_references_per_symbol: int = 20
    max_test_files: int = 20
    min_test_confidence: float = 0.2

    include_file_level_fallback: bool = True
    include_definition_chunk: bool = False


class CodeSkillChangeSummaryPublic(SQLModel):
    total_changed_files: int = 0
    total_added_lines: int = 0
    total_deleted_lines: int = 0

    total_changed_symbols: int = 0
    total_unresolved_files: int = 0

    total_references: int = 0
    total_impacted_files: int = 0

    total_test_candidates: int = 0
    total_recommended_tests: int = 0

    total_risk_signals: int = 0
    risk_level: str = "low"


class CodeSkillRiskSignalPublic(SQLModel):
    risk_type: str
    risk_level: str

    title: str
    message: str

    evidence: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    related_symbols: list[str] = Field(default_factory=list)


class CodeSkillReviewChecklistItemPublic(SQLModel):
    item_id: str
    category: str
    priority: str

    description: str
    reason: str

    related_files: list[str] = Field(default_factory=list)
    related_symbols: list[str] = Field(default_factory=list)


class CodeSkillEvidenceTraceStepPublic(SQLModel):
    step: str
    status: str = "success"
    duration_ms: int = 0
    summary: str


class CodeSkillReviewEvidenceResponse(SQLModel):
    change_summary: CodeSkillChangeSummaryPublic

    changed_files: list[CodeSkillChangedFilePublic] = Field(default_factory=list)

    changed_symbols: list[CodeSkillChangedSymbolPublic] = Field(default_factory=list)

    unresolved_files: list[str] = Field(default_factory=list)

    symbol_impacts: list[CodeSkillSymbolImpactPublic] = Field(default_factory=list)

    impacted_files_summary: list[CodeSkillImpactedFilePublic] = Field(
        default_factory=list
    )

    recommended_tests: list[CodeSkillRecommendedTestPublic] = Field(
        default_factory=list
    )

    test_gap_notes: list[str] = Field(default_factory=list)
    uncovered_changed_files: list[str] = Field(default_factory=list)
    uncovered_symbols: list[str] = Field(default_factory=list)

    risk_signals: list[CodeSkillRiskSignalPublic] = Field(default_factory=list)

    review_checklist: list[CodeSkillReviewChecklistItemPublic] = Field(
        default_factory=list
    )

    evidence_trace: list[CodeSkillEvidenceTraceStepPublic] = Field(default_factory=list)

    limitations: list[str] = Field(default_factory=list)


CodeReviewSourceProvider = Literal[
    "github",
    "gitlab",
]


class CodeReviewSourceResolveRequest(
    SQLModel,
):
    source_url: str = Field(
        min_length=1,
        max_length=2048,
    )


class CodeReviewSourceSnapshot(
    SQLModel,
):
    provider: CodeReviewSourceProvider

    source_url: str = Field(
        min_length=1,
        max_length=2048,
    )

    repository: str = Field(
        min_length=1,
        max_length=512,
    )

    change_number: int = Field(
        ge=1,
    )

    title: str = Field(
        min_length=1,
        max_length=512,
    )

    author: str | None = Field(
        default=None,
        max_length=255,
    )

    base_ref: str = Field(
        min_length=1,
        max_length=255,
    )

    head_ref: str = Field(
        min_length=1,
        max_length=255,
    )

    base_sha: str = Field(
        min_length=7,
        max_length=64,
    )

    head_sha: str = Field(
        min_length=7,
        max_length=64,
    )

    diff_hash: str = Field(
        min_length=64,
        max_length=64,
    )

    fetched_at: datetime


class CodeReviewSourceResolvedPublic(
    CodeReviewSourceSnapshot,
):
    diff_text: str = Field(
        min_length=1,
    )


class CodeSkillGenerateReviewReportRequest(SQLModel):
    diff_text: str = Field(min_length=1)

    max_references_per_symbol: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    max_test_files: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    min_test_confidence: float = Field(
        default=0.2,
        ge=0,
        le=1,
    )

    include_file_level_fallback: bool = True
    include_definition_chunk: bool = False

    language: Literal["zh-CN", "en-US"] = "zh-CN"

    source: CodeReviewSourceSnapshot | None = None


class CodeSkillGeneratedOverallAssessmentPublic(SQLModel):
    risk_level: Literal[
        "low",
        "medium",
        "high",
    ] = "low"

    conclusion: str

    merge_recommendation: Literal[
        "approve",
        "needs_review",
        "request_changes",
    ] = "needs_review"


class CodeSkillGeneratedFindingPublic(SQLModel):
    finding_id: str

    severity: Literal[
        "low",
        "medium",
        "high",
    ]

    category: str
    title: str
    description: str
    recommendation: str

    evidence_ids: list[str] = Field(
        min_length=1,
    )


class CodeSkillGeneratedTestPlanItemPublic(SQLModel):
    test_file: str
    reason: str

    priority: Literal[
        "low",
        "medium",
        "high",
    ] = "medium"

    evidence_ids: list[str] = Field(
        min_length=1,
    )


class CodeSkillGeneratedManualReviewItemPublic(SQLModel):
    description: str

    priority: Literal[
        "low",
        "medium",
        "high",
    ] = "medium"

    evidence_ids: list[str] = Field(
        min_length=1,
    )


class CodeSkillGeneratedReviewReportPublic(SQLModel):
    executive_summary: str

    overall_assessment: CodeSkillGeneratedOverallAssessmentPublic

    findings: list[CodeSkillGeneratedFindingPublic] = Field(default_factory=list)

    test_plan: list[CodeSkillGeneratedTestPlanItemPublic] = Field(default_factory=list)

    manual_review_items: list[CodeSkillGeneratedManualReviewItemPublic] = Field(
        default_factory=list
    )

    uncertainties: list[str] = Field(default_factory=list)


class CodeSkillReportGenerationTracePublic(SQLModel):
    model: str
    duration_ms: int = Field(default=0, ge=0)

    prompt_version: str = "repoguard-review-v1"

    evidence_item_count: int = Field(
        default=0,
        ge=0,
    )

    output_characters: int = Field(
        default=0,
        ge=0,
    )


class CodeSkillGenerateReviewReportResponse(SQLModel):
    generation_status: Literal[
        "completed",
        "evidence_only",
    ]

    review_report: CodeSkillGeneratedReviewReportPublic | None = None

    review_markdown: str | None = None

    evidence: CodeSkillReviewEvidenceResponse

    generation_trace: CodeSkillReportGenerationTracePublic

    generation_error: str | None = None
    review_run_id: uuid.UUID | None = None
    saved_at: datetime | None = None


CodeReviewGenerationStatus = Literal[
    "completed",
    "evidence_only",
]

CodeReviewRiskLevel = Literal[
    "low",
    "medium",
    "high",
]

CodeReviewMergeRecommendation = Literal[
    "approve",
    "needs_review",
    "request_changes",
]

CodeReviewCompareTrend = Literal[
    "increased",
    "decreased",
    "unchanged",
    "changed",
    "unavailable",
]


class CodeReviewRunSummaryPublic(SQLModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str

    generation_status: CodeReviewGenerationStatus
    language: str

    risk_level: CodeReviewRiskLevel | None = None
    merge_recommendation: CodeReviewMergeRecommendation | None = None

    changed_file_count: int
    changed_symbol_count: int
    finding_count: int
    recommended_test_count: int

    created_at: datetime
    source: CodeReviewSourceSnapshot | None = None


class CodeReviewRunsPublic(SQLModel):
    data: list[CodeReviewRunSummaryPublic]
    count: int


class CodeReviewRunDetailPublic(CodeReviewRunSummaryPublic):
    diff_text: str
    diff_hash: str

    request_parameters: dict[str, Any]

    review_report: CodeSkillGeneratedReviewReportPublic | None = None
    review_markdown: str | None = None

    evidence: CodeSkillReviewEvidenceResponse
    generation_trace: CodeSkillReportGenerationTracePublic

    generation_error: str | None = None


class CodeReviewCompareRequest(SQLModel):
    base_review_run_id: uuid.UUID
    target_review_run_id: uuid.UUID


class CodeReviewRunCompareReferencePublic(
    SQLModel,
):
    id: uuid.UUID
    title: str
    created_at: datetime

    generation_status: CodeReviewGenerationStatus

    risk_level: CodeReviewRiskLevel | None = None

    merge_recommendation: CodeReviewMergeRecommendation | None = None

    diff_hash: str


class CodeReviewValueChangePublic(
    SQLModel,
):
    base_value: str | None = None
    target_value: str | None = None

    trend: CodeReviewCompareTrend


class CodeReviewMetricChangePublic(
    SQLModel,
):
    base_value: int
    target_value: int
    delta: int

    trend: Literal[
        "increased",
        "decreased",
        "unchanged",
    ]


class CodeReviewCompareFindingPublic(
    SQLModel,
):
    fingerprint: str
    title: str

    severity: str | None = None
    category: str | None = None
    description: str | None = None
    recommendation: str | None = None


class CodeReviewCompareTestPublic(
    SQLModel,
):
    fingerprint: str
    title: str

    test_type: str | None = None
    file_path: str | None = None
    reason: str | None = None


class CodeReviewFindingChangesPublic(
    SQLModel,
):
    added: list[CodeReviewCompareFindingPublic] = Field(
        default_factory=list,
    )

    resolved: list[CodeReviewCompareFindingPublic] = Field(
        default_factory=list,
    )

    persisting: list[CodeReviewCompareFindingPublic] = Field(
        default_factory=list,
    )


class CodeReviewTestChangesPublic(
    SQLModel,
):
    added: list[CodeReviewCompareTestPublic] = Field(
        default_factory=list,
    )

    removed: list[CodeReviewCompareTestPublic] = Field(
        default_factory=list,
    )

    persisting: list[CodeReviewCompareTestPublic] = Field(
        default_factory=list,
    )


class CodeReviewOverallChangePublic(
    SQLModel,
):
    same_diff: bool

    risk: CodeReviewValueChangePublic

    merge_recommendation: CodeReviewValueChangePublic

    generation_status: CodeReviewValueChangePublic

    summary: str


class CodeReviewMetricChangesPublic(
    SQLModel,
):
    changed_file_count: CodeReviewMetricChangePublic

    changed_symbol_count: CodeReviewMetricChangePublic

    finding_count: CodeReviewMetricChangePublic

    recommended_test_count: CodeReviewMetricChangePublic


class CodeReviewTraceChangesPublic(
    SQLModel,
):
    model: CodeReviewValueChangePublic

    duration_ms: CodeReviewMetricChangePublic | None = None

    evidence_item_count: CodeReviewMetricChangePublic | None = None

    output_characters: CodeReviewMetricChangePublic | None = None


class CodeReviewCompareResponse(
    SQLModel,
):
    base_review: CodeReviewRunCompareReferencePublic

    target_review: CodeReviewRunCompareReferencePublic

    overall_change: CodeReviewOverallChangePublic

    metric_changes: CodeReviewMetricChangesPublic

    finding_changes: CodeReviewFindingChangesPublic

    test_changes: CodeReviewTestChangesPublic

    trace_changes: CodeReviewTraceChangesPublic
