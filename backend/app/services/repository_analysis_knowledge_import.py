from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    Document,
    DocumentChunk,
    KnowledgeBase,
    RepositoryAnalysisTask,
)
from app.services.code_parser import (
    is_code_file,
    split_code_into_chunks,
)
from app.services.github_repository_snapshot import (
    GitHubRepositorySnapshot,
    GitHubRepositorySnapshotDownloader,
    GitHubRepositorySnapshotError,
    cleanup_repository_snapshot,
)
from app.services.repository_analysis_task import (
    get_repository_analysis_task,
)
from app.services.repository_structure_scanner import (
    IGNORED_DIRECTORY_NAMES,
)


DOCUMENT_STORAGE_ROOT = Path(
    "storage/documents",
)

MAX_IMPORT_FILE_COUNT = 3_000

MAX_IMPORT_TOTAL_BYTES = (
    1024 * 1024 * 1024
)

MAX_IMPORT_SINGLE_FILE_BYTES = (
    2 * 1024 * 1024
)


class RepositoryAnalysisKnowledgeImportError(
    RuntimeError,
):
    """仓库代码导入知识库的基础异常。"""


class RepositoryAnalysisKnowledgeImportTaskStateError(
    RepositoryAnalysisKnowledgeImportError,
):
    """仓库分析任务当前状态不允许导入。"""


class RepositoryAnalysisKnowledgeImportNotBoundError(
    RepositoryAnalysisKnowledgeImportError,
):
    """仓库分析任务尚未绑定知识库。"""


class RepositoryAnalysisKnowledgeImportCommitError(
    RepositoryAnalysisKnowledgeImportError,
):
    """仓库分析任务没有固定 Commit。"""


class RepositoryAnalysisKnowledgeImportKnowledgeBaseError(
    RepositoryAnalysisKnowledgeImportError,
):
    """绑定的知识库不存在或不属于当前用户。"""


class RepositoryAnalysisKnowledgeImportTooLargeError(
    RepositoryAnalysisKnowledgeImportError,
):
    """仓库代码总量超过导入限制。"""


class RepositoryAnalysisKnowledgeImportNoFilesError(
    RepositoryAnalysisKnowledgeImportError,
):
    """仓库中没有可以导入的代码文件。"""


class RepositoryAnalysisKnowledgeImportSnapshotError(
    RepositoryAnalysisKnowledgeImportError,
):
    """仓库快照不存在且重新下载失败。"""


class RepositoryAnalysisKnowledgeImportStorageError(
    RepositoryAnalysisKnowledgeImportError,
):
    """知识库文档存储失败。"""


@dataclass(
    frozen=True,
    slots=True,
)
class RepositoryAnalysisKnowledgeImportResult:
    """
    一次固定 Commit 导入结果。
    """

    task_id: uuid.UUID
    knowledge_base_id: uuid.UUID

    repository_full_name: str
    commit_sha: str

    document_count: int
    chunk_count: int
    imported_bytes: int

    skipped_unsupported_file_count: int
    skipped_large_file_count: int
    skipped_unreadable_file_count: int

    import_truncated: bool
    already_imported: bool


