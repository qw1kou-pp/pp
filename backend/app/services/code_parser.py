from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


CODE_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript-react",
    ".js": "javascript",
    ".jsx": "javascript-react",
    ".java": "java",
    ".go": "go",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c-header",
    ".hpp": "cpp-header",
    ".cs": "csharp",
    ".rs": "rust",
    ".vue": "vue",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
}


@dataclass
class CodeChunk:
    content: str
    file_path: str
    language: str
    symbol_name: str | None
    symbol_type: str | None
    start_line: int
    end_line: int


def is_code_file(filename: str) -> bool:
    extension = Path(filename).suffix.lower()
    return extension in CODE_EXTENSIONS


def get_code_language(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    return CODE_EXTENSIONS.get(extension, "text")


def decode_code_file(file_bytes: bytes) -> str:
    encodings = [
        "utf-8",
        "utf-8-sig",
        "gb18030",
        "latin-1",
    ]

    for encoding in encodings:
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    return file_bytes.decode("utf-8", errors="ignore")


def build_code_chunk_content(
    *,
    file_path: str,
    language: str,
    symbol_name: str | None,
    symbol_type: str | None,
    start_line: int,
    end_line: int,
    code: str,
) -> str:
    header = [
        f"file_path: {file_path}",
        f"language: {language}",
        f"symbol_name: {symbol_name or '-'}",
        f"symbol_type: {symbol_type or '-'}",
        f"line_range: {start_line}-{end_line}",
    ]

    return (
        "\n".join(header)
        + "\n\n"
        + "```"
        + language
        + "\n"
        + code.strip()
        + "\n```"
    )


def find_python_symbols(lines: list[str]) -> list[tuple[int, str, str]]:
    symbols: list[tuple[int, str, str]] = []

    pattern = re.compile(
        r"^\s*(class|def|async\s+def)\s+([A-Za-z_][A-Za-z0-9_]*)"
    )

    for index, line in enumerate(lines):
        match = pattern.match(line)

        if not match:
            continue

        raw_type = match.group(1)
        name = match.group(2)

        if raw_type == "class":
            symbol_type = "class"
        else:
            symbol_type = "function"

        symbols.append((index, symbol_type, name))

    return symbols


def find_ts_js_symbols(lines: list[str]) -> list[tuple[int, str, str]]:
    symbols: list[tuple[int, str, str]] = []

    patterns: list[tuple[re.Pattern[str], str]] = [
        (
            re.compile(
                r"^\s*export\s+default\s+function\s+([A-Za-z_$][A-Za-z0-9_$]*)"
            ),
            "function",
        ),
        (
            re.compile(
                r"^\s*export\s+function\s+([A-Za-z_$][A-Za-z0-9_$]*)"
            ),
            "function",
        ),
        (
            re.compile(r"^\s*function\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
            "function",
        ),
        (
            re.compile(r"^\s*export\s+class\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
            "class",
        ),
        (
            re.compile(r"^\s*class\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
            "class",
        ),
        (
            re.compile(
                r"^\s*export\s+const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*="
            ),
            "constant_or_component",
        ),
        (
            re.compile(r"^\s*const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*="),
            "constant_or_component",
        ),
        (
            re.compile(
                r"^\s*export\s+async\s+function\s+([A-Za-z_$][A-Za-z0-9_$]*)"
            ),
            "function",
        ),
        (
            re.compile(r"^\s*async\s+function\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
            "function",
        ),
    ]

    for index, line in enumerate(lines):
        for pattern, symbol_type in patterns:
            match = pattern.match(line)

            if not match:
                continue

            name = match.group(1)
            symbols.append((index, symbol_type, name))
            break

    return symbols


def find_go_symbols(lines: list[str]) -> list[tuple[int, str, str]]:
    symbols: list[tuple[int, str, str]] = []

    pattern = re.compile(
        r"^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\("
    )

    for index, line in enumerate(lines):
        match = pattern.match(line)

        if not match:
            continue

        symbols.append((index, "function", match.group(1)))

    return symbols


def find_java_symbols(lines: list[str]) -> list[tuple[int, str, str]]:
    symbols: list[tuple[int, str, str]] = []

    class_pattern = re.compile(
        r"^\s*(public|private|protected)?\s*(abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"
    )

    method_pattern = re.compile(
        r"^\s*(public|private|protected)?\s*(static\s+)?[A-Za-z_<>\[\]]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
    )

    for index, line in enumerate(lines):
        class_match = class_pattern.match(line)

        if class_match:
            symbols.append((index, "class", class_match.group(3)))
            continue

        method_match = method_pattern.match(line)

        if method_match:
            symbols.append((index, "method", method_match.group(3)))

    return symbols


def find_code_symbols(
    *,
    language: str,
    lines: list[str],
) -> list[tuple[int, str, str]]:
    if language == "python":
        return find_python_symbols(lines)

    if language in [
        "typescript",
        "typescript-react",
        "javascript",
        "javascript-react",
    ]:
        return find_ts_js_symbols(lines)

    if language == "go":
        return find_go_symbols(lines)

    if language == "java":
        return find_java_symbols(lines)

    return []


def split_large_code_block(
    *,
    file_path: str,
    language: str,
    code: str,
    start_line: int,
    max_lines: int = 120,
) -> list[CodeChunk]:
    lines = code.splitlines()
    chunks: list[CodeChunk] = []

    for offset in range(0, len(lines), max_lines):
        part_lines = lines[offset : offset + max_lines]

        if not part_lines:
            continue

        part_start_line = start_line + offset
        part_end_line = part_start_line + len(part_lines) - 1
        part_code = "\n".join(part_lines)

        chunk = CodeChunk(
            content=build_code_chunk_content(
                file_path=file_path,
                language=language,
                symbol_name=None,
                symbol_type="file_part",
                start_line=part_start_line,
                end_line=part_end_line,
                code=part_code,
            ),
            file_path=file_path,
            language=language,
            symbol_name=None,
            symbol_type="file_part",
            start_line=part_start_line,
            end_line=part_end_line,
        )

        chunks.append(chunk)

    return chunks


def split_code_into_chunks(
    *,
    filename: str,
    file_bytes: bytes,
    max_symbol_lines: int = 160,
) -> list[CodeChunk]:
    language = get_code_language(filename)
    text = decode_code_file(file_bytes)

    lines = text.splitlines()

    if not lines:
        return []

    symbols = find_code_symbols(
        language=language,
        lines=lines,
    )

    if not symbols:
        return split_large_code_block(
            file_path=filename,
            language=language,
            code=text,
            start_line=1,
        )

    chunks: list[CodeChunk] = []

    for symbol_index, (start_index, symbol_type, symbol_name) in enumerate(symbols):
        if symbol_index + 1 < len(symbols):
            end_index = symbols[symbol_index + 1][0] - 1
        else:
            end_index = len(lines) - 1

        symbol_lines = lines[start_index : end_index + 1]

        if not symbol_lines:
            continue

        symbol_code = "\n".join(symbol_lines)

        start_line = start_index + 1
        end_line = end_index + 1

        if len(symbol_lines) > max_symbol_lines:
            chunks.extend(
                split_large_code_block(
                    file_path=filename,
                    language=language,
                    code=symbol_code,
                    start_line=start_line,
                    max_lines=max_symbol_lines,
                )
            )
            continue

        chunk = CodeChunk(
            content=build_code_chunk_content(
                file_path=filename,
                language=language,
                symbol_name=symbol_name,
                symbol_type=symbol_type,
                start_line=start_line,
                end_line=end_line,
                code=symbol_code,
            ),
            file_path=filename,
            language=language,
            symbol_name=symbol_name,
            symbol_type=symbol_type,
            start_line=start_line,
            end_line=end_line,
        )

        chunks.append(chunk)

    return chunks