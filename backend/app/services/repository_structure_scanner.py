from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_MAX_SCAN_FILES = 10_000
DEFAULT_MAX_READ_BYTES = 1024 * 1024
DEFAULT_README_EXCERPT_CHARACTERS = 4_000

IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    ".nuxt",
    ".turbo",
    "__pycache__",
    "node_modules",
    "bower_components",
    "vendor",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "out",
    "target",
    "coverage",
    "htmlcov",
}

BINARY_FILE_SUFFIXES = {
    ".7z",
    ".avi",
    ".bin",
    ".bmp",
    ".class",
    ".db",
    ".dll",
    ".dylib",
    ".eot",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".mov",
    ".mp3",
    ".mp4",
    ".o",
    ".obj",
    ".otf",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".xz",
    ".zip",
}

LANGUAGE_BY_SUFFIX = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".dart": "Dart",
    ".go": "Go",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".lua": "Lua",
    ".m": "Objective-C",
    ".md": "Markdown",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".scala": "Scala",
    ".scss": "SCSS",
    ".sh": "Shell",
    ".sql": "SQL",
    ".swift": "Swift",
    ".svelte": "Svelte",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
}

README_NAMES = {
    "readme",
    "readme.md",
    "readme.rst",
    "readme.txt",
    "readme.adoc",
}

MANIFEST_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-prod.txt",
    "poetry.lock",
    "uv.lock",
    "pdm.lock",
    "pipfile",
    "pipfile.lock",
    "go.mod",
    "go.sum",
    "cargo.toml",
    "cargo.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "composer.json",
    "gemfile",
    "gemfile.lock",
    "mix.exs",
}

ENTRY_POINT_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "main.go",
    "main.rs",
    "index.js",
    "index.ts",
    "main.js",
    "main.ts",
    "main.tsx",
    "index.tsx",
}

DEPLOYMENT_NAMES = {
    "compose.yml",
    "compose.yaml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "procfile",
    "fly.toml",
    "render.yaml",
    "railway.json",
    "vercel.json",
    "netlify.toml",
    "helmfile.yaml",
    "helmfile.yml",
}

CI_NAMES = {
    ".gitlab-ci.yml",
    ".gitlab-ci.yaml",
    "jenkinsfile",
    "azure-pipelines.yml",
    "azure-pipelines.yaml",
    "bitbucket-pipelines.yml",
    "bitbucket-pipelines.yaml",
    "buildkite.yml",
    "buildkite.yaml",
}

SOURCE_ROOT_NAMES = {
    "app",
    "apps",
    "backend",
    "client",
    "frontend",
    "lib",
    "packages",
    "server",
    "services",
    "src",
}


@dataclass(frozen=True, slots=True)
class RepositoryScanResult:
    """
    仓库确定性扫描结果。

    这里只保存从文件系统中直接观察到的信息，
    不包含大模型推断。
    """

    project_title: str
    project_summary: str | None

    scanned_file_count: int
    ignored_directory_count: int
    skipped_large_file_count: int
    scan_truncated: bool

    tree: tuple[str, ...]
    language_file_counts: dict[str, int]

    readme_path: str | None
    readme_excerpt: str | None

    manifests: tuple[str, ...]
    dependency_names: tuple[str, ...]

    entry_points: tuple[str, ...]
    deployment_files: tuple[str, ...]
    ci_files: tuple[str, ...]
    migration_paths: tuple[str, ...]
    test_paths: tuple[str, ...]
    module_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """转换为可以直接保存到 JSONB 的结构。"""

        return {
            "project_title": self.project_title,
            "project_summary": self.project_summary,
            "scan_statistics": {
                "scanned_file_count": (
                    self.scanned_file_count
                ),
                "ignored_directory_count": (
                    self.ignored_directory_count
                ),
                "skipped_large_file_count": (
                    self.skipped_large_file_count
                ),
                "scan_truncated": self.scan_truncated,
            },
            "tree": list(self.tree),
            "language_file_counts": dict(
                self.language_file_counts,
            ),
            "readme": {
                "path": self.readme_path,
                "excerpt": self.readme_excerpt,
            },
            "manifests": list(self.manifests),
            "dependency_names": list(
                self.dependency_names,
            ),
            "entry_points": list(self.entry_points),
            "deployment_files": list(
                self.deployment_files,
            ),
            "ci_files": list(self.ci_files),
            "migration_paths": list(
                self.migration_paths,
            ),
            "test_paths": list(self.test_paths),
            "module_paths": list(self.module_paths),
        }