def import_repository_analysis_into_knowledge_base(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
) -> RepositoryAnalysisKnowledgeImportResult | None:
    """
    把仓库分析任务固定的 Commit 导入绑定知识库。

    执行流程：

    1. 查询属于当前用户的仓库分析任务；
    2. 检查任务是否完成；
    3. 检查是否已绑定知识库；
    4. 检查是否已经导入；
    5. 优先复用仓库分析阶段留下的快照；
    6. 快照不存在时重新下载同一个 Commit；
    7. 创建 Document；
    8. 创建 pending 状态的 DocumentChunk；
    9. 一次性提交数据库事务。
    """

    task = get_repository_analysis_task(
        session=session,
        owner_id=owner_id,
        task_id=task_id,
    )

    if task is None:
        return None

    _validate_task_for_import(
        session=session,
        task=task,
        owner_id=owner_id,
    )

    existing_result = _get_existing_import_result(
        session=session,
        task=task,
    )

    if existing_result is not None:
        return existing_result

    repository_root: Path | None = None

    temporary_snapshot: (
        GitHubRepositorySnapshot | None
    ) = None

    import_directory = (
        DOCUMENT_STORAGE_ROOT
        / str(owner_id)
        / str(task.knowledge_base_id)
        / "repository-imports"
        / str(task.id)
    )

    try:
        (
            repository_root,
            temporary_snapshot,
        ) = _resolve_repository_root(
            task=task,
        )

        # 数据库中没有当前任务的文档，
        # 说明以前没有成功提交过导入。
        # 若磁盘上存在同名目录，视为上一次中断留下的残留。
        shutil.rmtree(
            import_directory,
            ignore_errors=True,
        )

        import_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        result = _import_repository_files(
            session=session,
            task=task,
            repository_root=repository_root,
            import_directory=import_directory,
        )

        session.commit()

        return result

    except Exception:
        session.rollback()

        shutil.rmtree(
            import_directory,
            ignore_errors=True,
        )

        raise

    finally:
        if temporary_snapshot is not None:
            cleanup_repository_snapshot(
                temporary_snapshot,
            )


def _validate_task_for_import(
    *,
    session: Session,
    task: RepositoryAnalysisTask,
    owner_id: uuid.UUID,
) -> KnowledgeBase:
    """
    检查任务、知识库和 Commit 是否满足导入条件。

    返回值是已经完成权限校验的 KnowledgeBase。
    """

    if task.status != "completed":
        raise (
            RepositoryAnalysisKnowledgeImportTaskStateError(
                "Only completed repository analyses "
                "can be imported",
            )
        )

    if task.knowledge_base_id is None:
        raise (
            RepositoryAnalysisKnowledgeImportNotBoundError(
                "Repository analysis is not bound "
                "to a knowledge base",
            )
        )

    commit_sha = str(
        task.resolved_commit_sha or "",
    ).strip()

    if not commit_sha:
        raise (
            RepositoryAnalysisKnowledgeImportCommitError(
                "Repository analysis has no resolved Commit SHA",
            )
        )

    knowledge_base = session.get(
        KnowledgeBase,
        task.knowledge_base_id,
    )

    if (
        knowledge_base is None
        or knowledge_base.owner_id != owner_id
    ):
        raise (
            RepositoryAnalysisKnowledgeImportKnowledgeBaseError(
                "The bound knowledge base was not found "
                "or does not belong to the current user",
            )
        )

    return knowledge_base


def _get_existing_import_result(
    *,
    session: Session,
    task: RepositoryAnalysisTask,
) -> RepositoryAnalysisKnowledgeImportResult | None:
    """
    检查当前任务是否已经成功导入。

    只要数据库中已经存在带有当前
    repository_analysis_task_id 的文档，
    就直接返回已有统计，不再重复创建。
    """

    document_count = int(
        session.exec(
            select(
                func.count(Document.id),
            ).where(
                Document.repository_analysis_task_id
                == task.id,
            )
        ).one()
    )

    if document_count == 0:
        return None

    chunk_count = int(
        session.exec(
            select(
                func.count(DocumentChunk.id),
            )
            .select_from(DocumentChunk)
            .join(
                Document,
                Document.id
                == DocumentChunk.document_id,
            )
            .where(
                Document.repository_analysis_task_id
                == task.id,
            )
        ).one()
    )

    imported_bytes = int(
        session.exec(
            select(
                func.coalesce(
                    func.sum(Document.file_size),
                    0,
                ),
            ).where(
                Document.repository_analysis_task_id
                == task.id,
            )
        ).one()
    )

    return RepositoryAnalysisKnowledgeImportResult(
        task_id=task.id,
        knowledge_base_id=task.knowledge_base_id,
        repository_full_name=(
            task.repository_full_name
        ),
        commit_sha=(
            task.resolved_commit_sha or ""
        ),
        document_count=document_count,
        chunk_count=chunk_count,
        imported_bytes=imported_bytes,
        skipped_unsupported_file_count=0,
        skipped_large_file_count=0,
        skipped_unreadable_file_count=0,
        import_truncated=False,
        already_imported=True,
    )


