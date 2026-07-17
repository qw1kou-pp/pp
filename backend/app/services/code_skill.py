from __future__ import annotations
from typing import Any
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from collections.abc import Iterable

TEST_DIRECTORY_NAMES = {
    "test",
    "tests",
    "__tests__",
    "spec",
    "specs",
}

GENERIC_PATH_TOKENS = {
    "src",
    "source",
    "app",
    "lib",
    "backend",
    "frontend",
    "test",
    "tests",
    "spec",
    "specs",
    "__tests__",
    "main",
    "index",
}

CODE_FILE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".cs",
}


def deduplicate_strings(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized_value = str(value).strip()

        if not normalized_value:
            continue

        if normalized_value in seen:
            continue

        seen.add(normalized_value)
        result.append(normalized_value)

    return result


def is_test_file_path(file_path: str) -> bool:
    normalized_path = normalize_repo_path(file_path).lower()

    if not normalized_path:
        return False

    path = PurePosixPath(normalized_path)
    directory_parts = set(path.parts[:-1])
    filename = path.name

    if directory_parts.intersection(TEST_DIRECTORY_NAMES):
        return True

    test_file_patterns = [
        r"test_.+\.(py|js|jsx|ts|tsx|java|go|rb|php|cs)$",
        r".+_test\.(py|go|rb|php|cs|java)$",
        r".+\.(test|spec)\.(js|jsx|ts|tsx)$",
        r".+_(test|spec)\.rb$",
        r".+(test|tests)\.java$",
        r".+tests?\.cs$",
    ]

    return any(
        re.fullmatch(pattern, filename)
        for pattern in test_file_patterns
    )


def get_logical_file_stem(file_path: str) -> str:
    filename = PurePosixPath(
        normalize_repo_path(file_path)
    ).name.lower()

    for suffix in sorted(CODE_FILE_SUFFIXES, key=len, reverse=True):
        if filename.endswith(suffix):
            filename = filename[: -len(suffix)]
            break

    filename = re.sub(r"\.(test|spec)$", "", filename)
    filename = re.sub(r"^(test_|spec_)", "", filename)
    filename = re.sub(r"(_test|_tests|_spec)$", "", filename)

    return filename.strip("._-")


def get_meaningful_path_tokens(file_path: str) -> set[str]:
    normalized_path = normalize_repo_path(file_path).lower()

    normalized_path = re.sub(
        r"\.(test|spec)(?=\.)",
        "",
        normalized_path,
    )

    tokens = {
        token
        for token in re.split(
            r"[/\\._\-]+",
            normalized_path,
        )
        if token
        and token not in GENERIC_PATH_TOKENS
        and token not in {
            suffix.lstrip(".")
            for suffix in CODE_FILE_SUFFIXES
        }
    }

    logical_stem = get_logical_file_stem(file_path)

    if logical_stem:
        tokens.add(logical_stem)

    return tokens


def calculate_test_path_match(
    *,
    test_file_path: str,
    source_file_path: str,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    test_stem = get_logical_file_stem(test_file_path)
    source_stem = get_logical_file_stem(source_file_path)

    if test_stem and test_stem == source_stem:
        score += 0.55
        reasons.append(
            f"测试文件逻辑名称与 {source_file_path} 一致"
        )
    elif (
        test_stem
        and source_stem
        and (
            test_stem in source_stem
            or source_stem in test_stem
        )
    ):
        score += 0.35
        reasons.append(
            f"测试文件名与 {source_file_path} 高度相似"
        )

    test_tokens = get_meaningful_path_tokens(test_file_path)
    source_tokens = get_meaningful_path_tokens(source_file_path)

    common_tokens = test_tokens.intersection(source_tokens)

    if common_tokens:
        token_ratio = len(common_tokens) / max(
            1,
            len(source_tokens),
        )

        token_score = min(0.25, token_ratio * 0.25)
        score += token_score

        reasons.append(
            "路径中包含共同关键词："
            + "、".join(sorted(common_tokens))
        )

    test_suffix = PurePosixPath(
        normalize_repo_path(test_file_path)
    ).suffix.lower()

    source_suffix = PurePosixPath(
        normalize_repo_path(source_file_path)
    ).suffix.lower()

    if test_suffix and test_suffix == source_suffix:
        score += 0.05

    return round(min(score, 0.85), 2), reasons


def find_symbol_occurrences_in_content(
    *,
    content: str,
    symbol_names: Iterable[str],
) -> dict[str, int]:
    code_body = strip_code_chunk_metadata_header(content)

    result: dict[str, int] = {}

    for symbol_name in deduplicate_strings(symbol_names):
        regex = build_symbol_search_regex(symbol_name)

        if regex is None:
            continue

        occurrence_count = len(regex.findall(code_body))

        if occurrence_count > 0:
            result[symbol_name] = occurrence_count

    return result


def calculate_test_recommendation_confidence(
    *,
    path_match_score: float,
    symbol_match_count: int,
    matched_symbol_count: int,
    related_file_count: int,
) -> float:
    confidence = path_match_score

    confidence += min(
        0.30,
        matched_symbol_count * 0.12,
    )

    confidence += min(
        0.10,
        symbol_match_count * 0.03,
    )

    confidence += min(
        0.08,
        related_file_count * 0.02,
    )

    return round(min(confidence, 0.98), 2)


def build_test_candidate_preview(
    *,
    chunk_contents: list[str],
    matched_symbols: list[str],
    max_chars: int = 600,
) -> str | None:
    for content in chunk_contents:
        for symbol_name in matched_symbols:
            preview = build_reference_preview(
                content=content,
                symbol_name=symbol_name,
                context_line_count=2,
                max_chars=max_chars,
            )

            if preview:
                return preview

    for content in chunk_contents:
        code_body = strip_code_chunk_metadata_header(content).strip()

        if not code_body:
            continue

        if len(code_body) > max_chars:
            return code_body[:max_chars] + "..."

        return code_body

    return None


def resolve_code_file_path(
    *,
    document_filename: str,
    chunk_contents: list[str],
) -> str:
    for content in chunk_contents:
        metadata = extract_code_chunk_metadata(content)

        file_path = metadata.get("file_path")

        if file_path:
            return file_path

    return document_filename


def build_test_gap_notes(
    *,
    recommended_test_count: int,
    uncovered_changed_files: list[str],
    uncovered_symbols: list[str],
) -> list[str]:
    notes: list[str] = []

    if recommended_test_count == 0:
        notes.append(
            "未找到与本次变更明显相关的测试文件，"
            "建议检查仓库是否包含测试代码，或补充对应测试。"
        )

    if uncovered_changed_files:
        notes.append(
            "以下变更文件未找到明确相关测试："
            + "、".join(uncovered_changed_files[:10])
        )

    if uncovered_symbols:
        notes.append(
            "以下变更符号未在推荐测试中直接出现："
            + "、".join(uncovered_symbols[:10])
        )

    return notes


@dataclass
class DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    added_lines: int = 0
    deleted_lines: int = 0
    context_lines: int = 0


@dataclass
class DiffChangedFile:
    old_path: str | None
    new_path: str | None
    file_path: str
    change_type: str
    added_lines: int
    deleted_lines: int
    hunks: list[DiffHunk]


def normalize_diff_path(path: str) -> str:
    path = path.strip()

    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]

    return path


def parse_hunk_header(line: str) -> DiffHunk | None:
    pattern = r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"

    match = re.search(pattern, line)

    if not match:
        return None

    old_start = int(match.group(1))
    old_count = int(match.group(2) or "1")
    new_start = int(match.group(3))
    new_count = int(match.group(4) or "1")

    return DiffHunk(
        old_start=old_start,
        old_count=old_count,
        new_start=new_start,
        new_count=new_count,
    )


def infer_change_type(
    *,
    old_path: str | None,
    new_path: str | None,
) -> str:
    if old_path is None and new_path is not None:
        return "added"

    if old_path is not None and new_path is None:
        return "deleted"

    if old_path and new_path and old_path != new_path:
        return "renamed"

    return "modified"


def parse_git_diff(diff_text: str) -> list[DiffChangedFile]:
    changed_files: list[DiffChangedFile] = []

    current_old_path: str | None = None
    current_new_path: str | None = None
    current_hunks: list[DiffHunk] = []
    current_hunk: DiffHunk | None = None

    def flush_current_file() -> None:
        nonlocal current_old_path
        nonlocal current_new_path
        nonlocal current_hunks
        nonlocal current_hunk

        if current_old_path is None and current_new_path is None:
            return

        file_path = current_new_path or current_old_path or "unknown"

        added_lines = sum(hunk.added_lines for hunk in current_hunks)
        deleted_lines = sum(hunk.deleted_lines for hunk in current_hunks)

        changed_files.append(
            DiffChangedFile(
                old_path=current_old_path,
                new_path=current_new_path,
                file_path=file_path,
                change_type=infer_change_type(
                    old_path=current_old_path,
                    new_path=current_new_path,
                ),
                added_lines=added_lines,
                deleted_lines=deleted_lines,
                hunks=current_hunks,
            )
        )

        current_old_path = None
        current_new_path = None
        current_hunks = []
        current_hunk = None

    for raw_line in diff_text.splitlines():
        line = raw_line.rstrip("\n")

        if line.startswith("diff --git "):
            flush_current_file()
            continue

        if line.startswith("--- "):
            old_path = line.removeprefix("--- ").strip()

            if old_path == "/dev/null":
                current_old_path = None
            else:
                current_old_path = normalize_diff_path(old_path)

            continue

        if line.startswith("+++ "):
            new_path = line.removeprefix("+++ ").strip()

            if new_path == "/dev/null":
                current_new_path = None
            else:
                current_new_path = normalize_diff_path(new_path)

            continue

        if line.startswith("@@ "):
            hunk = parse_hunk_header(line)

            if hunk is not None:
                current_hunks.append(hunk)
                current_hunk = hunk

            continue

        if current_hunk is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            current_hunk.added_lines += 1
            continue

        if line.startswith("-") and not line.startswith("---"):
            current_hunk.deleted_lines += 1
            continue

        current_hunk.context_lines += 1

    flush_current_file()

    return changed_files


def normalize_repo_path(path: str | None) -> str:
    if not path:
        return ""

    return path.replace("\\", "/").strip().lstrip("./")


def repo_paths_match(document_path: str, changed_path: str) -> bool:
    document_path = normalize_repo_path(document_path)
    changed_path = normalize_repo_path(changed_path)

    if not document_path or not changed_path:
        return False

    if document_path == changed_path:
        return True

    if document_path.endswith("/" + changed_path):
        return True

    if changed_path.endswith("/" + document_path):
        return True

    return False


def extract_code_chunk_metadata(content: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    for line in content.splitlines()[:8]:
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key in {
            "file_path",
            "language",
            "symbol_name",
            "symbol_type",
            "line_range",
        }:
            metadata[key] = value

    return metadata


def parse_line_range(line_range: str | None) -> tuple[int, int] | None:
    if not line_range:
        return None

    numbers = re.findall(r"\d+", line_range)

    if not numbers:
        return None

    if len(numbers) == 1:
        line_number = int(numbers[0])
        return line_number, line_number

    start_line = int(numbers[0])
    end_line = int(numbers[1])

    if start_line > end_line:
        start_line, end_line = end_line, start_line

    return start_line, end_line


def get_hunk_new_line_range(hunk: DiffHunk) -> tuple[int, int]:
    if hunk.new_count <= 0:
        return hunk.new_start, hunk.new_start

    return hunk.new_start, hunk.new_start + hunk.new_count - 1


def calculate_range_overlap(
    *,
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> tuple[int, int, int] | None:
    overlap_start = max(first_start, second_start)
    overlap_end = min(first_end, second_end)

    if overlap_start > overlap_end:
        return None

    return overlap_start, overlap_end, overlap_end - overlap_start + 1


def build_changed_symbol_reason(
    *,
    symbol_name: str,
    symbol_type: str,
    symbol_start: int,
    symbol_end: int,
    hunk_start: int,
    hunk_end: int,
) -> str:
    return (
        f"diff hunk 新文件行号 {hunk_start}-{hunk_end} "
        f"与 {symbol_type} {symbol_name} 的行号范围 "
        f"{symbol_start}-{symbol_end} 发生重叠"
    )


def calculate_symbol_confidence(
    *,
    overlap_line_count: int,
    hunk_start: int,
    hunk_end: int,
    symbol_start: int,
    symbol_end: int,
) -> float:
    hunk_length = max(1, hunk_end - hunk_start + 1)
    symbol_length = max(1, symbol_end - symbol_start + 1)

    hunk_overlap_ratio = overlap_line_count / hunk_length
    symbol_overlap_ratio = overlap_line_count / symbol_length

    confidence = 0.6 + min(0.3, hunk_overlap_ratio * 0.2 + symbol_overlap_ratio * 0.1)

    return round(min(confidence, 0.95), 2)


def build_file_level_fallback_symbol(
    *,
    file_path: str,
    hunk: DiffHunk,
) -> dict[str, Any]:
    hunk_start, hunk_end = get_hunk_new_line_range(hunk)

    return {
        "symbol_name": file_path.split("/")[-1],
        "symbol_type": "file",
        "line_range": f"{hunk_start}-{hunk_end}",
        "symbol_start_line": hunk_start,
        "symbol_end_line": hunk_end,
        "changed_hunk_new_start": hunk_start,
        "changed_hunk_new_end": hunk_end,
        "overlap_start_line": hunk_start,
        "overlap_end_line": hunk_end,
        "overlap_line_count": max(1, hunk_end - hunk_start + 1),
        "confidence": 0.3,
        "reason": "未找到函数/类级元数据，降级为文件级变更定位",
    }


def strip_code_chunk_metadata_header(content: str) -> str:
    metadata_keys = {
        "file_path",
        "language",
        "symbol_name",
        "symbol_type",
        "line_range",
    }

    lines = content.splitlines()
    start_index = 0

    for index, line in enumerate(lines[:10]):
        if not line.strip():
            start_index = index + 1
            break

        if ":" not in line:
            break

        key = line.split(":", 1)[0].strip()

        if key not in metadata_keys:
            break

        start_index = index + 1

    return "\n".join(lines[start_index:])


def build_symbol_search_regex(symbol_name: str) -> re.Pattern[str] | None:
    symbol_name = symbol_name.strip()

    if not symbol_name:
        return None

    escaped_symbol_name = re.escape(symbol_name)

    pattern = rf"(?<![A-Za-z0-9_]){escaped_symbol_name}(?![A-Za-z0-9_])"

    return re.compile(pattern)


def count_symbol_occurrences(
    *,
    content: str,
    symbol_name: str,
) -> int:
    regex = build_symbol_search_regex(symbol_name)

    if regex is None:
        return 0

    code_body = strip_code_chunk_metadata_header(content)

    return len(regex.findall(code_body))


def build_reference_preview(
    *,
    content: str,
    symbol_name: str,
    context_line_count: int = 2,
    max_chars: int = 500,
) -> str | None:
    regex = build_symbol_search_regex(symbol_name)

    if regex is None:
        return None

    code_body = strip_code_chunk_metadata_header(content)
    lines = code_body.splitlines()

    for index, line in enumerate(lines):
        if regex.search(line):
            start_index = max(0, index - context_line_count)
            end_index = min(len(lines), index + context_line_count + 1)

            preview = "\n".join(lines[start_index:end_index]).strip()

            if len(preview) > max_chars:
                preview = preview[:max_chars] + "..."

            return preview

    return None


def is_definition_chunk_for_symbol(
    *,
    metadata: dict[str, str],
    chunk_id: str,
    changed_symbol_name: str,
    changed_symbol_file_path: str,
    changed_symbol_chunk_id: str | None,
) -> bool:
    metadata_symbol_name = metadata.get("symbol_name")
    metadata_file_path = metadata.get("file_path")

    if changed_symbol_chunk_id and chunk_id == changed_symbol_chunk_id:
        return True

    if metadata_symbol_name != changed_symbol_name:
        return False

    if metadata_file_path and repo_paths_match(
        document_path=metadata_file_path,
        changed_path=changed_symbol_file_path,
    ):
        return True

    return False


def calculate_reference_confidence(
    *,
    occurrence_count: int,
    same_file: bool,
    containing_symbol_name: str | None,
) -> float:
    confidence = 0.55

    if occurrence_count >= 1:
        confidence += 0.2

    if occurrence_count >= 2:
        confidence += 0.1

    if containing_symbol_name:
        confidence += 0.1

    if same_file:
        confidence += 0.05

    return round(min(confidence, 0.95), 2)


def build_impact_reference_reason(
    *,
    changed_symbol_name: str,
    occurrence_count: int,
    containing_symbol_name: str | None,
    file_path: str,
) -> str:
    location = (
        f"符号 {containing_symbol_name} 中"
        if containing_symbol_name
        else "该代码片段中"
    )

    return (
        f"{location}出现了 {occurrence_count} 次 "
        f"{changed_symbol_name}，因此文件 {file_path} "
        "可能受到本次变更影响"
    )