@dataclass(frozen=True, slots=True)
class _ScannedFile:
    """扫描过程中使用的内部文件记录。"""

    absolute_path: Path
    relative_path: str
    size_bytes: int
    language: str | None


def scan_repository_structure(
    repository_root: Path | str,
    *,
    max_scan_files: int = DEFAULT_MAX_SCAN_FILES,
    max_read_bytes: int = DEFAULT_MAX_READ_BYTES,
) -> RepositoryScanResult:
    """
    扫描仓库结构和关键文件。

    扫描采用固定排序，保证对同一个 Commit
    多次执行时尽量得到一致结果。
    """

    root = Path(repository_root).resolve()

    if not root.exists():
        raise FileNotFoundError(
            f"Repository root does not exist: {root}",
        )

    if not root.is_dir():
        raise NotADirectoryError(
            f"Repository root is not a directory: {root}",
        )

    scanned_files: list[_ScannedFile] = []

    ignored_directory_count = 0
    skipped_large_file_count = 0
    scan_truncated = False

    for (
        current_directory,
        directory_names,
        file_names,
    ) in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current_directory)

        retained_directories: list[str] = []

        for directory_name in sorted(
            directory_names,
            key=str.lower,
        ):
            if _should_ignore_directory(
                directory_name,
            ):
                ignored_directory_count += 1
                continue

            candidate_directory = (
                current_path / directory_name
            )

            if candidate_directory.is_symlink():
                ignored_directory_count += 1
                continue

            retained_directories.append(
                directory_name,
            )

        directory_names[:] = retained_directories

        for file_name in sorted(
            file_names,
            key=str.lower,
        ):
            if len(scanned_files) >= max_scan_files:
                scan_truncated = True
                break

            file_path = current_path / file_name

            if file_path.is_symlink():
                continue

            try:
                file_size = file_path.stat().st_size
            except OSError:
                continue

            relative_path = file_path.relative_to(
                root,
            ).as_posix()

            language = _detect_language(
                file_path,
            )

            scanned_files.append(
                _ScannedFile(
                    absolute_path=file_path,
                    relative_path=relative_path,
                    size_bytes=file_size,
                    language=language,
                ),
            )

            if file_size > max_read_bytes:
                skipped_large_file_count += 1

        if scan_truncated:
            break

    readme_file = _select_readme(
        scanned_files,
    )

    readme_excerpt = None
    project_title = root.name
    project_summary = None

    if readme_file is not None:
        readme_excerpt = _read_text_file(
            readme_file.absolute_path,
            max_read_bytes=max_read_bytes,
        )

        if readme_excerpt:
            project_title = (
                _extract_markdown_title(
                    readme_excerpt,
                )
                or project_title
            )

            project_summary = (
                _extract_readme_summary(
                    readme_excerpt,
                )
            )

    manifests = _find_manifests(
        scanned_files,
    )

    dependencies = _extract_dependencies(
        scanned_files,
        max_read_bytes=max_read_bytes,
    )

    entry_points = _find_entry_points(
        scanned_files,
    )

    deployment_files = _find_deployment_files(
        scanned_files,
    )

    ci_files = _find_ci_files(
        scanned_files,
    )

    migration_paths = _find_migration_paths(
        scanned_files,
    )

    test_paths = _find_test_paths(
        scanned_files,
    )

    module_paths = _find_module_paths(
        root,
    )

    tree = _build_tree(
        scanned_files,
    )

    language_counts = _count_languages(
        scanned_files,
    )

    return RepositoryScanResult(
        project_title=project_title,
        project_summary=project_summary,
        scanned_file_count=len(scanned_files),
        ignored_directory_count=(
            ignored_directory_count
        ),
        skipped_large_file_count=(
            skipped_large_file_count
        ),
        scan_truncated=scan_truncated,
        tree=tree,
        language_file_counts=language_counts,
        readme_path=(
            readme_file.relative_path
            if readme_file is not None
            else None
        ),
        readme_excerpt=readme_excerpt,
        manifests=manifests,
        dependency_names=dependencies,
        entry_points=entry_points,
        deployment_files=deployment_files,
        ci_files=ci_files,
        migration_paths=migration_paths,
        test_paths=test_paths,
        module_paths=module_paths,
    )


