from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from app.services.repository_structure_scanner import (
    IGNORED_DIRECTORY_NAMES,
)


DEFAULT_MAX_CODE_FILES = 1024
DEFAULT_MAX_CODE_FILE_BYTES = 1024 * 1024

PYTHON_SUFFIX = ".py"

JAVASCRIPT_TYPESCRIPT_SUFFIXES = {
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
}

HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
}

_ROUTE_PLACEHOLDER_PATTERN = re.compile(
    r"\{[^{}]+\}|:\w+|\$\{[^{}]+\}",
)

_JS_FUNCTION_PATTERN = re.compile(
    r"""
    (?:
        export\s+
    )?
    (?:
        default\s+
    )?
    (?:
        async\s+
    )?
    function\s+
    (?P<name>[A-Za-z_$][A-Za-z0-9_$]*)
    """,
    re.VERBOSE,
)

_JS_ARROW_FUNCTION_PATTERN = re.compile(
    r"""
    (?:
        export\s+
    )?
    const\s+
    (?P<name>[A-Za-z_$][A-Za-z0-9_$]*)
    \s*=\s*
    (?:
        async\s*
    )?
    (?:
        \([^)]*\)
        |
        [A-Za-z_$][A-Za-z0-9_$]*
    )
    \s*=>    
    """,
    re.VERBOSE,
)

_CREATE_FILE_ROUTE_PATTERN = re.compile(
    r"""
    createFileRoute
    \(
        \s*
        ["'`]
        (?P<path>[^"'`]+)
        ["'`]
    """,
    re.VERBOSE,
)

_REACT_ROUTE_PATH_PATTERN = re.compile(
    r"""
    <Route
    [^>]*?
    \bpath=
    ["']
    (?P<path>[^"']+)
    ["']
    """,
    re.VERBOSE,
)

_FETCH_PATTERN = re.compile(
    r"""
    fetch
    \(
        \s*
        ["'`]
        (?P<url>[^"'`]+)
        ["'`]
    """,
    re.VERBOSE,
)

