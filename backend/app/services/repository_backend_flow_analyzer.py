from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from app.services.repository_fastapi_router_analyzer import (
    FastApiRouterAnalysis,
)
from app.services.repository_structure_scanner import (
    IGNORED_DIRECTORY_NAMES,
)


DEFAULT_MAX_PYTHON_FILES = 1_000
DEFAULT_MAX_PYTHON_FILE_BYTES = 1024 * 1024

DEFAULT_MAX_FLOW_DEPTH = 8
DEFAULT_MAX_PATHS_PER_ROUTE = 30

_IGNORED_DIRECTORIES_LOWER = {
    name.lower()
    for name in IGNORED_DIRECTORY_NAMES
}

_DATABASE_METHOD_KIND = {
    "add": "database_write",
    "add_all": "database_write",
    "delete": "database_write",
    "merge": "database_write",
    "exec": "database_query",
    "execute": "database_query",
    "scalar": "database_query",
    "scalars": "database_query",
    "get": "database_query",
    "query": "database_query",
    "commit": "transaction_commit",
    "rollback": "transaction_rollback",
    "refresh": "database_refresh",
    "flush": "database_flush",
}


@dataclass(frozen=True, slots=True)
class PythonInternalSymbolEvidence:
    """
    仓库内部的 Python 函数、方法或数据模型。
    """

    qualified_name: str
    name: str
    kind: str
    layer: str

    file_path: str
    line_start: int
    line_end: int


@dataclass(frozen=True, slots=True)
class PythonInternalCallEvidence:
    """
    仓库内部可以静态解析的函数调用关系。
    """

    caller: str
    callee: str
    expression: str

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class PythonUnresolvedCallEvidence:
    """
    无法解析到仓库内部符号的函数调用。

    可能是第三方库、运行时对象方法或动态依赖。
    """

    caller: str
    expression: str

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class PythonModelUsageEvidence:
    """
    某个函数对数据模型的使用。
    """

    caller: str
    model: str
    usage_kind: str

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class PythonDatabaseOperationEvidence:
    """
    某个函数中的数据库操作。

    示例：
    session.exec
    session.add
    session.commit
    """

    caller: str
    operation_kind: str
    expression: str

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class BackendFlowStepEvidence:
    """
    一条调用路径中的一个步骤。
    """

    order: int
    symbol: str
    name: str
    kind: str
    layer: str

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class BackendCallPathEvidence:
    """
    从 Handler 开始的一条静态调用路径。
    """

    steps: tuple[BackendFlowStepEvidence, ...]
    terminal_reason: str


@dataclass(frozen=True, slots=True)
class BackendRouteFlowEvidence:
    """
    一条 HTTP 路由对应的后端业务分析结果。
    """

    method: str
    path: str
    path_complete: bool

    handler: str
    handler_resolved: bool

    call_paths: tuple[
        BackendCallPathEvidence,
        ...
    ]

    model_usages: tuple[
        PythonModelUsageEvidence,
        ...
    ]

    database_operations: tuple[
        PythonDatabaseOperationEvidence,
        ...
    ]

    unresolved_calls: tuple[
        PythonUnresolvedCallEvidence,
        ...
    ]

    paths_truncated: bool


@dataclass(frozen=True, slots=True)
class RepositoryBackendFlowAnalysis:
    """
    整个仓库的后端业务调用链结果。
    """

    scanned_python_file_count: int
    skipped_large_file_count: int
    parse_error_count: int
    analysis_truncated: bool

    symbols: tuple[
        PythonInternalSymbolEvidence,
        ...
    ]

    internal_calls: tuple[
        PythonInternalCallEvidence,
        ...
    ]

    unresolved_calls: tuple[
        PythonUnresolvedCallEvidence,
        ...
    ]

    model_usages: tuple[
        PythonModelUsageEvidence,
        ...
    ]

    database_operations: tuple[
        PythonDatabaseOperationEvidence,
        ...
    ]

    route_flows: tuple[
        BackendRouteFlowEvidence,
        ...
    ]

    def to_dict(self) -> dict[str, Any]:
        """
        转换为可以保存到 JSONB 的结构。
        """

        return {
            "statistics": {
                "scanned_python_file_count": (
                    self.scanned_python_file_count
                ),
                "skipped_large_file_count": (
                    self.skipped_large_file_count
                ),
                "parse_error_count": (
                    self.parse_error_count
                ),
                "analysis_truncated": (
                    self.analysis_truncated
                ),
            },
            "symbols": [
                asdict(item)
                for item in self.symbols
            ],
            "internal_calls": [
                asdict(item)
                for item in self.internal_calls
            ],
            "unresolved_calls": [
                asdict(item)
                for item in self.unresolved_calls
            ],
            "model_usages": [
                asdict(item)
                for item in self.model_usages
            ],
            "database_operations": [
                asdict(item)
                for item in self.database_operations
            ],
            "route_flows": [
                asdict(item)
                for item in self.route_flows
            ],
        }