def _should_ignore_directory(
    directory_name: str,
) -> bool:
    normalized_name = directory_name.lower()

    return normalized_name in {
        name.lower()
        for name in IGNORED_DIRECTORY_NAMES
    }


def _detect_language(
    file_path: Path,
) -> str | None:
    file_name = file_path.name.lower()

    if file_name == "dockerfile" or file_name.startswith(
        "dockerfile.",
    ):
        return "Dockerfile"

    if file_name == "makefile":
        return "Makefile"

    return LANGUAGE_BY_SUFFIX.get(
        file_path.suffix.lower(),
    )


def _select_readme(
    scanned_files: list[_ScannedFile],
) -> _ScannedFile | None:
    candidates = [
        scanned_file
        for scanned_file in scanned_files
        if scanned_file.absolute_path.name.lower()
        in README_NAMES
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            len(
                PurePosixPath(
                    item.relative_path,
                ).parts,
            ),
            item.relative_path.lower(),
        ),
    )

    return candidates[0]


def _read_text_file(
    file_path: Path,
    *,
    max_read_bytes: int,
) -> str | None:
    if file_path.suffix.lower() in BINARY_FILE_SUFFIXES:
        return None

    try:
        with file_path.open("rb") as source:
            content = source.read(
                max_read_bytes + 1,
            )
    except OSError:
        return None

    if b"\x00" in content:
        return None

    content = content[:max_read_bytes]

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode(
            "utf-8",
            errors="replace",
        )

    normalized_text = text.strip()

    if not normalized_text:
        return None

    return normalized_text[
        :DEFAULT_README_EXCERPT_CHARACTERS
    ]


def _extract_markdown_title(
    readme_text: str,
) -> str | None:
    for line in readme_text.splitlines():
        normalized_line = line.strip()

        if normalized_line.startswith("# "):
            title = normalized_line[2:].strip()

            if title:
                return title[:300]

    return None


def _extract_readme_summary(
    readme_text: str,
) -> str | None:
    paragraph_lines: list[str] = []

    for line in readme_text.splitlines():
        normalized_line = line.strip()

        if not normalized_line:
            if paragraph_lines:
                break

            continue

        if normalized_line.startswith(
            (
                "#",
                "![",
                "[![",
                "<",
                "```",
                "---",
            ),
        ):
            continue

        paragraph_lines.append(
            normalized_line,
        )

        if sum(
            len(item)
            for item in paragraph_lines
        ) >= 600:
            break

    if not paragraph_lines:
        return None

    summary = " ".join(
        paragraph_lines,
    )

    summary = re.sub(
        r"\s+",
        " ",
        summary,
    ).strip()

    return summary[:800] or None


def _find_manifests(
    scanned_files: list[_ScannedFile],
) -> tuple[str, ...]:
    results = {
        item.relative_path
        for item in scanned_files
        if (
            item.absolute_path.name.lower()
            in MANIFEST_NAMES
            or item.absolute_path.name.lower().startswith(
                "requirements-",
            )
            and item.absolute_path.suffix.lower()
            == ".txt"
        )
    }

    return tuple(
        sorted(
            results,
            key=str.lower,
        ),
    )


def _extract_dependencies(
    scanned_files: list[_ScannedFile],
    *,
    max_read_bytes: int,
) -> tuple[str, ...]:
    dependency_names: set[str] = set()

    for item in scanned_files:
        file_name = item.absolute_path.name.lower()

        if item.size_bytes > max_read_bytes:
            continue

        if file_name == "package.json":
            dependency_names.update(
                _extract_package_json_dependencies(
                    item.absolute_path,
                ),
            )

        elif (
            file_name == "requirements.txt"
            or (
                file_name.startswith(
                    "requirements-",
                )
                and file_name.endswith(".txt")
            )
        ):
            dependency_names.update(
                _extract_requirements_dependencies(
                    item.absolute_path,
                    max_read_bytes=max_read_bytes,
                ),
            )

        elif file_name == "pyproject.toml":
            dependency_names.update(
                _extract_pyproject_dependencies(
                    item.absolute_path,
                    max_read_bytes=max_read_bytes,
                ),
            )

    return tuple(
        sorted(
            dependency_names,
            key=str.lower,
        )[:300],
    )