_AXIOS_PATTERN = re.compile(
    r"""
    axios
    \.
    (?P<method>get|post|put|patch|delete)
    \(
        \s*
        ["'`]
        (?P<url>[^"'`]+)
        ["'`]
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class CodeSymbolEvidence:
    """从源代码中确定性识别出的符号。"""

    name: str
    qualified_name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int


@dataclass(frozen=True, slots=True)
class BackendRouteEvidence:
    """后端 HTTP 路由定义。"""

    method: str
    path: str
    handler: str
    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class FrontendRouteEvidence:
    """前端页面路由定义。"""

    path: str
    source_kind: str
    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class FrontendApiCallEvidence:
    """前端发出的 HTTP 请求。"""

    method: str
    url: str
    source_kind: str
    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class CallEdgeEvidence:
    """Python 函数之间的静态调用边。"""

    caller: str
    callee: str
    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class DataModelEvidence:
    """SQLModel、Pydantic 等数据模型。"""

    name: str
    model_kind: str
    fields: tuple[str, ...]
    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class BusinessFlowEvidence:
    """
    通过 URL 和 HTTP 方法匹配得到的前后端可能闭环。

    这里只表示“可能关联”，不表示已经完成运行时验证。
    """

    frontend_method: str
    frontend_url: str
    frontend_file_path: str
    frontend_line: int

    backend_method: str
    backend_path: str
    backend_handler: str
    backend_file_path: str
    backend_line: int


@dataclass(frozen=True, slots=True)
class RepositoryCodeAnalysis:
    """整个仓库的确定性代码结构分析结果。"""

    scanned_code_file_count: int
    skipped_large_code_file_count: int
    parse_error_count: int
    analysis_truncated: bool

    symbols: tuple[CodeSymbolEvidence, ...]
    backend_routes: tuple[BackendRouteEvidence, ...]
    frontend_routes: tuple[FrontendRouteEvidence, ...]
    frontend_api_calls: tuple[
        FrontendApiCallEvidence,
        ...
    ]
    call_edges: tuple[CallEdgeEvidence, ...]
    data_models: tuple[DataModelEvidence, ...]
    business_flows: tuple[BusinessFlowEvidence, ...]

    def to_dict(self) -> dict[str, Any]:
        """转换为可以写入 PostgreSQL JSONB 的结构。"""

        return {
            "statistics": {
                "scanned_code_file_count": (
                    self.scanned_code_file_count
                ),
                "skipped_large_code_file_count": (
                    self.skipped_large_code_file_count
                ),
                "parse_error_count": (
                    self.parse_error_count
                ),
                "analysis_truncated": (
                    self.analysis_truncated
                ),
            },
            "symbols": [
                _dataclass_to_dict(item)
                for item in self.symbols
            ],
            "backend_routes": [
                _dataclass_to_dict(item)
                for item in self.backend_routes
            ],
            "frontend_routes": [
                _dataclass_to_dict(item)
                for item in self.frontend_routes
            ],
            "frontend_api_calls": [
                _dataclass_to_dict(item)
                for item in self.frontend_api_calls
            ],
            "call_edges": [
                _dataclass_to_dict(item)
                for item in self.call_edges
            ],
            "data_models": [
                _dataclass_to_dict(item)
                for item in self.data_models
            ],
            "business_flows": [
                _dataclass_to_dict(item)
                for item in self.business_flows
            ],
        }


def analyze_repository_code(
    repository_root: Path | str,
    *,
    max_code_files: int = DEFAULT_MAX_CODE_FILES,
    max_code_file_bytes: int = (
        DEFAULT_MAX_CODE_FILE_BYTES
    ),
) -> RepositoryCodeAnalysis:
    """
    对仓库中的 Python、JavaScript 和 TypeScript
    文件执行确定性静态分析。

    不导入、不执行、不编译被分析仓库中的代码。
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

    candidate_files = _find_candidate_code_files(
        root,
    )

    analysis_truncated = (
        len(candidate_files) > max_code_files
    )

    candidate_files = candidate_files[
        :max_code_files
    ]

    symbols: list[CodeSymbolEvidence] = []
    backend_routes: list[
        BackendRouteEvidence
    ] = []
    frontend_routes: list[
        FrontendRouteEvidence
    ] = []
    frontend_api_calls: list[
        FrontendApiCallEvidence
    ] = []
    call_edges: list[CallEdgeEvidence] = []
    data_models: list[DataModelEvidence] = []

    skipped_large_code_file_count = 0
    parse_error_count = 0
    scanned_code_file_count = 0

    for file_path in candidate_files:
        try:
            file_size = file_path.stat().st_size
        except OSError:
            parse_error_count += 1
            continue

        if file_size > max_code_file_bytes:
            skipped_large_code_file_count += 1
            continue

        source = _read_source_file(
            file_path,
            max_bytes=max_code_file_bytes,
        )

        if source is None:
            parse_error_count += 1
            continue

        relative_path = file_path.relative_to(
            root,
        ).as_posix()

        suffix = file_path.suffix.lower()

        if suffix == PYTHON_SUFFIX:
            try:
                python_result = _analyze_python_file(
                    source=source,
                    relative_path=relative_path,
                )
            except SyntaxError:
                parse_error_count += 1
                continue

            symbols.extend(
                python_result.symbols,
            )
            backend_routes.extend(
                python_result.backend_routes,
            )
            call_edges.extend(
                python_result.call_edges,
            )
            data_models.extend(
                python_result.data_models,
            )

        elif (
            suffix
            in JAVASCRIPT_TYPESCRIPT_SUFFIXES
        ):
            javascript_result = (
                _analyze_javascript_typescript_file(
                    source=source,
                    relative_path=relative_path,
                )
            )

            symbols.extend(
                javascript_result.symbols,
            )
            frontend_routes.extend(
                javascript_result.frontend_routes,
            )
            frontend_api_calls.extend(
                javascript_result.api_calls,
            )

        scanned_code_file_count += 1

    business_flows = _match_business_flows(
        frontend_api_calls=frontend_api_calls,
        backend_routes=backend_routes,
    )

    return RepositoryCodeAnalysis(
        scanned_code_file_count=(
            scanned_code_file_count
        ),
        skipped_large_code_file_count=(
            skipped_large_code_file_count
        ),
        parse_error_count=parse_error_count,
        analysis_truncated=analysis_truncated,
        symbols=tuple(
            sorted(
                symbols,
                key=lambda item: (
                    item.file_path.lower(),
                    item.line_start,
                    item.qualified_name.lower(),
                ),
            ),
        ),
        backend_routes=tuple(
            sorted(
                backend_routes,
                key=lambda item: (
                    item.path.lower(),
                    item.method,
                    item.file_path.lower(),
                    item.line,
                ),
            ),
        ),
        frontend_routes=tuple(
            sorted(
                frontend_routes,
                key=lambda item: (
                    item.path.lower(),
                    item.file_path.lower(),
                    item.line,
                ),
            ),
        ),
        frontend_api_calls=tuple(
            sorted(
                frontend_api_calls,
                key=lambda item: (
                    item.url.lower(),
                    item.method,
                    item.file_path.lower(),
                    item.line,
                ),
            ),
        ),
        call_edges=tuple(
            sorted(
                call_edges,
                key=lambda item: (
                    item.caller.lower(),
                    item.callee.lower(),
                    item.file_path.lower(),
                    item.line,
                ),
            ),
        ),
        data_models=tuple(
            sorted(
                data_models,
                key=lambda item: (
                    item.name.lower(),
                    item.file_path.lower(),
                    item.line,
                ),
            ),
        ),
        business_flows=tuple(
            business_flows,
        ),
    )


@dataclass(frozen=True, slots=True)
class _PythonFileAnalysis:
    symbols: tuple[CodeSymbolEvidence, ...]
    backend_routes: tuple[BackendRouteEvidence, ...]
    call_edges: tuple[CallEdgeEvidence, ...]
    data_models: tuple[DataModelEvidence, ...]


class _PythonAstAnalyzer(ast.NodeVisitor):
    """分析单个 Python AST。"""

    def __init__(
        self,
        *,
        relative_path: str,
    ) -> None:
        self.relative_path = relative_path

        self.scope: list[str] = []

        self.router_prefixes: dict[str, str] = {}

        self.symbols: list[
            CodeSymbolEvidence
        ] = []

        self.backend_routes: list[
            BackendRouteEvidence
        ] = []

        self.call_edges: list[
            CallEdgeEvidence
        ] = []

        self.data_models: list[
            DataModelEvidence
        ] = []

    def visit_Assign(
        self,
        node: ast.Assign,
    ) -> None:
        """
        尝试识别：

        router = APIRouter(prefix="/users")
        """

        if not isinstance(
            node.value,
            ast.Call,
        ):
            self.generic_visit(node)
            return

        function_name = _expression_name(
            node.value.func,
        )

        if not function_name.endswith(
            "APIRouter",
        ):
            self.generic_visit(node)
            return

        prefix = _get_keyword_string(
            node.value,
            "prefix",
        )

        if prefix is None:
            prefix = ""

        for target in node.targets:
            if isinstance(target, ast.Name):
                self.router_prefixes[
                    target.id
                ] = prefix

        self.generic_visit(node)

    def visit_ClassDef(
        self,
        node: ast.ClassDef,
    ) -> None:
        qualified_name = self._qualified_name(
            node.name,
        )

        self.symbols.append(
            CodeSymbolEvidence(
                name=node.name,
                qualified_name=qualified_name,
                kind="class",
                file_path=self.relative_path,
                line_start=node.lineno,
                line_end=getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                ),
            ),
        )

        model_kind = _detect_model_kind(
            node,
        )

        if model_kind is not None:
            self.data_models.append(
                DataModelEvidence(
                    name=qualified_name,
                    model_kind=model_kind,
                    fields=_extract_model_fields(
                        node,
                    ),
                    file_path=self.relative_path,
                    line=node.lineno,
                ),
            )

        self.scope.append(node.name)

        self.generic_visit(node)

        self.scope.pop()

    def visit_FunctionDef(
        self,
        node: ast.FunctionDef,
    ) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        self._visit_function(node)

    def _visit_function(
        self,
        node: (
            ast.FunctionDef
            | ast.AsyncFunctionDef
        ),
    ) -> None:
        qualified_name = self._qualified_name(
            node.name,
        )

        kind = (
            "method"
            if self.scope
            else "function"
        )

        self.symbols.append(
            CodeSymbolEvidence(
                name=node.name,
                qualified_name=qualified_name,
                kind=kind,
                file_path=self.relative_path,
                line_start=node.lineno,
                line_end=getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                ),
            ),
        )

        for route in _extract_backend_routes(
            decorators=node.decorator_list,
            router_prefixes=self.router_prefixes,
        ):
            self.backend_routes.append(
                BackendRouteEvidence(
                    method=route[0],
                    path=route[1],
                    handler=qualified_name,
                    file_path=self.relative_path,
                    line=node.lineno,
                ),
            )

        self.call_edges.extend(
            _extract_function_calls(
                node=node,
                caller=qualified_name,
                relative_path=self.relative_path,
            ),
        )

        self.scope.append(node.name)

        self.generic_visit(node)

        self.scope.pop()

    def _qualified_name(
        self,
        local_name: str,
    ) -> str:
        module_name = _module_name_from_path(
            self.relative_path,
        )

        parts = [
            module_name,
            *self.scope,
            local_name,
        ]

        return ".".join(
            part
            for part in parts
            if part
        )