@dataclass(slots=True)
class _SymbolRecord:
    """
    分析器内部使用的符号记录。

    node 不会写入最终 JSON。
    """

    evidence: PythonInternalSymbolEvidence
    module_name: str
    class_name: str | None
    imports: dict[str, str]
    node: ast.AST


@dataclass(frozen=True, slots=True)
class _ParsedPythonModule:
    """
    一个 Python 文件解析后的中间结果。
    """

    module_name: str
    relative_path: str
    syntax_tree: ast.Module
    imports: dict[str, str]


class _CallCollector(ast.NodeVisitor):
    """
    收集一个函数体中的调用。

    不进入内部嵌套函数和嵌套类，避免把调用错误地
    归属到外层函数。
    """

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(
        self,
        node: ast.Call,
    ) -> None:
        self.calls.append(node)
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


def analyze_repository_backend_flows(
    repository_root: Path | str,
    *,
    fastapi_router_analysis: FastApiRouterAnalysis,
    max_python_files: int = DEFAULT_MAX_PYTHON_FILES,
    max_python_file_bytes: int = (
        DEFAULT_MAX_PYTHON_FILE_BYTES
    ),
    max_flow_depth: int = DEFAULT_MAX_FLOW_DEPTH,
    max_paths_per_route: int = (
        DEFAULT_MAX_PATHS_PER_ROUTE
    ),
) -> RepositoryBackendFlowAnalysis:
    """
    从完整 FastAPI 路由开始分析后端调用链。

    整体流程：
    1. 建立 Python 符号索引；
    2. 解析内部函数调用；
    3. 识别数据模型和数据库操作；
    4. 从每个路由 Handler 开始遍历调用图。
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

    python_files = _find_python_files(root)

    analysis_truncated = (
        len(python_files) > max_python_files
    )

    selected_files = python_files[
        :max_python_files
    ]

    parsed_modules: list[_ParsedPythonModule] = []

    skipped_large_file_count = 0
    parse_error_count = 0

    for file_path in selected_files:
        try:
            size_bytes = file_path.stat().st_size
        except OSError:
            parse_error_count += 1
            continue

        if size_bytes > max_python_file_bytes:
            skipped_large_file_count += 1
            continue

        source = _read_python_source(
            file_path,
            max_bytes=max_python_file_bytes,
        )

        if source is None:
            parse_error_count += 1
            continue

        relative_path = file_path.relative_to(
            root,
        ).as_posix()

        module_name = _module_name_from_path(
            relative_path,
        )

        try:
            syntax_tree = ast.parse(
                source,
                filename=relative_path,
            )
        except SyntaxError:
            parse_error_count += 1
            continue

        imports = _collect_module_imports(
            syntax_tree,
            module_name=module_name,
        )

        parsed_modules.append(
            _ParsedPythonModule(
                module_name=module_name,
                relative_path=relative_path,
                syntax_tree=syntax_tree,
                imports=imports,
            ),
        )

    symbol_records = _collect_symbols(
        parsed_modules,
    )

    symbol_by_name = {
        qualified_name: record
        for qualified_name, record
        in symbol_records.items()
    }

    model_symbols = {
        qualified_name
        for qualified_name, record
        in symbol_records.items()
        if record.evidence.kind
        in {
            "sqlmodel",
            "sqlmodel_table",
            "pydantic_model",
        }
    }

    internal_calls: list[
        PythonInternalCallEvidence
    ] = []

    unresolved_calls: list[
        PythonUnresolvedCallEvidence
    ] = []

    model_usages: list[
        PythonModelUsageEvidence
    ] = []

    database_operations: list[
        PythonDatabaseOperationEvidence
    ] = []

    callable_records = [
        record
        for record in symbol_records.values()
        if record.evidence.kind
        in {
            "function",
            "method",
        }
    ]

    for record in callable_records:
        (
            function_calls,
            function_unresolved,
            function_models,
            function_database_operations,
        ) = _analyze_callable(
            record=record,
            symbol_by_name=symbol_by_name,
            model_symbols=model_symbols,
        )

        internal_calls.extend(function_calls)
        unresolved_calls.extend(
            function_unresolved,
        )
        model_usages.extend(function_models)
        database_operations.extend(
            function_database_operations,
        )

    route_handler_names = {
        route.handler
        for route
        in fastapi_router_analysis.routes
    }

    public_symbols = tuple(
        _mark_route_handler_layers(
            symbol_records=symbol_records,
            route_handler_names=(
                route_handler_names
            ),
        ),
    )

    public_symbol_by_name = {
        item.qualified_name: item
        for item in public_symbols
    }

    route_flows = _build_route_flows(
        fastapi_router_analysis=(
            fastapi_router_analysis
        ),
        symbol_by_name=public_symbol_by_name,
        internal_calls=internal_calls,
        unresolved_calls=unresolved_calls,
        model_usages=model_usages,
        database_operations=database_operations,
        max_flow_depth=max_flow_depth,
        max_paths_per_route=(
            max_paths_per_route
        ),
    )

    return RepositoryBackendFlowAnalysis(
        scanned_python_file_count=len(
            parsed_modules,
        ),
        skipped_large_file_count=(
            skipped_large_file_count
        ),
        parse_error_count=parse_error_count,
        analysis_truncated=analysis_truncated,
        symbols=tuple(
            sorted(
                public_symbols,
                key=lambda item: (
                    item.file_path.lower(),
                    item.line_start,
                    item.qualified_name.lower(),
                ),
            ),
        ),
        internal_calls=tuple(
            _deduplicate_dataclasses(
                internal_calls,
            ),
        ),
        unresolved_calls=tuple(
            _deduplicate_dataclasses(
                unresolved_calls,
            ),
        ),
        model_usages=tuple(
            _deduplicate_dataclasses(
                model_usages,
            ),
        ),
        database_operations=tuple(
            _deduplicate_dataclasses(
                database_operations,
            ),
        ),
        route_flows=tuple(route_flows),
    )


def _collect_symbols(
    modules: list[_ParsedPythonModule],
) -> dict[str, _SymbolRecord]:
    """
    建立仓库内部符号表。

    第一遍只收集定义，不分析调用。
    """

    results: dict[str, _SymbolRecord] = {}

    for module in modules:
        for statement in module.syntax_tree.body:
            if isinstance(
                statement,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                qualified_name = (
                    f"{module.module_name}."
                    f"{statement.name}"
                )

                evidence = (
                    PythonInternalSymbolEvidence(
                        qualified_name=qualified_name,
                        name=statement.name,
                        kind="function",
                        layer=_classify_layer(
                            module.relative_path,
                            kind="function",
                        ),
                        file_path=(
                            module.relative_path
                        ),
                        line_start=statement.lineno,
                        line_end=getattr(
                            statement,
                            "end_lineno",
                            statement.lineno,
                        ),
                    )
                )

                results[qualified_name] = (
                    _SymbolRecord(
                        evidence=evidence,
                        module_name=(
                            module.module_name
                        ),
                        class_name=None,
                        imports=module.imports,
                        node=statement,
                    )
                )

            elif isinstance(
                statement,
                ast.ClassDef,
            ):
                class_name = (
                    f"{module.module_name}."
                    f"{statement.name}"
                )

                model_kind = _detect_model_kind(
                    statement,
                )

                class_kind = (
                    model_kind or "class"
                )

                class_evidence = (
                    PythonInternalSymbolEvidence(
                        qualified_name=class_name,
                        name=statement.name,
                        kind=class_kind,
                        layer=_classify_layer(
                            module.relative_path,
                            kind=class_kind,
                        ),
                        file_path=(
                            module.relative_path
                        ),
                        line_start=statement.lineno,
                        line_end=getattr(
                            statement,
                            "end_lineno",
                            statement.lineno,
                        ),
                    )
                )

                results[class_name] = (
                    _SymbolRecord(
                        evidence=class_evidence,
                        module_name=(
                            module.module_name
                        ),
                        class_name=statement.name,
                        imports=module.imports,
                        node=statement,
                    )
                )

                for class_statement in statement.body:
                    if not isinstance(
                        class_statement,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                        ),
                    ):
                        continue

                    method_name = (
                        f"{class_name}."
                        f"{class_statement.name}"
                    )

                    method_evidence = (
                        PythonInternalSymbolEvidence(
                            qualified_name=(
                                method_name
                            ),
                            name=(
                                class_statement.name
                            ),
                            kind="method",
                            layer=_classify_layer(
                                module.relative_path,
                                kind="method",
                            ),
                            file_path=(
                                module.relative_path
                            ),
                            line_start=(
                                class_statement.lineno
                            ),
                            line_end=getattr(
                                class_statement,
                                "end_lineno",
                                class_statement.lineno,
                            ),
                        )
                    )

                    results[method_name] = (
                        _SymbolRecord(
                            evidence=method_evidence,
                            module_name=(
                                module.module_name
                            ),
                            class_name=(
                                statement.name
                            ),
                            imports=module.imports,
                            node=class_statement,
                        )
                    )

    return results


def _analyze_callable(
    *,
    record: _SymbolRecord,
    symbol_by_name: dict[str, _SymbolRecord],
    model_symbols: set[str],
) -> tuple[
    list[PythonInternalCallEvidence],
    list[PythonUnresolvedCallEvidence],
    list[PythonModelUsageEvidence],
    list[PythonDatabaseOperationEvidence],
]:
    """
    分析一个函数或方法内部的调用。
    """

    if not isinstance(
        record.node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        return [], [], [], []

    collector = _CallCollector()

    for statement in record.node.body:
        collector.visit(statement)

    internal_calls: list[
        PythonInternalCallEvidence
    ] = []

    unresolved_calls: list[
        PythonUnresolvedCallEvidence
    ] = []

    model_usages: list[
        PythonModelUsageEvidence
    ] = []

    database_operations: list[
        PythonDatabaseOperationEvidence
    ] = []

    caller = record.evidence.qualified_name

    for call in collector.calls:
        expression = _expression_name(
            call.func,
        )

        if not expression:
            continue

        database_operation = (
            _detect_database_operation(
                caller=caller,
                expression=expression,
                file_path=(
                    record.evidence.file_path
                ),
                line=call.lineno,
            )
        )

        if database_operation is not None:
            database_operations.append(
                database_operation,
            )

        resolved_target = _resolve_call_target(
            expression=expression,
            record=record,
            symbol_by_name=symbol_by_name,
        )

        if (
            resolved_target is not None
            and resolved_target
            in model_symbols
        ):
            model_usages.append(
                PythonModelUsageEvidence(
                    caller=caller,
                    model=resolved_target,
                    usage_kind="construct",
                    file_path=(
                        record.evidence.file_path
                    ),
                    line=call.lineno,
                ),
            )
            continue

        if resolved_target is not None:
            internal_calls.append(
                PythonInternalCallEvidence(
                    caller=caller,
                    callee=resolved_target,
                    expression=expression,
                    file_path=(
                        record.evidence.file_path
                    ),
                    line=call.lineno,
                ),
            )
        elif not _is_common_external_call(
            expression,
        ):
            unresolved_calls.append(
                PythonUnresolvedCallEvidence(
                    caller=caller,
                    expression=expression,
                    file_path=(
                        record.evidence.file_path
                    ),
                    line=call.lineno,
                ),
            )

        model_usages.extend(
            _detect_model_arguments(
                call=call,
                caller=caller,
                record=record,
                model_symbols=model_symbols,
                symbol_by_name=symbol_by_name,
            ),
        )

    return (
        internal_calls,
        unresolved_calls,
        model_usages,
        database_operations,
    )


def _resolve_call_target(
    *,
    expression: str,
    record: _SymbolRecord,
    symbol_by_name: dict[str, _SymbolRecord],
) -> str | None:
    """
    将函数调用表达式解析到仓库内部符号。

    支持：
    local_function()
    imported_function()
    service.create()
    Class.method()
    self.method()
    """

    expression_parts = expression.split(".")

    if not expression_parts:
        return None

    if (
        expression_parts[0] == "self"
        and record.class_name
        and len(expression_parts) == 2
    ):
        candidate = (
            f"{record.module_name}."
            f"{record.class_name}."
            f"{expression_parts[1]}"
        )

        if candidate in symbol_by_name:
            return candidate

    if len(expression_parts) == 1:
        local_candidate = (
            f"{record.module_name}."
            f"{expression}"
        )

        if local_candidate in symbol_by_name:
            return local_candidate

        imported_target = record.imports.get(
            expression,
        )

        if (
            imported_target is not None
            and imported_target
            in symbol_by_name
        ):
            return imported_target

        return None

    first_part = expression_parts[0]

    imported_base = record.imports.get(
        first_part,
    )

    if imported_base is not None:
        imported_candidate = ".".join(
            [
                imported_base,
                *expression_parts[1:],
            ],
        )

        if imported_candidate in symbol_by_name:
            return imported_candidate

    direct_candidate = ".".join(
        [
            record.module_name,
            *expression_parts,
        ],
    )

    if direct_candidate in symbol_by_name:
        return direct_candidate

    return None


def _detect_model_arguments(
    *,
    call: ast.Call,
    caller: str,
    record: _SymbolRecord,
    model_symbols: set[str],
    symbol_by_name: dict[str, _SymbolRecord],
) -> list[PythonModelUsageEvidence]:
    """
    识别：

    select(User)
    session.get(User, user_id)
    Model(...)
    """

    results: list[
        PythonModelUsageEvidence
    ] = []

    expression = _expression_name(
        call.func,
    )

    operation_name = (
        expression.split(".")[-1]
        if expression
        else ""
    )

    if operation_name not in {
        "select",
        "get",
        "delete",
        "query",
    }:
        return results

    for argument in call.args:
        argument_expression = _expression_name(
            argument,
        )

        if not argument_expression:
            continue

        resolved_model = _resolve_call_target(
            expression=argument_expression,
            record=record,
            symbol_by_name=symbol_by_name,
        )

        if resolved_model not in model_symbols:
            continue

        results.append(
            PythonModelUsageEvidence(
                caller=caller,
                model=resolved_model,
                usage_kind=operation_name,
                file_path=(
                    record.evidence.file_path
                ),
                line=call.lineno,
            ),
        )

    return results


def _detect_database_operation(
    *,
    caller: str,
    expression: str,
    file_path: str,
    line: int,
) -> PythonDatabaseOperationEvidence | None:
    """
    根据调用方法名识别数据库操作。

    此处是启发式规则，不保证对象一定是 SQLModel Session。
    """

    method_name = expression.split(".")[-1]

    operation_kind = _DATABASE_METHOD_KIND.get(
        method_name,
    )

    if operation_kind is None:
        return None

    return PythonDatabaseOperationEvidence(
        caller=caller,
        operation_kind=operation_kind,
        expression=expression,
        file_path=file_path,
        line=line,
    )


def _build_route_flows(
    *,
    fastapi_router_analysis: FastApiRouterAnalysis,
    symbol_by_name: dict[
        str,
        PythonInternalSymbolEvidence,
    ],
    internal_calls: list[
        PythonInternalCallEvidence
    ],
    unresolved_calls: list[
        PythonUnresolvedCallEvidence
    ],
    model_usages: list[
        PythonModelUsageEvidence
    ],
    database_operations: list[
        PythonDatabaseOperationEvidence
    ],
    max_flow_depth: int,
    max_paths_per_route: int,
) -> list[BackendRouteFlowEvidence]:
    """
    从每个 FastAPI Handler 开始遍历调用图。
    """

    outgoing_calls: dict[
        str,
        list[PythonInternalCallEvidence],
    ] = {}

    for call in internal_calls:
        outgoing_calls.setdefault(
            call.caller,
            [],
        ).append(call)

    results: list[
        BackendRouteFlowEvidence
    ] = []

    for route in fastapi_router_analysis.routes:
        handler = route.handler

        handler_resolved = (
            handler in symbol_by_name
        )

        call_paths: list[
            BackendCallPathEvidence
        ] = []

        paths_truncated = False

        if handler_resolved:
            paths_truncated = _enumerate_call_paths(
                current_symbol=handler,
                current_path=(),
                active_symbols=set(),
                symbol_by_name=symbol_by_name,
                outgoing_calls=outgoing_calls,
                output=call_paths,
                max_depth=max_flow_depth,
                max_paths=max_paths_per_route,
            )

        visited_symbols = {
            step.symbol
            for call_path in call_paths
            for step in call_path.steps
        }

        if handler_resolved:
            visited_symbols.add(handler)

        route_models = [
            item
            for item in model_usages
            if item.caller in visited_symbols
        ]

        route_database_operations = [
            item
            for item in database_operations
            if item.caller in visited_symbols
        ]

        route_unresolved_calls = [
            item
            for item in unresolved_calls
            if item.caller in visited_symbols
        ]

        results.append(
            BackendRouteFlowEvidence(
                method=route.method,
                path=route.path,
                path_complete=(
                    route.path_complete
                ),
                handler=handler,
                handler_resolved=(
                    handler_resolved
                ),
                call_paths=tuple(call_paths),
                model_usages=tuple(
                    _deduplicate_dataclasses(
                        route_models,
                    ),
                ),
                database_operations=tuple(
                    _deduplicate_dataclasses(
                        route_database_operations,
                    ),
                ),
                unresolved_calls=tuple(
                    _deduplicate_dataclasses(
                        route_unresolved_calls,
                    ),
                ),
                paths_truncated=paths_truncated,
            ),
        )

    return sorted(
        results,
        key=lambda item: (
            item.path.lower(),
            item.method,
            item.handler.lower(),
        ),
    )


def _enumerate_call_paths(
    *,
    current_symbol: str,
    current_path: tuple[
        BackendFlowStepEvidence,
        ...
    ],
    active_symbols: set[str],
    symbol_by_name: dict[
        str,
        PythonInternalSymbolEvidence,
    ],
    outgoing_calls: dict[
        str,
        list[PythonInternalCallEvidence],
    ],
    output: list[BackendCallPathEvidence],
    max_depth: int,
    max_paths: int,
) -> bool:
    """
    深度遍历函数调用图。

    返回 True 表示路径数量被截断。
    """

    if len(output) >= max_paths:
        return True

    symbol = symbol_by_name.get(
        current_symbol,
    )

    if symbol is None:
        return False

    current_step = BackendFlowStepEvidence(
        order=len(current_path) + 1,
        symbol=symbol.qualified_name,
        name=symbol.name,
        kind=symbol.kind,
        layer=symbol.layer,
        file_path=symbol.file_path,
        line=symbol.line_start,
    )

    next_path = (
        *current_path,
        current_step,
    )

    if current_symbol in active_symbols:
        output.append(
            BackendCallPathEvidence(
                steps=next_path,
                terminal_reason="cycle_detected",
            ),
        )
        return False

    if len(next_path) >= max_depth:
        output.append(
            BackendCallPathEvidence(
                steps=next_path,
                terminal_reason="max_depth_reached",
            ),
        )
        return False

    outgoing = sorted(
        outgoing_calls.get(
            current_symbol,
            [],
        ),
        key=lambda item: (
            item.file_path.lower(),
            item.line,
            item.callee.lower(),
        ),
    )

    if not outgoing:
        output.append(
            BackendCallPathEvidence(
                steps=next_path,
                terminal_reason=(
                    "no_resolved_internal_call"
                ),
            ),
        )
        return False

    truncated = False

    next_active_symbols = {
        *active_symbols,
        current_symbol,
    }

    for call in outgoing:
        if len(output) >= max_paths:
            truncated = True
            break

        child_truncated = _enumerate_call_paths(
            current_symbol=call.callee,
            current_path=next_path,
            active_symbols=next_active_symbols,
            symbol_by_name=symbol_by_name,
            outgoing_calls=outgoing_calls,
            output=output,
            max_depth=max_depth,
            max_paths=max_paths,
        )

        truncated = (
            truncated or child_truncated
        )

    return truncated


def _mark_route_handler_layers(
    *,
    symbol_records: dict[str, _SymbolRecord],
    route_handler_names: set[str],
) -> list[PythonInternalSymbolEvidence]:
    """
    将路由处理函数明确标记为 handler 层。
    """

    results: list[
        PythonInternalSymbolEvidence
    ] = []

    for qualified_name, record in (
        symbol_records.items()
    ):
        evidence = record.evidence

        if qualified_name not in route_handler_names:
            results.append(evidence)
            continue

        results.append(
            PythonInternalSymbolEvidence(
                qualified_name=(
                    evidence.qualified_name
                ),
                name=evidence.name,
                kind=evidence.kind,
                layer="handler",
                file_path=evidence.file_path,
                line_start=evidence.line_start,
                line_end=evidence.line_end,
            ),
        )

    return results


def _collect_module_imports(
    syntax_tree: ast.Module,
    *,
    module_name: str,
) -> dict[str, str]:
    """
    收集模块级 import 别名。

    示例：
    from app.services.task import create_task
    → create_task = app.services.task.create_task
    """

    imports: dict[str, str] = {}

    for statement in syntax_tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                local_name = (
                    alias.asname
                    or alias.name.split(".")[0]
                )

                imports[local_name] = alias.name

        elif isinstance(
            statement,
            ast.ImportFrom,
        ):
            base_module = (
                _resolve_import_from_module(
                    current_module=module_name,
                    imported_module=(
                        statement.module
                    ),
                    level=statement.level,
                )
            )

            for alias in statement.names:
                if alias.name == "*":
                    continue

                local_name = (
                    alias.asname
                    or alias.name
                )

                imports[local_name] = ".".join(
                    part
                    for part in (
                        base_module,
                        alias.name,
                    )
                    if part
                )

    return imports


def _detect_model_kind(
    node: ast.ClassDef,
) -> str | None:
    """
    识别 SQLModel 和 Pydantic 模型。
    """

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

    if table_enabled:
        return "sqlmodel_table"

    if any(
        name.endswith("SQLModel")
        for name in base_names
    ):
        return "sqlmodel"

    if any(
        name.endswith("BaseModel")
        for name in base_names
    ):
        return "pydantic_model"

    return None


def _classify_layer(
    file_path: str,
    *,
    kind: str,
) -> str:
    """
    根据目录和文件名判断代码所属层。

    这是启发式分类，不是强制架构规则。
    """

    normalized = (
        "/" + file_path.lower().strip("/")
    )

    file_name = PurePosixPath(
        file_path,
    ).name.lower()

    if kind in {
        "sqlmodel",
        "sqlmodel_table",
        "pydantic_model",
    }:
        return "model"

    if (
        "/api/routes/" in normalized
        or "/routes/" in normalized
        or "/controllers/" in normalized
    ):
        return "handler"

    if "/services/" in normalized:
        return "service"

    if (
        "/repositories/" in normalized
        or "/repository/" in normalized
        or "/crud/" in normalized
        or "/dao/" in normalized
    ):
        return "repository"

    if (
        "/models/" in normalized
        or file_name == "models.py"
    ):
        return "model"

    if (
        "/core/" in normalized
        or "/infrastructure/" in normalized
        or "/database/" in normalized
        or "/db/" in normalized
    ):
        return "infrastructure"

    return "internal"


def _is_common_external_call(
    expression: str,
) -> bool:
    """
    过滤常见内置函数和无分析价值的表达式。
    """

    root_name = expression.split(".")[0]

    return root_name in {
        "bool",
        "dict",
        "enumerate",
        "float",
        "getattr",
        "hasattr",
        "int",
        "isinstance",
        "len",
        "list",
        "max",
        "min",
        "print",
        "range",
        "set",
        "sorted",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "zip",
    }


def _find_python_files(
    root: Path,
) -> list[Path]:
    results: list[Path] = []

    for path in root.rglob("*.py"):
        if not path.is_file():
            continue

        relative_parts = path.relative_to(
            root,
        ).parts

        if any(
            part.lower()
            in _IGNORED_DIRECTORIES_LOWER
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


def _read_python_source(
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


def _resolve_import_from_module(
    *,
    current_module: str,
    imported_module: str | None,
    level: int,
) -> str:
    imported_parts = (
        imported_module.split(".")
        if imported_module
        else []
    )

    if level <= 0:
        return ".".join(imported_parts)

    current_package = (
        current_module.split(".")[:-1]
    )

    remove_count = max(
        level - 1,
        0,
    )

    if remove_count:
        current_package = current_package[
            :-remove_count
        ]

    return ".".join(
        [
            *current_package,
            *imported_parts,
        ],
    )


def _module_name_from_path(
    relative_path: str,
) -> str:
    path = PurePosixPath(relative_path)

    parts = list(path.parts)

    if not parts:
        return ""

    parts[-1] = Path(
        parts[-1],
    ).stem

    if parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts)


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
            return (
                f"{parent}.{expression.attr}"
            )

        return expression.attr

    return ""


def _deduplicate_dataclasses(
    items: list[Any],
) -> list[Any]:
    """
    保持顺序地删除重复证据。
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