def _extract_package_json_dependencies(
    file_path: Path,
) -> set[str]:
    try:
        payload = json.loads(
            file_path.read_text(
                encoding="utf-8",
            ),
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return set()

    if not isinstance(payload, dict):
        return set()

    results: set[str] = set()

    for section_name in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ):
        section = payload.get(section_name)

        if not isinstance(section, dict):
            continue

        results.update(
            dependency
            for dependency in section
            if isinstance(dependency, str)
            and dependency.strip()
        )

    return results


def _extract_requirements_dependencies(
    file_path: Path,
    *,
    max_read_bytes: int,
) -> set[str]:
    text = _read_text_file(
        file_path,
        max_read_bytes=max_read_bytes,
    )

    if text is None:
        return set()

    results: set[str] = set()

    for line in text.splitlines():
        normalized_line = line.strip()

        if (
            not normalized_line
            or normalized_line.startswith(
                ("#", "-", "git+"),
            )
        ):
            continue

        package_name = re.split(
            r"[<>=!~;\[\]\s]",
            normalized_line,
            maxsplit=1,
        )[0].strip()

        if package_name:
            results.add(package_name)

    return results


def _extract_pyproject_dependencies(
    file_path: Path,
    *,
    max_read_bytes: int,
) -> set[str]:
    text = _read_text_file(
        file_path,
        max_read_bytes=max_read_bytes,
    )

    if text is None:
        return set()

    results: set[str] = set()

    dependency_pattern = re.compile(
        r'^\s*["\']?([A-Za-z0-9_.-]+)'
        r'(?:\[[^\]]+\])?'
        r'(?:\s*[<>=!~^].*)?["\']?,?\s*$',
    )

    inside_dependency_section = False

    for line in text.splitlines():
        normalized_line = line.strip()

        if normalized_line.startswith("["):
            inside_dependency_section = (
                normalized_line
                in {
                    "[project.dependencies]",
                    "[tool.poetry.dependencies]",
                    "[tool.poetry.group.dev.dependencies]",
                    "[tool.pdm.dev-dependencies]",
                }
            )
            continue

        if "dependencies = [" in normalized_line:
            inside_dependency_section = True
            continue

        if inside_dependency_section:
            if normalized_line == "]":
                inside_dependency_section = False
                continue

            match = dependency_pattern.match(
                normalized_line,
            )

            if match:
                dependency_name = match.group(1)

                if dependency_name.lower() != "python":
                    results.add(dependency_name)

    return results


def _find_entry_points(
    scanned_files: list[_ScannedFile],
) -> tuple[str, ...]:
    results: set[str] = set()

    for item in scanned_files:
        path = PurePosixPath(
            item.relative_path,
        )

        file_name = path.name.lower()
        path_text = item.relative_path.lower()

        if file_name in ENTRY_POINT_NAMES:
            results.add(item.relative_path)
            continue

        if path_text in {
            "src/main.ts",
            "src/main.tsx",
            "src/index.ts",
            "src/index.tsx",
            "src/main.py",
            "app/main.py",
            "backend/app/main.py",
            "frontend/src/main.tsx",
            "frontend/src/main.ts",
        }:
            results.add(item.relative_path)
            continue

        if (
            len(path.parts) >= 3
            and path.parts[0].lower() == "cmd"
            and file_name == "main.go"
        ):
            results.add(item.relative_path)

    return tuple(
        sorted(
            results,
            key=str.lower,
        ),
    )


def _find_deployment_files(
    scanned_files: list[_ScannedFile],
) -> tuple[str, ...]:
    results: set[str] = set()

    for item in scanned_files:
        path = PurePosixPath(
            item.relative_path,
        )

        file_name = path.name.lower()
        lower_parts = {
            part.lower()
            for part in path.parts
        }

        if (
            file_name in DEPLOYMENT_NAMES
            or file_name == "dockerfile"
            or file_name.startswith("dockerfile.")
            or "k8s" in lower_parts
            or "kubernetes" in lower_parts
            or "helm" in lower_parts
        ):
            results.add(item.relative_path)

    return tuple(
        sorted(
            results,
            key=str.lower,
        ),
    )