def _analyze_python_file(
    *,
    source: str,
    relative_path: str,
) -> _PythonFileAnalysis:
    tree = ast.parse(
        source,
        filename=relative_path,
    )

    analyzer = _PythonAstAnalyzer(
        relative_path=relative_path,
    )

    analyzer.visit(tree)

    return _PythonFileAnalysis(
        symbols=tuple(analyzer.symbols),
        backend_routes=tuple(
            analyzer.backend_routes,
        ),
        call_edges=tuple(analyzer.call_edges),
        data_models=tuple(analyzer.data_models),
    )


@dataclass(frozen=True, slots=True)
class _JavascriptFileAnalysis:
    symbols: tuple[CodeSymbolEvidence, ...]
    frontend_routes: tuple[
        FrontendRouteEvidence,
        ...
    ]
    api_calls: tuple[
        FrontendApiCallEvidence,
        ...
    ]


def _analyze_javascript_typescript_file(
    *,
    source: str,
    relative_path: str,
) -> _JavascriptFileAnalysis:
    symbols: list[CodeSymbolEvidence] = []
    frontend_routes: list[
        FrontendRouteEvidence
    ] = []
    api_calls: list[
        FrontendApiCallEvidence
    ] = []

    seen_symbols: set[
        tuple[str, int]
    ] = set()

    for pattern, symbol_kind in (
        (_JS_FUNCTION_PATTERN, "function"),
        (
            _JS_ARROW_FUNCTION_PATTERN,
            "function",
        ),
    ):
        for match in pattern.finditer(source):
            name = match.group("name")
            line = _line_number(
                source,
                match.start(),
            )

            key = (name, line)

            if key in seen_symbols:
                continue

            seen_symbols.add(key)

            symbols.append(
                CodeSymbolEvidence(
                    name=name,
                    qualified_name=(
                        f"{relative_path}:{name}"
                    ),
                    kind=symbol_kind,
                    file_path=relative_path,
                    line_start=line,
                    line_end=line,
                ),
            )

    for match in _CREATE_FILE_ROUTE_PATTERN.finditer(
        source,
    ):
        frontend_routes.append(
            FrontendRouteEvidence(
                path=match.group("path"),
                source_kind="tanstack_file_route",
                file_path=relative_path,
                line=_line_number(
                    source,
                    match.start(),
                ),
            ),
        )

    for match in _REACT_ROUTE_PATH_PATTERN.finditer(
        source,
    ):
        frontend_routes.append(
            FrontendRouteEvidence(
                path=match.group("path"),
                source_kind="react_router",
                file_path=relative_path,
                line=_line_number(
                    source,
                    match.start(),
                ),
            ),
        )

    for match in _FETCH_PATTERN.finditer(source):
        api_calls.append(
            FrontendApiCallEvidence(
                method="GET",
                url=match.group("url"),
                source_kind="fetch",
                file_path=relative_path,
                line=_line_number(
                    source,
                    match.start(),
                ),
            ),
        )

    for match in _AXIOS_PATTERN.finditer(source):
        api_calls.append(
            FrontendApiCallEvidence(
                method=match.group(
                    "method",
                ).upper(),
                url=match.group("url"),
                source_kind="axios",
                file_path=relative_path,
                line=_line_number(
                    source,
                    match.start(),
                ),
            ),
        )

    return _JavascriptFileAnalysis(
        symbols=tuple(symbols),
        frontend_routes=tuple(
            frontend_routes,
        ),
        api_calls=tuple(api_calls),
    )


