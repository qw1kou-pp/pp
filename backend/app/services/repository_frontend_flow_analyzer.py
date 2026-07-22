from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from app.services.repository_backend_flow_analyzer import (
    RepositoryBackendFlowAnalysis,
)
from app.services.repository_fastapi_router_analyzer import (
    FastApiResolvedRouteEvidence,
    FastApiRouterAnalysis,
)
from app.services.repository_structure_scanner import (
    IGNORED_DIRECTORY_NAMES,
)


DEFAULT_MAX_FRONTEND_FILES = 1_000
DEFAULT_MAX_FRONTEND_FILE_BYTES = 1024 * 1024
DEFAULT_MAX_FRONTEND_FLOW_DEPTH = 8
DEFAULT_MAX_FLOWS_PER_PAGE = 30

FRONTEND_FILE_SUFFIXES = {
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
}

IGNORED_DIRECTORIES_LOWER = {
    name.lower()
    for name in IGNORED_DIRECTORY_NAMES
}

CALL_EXCLUSIONS = {
    "catch",
    "createFileRoute",
    "describe",
    "for",
    "if",
    "it",
    "map",
    "new",
    "reduce",
    "setTimeout",
    "switch",
    "test",
    "while",
}

CLASS_PATTERN = re.compile(
    r"\bclass\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"(?:\s+extends\s+[^{]+)?\s*\{",
)

FUNCTION_PATTERN = re.compile(
    r"\b"
    r"(?:export\s+)?"
    r"(?:default\s+)?"
    r"(?:async\s+)?"
    r"function\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s*\([^)]*\)\s*\{",
)

ARROW_FUNCTION_PATTERN = re.compile(
    r"\b"
    r"(?:export\s+)?"
    r"(?:default\s+)?"
    r"(?:const|let)\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s*=\s*"
    r"(?:async\s*)?"
    r"(?:"
    r"\([^)]*\)"
    r"|"
    r"[A-Za-z_$][A-Za-z0-9_$]*"
    r")"
    r"\s*=>\s*\{",
)

METHOD_PATTERN = re.compile(
    r"(?m)^[ \t]*"
    r"(?:(?:"
    r"public|private|protected|static|readonly|async"
    r")\s+)*"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s*\([^;{}]*\)"
    r"\s*(?::\s*[^={]+)?\s*\{",
)

NAMED_IMPORT_PATTERN = re.compile(
    r"\bimport\s*\{"
    r"(?P<body>[^}]+)"
    r"\}\s*from\s*"
    r"[\"'](?P<module>[^\"']+)[\"']",
    re.DOTALL,
)

DEFAULT_IMPORT_PATTERN = re.compile(
    r"\bimport\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s*from\s*"
    r"[\"'](?P<module>[^\"']+)[\"']",
)

NAMESPACE_IMPORT_PATTERN = re.compile(
    r"\bimport\s+\*\s+as\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s*from\s*"
    r"[\"'](?P<module>[^\"']+)[\"']",
)

CALL_PATTERN = re.compile(
    r"\b"
    r"(?P<expression>"
    r"[A-Za-z_$][A-Za-z0-9_$]*"
    r"(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*"
    r")"
    r"\s*\(",
)

CREATE_FILE_ROUTE_PATTERN = re.compile(
    r"createFileRoute\s*\(\s*"
    r"[\"'`](?P<path>[^\"'`]+)[\"'`]"
    r"\s*\)",
)

REACT_ROUTE_PATTERN = re.compile(
    r"<Route\b"
    r"[^>]*"
    r"\bpath="
    r"[\"'](?P<path>[^\"']+)[\"']"
    r"[^>]*>",
    re.DOTALL,
)

ROUTE_COMPONENT_PATTERN = re.compile(
    r"\bcomponent\s*:\s*"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)",
)

ROUTE_ELEMENT_PATTERN = re.compile(
    r"\belement\s*=\s*\{\s*<"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)",
)

FETCH_PATTERN = re.compile(
    r"\bfetch\s*\(\s*"
    r"[\"'`](?P<url>[^\"'`]+)[\"'`]"
    r"(?P<tail>.{0,350}?)"
    r"\)",
    re.DOTALL,
)

AXIOS_PATTERN = re.compile(
    r"\baxios\."
    r"(?P<method>"
    r"get|post|put|patch|delete|options|head"
    r")"
    r"\s*\(\s*"
    r"[\"'`](?P<url>[^\"'`]+)[\"'`]",
    re.IGNORECASE,
)

HTTP_CONFIG_METHOD_FIRST_PATTERN = re.compile(
    r"\bmethod\s*:\s*"
    r"[\"']"
    r"(?P<method>"
    r"GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD"
    r")"
    r"[\"']"
    r"(?P<middle>.{0,500}?)"
    r"\burl\s*:\s*"
    r"[\"'`](?P<url>[^\"'`]+)[\"'`]",
    re.DOTALL,
)

HTTP_CONFIG_URL_FIRST_PATTERN = re.compile(
    r"\burl\s*:\s*"
    r"[\"'`](?P<url>[^\"'`]+)[\"'`]"
    r"(?P<middle>.{0,500}?)"
    r"\bmethod\s*:\s*"
    r"[\"']"
    r"(?P<method>"
    r"GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD"
    r")"
    r"[\"']",
    re.DOTALL,
)

METHOD_OPTION_PATTERN = re.compile(
    r"\bmethod\s*:\s*"
    r"[\"']"
    r"(?P<method>"
    r"GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD"
    r")"
    r"[\"']",
    re.IGNORECASE,
)

