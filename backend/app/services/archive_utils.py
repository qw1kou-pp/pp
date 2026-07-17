from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import rarfile


SUPPORTED_REPOSITORY_ARCHIVE_EXTENSIONS = {
    ".zip",
    ".rar",
}


class ArchiveExtractError(Exception):
    pass


@dataclass
class ArchiveExtractResult:
    archive_type: str
    extracted_files_count: int


def get_archive_extension(filename: str) -> str:
    return Path(filename.lower()).suffix


def is_supported_repository_archive(filename: str) -> bool:
    return get_archive_extension(filename) in SUPPORTED_REPOSITORY_ARCHIVE_EXTENSIONS


def get_archive_type(filename: str) -> str:
    extension = get_archive_extension(filename)

    if extension == ".zip":
        return "zip"

    if extension == ".rar":
        return "rar"

    raise ArchiveExtractError(
        f"Unsupported archive type: {extension}. Only .zip and .rar are supported."
    )


def normalize_archive_member_name(member_name: str) -> str | None:
    normalized_name = member_name.replace("\\", "/").strip()

    if not normalized_name:
        return None

    path = PurePosixPath(normalized_name)

    if path.is_absolute():
        return None

    if any(part == ".." for part in path.parts):
        return None

    return str(path)


def ensure_safe_target_path(
    *,
    extract_dir: Path,
    member_name: str,
) -> Path:
    normalized_name = normalize_archive_member_name(member_name)

    if normalized_name is None:
        raise ArchiveExtractError(f"Unsafe archive path: {member_name}")

    extract_dir = extract_dir.resolve()
    target_path = (extract_dir / normalized_name).resolve()

    try:
        target_path.relative_to(extract_dir)
    except ValueError as exc:
        raise ArchiveExtractError(f"Unsafe archive path: {member_name}") from exc

    return target_path


def is_zip_symlink(zip_info: zipfile.ZipInfo) -> bool:
    file_mode = (zip_info.external_attr >> 16) & 0o170000
    return file_mode == 0o120000


def extract_zip_archive(
    *,
    archive_path: Path,
    extract_dir: Path,
) -> int:
    extracted_files_count = 0

    try:
        with zipfile.ZipFile(archive_path) as zip_file:
            for zip_info in zip_file.infolist():
                if is_zip_symlink(zip_info):
                    raise ArchiveExtractError(
                        f"Symbolic links are not allowed in archives: {zip_info.filename}"
                    )

                target_path = ensure_safe_target_path(
                    extract_dir=extract_dir,
                    member_name=zip_info.filename,
                )

                if zip_info.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)

                with zip_file.open(zip_info) as source_file:
                    with target_path.open("wb") as target_file:
                        shutil.copyfileobj(source_file, target_file)

                extracted_files_count += 1

    except zipfile.BadZipFile as exc:
        raise ArchiveExtractError("Invalid zip archive.") from exc

    return extracted_files_count


def rar_info_is_dir(rar_info: rarfile.RarInfo) -> bool:
    isdir = getattr(rar_info, "isdir", None)

    if callable(isdir):
        return bool(isdir())

    return rar_info.filename.endswith("/")


def rar_info_is_symlink(rar_info: rarfile.RarInfo) -> bool:
    is_symlink = getattr(rar_info, "is_symlink", None)

    if callable(is_symlink):
        return bool(is_symlink())

    return False


def extract_rar_archive(
    *,
    archive_path: Path,
    extract_dir: Path,
) -> int:
    extracted_files_count = 0

    try:
        with rarfile.RarFile(archive_path) as rar_file:
            for rar_info in rar_file.infolist():
                if rar_info_is_symlink(rar_info):
                    raise ArchiveExtractError(
                        f"Symbolic links are not allowed in archives: {rar_info.filename}"
                    )

                target_path = ensure_safe_target_path(
                    extract_dir=extract_dir,
                    member_name=rar_info.filename,
                )

                if rar_info_is_dir(rar_info):
                    target_path.mkdir(parents=True, exist_ok=True)
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)

                with rar_file.open(rar_info) as source_file:
                    with target_path.open("wb") as target_file:
                        shutil.copyfileobj(source_file, target_file)

                extracted_files_count += 1

    except rarfile.RarCannotExec as exc:
        raise ArchiveExtractError(
            "RAR extraction tool is not available. Please install unar or unrar in the backend container."
        ) from exc
    except rarfile.PasswordRequired as exc:
        raise ArchiveExtractError("Password-protected rar archives are not supported.") from exc
    except rarfile.BadRarFile as exc:
        raise ArchiveExtractError("Invalid rar archive.") from exc
    except rarfile.Error as exc:
        raise ArchiveExtractError(f"Failed to extract rar archive: {exc}") from exc

    return extracted_files_count


def extract_repository_archive(
    *,
    archive_path: Path,
    original_filename: str,
    extract_dir: Path,
) -> ArchiveExtractResult:
    archive_type = get_archive_type(original_filename)

    extract_dir.mkdir(parents=True, exist_ok=True)

    if archive_type == "zip":
        extracted_files_count = extract_zip_archive(
            archive_path=archive_path,
            extract_dir=extract_dir,
        )
    elif archive_type == "rar":
        extracted_files_count = extract_rar_archive(
            archive_path=archive_path,
            extract_dir=extract_dir,
        )
    else:
        raise ArchiveExtractError(f"Unsupported archive type: {archive_type}")

    return ArchiveExtractResult(
        archive_type=archive_type,
        extracted_files_count=extracted_files_count,
    )