def _extract_backend_routes(
    *,
    decorators: list[ast.expr],
    router_prefixes: dict[str, str],
) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []

    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue

        if not isinstance(
            decorator.func,
            ast.Attribute,
        ):
            continue

        method = decorator.func.attr.lower()

        if method not in HTTP_METHODS:
            continue

        route_path = _get_first_string_argument(
            decorator,
        )

        if route_path is None:
            route_path = _get_keyword_string(
                decorator,
                "path",
            )

        if route_path is None:
            continue

        router_name = _expression_name(
            decorator.func.value,
        )

        prefix = router_prefixes.get(
            router_name,
            "",
        )

        full_path = _join_route_paths(
            prefix,
            route_path,
        )

        results.append(
            (
                method.upper(),
                full_path,
            ),
        )

    return results


def _extract_function_calls(
    *,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    caller: str,
    relative_path: str,
) -> list[CallEdgeEvidence]:
    collector = _FunctionCallCollector()

    for statement in node.body:
        collector.visit(statement)

    results: list[CallEdgeEvidence] = []

    seen: set[
        tuple[str, int]
    ] = set()

    for call_name, line in collector.calls:
        if not call_name:
            continue

        key = (call_name, line)

        if key in seen:
            continue

        seen.add(key)

        results.append(
            CallEdgeEvidence(
                caller=caller,
                callee=call_name,
                file_path=relative_path,
                line=line,
            ),
        )

    return results