def _find_ci_files(
    scanned_files: list[_ScannedFile],
) -> tuple[str, ...]:
    results: set[str] = set()

    for item in scanned_files:
        path_text = item.relative_path.lower()
        file_name = item.absolute_path.name.lower()

        if (
            path_text.startswith(
                ".github/workflows/",
            )
            or path_text
            == ".circleci/config.yml"
            or path_text
            == ".circleci/config.yaml"
            or file_name in CI_NAMES
        ):
            results.add(item.relative_path)

    return tuple(
        sorted(
            results,
            key=str.lower,
        ),
    )


def _find_migration_paths(
    scanned_files: list[_ScannedFile],
) -> tuple[str, ...]:
    results: set[str] = set()

    migration_directory_names = {
        "alembic",
        "migrations",
        "migration",
    }

    for item in scanned_files:
        path = PurePosixPath(
            item.relative_path,
        )

        lower_parts = {
            part.lower()
            for part in path.parts
        }

        if (
            lower_parts
            & migration_directory_names
            or item.absolute_path.name.lower()
            in {
                "alembic.ini",
                "schema.prisma",
            }
        ):
            results.add(item.relative_path)

    return tuple(
        sorted(
            results,
            key=str.lower,
        )[:200],
    )


def _find_test_paths(
    scanned_files: list[_ScannedFile],
) -> tuple[str, ...]:
    results: set[str] = set()

    test_directory_names = {
        "test",
        "tests",
        "__tests__",
        "spec",
        "specs",
    }

    for item in scanned_files:
        path = PurePosixPath(
            item.relative_path,
        )

        lower_parts = {
            part.lower()
            for part in path.parts[:-1]
        }

        file_name = path.name.lower()

        if (
            lower_parts & test_directory_names
            or file_name.startswith("test_")
            or file_name.endswith("_test.py")
            or ".test." in file_name
            or ".spec." in file_name
        ):
            results.add(item.relative_path)

    return tuple(
        sorted(
            results,
            key=str.lower,
        )[:300],
    )


def _find_module_paths(
    repository_root: Path,
) -> tuple[str, ...]:
    results: set[str] = set()

    try:
        root_children = sorted(
            repository_root.iterdir(),
            key=lambda item: item.name.lower(),
        )
    except OSError:
        return ()

    for child in root_children:
        if (
            not child.is_dir()
            or child.is_symlink()
            or _should_ignore_directory(
                child.name,
            )
        ):
            continue

        results.add(
            f"{child.name}/",
        )

        if child.name.lower() not in SOURCE_ROOT_NAMES:
            continue

        try:
            second_level_children = sorted(
                child.iterdir(),
                key=lambda item: item.name.lower(),
            )
        except OSError:
            continue

        for second_level in second_level_children:
            if (
                second_level.is_dir()
                and not second_level.is_symlink()
                and not _should_ignore_directory(
                    second_level.name,
                )
            ):
                results.add(
                    (
                        f"{child.name}/"
                        f"{second_level.name}/"
                    ),
                )

    return tuple(
        sorted(
            results,
            key=str.lower,
        ),
    )


def _build_tree(
    scanned_files: list[_ScannedFile],
) -> tuple[str, ...]:
    entries: set[str] = set()

    for item in scanned_files:
        path = PurePosixPath(
            item.relative_path,
        )

        if len(path.parts) == 1:
            entries.add(path.parts[0])
            continue

        entries.add(
            f"{path.parts[0]}/",
        )

        second_level = (
            f"{path.parts[0]}/"
            f"{path.parts[1]}"
        )

        if len(path.parts) > 2:
            second_level += "/"

        entries.add(second_level)

    return tuple(
        sorted(
            entries,
            key=str.lower,
        ),
    )


def _count_languages(
    scanned_files: list[_ScannedFile],
) -> dict[str, int]:
    counts: dict[str, int] = {}

    for item in scanned_files:
        if item.language is None:
            continue

        counts[item.language] = (
            counts.get(item.language, 0) + 1
        )

    return dict(
        sorted(
            counts.items(),
            key=lambda item: (
                -item[1],
                item[0].lower(),
            ),
        ),
    )