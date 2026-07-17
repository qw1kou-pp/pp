from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from urllib.parse import quote

import httpx


DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_GITHUB_API_VERSION = "2022-11-28"

DEFAULT_MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_SINGLE_FILE_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_FILE_COUNT = 20_000

_COPY_CHUNK_SIZE = 64 * 1024

_COMMIT_SHA_PATTERN = re.compile(
    r"^[0-9a-fA-F]{7,64}$",
)


class GitHubRepositorySnapshotError(RuntimeError):
    """仓库快照处理基础异常。"""


class GitHubRepositorySnapshotNotFoundError(
    GitHubRepositorySnapshotError,
):
    """固定 Commit 对应的快照不存在。"""


class GitHubRepositorySnapshotDownloadError(
    GitHubRepositorySnapshotError,
):
    """仓库快照下载失败。"""


class GitHubRepositorySnapshotTooLargeError(
    GitHubRepositorySnapshotError,
):
    """仓库快照超出系统安全限制。"""


class GitHubRepositorySnapshotInvalidArchiveError(
    GitHubRepositorySnapshotError,
):
    """下载内容不是有效 ZIP。"""


class GitHubRepositorySnapshotUnsafeArchiveError(
    GitHubRepositorySnapshotError,
):
    """ZIP 包含不安全路径或特殊文件。"""


@dataclass(frozen=True, slots=True)
class GitHubRepositorySnapshot:
    """
    已下载并安全解压的仓库快照。

    workspace_path 是本次任务的临时工作目录；
    repository_root 是真正包含仓库文件的目录。
    """

    source: str

    commit_sha: str

    workspace_path: Path
    archive_path: Path
    extraction_path: Path
    repository_root: Path

    compressed_bytes: int
    uncompressed_bytes: int
    file_count: int