def _resolve_repository_root(
    *,
    task: RepositoryAnalysisTask,
) -> tuple[
    Path,
    GitHubRepositorySnapshot | None,
]:
    """
    获取用于导入的仓库根目录。

    优先复用任务已有快照；
    若快照已被清理，则重新下载同一个 Commit。
    """

    raw_storage_path = str(
        task.snapshot_storage_path or "",
    ).strip()

    if raw_storage_path:
        existing_root = Path(
            raw_storage_path,
        ).resolve(
            strict=False,
        )

        if (
            existing_root.exists()
            and existing_root.is_dir()
        ):
            return existing_root, None

    try:
        with GitHubRepositorySnapshotDownloader() as downloader:
            snapshot = (
                downloader.download_and_extract(
                    owner=task.repository_owner,
                    repository_name=(
                        task.repository_name
                    ),
                    commit_sha=(
                        task.resolved_commit_sha
                        or ""
                    ),
                    task_id=task.id,
                )
            )
    except (
        GitHubRepositorySnapshotError,
        ValueError,
    ) as exc:
        raise (
            RepositoryAnalysisKnowledgeImportSnapshotError(
                "The fixed Commit snapshot could "
                "not be prepared for import",
            )
        ) from exc

    return (
        snapshot.repository_root,
        snapshot,
    )


def _import_repository_files(
    *,
    session: Session,
    task: RepositoryAnalysisTask,
    repository_root: Path,
    import_directory: Path,
) -> RepositoryAnalysisKnowledgeImportResult:
    """
    遍历仓库并创建 Document 和 DocumentChunk。

    本函数只创建 pending chunk，
    不调用 Embedding API。
    """

    document_count = 0
    chunk_count = 0
    imported_bytes = 0

    skipped_unsupported_file_count = 0
    skipped_large_file_count = 0
    skipped_unreadable_file_count = 0

    import_truncated = False

    for source_path in _iter_repository_files(
        repository_root,
    ):
        relative_path = (
            source_path
            .relative_to(repository_root)
            .as_posix()
        )

        if not is_code_file(relative_path):
            skipped_unsupported_file_count += 1
            continue

        try:
            file_size = (
                source_path.stat().st_size
            )
        except OSError:
            skipped_unreadable_file_count += 1
            continue

        if file_size <= 0:
            skipped_unreadable_file_count += 1
            continue

        if (
            file_size
            > MAX_IMPORT_SINGLE_FILE_BYTES
        ):
            skipped_large_file_count += 1
            continue

        if (
            document_count
            >= MAX_IMPORT_FILE_COUNT
        ):
            import_truncated = True
            break

        if (
            imported_bytes + file_size
            > MAX_IMPORT_TOTAL_BYTES
        ):
            raise (
                RepositoryAnalysisKnowledgeImportTooLargeError(
                    "Repository code files exceed "
                    "the total import size limit",
                )
            )

        try:
            file_bytes = source_path.read_bytes()
        except OSError:
            skipped_unreadable_file_count += 1
            continue

        if not file_bytes:
            skipped_unreadable_file_count += 1
            continue

        (
            created_document,
            created_chunk_count,
        ) = _create_repository_document(
            session=session,
            task=task,
            relative_path=relative_path,
            file_bytes=file_bytes,
            import_directory=import_directory,
        )

        session.add(created_document)

        document_count += 1
        chunk_count += created_chunk_count
        imported_bytes += len(file_bytes)

    if document_count == 0:
        raise (
            RepositoryAnalysisKnowledgeImportNoFilesError(
                "No supported code files were found "
                "in the repository snapshot",
            )
        )

    return RepositoryAnalysisKnowledgeImportResult(
        task_id=task.id,
        knowledge_base_id=(
            task.knowledge_base_id
        ),
        repository_full_name=(
            task.repository_full_name
        ),
        commit_sha=(
            task.resolved_commit_sha or ""
        ),
        document_count=document_count,
        chunk_count=chunk_count,
        imported_bytes=imported_bytes,
        skipped_unsupported_file_count=(
            skipped_unsupported_file_count
        ),
        skipped_large_file_count=(
            skipped_large_file_count
        ),
        skipped_unreadable_file_count=(
            skipped_unreadable_file_count
        ),
        import_truncated=import_truncated,
        already_imported=False,
    )