class _FunctionCallCollector(ast.NodeVisitor):
    """
    收集当前函数直接包含的调用。

    不进入内部嵌套函数或类，避免重复归属。
    """

    def __init__(self) -> None:
        self.calls: list[
            tuple[str, int]
        ] = []

    def visit_Call(
        self,
        node: ast.Call,
    ) -> None:
        call_name = _expression_name(
            node.func,
        )

        if call_name:
            self.calls.append(
                (
                    call_name,
                    node.lineno,
                ),
            )

        self.generic_visit(node)

    def visit_FunctionDef(
        self,
        _node: ast.FunctionDef,
    ) -> None:
        return

    def visit_AsyncFunctionDef(
        self,
        _node: ast.AsyncFunctionDef,
    ) -> None:
        return

    def visit_ClassDef(
        self,
        _node: ast.ClassDef,
    ) -> None:
        return


def _detect_model_kind(
    node: ast.ClassDef,
) -> str | None:
    base_names = {
        _expression_name(base)
        for base in node.bases
    }

    table_enabled = any(
        keyword.arg == "table"
        and isinstance(
            keyword.value,
            ast.Constant,
        )
        and keyword.value.value is True
        for keyword in node.keywords
    )

    if table_enabled or any(
        base_name.endswith("SQLModel")
        for base_name in base_names
    ):
        return (
            "sqlmodel_table"
            if table_enabled
            else "sqlmodel"
        )

    if any(
        base_name.endswith("BaseModel")
        for base_name in base_names
    ):
        return "pydantic"

    return None


def _extract_model_fields(
    node: ast.ClassDef,
) -> tuple[str, ...]:
    fields: list[str] = []

    for statement in node.body:
        if isinstance(
            statement,
            ast.AnnAssign,
        ) and isinstance(
            statement.target,
            ast.Name,
        ):
            fields.append(
                statement.target.id,
            )

    return tuple(fields)


def _find_candidate_code_files(
    root: Path,
) -> list[Path]:
    results: list[Path] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative_parts = path.relative_to(
            root,
        ).parts

        if any(
            part.lower()
            in {
                ignored.lower()
                for ignored
                in IGNORED_DIRECTORY_NAMES
            }
            for part in relative_parts[:-1]
        ):
            continue

        suffix = path.suffix.lower()

        if (
            suffix == PYTHON_SUFFIX
            or suffix
            in JAVASCRIPT_TYPESCRIPT_SUFFIXES
        ):
            results.append(path)

    return sorted(
        results,
        key=lambda item: (
            item.relative_to(root)
            .as_posix()
            .lower()
        ),
    )