class GitHubRepositorySnapshotDownloader:
    """
    下载并安全解压固定 Commit 对应的 GitHub ZIP。

    主要安全措施：
    1. 限制压缩文件大小；
    2. 限制解压后总大小；
    3. 限制单文件大小；
    4. 限制文件数量；
    5. 拒绝路径穿越；
    6. 拒绝符号链接和特殊文件；
    7. 手动逐文件解压。
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        api_base_url: str = DEFAULT_GITHUB_API_URL,
        api_version: str = DEFAULT_GITHUB_API_VERSION,
        snapshot_root: Path | str | None = None,
        timeout_seconds: float = 60.0,
        max_archive_bytes: int = (
            DEFAULT_MAX_ARCHIVE_BYTES
        ),
        max_uncompressed_bytes: int = (
            DEFAULT_MAX_UNCOMPRESSED_BYTES
        ),
        max_single_file_bytes: int = (
            DEFAULT_MAX_SINGLE_FILE_BYTES
        ),
        max_file_count: int = DEFAULT_MAX_FILE_COUNT,
    ) -> None:
        normalized_token = str(
            token
            if token is not None
            else os.getenv("GITHUB_TOKEN", "")
        ).strip()

        configured_root = (
            snapshot_root
            or os.getenv(
                "REPOSITORY_SNAPSHOT_ROOT",
                "",
            ).strip()
            or (
                Path(tempfile.gettempdir())
                / "repoguard-repository-snapshots"
            )
        )

        self._snapshot_root = Path(
            configured_root,
        ).resolve()

        self._snapshot_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._max_archive_bytes = int(
            max_archive_bytes,
        )
        self._max_uncompressed_bytes = int(
            max_uncompressed_bytes,
        )
        self._max_single_file_bytes = int(
            max_single_file_bytes,
        )
        self._max_file_count = int(
            max_file_count,
        )

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version,
            "User-Agent": (
                "RepoGuard-Repository-Analyzer"
            ),
        }

        if normalized_token:
            headers["Authorization"] = (
                f"Bearer {normalized_token}"
            )

        self._client = httpx.Client(
            base_url=api_base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    def __enter__(
        self,
    ) -> GitHubRepositorySnapshotDownloader:
        return self

    def __exit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        """关闭 HTTP 连接池。"""

        self._client.close()

    def download_and_extract(
        self,
        *,
        owner: str,
        repository_name: str,
        commit_sha: str,
        task_id: uuid.UUID,
    ) -> GitHubRepositorySnapshot:
        """
        下载并安全解压一个固定 Commit。

        任意阶段失败时都会删除本次尚未完成的临时目录。
        """

        normalized_sha = str(
            commit_sha or "",
        ).strip()

        if not _COMMIT_SHA_PATTERN.fullmatch(
            normalized_sha,
        ):
            raise ValueError(
                "commit_sha must be a hexadecimal Git SHA",
            )

        workspace_path = Path(
            tempfile.mkdtemp(
                prefix=f"{task_id}-",
                dir=self._snapshot_root,
            ),
        ).resolve()

        archive_path = (
            workspace_path / "repository.zip"
        )

        extraction_path = (
            workspace_path / "extracted"
        )

        try:
            compressed_bytes = self._download_archive(
                owner=owner,
                repository_name=repository_name,
                commit_sha=normalized_sha,
                archive_path=archive_path,
            )

            (
                file_count,
                declared_uncompressed_bytes,
            ) = self._inspect_archive(
                archive_path,
            )

            (
                repository_root,
                actual_uncompressed_bytes,
            ) = self._extract_archive(
                archive_path=archive_path,
                extraction_path=extraction_path,
            )

            if (
                actual_uncompressed_bytes
                != declared_uncompressed_bytes
            ):
                raise (
                    GitHubRepositorySnapshotInvalidArchiveError(
                        "ZIP extracted size does not match "
                        "its declared file sizes",
                    )
                )

            return GitHubRepositorySnapshot(
                source="github_zip",
                commit_sha=normalized_sha,
                workspace_path=workspace_path,
                archive_path=archive_path,
                extraction_path=extraction_path,
                repository_root=repository_root,
                compressed_bytes=compressed_bytes,
                uncompressed_bytes=(
                    actual_uncompressed_bytes
                ),
                file_count=file_count,
            )
        except Exception:
            shutil.rmtree(
                workspace_path,
                ignore_errors=True,
            )
            raise

    def _download_archive(
        self,
        *,
        owner: str,
        repository_name: str,
        commit_sha: str,
        archive_path: Path,
    ) -> int:
        """以流式方式下载 ZIP，并限制压缩文件大小。"""

        request_path = (
            f"/repos/{quote(owner, safe='')}/"
            f"{quote(repository_name, safe='')}/"
            f"zipball/{quote(commit_sha, safe='')}"
        )

        try:
            with self._client.stream(
                "GET",
                request_path,
            ) as response:
                self._raise_for_download_response(
                    response,
                )

                content_length = (
                    response.headers.get(
                        "content-length",
                    )
                )

                if content_length:
                    try:
                        declared_size = int(
                            content_length,
                        )
                    except ValueError:
                        declared_size = 0

                    if (
                        declared_size
                        > self._max_archive_bytes
                    ):
                        raise (
                            GitHubRepositorySnapshotTooLargeError(
                                "Repository ZIP exceeds "
                                "the compressed size limit",
                            )
                        )

                downloaded_bytes = 0

                with archive_path.open("wb") as target:
                    for chunk in response.iter_bytes(
                        _COPY_CHUNK_SIZE,
                    ):
                        if not chunk:
                            continue

                        downloaded_bytes += len(chunk)

                        if (
                            downloaded_bytes
                            > self._max_archive_bytes
                        ):
                            raise (
                                GitHubRepositorySnapshotTooLargeError(
                                    "Repository ZIP exceeds "
                                    "the compressed size limit",
                                )
                            )

                        target.write(chunk)

        except httpx.TimeoutException as exc:
            raise GitHubRepositorySnapshotDownloadError(
                "Repository ZIP download timed out",
            ) from exc
        except httpx.RequestError as exc:
            raise GitHubRepositorySnapshotDownloadError(
                "Repository ZIP could not be downloaded",
            ) from exc

        if downloaded_bytes == 0:
            raise GitHubRepositorySnapshotInvalidArchiveError(
                "Downloaded repository ZIP is empty",
            )

        return downloaded_bytes

    def _raise_for_download_response(
        self,
        response: httpx.Response,
    ) -> None:
        """统一处理 ZIP 下载接口的 HTTP 状态。"""

        if response.status_code == 404:
            raise GitHubRepositorySnapshotNotFoundError(
                "Repository snapshot was not found",
            )

        if response.status_code == 403:
            raise GitHubRepositorySnapshotDownloadError(
                "GitHub rejected the snapshot request",
            )

        if response.status_code >= 500:
            raise GitHubRepositorySnapshotDownloadError(
                "GitHub snapshot service is unavailable",
            )

        if not response.is_success:
            raise GitHubRepositorySnapshotDownloadError(
                "Unexpected GitHub snapshot response: "
                f"{response.status_code}",
            )

    def _inspect_archive(
        self,
        archive_path: Path,
    ) -> tuple[int, int]:
        """
        解压前检查 ZIP 元数据。

        这里不信任文件名、文件大小和文件类型。
        """

        if not zipfile.is_zipfile(archive_path):
            raise GitHubRepositorySnapshotInvalidArchiveError(
                "Downloaded content is not a valid ZIP",
            )

        file_count = 0
        total_uncompressed_bytes = 0
        normalized_paths: set[str] = set()

        try:
            with zipfile.ZipFile(
                archive_path,
                mode="r",
            ) as archive:
                for member in archive.infolist():
                    relative_path = (
                        self._validate_member(
                            member,
                        )
                    )

                    normalized_key = (
                        relative_path.as_posix()
                    )

                    if normalized_key in normalized_paths:
                        raise (
                            GitHubRepositorySnapshotUnsafeArchiveError(
                                "ZIP contains duplicate paths",
                            )
                        )

                    normalized_paths.add(
                        normalized_key,
                    )

                    if member.is_dir():
                        continue

                    file_count += 1

                    if (
                        file_count
                        > self._max_file_count
                    ):
                        raise (
                            GitHubRepositorySnapshotTooLargeError(
                                "Repository ZIP contains "
                                "too many files",
                            )
                        )

                    if (
                        member.file_size
                        > self._max_single_file_bytes
                    ):
                        raise (
                            GitHubRepositorySnapshotTooLargeError(
                                "Repository ZIP contains "
                                "a file larger than allowed",
                            )
                        )

                    total_uncompressed_bytes += (
                        member.file_size
                    )

                    if (
                        total_uncompressed_bytes
                        > self._max_uncompressed_bytes
                    ):
                        raise (
                            GitHubRepositorySnapshotTooLargeError(
                                "Repository ZIP exceeds "
                                "the uncompressed size limit",
                            )
                        )
        except zipfile.BadZipFile as exc:
            raise GitHubRepositorySnapshotInvalidArchiveError(
                "Repository ZIP is corrupted",
            ) from exc

        return (
            file_count,
            total_uncompressed_bytes,
        )

    def _validate_member(
        self,
        member: zipfile.ZipInfo,
    ) -> Path:
        """
        校验一个 ZIP 成员的路径与文件类型。
        """

        raw_name = member.filename

        if not raw_name or "\x00" in raw_name:
            raise GitHubRepositorySnapshotUnsafeArchiveError(
                "ZIP contains an invalid file name",
            )

        if member.flag_bits & 0x1:
            raise GitHubRepositorySnapshotUnsafeArchiveError(
                "Encrypted ZIP entries are not supported",
            )

        normalized_name = raw_name.replace(
            "\\",
            "/",
        )

        normalized_name = normalized_name.rstrip(
            "/",
        )

        if not normalized_name:
            raise GitHubRepositorySnapshotUnsafeArchiveError(
                "ZIP contains an empty path",
            )

        pure_path = PurePosixPath(
            normalized_name,
        )

        if pure_path.is_absolute():
            raise GitHubRepositorySnapshotUnsafeArchiveError(
                "ZIP contains an absolute path",
            )

        path_parts = pure_path.parts

        if not path_parts:
            raise GitHubRepositorySnapshotUnsafeArchiveError(
                "ZIP contains an empty path",
            )

        if any(
            part in {"", ".", ".."}
            for part in path_parts
        ):
            raise GitHubRepositorySnapshotUnsafeArchiveError(
                "ZIP contains a path traversal component",
            )

        first_part = path_parts[0]

        if (
            len(first_part) >= 2
            and first_part[1] == ":"
        ):
            raise GitHubRepositorySnapshotUnsafeArchiveError(
                "ZIP contains a drive-qualified path",
            )

        mode = (
            member.external_attr >> 16
        ) & 0xFFFF

        if stat.S_ISLNK(mode):
            raise GitHubRepositorySnapshotUnsafeArchiveError(
                "ZIP contains a symbolic link",
            )

        file_type = stat.S_IFMT(mode)

        if file_type not in {
            0,
            stat.S_IFREG,
            stat.S_IFDIR,
        }:
            raise GitHubRepositorySnapshotUnsafeArchiveError(
                "ZIP contains a special filesystem entry",
            )

        return Path(*path_parts)

    def _extract_archive(
        self,
        *,
        archive_path: Path,
        extraction_path: Path,
    ) -> tuple[Path, int]:
        """
        手动逐项解压，并再次限制实际写入大小。
        """

        extraction_path.mkdir(
            parents=True,
            exist_ok=False,
        )

        extraction_root = (
            extraction_path.resolve()
        )

        total_written = 0

        try:
            with zipfile.ZipFile(
                archive_path,
                mode="r",
            ) as archive:
                for member in archive.infolist():
                    relative_path = (
                        self._validate_member(
                            member,
                        )
                    )

                    target_path = (
                        extraction_root
                        / relative_path
                    ).resolve()

                    try:
                        target_path.relative_to(
                            extraction_root,
                        )
                    except ValueError as exc:
                        raise (
                            GitHubRepositorySnapshotUnsafeArchiveError(
                                "ZIP entry escapes "
                                "the extraction directory",
                            )
                        ) from exc

                    if member.is_dir():
                        target_path.mkdir(
                            parents=True,
                            exist_ok=True,
                        )
                        continue

                    target_path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    written_for_file = (
                        self._copy_member(
                            archive=archive,
                            member=member,
                            target_path=target_path,
                        )
                    )

                    total_written += written_for_file

                    if (
                        total_written
                        > self._max_uncompressed_bytes
                    ):
                        raise (
                            GitHubRepositorySnapshotTooLargeError(
                                "Extracted repository exceeds "
                                "the uncompressed size limit",
                            )
                        )
        except zipfile.BadZipFile as exc:
            raise GitHubRepositorySnapshotInvalidArchiveError(
                "Repository ZIP became unreadable",
            ) from exc

        repository_root = (
            self._find_repository_root(
                extraction_root,
            )
        )

        return repository_root, total_written

    def _copy_member(
        self,
        *,
        archive: zipfile.ZipFile,
        member: zipfile.ZipInfo,
        target_path: Path,
    ) -> int:
        """复制单个 ZIP 文件，并限制实际写入大小。"""

        written_bytes = 0

        with archive.open(
            member,
            mode="r",
        ) as source:
            with target_path.open("xb") as target:
                written_bytes = (
                    self._copy_limited(
                        source=source,
                        target=target,
                    )
                )

        return written_bytes

    def _copy_limited(
        self,
        *,
        source: BinaryIO,
        target: BinaryIO,
    ) -> int:
        """复制数据，同时限制单文件实际大小。"""

        written_bytes = 0

        while True:
            chunk = source.read(
                _COPY_CHUNK_SIZE,
            )

            if not chunk:
                break

            written_bytes += len(chunk)

            if (
                written_bytes
                > self._max_single_file_bytes
            ):
                raise GitHubRepositorySnapshotTooLargeError(
                    "Extracted file exceeds "
                    "the single-file size limit",
                )

            target.write(chunk)

        return written_bytes

    @staticmethod
    def _find_repository_root(
        extraction_root: Path,
    ) -> Path:
        """
        GitHub ZIP 通常包含一个顶层目录。

        如果确实只有一个顶层目录，就返回该目录；
        否则返回整个解压目录。
        """

        children = list(
            extraction_root.iterdir(),
        )

        if (
            len(children) == 1
            and children[0].is_dir()
        ):
            return children[0].resolve()

        return extraction_root


def cleanup_repository_snapshot(
    snapshot: GitHubRepositorySnapshot,
) -> None:
    """删除一个已经不再需要的临时仓库快照。"""

    shutil.rmtree(
        snapshot.workspace_path,
        ignore_errors=True,
    )