def _iter_repository_files(
    repository_root: Path,
):
    """
    遍历仓库文件。

    os.walk 允许直接修改 dir_names，
    从而跳过 node_modules、.git、dist 等目录。
    """

    for (
        current_root,
        dir_names,
        file_names,
    ) in os.walk(
        repository_root,
        followlinks=False,
    ):
        dir_names[:] = [
            directory_name
            for directory_name in dir_names
            if (
                directory_name
                not in IGNORED_DIRECTORY_NAMES
            )
        ]

        current_directory = Path(
            current_root,
        )

        for file_name in file_names:
            source_path = (
                current_directory
                / file_name
            )

            if source_path.is_symlink():
                continue

            if not source_path.is_file():
                continue

            yield source_path


def _create_repository_document(
    *,
    session: Session,
    task: RepositoryAnalysisTask,
    relative_path: str,
    file_bytes: bytes,
    import_directory: Path,
) -> tuple[Document, int]:
    """
    为一个仓库代码文件创建 Document 和 Chunk。

    返回：

    tuple[Document, int]

    第一个值是创建的 Document；
    第二个值是创建的 chunk 数量。
    """

    document_id = uuid.uuid4()

    suffix = Path(
        relative_path,
    ).suffix.lower()

    stored_filename = (
        f"{document_id}{suffix}"
    )

    storage_path = (
        import_directory
        / stored_filename
    )

    try:
        storage_path.write_bytes(
            file_bytes,
        )
    except OSError as exc:
        raise (
            RepositoryAnalysisKnowledgeImportStorageError(
                f"Could not store repository file: "
                f"{relative_path}",
            )
        ) from exc

    document = Document(
        id=document_id,
        knowledge_base_id=(
            task.knowledge_base_id
        ),
        owner_id=task.owner_id,
        repository_analysis_task_id=(
            task.id
        ),
        repository_relative_path=(
            relative_path
        ),
        source_commit_sha=(
            task.resolved_commit_sha
        ),
        filename=stored_filename,
        original_filename=(
            _build_original_filename(
                task=task,
                relative_path=relative_path,
            )
        ),
        content_type="text/plain",
        file_size=len(file_bytes),
        storage_path=str(storage_path),
        status="uploaded",
    )

    session.add(document)

    code_chunks = split_code_into_chunks(
        filename=relative_path,
        file_bytes=file_bytes,
    )

    for index, code_chunk in enumerate(
        code_chunks,
    ):
        chunk = DocumentChunk(
            document_id=document.id,
            knowledge_base_id=(
                document.knowledge_base_id
            ),
            owner_id=document.owner_id,
            chunk_index=index,
            content=code_chunk.content,
            content_length=len(
                code_chunk.content,
            ),
            embedding_status="pending",
        )

        session.add(chunk)

    if code_chunks:
        document.status = "parsed"
        document.error_message = None
    else:
        document.status = "uploaded"
        document.error_message = (
            "No extractable code found"
        )

    return document, len(code_chunks)


def _build_original_filename(
    *,
    task: RepositoryAnalysisTask,
    relative_path: str,
) -> str:
    """
    构造知识库页面显示的文件名。

    Document.original_filename 最大长度为 255，
    因此路径过长时只截断中间部分。
    完整路径仍保存在 repository_relative_path。
    """

    commit_prefix = str(
        task.resolved_commit_sha or "",
    )[:12]

    prefix = (
        f"{task.repository_full_name}"
        f"@{commit_prefix}/"
    )

    full_name = (
        prefix + relative_path
    )

    if len(full_name) <= 255:
        return full_name

    remaining_length = (
        255
        - len(prefix)
        - len(".../")
    )

    if remaining_length <= 0:
        return full_name[-255:]

    return (
        prefix
        + ".../"
        + relative_path[
            -remaining_length:
        ]
    )