def _read_source_file(
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


def _expression_name(
    expression: ast.expr,
) -> str:
    if isinstance(expression, ast.Name):
        return expression.id

    if isinstance(expression, ast.Attribute):
        parent = _expression_name(
            expression.value,
        )

        if parent:
            return f"{parent}.{expression.attr}"

        return expression.attr

    return ""


def _get_first_string_argument(
    call: ast.Call,
) -> str | None:
    if not call.args:
        return None

    first_argument = call.args[0]

    if (
        isinstance(
            first_argument,
            ast.Constant,
        )
        and isinstance(
            first_argument.value,
            str,
        )
    ):
        return first_argument.value

    return None


def _get_keyword_string(
    call: ast.Call,
    keyword_name: str,
) -> str | None:
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue

        if (
            isinstance(
                keyword.value,
                ast.Constant,
            )
            and isinstance(
                keyword.value.value,
                str,
            )
        ):
            return keyword.value.value

    return None


def _join_route_paths(
    prefix: str,
    route_path: str,
) -> str:
    normalized_prefix = prefix.strip("/")
    normalized_path = route_path.strip("/")

    parts = [
        part
        for part in (
            normalized_prefix,
            normalized_path,
        )
        if part
    ]

    if not parts:
        return "/"

    return "/" + "/".join(parts)


def _module_name_from_path(
    relative_path: str,
) -> str:
    path = PurePosixPath(relative_path)

    parts = list(path.parts)

    if parts:
        parts[-1] = Path(
            parts[-1],
        ).stem

    if parts and parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts)


def _line_number(
    source: str,
    offset: int,
) -> int:
    return source.count(
        "\n",
        0,
        offset,
    ) + 1


def _match_business_flows(
    *,
    frontend_api_calls: list[
        FrontendApiCallEvidence
    ],
    backend_routes: list[
        BackendRouteEvidence
    ],
) -> list[BusinessFlowEvidence]:
    results: list[BusinessFlowEvidence] = []

    for frontend_call in frontend_api_calls:
        for backend_route in backend_routes:
            if (
                frontend_call.method
                != backend_route.method
            ):
                continue

            if not _paths_may_match(
                frontend_call.url,
                backend_route.path,
            ):
                continue

            results.append(
                BusinessFlowEvidence(
                    frontend_method=(
                        frontend_call.method
                    ),
                    frontend_url=(
                        frontend_call.url
                    ),
                    frontend_file_path=(
                        frontend_call.file_path
                    ),
                    frontend_line=(
                        frontend_call.line
                    ),
                    backend_method=(
                        backend_route.method
                    ),
                    backend_path=(
                        backend_route.path
                    ),
                    backend_handler=(
                        backend_route.handler
                    ),
                    backend_file_path=(
                        backend_route.file_path
                    ),
                    backend_line=(
                        backend_route.line
                    ),
                ),
            )

    return sorted(
        results,
        key=lambda item: (
            item.frontend_url.lower(),
            item.backend_path.lower(),
            item.frontend_file_path.lower(),
            item.frontend_line,
        ),
    )


def _paths_may_match(
    frontend_url: str,
    backend_path: str,
) -> bool:
    normalized_frontend = (
        _normalize_url_path(
            frontend_url,
        )
    )

    normalized_backend = (
        _normalize_url_path(
            backend_path,
        )
    )

    frontend_parts = [
        part
        for part
        in normalized_frontend.split("/")
        if part
    ]

    backend_parts = [
        part
        for part
        in normalized_backend.split("/")
        if part
    ]

    if len(frontend_parts) != len(
        backend_parts,
    ):
        return False

    for frontend_part, backend_part in zip(
        frontend_parts,
        backend_parts,
        strict=True,
    ):
        if (
            frontend_part == "{parameter}"
            or backend_part == "{parameter}"
        ):
            continue

        if frontend_part != backend_part:
            return False

    return True


def _normalize_url_path(
    value: str,
) -> str:
    normalized = value.strip()

    if "://" in normalized:
        normalized = normalized.split(
            "://",
            maxsplit=1,
        )[1]

        if "/" in normalized:
            normalized = normalized[
                normalized.index("/")
            :]
        else:
            normalized = "/"

    normalized = normalized.split(
        "?",
        maxsplit=1,
    )[0]

    normalized = normalized.split(
        "#",
        maxsplit=1,
    )[0]

    normalized = _ROUTE_PLACEHOLDER_PATTERN.sub(
        "{parameter}",
        normalized,
    )

    return "/" + normalized.strip("/")


def _dataclass_to_dict(
    instance: object,
) -> dict[str, Any]:
    return {
        field_name: getattr(
            instance,
            field_name,
        )
        for field_name in instance.__dataclass_fields__
    }