ROUTE_PLACEHOLDER_PATTERN = re.compile(
    r"\{[^{}]+\}|:\w+|\$\{[^{}]+\}",
)


@dataclass(frozen=True, slots=True)
class FrontendSymbolEvidence:
    """
    前端代码中的函数、组件、类或者方法。
    """

    key: str
    name: str
    qualified_name: str
    kind: str

    file_path: str
    line_start: int
    line_end: int


@dataclass(frozen=True, slots=True)
class FrontendPageEvidence:
    """
    前端页面路由和页面组件的关系。
    """

    route_path: str
    component_symbol: str
    source_kind: str

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class FrontendCallEdgeEvidence:
    """
    两个前端函数之间的静态调用关系。
    """

    caller: str
    callee: str
    expression: str

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class FrontendHttpOperationEvidence:
    """
    前端或生成客户端中的 HTTP 操作。
    """

    symbol: str
    operation_name: str

    method: str
    path: str
    source_kind: str

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class FrontendPageOperationEvidence:
    """
    从页面组件到 HTTP 操作的一条调用路径。
    """

    route_path: str
    component_symbol: str

    call_chain: tuple[str, ...]

    operation: FrontendHttpOperationEvidence
    terminal_reason: str


@dataclass(frozen=True, slots=True)
class FullStackBusinessFlowEvidence:
    """
    前端页面到后端数据库操作的完整静态闭环。
    """

    frontend_route: str
    frontend_component: str
    frontend_call_chain: tuple[str, ...]

    http_method: str
    request_path: str
    client_operation: str

    backend_path: str | None
    backend_handler: str | None

    backend_match_kind: str
    backend_path_complete: bool | None

    backend_call_paths: tuple[
        tuple[str, ...],
        ...
    ]

    data_models: tuple[str, ...]
    database_operations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepositoryFrontendFlowAnalysis:
    """
    整个仓库的前端调用链和全栈业务闭环分析结果。
    """

    scanned_frontend_file_count: int
    skipped_large_file_count: int
    read_error_count: int
    analysis_truncated: bool

    symbols: tuple[
        FrontendSymbolEvidence,
        ...
    ]

    pages: tuple[
        FrontendPageEvidence,
        ...
    ]

    call_edges: tuple[
        FrontendCallEdgeEvidence,
        ...
    ]

    http_operations: tuple[
        FrontendHttpOperationEvidence,
        ...
    ]

    page_operations: tuple[
        FrontendPageOperationEvidence,
        ...
    ]

    full_stack_flows: tuple[
        FullStackBusinessFlowEvidence,
        ...
    ]

    def to_dict(self) -> dict[str, Any]:
        """
        转换成可写入 PostgreSQL JSONB 的字典。
        """

        return {
            "statistics": {
                "scanned_frontend_file_count": (
                    self.scanned_frontend_file_count
                ),
                "skipped_large_file_count": (
                    self.skipped_large_file_count
                ),
                "read_error_count": (
                    self.read_error_count
                ),
                "analysis_truncated": (
                    self.analysis_truncated
                ),
            },
            "symbols": [
                asdict(item)
                for item in self.symbols
            ],
            "pages": [
                asdict(item)
                for item in self.pages
            ],
            "call_edges": [
                asdict(item)
                for item in self.call_edges
            ],
            "http_operations": [
                asdict(item)
                for item in self.http_operations
            ],
            "page_operations": [
                asdict(item)
                for item in self.page_operations
            ],
            "full_stack_flows": [
                asdict(item)
                for item in self.full_stack_flows
            ],
        }


@dataclass(frozen=True, slots=True)
class _ImportBinding:
    """
    前端 import 的内部表示。
    """

    local_name: str
    imported_name: str
    module_specifier: str


@dataclass(frozen=True, slots=True)
class _SymbolSpan:
    """
    前端符号在源文件中的字符范围。
    """

    evidence: FrontendSymbolEvidence
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class _FrontendFile:
    """
    一个已经读取并初步分析的前端源文件。
    """

    path: Path
    relative_path: str
    source: str

    symbols: tuple[_SymbolSpan, ...]
    imports: tuple[_ImportBinding, ...]


def analyze_repository_frontend_flows(
    repository_root: Path | str,
    *,
    fastapi_router_analysis: FastApiRouterAnalysis,
    backend_flow_analysis: RepositoryBackendFlowAnalysis,
    max_frontend_files: int = (
        DEFAULT_MAX_FRONTEND_FILES
    ),
    max_frontend_file_bytes: int = (
        DEFAULT_MAX_FRONTEND_FILE_BYTES
    ),
    max_flow_depth: int = (
        DEFAULT_MAX_FRONTEND_FLOW_DEPTH
    ),
    max_flows_per_page: int = (
        DEFAULT_MAX_FLOWS_PER_PAGE
    ),
) -> RepositoryFrontendFlowAnalysis:
    """
    分析前端页面、API Client 和后端业务调用链。

    处理流程：

    1. 扫描 JavaScript 和 TypeScript 文件；
    2. 建立函数、组件和方法索引；
    3. 识别页面路由；
    4. 识别 HTTP 操作；
    5. 从页面组件遍历调用图；
    6. 将请求路径与 FastAPI 路由匹配；
    7. 拼接后端 Handler、模型和数据库操作。
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

    candidates = _find_frontend_files(root)

    analysis_truncated = (
        len(candidates) > max_frontend_files
    )

    candidates = candidates[
        :max_frontend_files
    ]

    files: list[_FrontendFile] = []

    skipped_large_file_count = 0
    read_error_count = 0

    for file_path in candidates:
        try:
            file_size = file_path.stat().st_size
        except OSError:
            read_error_count += 1
            continue

        if file_size > max_frontend_file_bytes:
            skipped_large_file_count += 1
            continue

        source = _read_frontend_source(
            file_path,
            max_bytes=max_frontend_file_bytes,
        )

        if source is None:
            read_error_count += 1
            continue

        relative_path = file_path.relative_to(
            root,
        ).as_posix()

        files.append(
            _FrontendFile(
                path=file_path,
                relative_path=relative_path,
                source=source,
                symbols=_discover_symbol_spans(
                    source=source,
                    relative_path=relative_path,
                ),
                imports=_parse_imports(source),
            ),
        )

    all_symbol_spans = [
        symbol
        for frontend_file in files
        for symbol in frontend_file.symbols
    ]

    symbol_by_key = {
        item.evidence.key: item.evidence
        for item in all_symbol_spans
    }

    symbols_by_name: dict[
        str,
        list[FrontendSymbolEvidence],
    ] = {}

    for item in all_symbol_spans:
        evidence = item.evidence

        symbols_by_name.setdefault(
            evidence.name,
            [],
        ).append(evidence)

        symbols_by_name.setdefault(
            evidence.qualified_name,
            [],
        ).append(evidence)

    pages: list[FrontendPageEvidence] = []

    operations: list[
        FrontendHttpOperationEvidence
    ] = []

    raw_calls: list[
        tuple[
            str,
            str,
            str,
            int,
            tuple[_ImportBinding, ...],
        ]
    ] = []

    for frontend_file in files:
        pages.extend(
            _extract_pages(frontend_file),
        )

        operations.extend(
            _extract_http_operations(
                frontend_file,
            ),
        )

        raw_calls.extend(
            _extract_raw_calls(
                frontend_file,
            ),
        )

    operation_by_name: dict[
        str,
        list[FrontendHttpOperationEvidence],
    ] = {}

    for operation in operations:
        operation_by_name.setdefault(
            operation.operation_name,
            [],
        ).append(operation)

        short_name = (
            operation.operation_name
            .split(".")[-1]
        )

        operation_by_name.setdefault(
            short_name,
            [],
        ).append(operation)

    call_edges: list[
        FrontendCallEdgeEvidence
    ] = []

    for (
        caller,
        expression,
        file_path,
        line,
        imports,
    ) in raw_calls:
        callee = _resolve_call_target(
            caller=caller,
            expression=expression,
            file_path=file_path,
            imports=imports,
            symbols_by_name=symbols_by_name,
            operation_by_name=operation_by_name,
        )

        if callee is None:
            continue

        if callee == caller:
            continue

        call_edges.append(
            FrontendCallEdgeEvidence(
                caller=caller,
                callee=callee,
                expression=expression,
                file_path=file_path,
                line=line,
            ),
        )

    page_operations = _build_page_operations(
        pages=pages,
        call_edges=call_edges,
        operations=operations,
        max_depth=max_flow_depth,
        max_flows_per_page=max_flows_per_page,
    )

    full_stack_flows = _build_full_stack_flows(
        page_operations=page_operations,
        fastapi_router_analysis=(
            fastapi_router_analysis
        ),
        backend_flow_analysis=(
            backend_flow_analysis
        ),
    )

    return RepositoryFrontendFlowAnalysis(
        scanned_frontend_file_count=len(
            files,
        ),
        skipped_large_file_count=(
            skipped_large_file_count
        ),
        read_error_count=read_error_count,
        analysis_truncated=analysis_truncated,
        symbols=tuple(
            sorted(
                symbol_by_key.values(),
                key=lambda item: (
                    item.file_path.lower(),
                    item.line_start,
                    item.qualified_name.lower(),
                ),
            ),
        ),
        pages=tuple(
            _deduplicate_dataclasses(
                sorted(
                    pages,
                    key=lambda item: (
                        item.route_path.lower(),
                        item.file_path.lower(),
                        item.line,
                    ),
                ),
            ),
        ),
        call_edges=tuple(
            _deduplicate_dataclasses(
                sorted(
                    call_edges,
                    key=lambda item: (
                        item.caller.lower(),
                        item.file_path.lower(),
                        item.line,
                    ),
                ),
            ),
        ),
        http_operations=tuple(
            _deduplicate_dataclasses(
                sorted(
                    operations,
                    key=lambda item: (
                        item.path.lower(),
                        item.method,
                        item.file_path.lower(),
                        item.line,
                    ),
                ),
            ),
        ),
        page_operations=tuple(
            page_operations,
        ),
        full_stack_flows=tuple(
            full_stack_flows,
        ),
    )


def _discover_symbol_spans(
    *,
    source: str,
    relative_path: str,
) -> tuple[_SymbolSpan, ...]:
    """
    识别文件中的函数、组件、类和类方法。

    字符范围用于判断一个 HTTP 请求属于哪个函数。
    """

    module_evidence = FrontendSymbolEvidence(
        key=f"{relative_path}:<module>",
        name="<module>",
        qualified_name="<module>",
        kind="module",
        file_path=relative_path,
        line_start=1,
        line_end=source.count("\n") + 1,
    )

    spans: list[_SymbolSpan] = [
        _SymbolSpan(
            evidence=module_evidence,
            start_offset=0,
            end_offset=len(source),
        ),
    ]

    class_spans: list[
        tuple[str, int, int]
    ] = []

    for match in CLASS_PATTERN.finditer(source):
        opening_brace = source.find(
            "{",
            match.start(),
            match.end(),
        )

        if opening_brace < 0:
            continue

        closing_brace = _find_matching_brace(
            source,
            opening_brace,
        )

        if closing_brace is None:
            continue

        class_name = match.group("name")

        class_spans.append(
            (
                class_name,
                opening_brace,
                closing_brace,
            ),
        )

        spans.append(
            _make_symbol_span(
                relative_path=relative_path,
                name=class_name,
                qualified_name=class_name,
                kind="class",
                source=source,
                start_offset=match.start(),
                end_offset=closing_brace + 1,
            ),
        )

    for pattern in (
        FUNCTION_PATTERN,
        ARROW_FUNCTION_PATTERN,
    ):
        for match in pattern.finditer(source):
            opening_brace = source.find(
                "{",
                match.start(),
                match.end(),
            )

            if opening_brace < 0:
                continue

            closing_brace = _find_matching_brace(
                source,
                opening_brace,
            )

            if closing_brace is None:
                continue

            name = match.group("name")

            spans.append(
                _make_symbol_span(
                    relative_path=relative_path,
                    name=name,
                    qualified_name=name,
                    kind="function",
                    source=source,
                    start_offset=match.start(),
                    end_offset=closing_brace + 1,
                ),
            )

    for (
        class_name,
        class_start,
        class_end,
    ) in class_spans:
        class_source = source[
            class_start:class_end
        ]

        for match in METHOD_PATTERN.finditer(
            class_source,
        ):
            method_name = match.group("name")

            if method_name in {
                "catch",
                "constructor",
                "for",
                "if",
                "switch",
                "while",
            }:
                continue

            absolute_start = (
                class_start + match.start()
            )

            opening_brace = source.find(
                "{",
                absolute_start,
                class_start + match.end(),
            )

            if opening_brace < 0:
                continue

            closing_brace = _find_matching_brace(
                source,
                opening_brace,
            )

            if closing_brace is None:
                continue

            if closing_brace > class_end:
                continue

            spans.append(
                _make_symbol_span(
                    relative_path=relative_path,
                    name=method_name,
                    qualified_name=(
                        f"{class_name}."
                        f"{method_name}"
                    ),
                    kind="method",
                    source=source,
                    start_offset=absolute_start,
                    end_offset=closing_brace + 1,
                ),
            )

    unique: dict[
        tuple[str, int, int],
        _SymbolSpan,
    ] = {}

    for span in spans:
        key = (
            span.evidence.qualified_name,
            span.start_offset,
            span.end_offset,
        )

        unique[key] = span

    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                item.start_offset,
                item.end_offset
                - item.start_offset,
            ),
        ),
    )


def _make_symbol_span(
    *,
    relative_path: str,
    name: str,
    qualified_name: str,
    kind: str,
    source: str,
    start_offset: int,
    end_offset: int,
) -> _SymbolSpan:
    """
    创建一个带文件位置的前端符号。
    """

    return _SymbolSpan(
        evidence=FrontendSymbolEvidence(
            key=(
                f"{relative_path}:"
                f"{qualified_name}"
            ),
            name=name,
            qualified_name=qualified_name,
            kind=kind,
            file_path=relative_path,
            line_start=_line_number(
                source,
                start_offset,
            ),
            line_end=_line_number(
                source,
                max(
                    end_offset - 1,
                    start_offset,
                ),
            ),
        ),
        start_offset=start_offset,
        end_offset=end_offset,
    )


def _parse_imports(
    source: str,
) -> tuple[_ImportBinding, ...]:
    """
    解析 ES Module import。

    支持：

    import { createUser } from "../client/users"
    import { createUser as submit } from "../client/users"
    import UsersService from "../client/users"
    import * as usersApi from "../client/users"
    """

    results: list[_ImportBinding] = []

    for match in NAMED_IMPORT_PATTERN.finditer(
        source,
    ):
        module_specifier = match.group(
            "module",
        )

        for raw_part in match.group(
            "body",
        ).split(","):
            part = raw_part.strip()

            if not part:
                continue

            alias_parts = re.split(
                r"\s+as\s+",
                part,
                maxsplit=1,
            )

            imported_name = (
                alias_parts[0].strip()
            )

            local_name = (
                alias_parts[1].strip()
                if len(alias_parts) == 2
                else imported_name
            )

            if not imported_name:
                continue

            if not local_name:
                continue

            results.append(
                _ImportBinding(
                    local_name=local_name,
                    imported_name=(
                        imported_name
                    ),
                    module_specifier=(
                        module_specifier
                    ),
                ),
            )

    for pattern in (
        DEFAULT_IMPORT_PATTERN,
        NAMESPACE_IMPORT_PATTERN,
    ):
        for match in pattern.finditer(source):
            name = match.group("name")

            results.append(
                _ImportBinding(
                    local_name=name,
                    imported_name=name,
                    module_specifier=(
                        match.group("module")
                    ),
                ),
            )

    return tuple(
        _deduplicate_dataclasses(results),
    )


def _extract_pages(
    frontend_file: _FrontendFile,
) -> list[FrontendPageEvidence]:
    """
    识别 TanStack Router 和 React Router 页面。
    """

    results: list[
        FrontendPageEvidence
    ] = []

    for match in CREATE_FILE_ROUTE_PATTERN.finditer(
        frontend_file.source,
    ):
        nearby_source = frontend_file.source[
            match.end():
            match.end() + 1_000
        ]

        component_match = (
            ROUTE_COMPONENT_PATTERN.search(
                nearby_source,
            )
        )

        component_name = (
            component_match.group("name")
            if component_match
            else None
        )

        component_symbol = (
            _find_symbol_key_by_name(
                frontend_file.symbols,
                component_name,
            )
        )

        if component_symbol is None:
            component_symbol = _owner_symbol(
                frontend_file.symbols,
                match.start(),
            ).evidence.key

        results.append(
            FrontendPageEvidence(
                route_path=match.group("path"),
                component_symbol=(
                    component_symbol
                ),
                source_kind=(
                    "tanstack_file_route"
                ),
                file_path=(
                    frontend_file.relative_path
                ),
                line=_line_number(
                    frontend_file.source,
                    match.start(),
                ),
            ),
        )

    for match in REACT_ROUTE_PATTERN.finditer(
        frontend_file.source,
    ):
        component_match = (
            ROUTE_ELEMENT_PATTERN.search(
                match.group(0),
            )
        )

        component_name = (
            component_match.group("name")
            if component_match
            else None
        )

        component_symbol = (
            _find_symbol_key_by_name(
                frontend_file.symbols,
                component_name,
            )
        )

        if component_symbol is None:
            component_symbol = _owner_symbol(
                frontend_file.symbols,
                match.start(),
            ).evidence.key

        results.append(
            FrontendPageEvidence(
                route_path=match.group("path"),
                component_symbol=(
                    component_symbol
                ),
                source_kind="react_router",
                file_path=(
                    frontend_file.relative_path
                ),
                line=_line_number(
                    frontend_file.source,
                    match.start(),
                ),
            ),
        )

    return results


def _extract_http_operations(
    frontend_file: _FrontendFile,
) -> list[FrontendHttpOperationEvidence]:
    """
    识别直接请求和生成客户端配置。

    支持：

    fetch(...)
    axios.get(...)
    axios.post(...)
    request({method: "GET", url: "/users"})
    """

    results: list[
        FrontendHttpOperationEvidence
    ] = []

    for match in FETCH_PATTERN.finditer(
        frontend_file.source,
    ):
        method_match = (
            METHOD_OPTION_PATTERN.search(
                match.group("tail"),
            )
        )

        method = (
            method_match.group(
                "method",
            ).upper()
            if method_match
            else "GET"
        )

        owner = _owner_symbol(
            frontend_file.symbols,
            match.start(),
        )

        results.append(
            _build_http_operation(
                owner=owner,
                method=method,
                path=match.group("url"),
                source_kind="fetch",
                frontend_file=frontend_file,
                offset=match.start(),
            ),
        )

    for match in AXIOS_PATTERN.finditer(
        frontend_file.source,
    ):
        owner = _owner_symbol(
            frontend_file.symbols,
            match.start(),
        )

        results.append(
            _build_http_operation(
                owner=owner,
                method=match.group(
                    "method",
                ).upper(),
                path=match.group("url"),
                source_kind="axios",
                frontend_file=frontend_file,
                offset=match.start(),
            ),
        )

    for pattern in (
        HTTP_CONFIG_METHOD_FIRST_PATTERN,
        HTTP_CONFIG_URL_FIRST_PATTERN,
    ):
        for match in pattern.finditer(
            frontend_file.source,
        ):
            owner = _owner_symbol(
                frontend_file.symbols,
                match.start(),
            )

            results.append(
                _build_http_operation(
                    owner=owner,
                    method=match.group(
                        "method",
                    ).upper(),
                    path=match.group("url"),
                    source_kind=(
                        "generated_client_config"
                    ),
                    frontend_file=(
                        frontend_file
                    ),
                    offset=match.start(),
                ),
            )

    return _deduplicate_dataclasses(
        results,
    )


def _build_http_operation(
    *,
    owner: _SymbolSpan,
    method: str,
    path: str,
    source_kind: str,
    frontend_file: _FrontendFile,
    offset: int,
) -> FrontendHttpOperationEvidence:
    """
    将 HTTP 请求归属到所在函数或方法。
    """

    operation_name = (
        owner.evidence.qualified_name
    )

    if operation_name == "<module>":
        operation_name = (
            f"{PurePosixPath(frontend_file.relative_path).stem}"
            f"@{_line_number(frontend_file.source, offset)}"
        )

    return FrontendHttpOperationEvidence(
        symbol=owner.evidence.key,
        operation_name=operation_name,
        method=method,
        path=path,
        source_kind=source_kind,
        file_path=frontend_file.relative_path,
        line=_line_number(
            frontend_file.source,
            offset,
        ),
    )


def _extract_raw_calls(
    frontend_file: _FrontendFile,
) -> list[
    tuple[
        str,
        str,
        str,
        int,
        tuple[_ImportBinding, ...],
    ]
]:
    """
    收集前端函数调用表达式。

    这里只收集调用，稍后再统一解析目标函数。
    """

    results: list[
        tuple[
            str,
            str,
            str,
            int,
            tuple[_ImportBinding, ...],
        ]
    ] = []

    for match in CALL_PATTERN.finditer(
        frontend_file.source,
    ):
        expression = match.group(
            "expression",
        )

        short_name = expression.split(
            ".",
        )[-1]

        if short_name in CALL_EXCLUSIONS:
            continue

        if _looks_like_declaration(
            frontend_file.source,
            match.start(),
        ):
            continue

        caller = _owner_symbol(
            frontend_file.symbols,
            match.start(),
        ).evidence.key

        results.append(
            (
                caller,
                expression,
                frontend_file.relative_path,
                _line_number(
                    frontend_file.source,
                    match.start(),
                ),
                frontend_file.imports,
            ),
        )

    return results


def _resolve_call_target(
    *,
    caller: str,
    expression: str,
    file_path: str,
    imports: tuple[_ImportBinding, ...],
    symbols_by_name: dict[
        str,
        list[FrontendSymbolEvidence],
    ],
    operation_by_name: dict[
        str,
        list[
            FrontendHttpOperationEvidence
        ],
    ],
) -> str | None:
    """
    将调用表达式解析到仓库内部函数或 API 操作。

    解析顺序：

    1. API Client 操作；
    2. 当前文件函数；
    3. import 指向的函数；
    4. 全仓库唯一同名函数。
    """

    expression_parts = expression.split(".")

    first_name = expression_parts[0]
    short_name = expression_parts[-1]

    binding = next(
        (
            item
            for item in imports
            if item.local_name == first_name
        ),
        None,
    )

    operation_candidates = (
        operation_by_name.get(
            expression,
            [],
        )
        or operation_by_name.get(
            short_name,
            [],
        )
    )

    if (
        len(operation_candidates) > 1
        and binding is not None
    ):
        operation_candidates = [
            item
            for item in operation_candidates
            if _module_specifier_matches_file(
                binding.module_specifier,
                item.file_path,
            )
        ]

    selected_operation = (
        _select_operation_candidate(
            operation_candidates,
            file_path=file_path,
        )
    )

    if selected_operation is not None:
        return selected_operation.symbol

    same_file_candidates = [
        item
        for item in symbols_by_name.get(
            short_name,
            [],
        )
        if item.file_path == file_path
    ]

    if len(same_file_candidates) == 1:
        return same_file_candidates[0].key

    if binding is not None:
        imported_name = (
            short_name
            if "." in expression
            else binding.imported_name
        )

        imported_candidates = (
            symbols_by_name.get(
                imported_name,
                [],
            )
        )

        matching_candidates = [
            item
            for item in imported_candidates
            if _module_specifier_matches_file(
                binding.module_specifier,
                item.file_path,
            )
        ]

        if len(matching_candidates) == 1:
            return matching_candidates[0].key

        if len(imported_candidates) == 1:
            return imported_candidates[0].key

    global_candidates = (
        symbols_by_name.get(
            short_name,
            [],
        )
    )

    if len(global_candidates) == 1:
        return global_candidates[0].key

    return None


def _select_operation_candidate(
    candidates: list[
        FrontendHttpOperationEvidence
    ],
    *,
    file_path: str,
) -> FrontendHttpOperationEvidence | None:
    """
    从多个同名 API 操作中选择唯一目标。
    """

    if len(candidates) == 1:
        return candidates[0]

    same_file = [
        item
        for item in candidates
        if item.file_path == file_path
    ]

    if len(same_file) == 1:
        return same_file[0]

    return None


def _build_page_operations(
    *,
    pages: list[FrontendPageEvidence],
    call_edges: list[
        FrontendCallEdgeEvidence
    ],
    operations: list[
        FrontendHttpOperationEvidence
    ],
    max_depth: int,
    max_flows_per_page: int,
) -> list[FrontendPageOperationEvidence]:
    """
    从页面组件开始遍历前端调用图，直到遇到 HTTP 操作。
    """

    outgoing: dict[
        str,
        list[str],
    ] = {}

    for edge in call_edges:
        outgoing.setdefault(
            edge.caller,
            [],
        ).append(edge.callee)

    operations_by_symbol: dict[
        str,
        list[
            FrontendHttpOperationEvidence
        ],
    ] = {}

    for operation in operations:
        operations_by_symbol.setdefault(
            operation.symbol,
            [],
        ).append(operation)

    results: list[
        FrontendPageOperationEvidence
    ] = []

    for page in pages:
        page_result_count = 0

        queue: list[
            tuple[
                str,
                tuple[str, ...],
            ]
        ] = [
            (
                page.component_symbol,
                (page.component_symbol,),
            ),
        ]

        visited: set[str] = set()

        while queue:
            if (
                page_result_count
                >= max_flows_per_page
            ):
                break

            current_symbol, chain = (
                queue.pop(0)
            )

            if current_symbol in visited:
                continue

            visited.add(current_symbol)

            for operation in (
                operations_by_symbol.get(
                    current_symbol,
                    [],
                )
            ):
                results.append(
                    FrontendPageOperationEvidence(
                        route_path=(
                            page.route_path
                        ),
                        component_symbol=(
                            page.component_symbol
                        ),
                        call_chain=chain,
                        operation=operation,
                        terminal_reason=(
                            "http_operation_reached"
                        ),
                    ),
                )

                page_result_count += 1

            if len(chain) >= max_depth:
                continue

            for callee in outgoing.get(
                current_symbol,
                [],
            ):
                if callee in visited:
                    continue

                queue.append(
                    (
                        callee,
                        (
                            *chain,
                            callee,
                        ),
                    ),
                )

    return _deduplicate_dataclasses(
        sorted(
            results,
            key=lambda item: (
                item.route_path.lower(),
                item.operation.method,
                item.operation.path.lower(),
                item.operation.file_path.lower(),
                item.operation.line,
            ),
        ),
    )


def _build_full_stack_flows(
    *,
    page_operations: list[
        FrontendPageOperationEvidence
    ],
    fastapi_router_analysis: (
        FastApiRouterAnalysis
    ),
    backend_flow_analysis: (
        RepositoryBackendFlowAnalysis
    ),
) -> list[FullStackBusinessFlowEvidence]:
    """
    将前端请求与 FastAPI 路由及后端调用链拼接。
    """

    results: list[
        FullStackBusinessFlowEvidence
    ] = []

    for page_operation in page_operations:
        operation = page_operation.operation

        (
            backend_route,
            match_kind,
        ) = _match_backend_route(
            method=operation.method,
            frontend_path=operation.path,
            routes=(
                fastapi_router_analysis.routes
            ),
        )

        backend_flow = None

        if backend_route is not None:
            backend_flow = next(
                (
                    item
                    for item
                    in backend_flow_analysis.route_flows
                    if (
                        item.method
                        == backend_route.method
                        and _normalize_url_path(
                            item.path,
                        )
                        == _normalize_url_path(
                            backend_route.path,
                        )
                    )
                ),
                None,
            )

        backend_call_paths: tuple[
            tuple[str, ...],
            ...
        ] = ()

        data_models: tuple[str, ...] = ()

        database_operations: tuple[
            str,
            ...
        ] = ()

        if backend_flow is not None:
            backend_call_paths = tuple(
                tuple(
                    step.symbol
                    for step
                    in call_path.steps
                )
                for call_path
                in backend_flow.call_paths
            )

            data_models = tuple(
                sorted(
                    {
                        model_usage.model
                        for model_usage
                        in backend_flow.model_usages
                    },
                    key=str.lower,
                ),
            )

            database_operations = tuple(
                sorted(
                    {
                        (
                            f"{operation_item.operation_kind}:"
                            f"{operation_item.expression}"
                        )
                        for operation_item
                        in backend_flow.database_operations
                    },
                    key=str.lower,
                ),
            )

        results.append(
            FullStackBusinessFlowEvidence(
                frontend_route=(
                    page_operation.route_path
                ),
                frontend_component=(
                    page_operation.component_symbol
                ),
                frontend_call_chain=(
                    page_operation.call_chain
                ),
                http_method=operation.method,
                request_path=operation.path,
                client_operation=(
                    operation.operation_name
                ),
                backend_path=(
                    backend_route.path
                    if backend_route
                    else None
                ),
                backend_handler=(
                    backend_route.handler
                    if backend_route
                    else None
                ),
                backend_match_kind=match_kind,
                backend_path_complete=(
                    backend_route.path_complete
                    if backend_route
                    else None
                ),
                backend_call_paths=(
                    backend_call_paths
                ),
                data_models=data_models,
                database_operations=(
                    database_operations
                ),
            ),
        )

    return _deduplicate_dataclasses(
        sorted(
            results,
            key=lambda item: (
                item.frontend_route.lower(),
                item.http_method,
                item.request_path.lower(),
            ),
        ),
    )


def _match_backend_route(
    *,
    method: str,
    frontend_path: str,
    routes: tuple[
        FastApiResolvedRouteEvidence,
        ...
    ],
) -> tuple[
    FastApiResolvedRouteEvidence | None,
    str,
]:
    """
    按 HTTP 方法和标准化路径匹配后端路由。

    exact：
    前后端路径完全匹配。

    suffix：
    前端缺少 /api/v1 等统一前缀，但剩余路径唯一匹配。

    unmatched：
    无法唯一匹配。
    """

    method_candidates = [
        route
        for route in routes
        if route.method == method
    ]

    exact_candidates = [
        route
        for route in method_candidates
        if _paths_match(
            frontend_path,
            route.path,
        )
    ]

    if len(exact_candidates) == 1:
        return (
            exact_candidates[0],
            "exact",
        )

    suffix_candidates = [
        route
        for route in method_candidates
        if _paths_suffix_match(
            frontend_path,
            route.path,
        )
    ]

    if len(suffix_candidates) == 1:
        return (
            suffix_candidates[0],
            "suffix",
        )

    return None, "unmatched"


def _paths_match(
    left: str,
    right: str,
) -> bool:
    left_parts = _path_parts(left)
    right_parts = _path_parts(right)

    if len(left_parts) != len(right_parts):
        return False

    return all(
        (
            left_part == right_part
            or left_part == "{parameter}"
            or right_part == "{parameter}"
        )
        for left_part, right_part
        in zip(
            left_parts,
            right_parts,
            strict=True,
        )
    )


def _paths_suffix_match(
    left: str,
    right: str,
) -> bool:
    left_parts = _path_parts(left)
    right_parts = _path_parts(right)

    shorter_length = min(
        len(left_parts),
        len(right_parts),
    )

    if shorter_length < 2:
        return False

    left_suffix = left_parts[
        -shorter_length:
    ]

    right_suffix = right_parts[
        -shorter_length:
    ]

    return all(
        (
            left_part == right_part
            or left_part == "{parameter}"
            or right_part == "{parameter}"
        )
        for left_part, right_part
        in zip(
            left_suffix,
            right_suffix,
            strict=True,
        )
    )


def _path_parts(
    value: str,
) -> list[str]:
    return [
        part
        for part
        in _normalize_url_path(
            value,
        ).split("/")
        if part
    ]


def _normalize_url_path(
    value: str,
) -> str:
    """
    将前后端 URL 转成可比较路径。

    示例：

    /users/${userId}
    /users/{user_id}
    /users/:userId

    都转换为：

    /users/{parameter}
    """

    normalized = value.strip()

    if "://" in normalized:
        normalized = urlsplit(
            normalized,
        ).path

    normalized = normalized.split(
        "?",
        maxsplit=1,
    )[0]

    normalized = normalized.split(
        "#",
        maxsplit=1,
    )[0]

    normalized = (
        ROUTE_PLACEHOLDER_PATTERN.sub(
            "{parameter}",
            normalized,
        )
    )

    normalized = re.sub(
        r"/+",
        "/",
        normalized,
    )

    return "/" + normalized.strip("/")


def _owner_symbol(
    symbols: tuple[_SymbolSpan, ...],
    offset: int,
) -> _SymbolSpan:
    """
    选择包含当前代码位置的最内层函数或方法。
    """

    candidates = [
        item
        for item in symbols
        if (
            item.start_offset
            <= offset
            < item.end_offset
        )
    ]

    return min(
        candidates,
        key=lambda item: (
            item.end_offset
            - item.start_offset
        ),
    )


def _find_symbol_key_by_name(
    symbols: tuple[_SymbolSpan, ...],
    name: str | None,
) -> str | None:
    if not name:
        return None

    candidates = [
        item.evidence.key
        for item in symbols
        if (
            item.evidence.name == name
            or item.evidence.qualified_name
            == name
        )
    ]

    if len(candidates) == 1:
        return candidates[0]

    return None


def _module_specifier_matches_file(
    module_specifier: str,
    file_path: str,
) -> bool:
    """
    判断 import 路径是否可能指向某个文件。

    支持基础形式：

    ../client/users
    @/client/users
    src/client/users
    """

    module = module_specifier.replace(
        "\\",
        "/",
    )

    if module.startswith("@/"):
        module = module[2:]

    while module.startswith("./"):
        module = module[2:]

    while module.startswith("../"):
        module = module[3:]

    candidate = file_path.replace(
        "\\",
        "/",
    )

    for suffix in FRONTEND_FILE_SUFFIXES:
        if candidate.endswith(suffix):
            candidate = candidate[
                :-len(suffix)
            ]
            break

    return (
        candidate.endswith(module)
        or candidate.endswith(
            f"/{module}",
        )
    )


def _looks_like_declaration(
    source: str,
    offset: int,
) -> bool:
    """
    避免把 function foo() 的 foo() 识别成函数调用。
    """

    prefix = source[
        max(
            0,
            offset - 60,
        ):
        offset
    ]

    return bool(
        re.search(
            r"\bfunction\s+$",
            prefix,
        ),
    )


def _find_matching_brace(
    source: str,
    opening_index: int,
) -> int | None:
    """
    查找 JavaScript/TypeScript 代码块的结束花括号。

    会跳过字符串、模板字符串和注释中的花括号。
    """

    if opening_index < 0:
        return None

    if source[opening_index] != "{":
        return None

    depth = 0
    index = opening_index

    quote: str | None = None
    escaped = False

    line_comment = False
    block_comment = False

    while index < len(source):
        character = source[index]

        next_character = (
            source[index + 1]
            if index + 1 < len(source)
            else ""
        )

        if line_comment:
            if character == "\n":
                line_comment = False

            index += 1
            continue

        if block_comment:
            if (
                character == "*"
                and next_character == "/"
            ):
                block_comment = False
                index += 2
                continue

            index += 1
            continue

        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None

            index += 1
            continue

        if (
            character == "/"
            and next_character == "/"
        ):
            line_comment = True
            index += 2
            continue

        if (
            character == "/"
            and next_character == "*"
        ):
            block_comment = True
            index += 2
            continue

        if character in {
            "'",
            '"',
            "`",
        }:
            quote = character
            index += 1
            continue

        if character == "{":
            depth += 1

        elif character == "}":
            depth -= 1

            if depth == 0:
                return index

        index += 1

    return None


def _find_frontend_files(
    root: Path,
) -> list[Path]:
    """
    查找 JavaScript 和 TypeScript 文件。
    """

    results: list[Path] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if (
            path.suffix.lower()
            not in FRONTEND_FILE_SUFFIXES
        ):
            continue

        relative_parts = path.relative_to(
            root,
        ).parts

        if any(
            part.lower()
            in IGNORED_DIRECTORIES_LOWER
            for part in relative_parts[:-1]
        ):
            continue

        results.append(path)

    return sorted(
        results,
        key=lambda item: (
            item.relative_to(root)
            .as_posix()
            .lower()
        ),
    )


def _read_frontend_source(
    file_path: Path,
    *,
    max_bytes: int,
) -> str | None:
    try:
        content = file_path.read_bytes()
    except OSError:
        return None

    if len(content) > max_bytes:
        return None

    if b"\x00" in content:
        return None

    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode(
            "utf-8",
            errors="replace",
        )


def _line_number(
    source: str,
    offset: int,
) -> int:
    return source.count(
        "\n",
        0,
        offset,
    ) + 1


def _deduplicate_dataclasses(
    items: list[Any],
) -> list[Any]:
    """
    在保持原顺序的情况下删除重复证据。
    """

    results: list[Any] = []
    seen: set[str] = set()

    for item in items:
        key = repr(item)

        if key in seen:
            continue

        seen.add(key)
        results.append(item)

    return results