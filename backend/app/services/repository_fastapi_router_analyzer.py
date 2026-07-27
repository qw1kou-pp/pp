from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.services.repository_structure_scanner import (
    IGNORED_DIRECTORY_NAMES,
)


DEFAULT_MAX_PYTHON_FILES = 1_000
DEFAULT_MAX_PYTHON_FILE_BYTES = 1024 * 1024

HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
}

_IGNORED_DIRECTORIES_LOWER = {
    name.lower()
    for name in IGNORED_DIRECTORY_NAMES
}


@dataclass(frozen=True, slots=True)
class FastApiRouterDefinitionEvidence:
    """
    一个 FastAPI 应用或 APIRouter 对象。

    示例：
    app = FastAPI()
    router = APIRouter(prefix="/users")
    """

    key: str
    module_name: str
    variable_name: str
    router_kind: str

    prefix: str
    prefix_resolved: bool

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class FastApiRouterRegistrationEvidence:
    """
    一次 include_router 注册关系。

    示例：
    api_router.include_router(
        users.router,
        prefix="/admin",
    )
    """

    parent_router_key: str
    child_router_key: str | None
    child_expression: str

    include_prefix: str
    prefix_resolved: bool

    file_path: str
    line: int


@dataclass(frozen=True, slots=True)
class FastApiResolvedRouteEvidence:
    """
    拼接跨文件前缀后的完整 FastAPI 路由。
    """

    method: str
    path: str
    path_complete: bool

    handler: str
    router_key: str

    file_path: str
    line: int

    registration_chain: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FastApiRouterAnalysis:
    """
    FastAPI 路由注册图的完整分析结果。
    """

    scanned_python_file_count: int
    parse_error_count: int
    skipped_large_file_count: int
    analysis_truncated: bool

    router_definitions: tuple[
        FastApiRouterDefinitionEvidence,
        ...
    ]

    registrations: tuple[
        FastApiRouterRegistrationEvidence,
        ...
    ]

    routes: tuple[
        FastApiResolvedRouteEvidence,
        ...
    ]

    def to_dict(self) -> dict[str, Any]:
        """
        转换为可保存到 PostgreSQL JSONB 的字典。
        """

        return {
            "statistics": {
                "scanned_python_file_count": (
                    self.scanned_python_file_count
                ),
                "parse_error_count": (
                    self.parse_error_count
                ),
                "skipped_large_file_count": (
                    self.skipped_large_file_count
                ),
                "analysis_truncated": (
                    self.analysis_truncated
                ),
            },
            "router_definitions": [
                asdict(item)
                for item in self.router_definitions
            ],
            "registrations": [
                asdict(item)
                for item in self.registrations
            ],
            "routes": [
                asdict(item)
                for item in self.routes
            ],
        }


@dataclass(frozen=True, slots=True)
class _StringExpression:
    """
    静态字符串解析结果。

    resolved=False 表示字符串中仍包含无法静态确定的内容。
    """

    value: str
    resolved: bool


@dataclass(frozen=True, slots=True)
class _LocalRouteDefinition:
    """
    尚未拼接全局前缀的路由。
    """

    router_key: str

    method: str
    local_path: str
    path_resolved: bool

    handler: str
    file_path: str
    line: int


class _FastApiFileAnalyzer(ast.NodeVisitor):
    """
    分析单个 Python 文件中的 FastAPI 路由结构。
    """

    def __init__(
        self,
        *,
        module_name: str,
        relative_path: str,
    ) -> None:
        self.module_name = module_name
        self.relative_path = relative_path

        self.imports: dict[str, str] = {}
        self.string_constants: dict[str, str] = {}

        self.router_definitions: list[
            FastApiRouterDefinitionEvidence
        ] = []

        self.registrations: list[
            FastApiRouterRegistrationEvidence
        ] = []

        self.routes: list[
            _LocalRouteDefinition
        ] = []

        self.scope: list[str] = []

    def visit_Import(
        self,
        node: ast.Import,
    ) -> None:
        """
        处理：

        import app.api.routes.users as users
        """

        for alias in node.names:
            if alias.asname:
                local_name = alias.asname
            else:
                local_name = alias.name.split(
                    ".",
                    maxsplit=1,
                )[0]

            self.imports[local_name] = alias.name

        self.generic_visit(node)

    def visit_ImportFrom(
        self,
        node: ast.ImportFrom,
    ) -> None:
        """
        处理：

        from app.api.routes import users
        from app.api.routes.users import router
        from .routes import users
        """

        base_module = _resolve_import_from_module(
            current_module=self.module_name,
            imported_module=node.module,
            level=node.level,
        )

        for alias in node.names:
            if alias.name == "*":
                continue

            local_name = alias.asname or alias.name

            imported_target = ".".join(
                part
                for part in (
                    base_module,
                    alias.name,
                )
                if part
            )

            self.imports[local_name] = (
                imported_target
            )

        self.generic_visit(node)

    def visit_Assign(
        self,
        node: ast.Assign,
    ) -> None:
        """
        识别普通字符串常量以及 Router 对象。

        示例：
        API_PREFIX = "/api/v1"
        router = APIRouter(prefix="/users")
        app = FastAPI()
        """

        if len(node.targets) != 1:
            self.generic_visit(node)
            return

        target = node.targets[0]

        if not isinstance(target, ast.Name):
            self.generic_visit(node)
            return

        string_value = _evaluate_string_expression(
            node.value,
            constants=self.string_constants,
        )

        if string_value.resolved:
            self.string_constants[target.id] = (
                string_value.value
            )

        if not isinstance(node.value, ast.Call):
            self.generic_visit(node)
            return

        constructor_name = _expression_name(
            node.value.func,
        ).split(".")[-1]

        if constructor_name not in {
            "APIRouter",
            "FastAPI",
        }:
            self.generic_visit(node)
            return

        prefix = _get_call_keyword_string(
            node.value,
            keyword_name="prefix",
            constants=self.string_constants,
        )

        router_kind = (
            "fastapi_application"
            if constructor_name == "FastAPI"
            else "api_router"
        )

        router_key = (
            f"{self.module_name}.{target.id}"
        )

        self.router_definitions.append(
            FastApiRouterDefinitionEvidence(
                key=router_key,
                module_name=self.module_name,
                variable_name=target.id,
                router_kind=router_kind,
                prefix=prefix.value,
                prefix_resolved=prefix.resolved,
                file_path=self.relative_path,
                line=node.lineno,
            ),
        )

        self.generic_visit(node)

    def visit_Call(
        self,
        node: ast.Call,
    ) -> None:
        """
        识别：

        app.include_router(api_router)
        api_router.include_router(users.router)
        """

        if not isinstance(
            node.func,
            ast.Attribute,
        ):
            self.generic_visit(node)
            return

        if node.func.attr != "include_router":
            self.generic_visit(node)
            return

        parent_router_key = (
            self._resolve_router_expression(
                node.func.value,
            )
        )

        if parent_router_key is None:
            self.generic_visit(node)
            return

        child_expression_node: ast.expr | None = None

        if node.args:
            child_expression_node = node.args[0]
        else:
            for keyword in node.keywords:
                if keyword.arg == "router":
                    child_expression_node = (
                        keyword.value
                    )
                    break

        if child_expression_node is None:
            self.generic_visit(node)
            return

        child_expression = _expression_name(
            child_expression_node,
        )

        child_router_key = (
            self._resolve_router_expression(
                child_expression_node,
            )
        )

        include_prefix = (
            _get_call_keyword_string(
                node,
                keyword_name="prefix",
                constants=self.string_constants,
            )
        )

        self.registrations.append(
            FastApiRouterRegistrationEvidence(
                parent_router_key=(
                    parent_router_key
                ),
                child_router_key=(
                    child_router_key
                ),
                child_expression=child_expression,
                include_prefix=(
                    include_prefix.value
                ),
                prefix_resolved=(
                    include_prefix.resolved
                ),
                file_path=self.relative_path,
                line=node.lineno,
            ),
        )

        self.generic_visit(node)

    def visit_ClassDef(
        self,
        node: ast.ClassDef,
    ) -> None:
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
        """
        从函数装饰器中提取 HTTP 路由。
        """

        handler_name = ".".join(
            [
                self.module_name,
                *self.scope,
                node.name,
            ],
        )

        for decorator in node.decorator_list:
            route = self._extract_route_decorator(
                decorator,
            )

            if route is None:
                continue

            (
                router_key,
                method,
                local_path,
            ) = route

            self.routes.append(
                _LocalRouteDefinition(
                    router_key=router_key,
                    method=method,
                    local_path=(
                        local_path.value
                    ),
                    path_resolved=(
                        local_path.resolved
                    ),
                    handler=handler_name,
                    file_path=self.relative_path,
                    line=node.lineno,
                ),
            )

        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _extract_route_decorator(
        self,
        decorator: ast.expr,
    ) -> tuple[
        str,
        str,
        _StringExpression,
    ] | None:
        """
        识别：

        @router.get("/users")
        @app.post(path="/login")
        """

        if not isinstance(decorator, ast.Call):
            return None

        if not isinstance(
            decorator.func,
            ast.Attribute,
        ):
            return None

        method = decorator.func.attr.lower()

        if method not in HTTP_METHODS:
            return None

        router_key = (
            self._resolve_router_expression(
                decorator.func.value,
            )
        )

        if router_key is None:
            return None

        route_path = _get_call_path_string(
            decorator,
            constants=self.string_constants,
        )

        if route_path.value == "":
            route_path = _StringExpression(
                value="/",
                resolved=route_path.resolved,
            )

        return (
            router_key,
            method.upper(),
            route_path,
        )

    def _resolve_router_expression(
        self,
        expression: ast.expr,
    ) -> str | None:
        """
        将 Router 表达式转换成全限定标识。

        示例：
        router
        → app.api.routes.users.router

        users.router
        → app.api.routes.users.router
        """

        expression_name = _expression_name(
            expression,
        )

        if not expression_name:
            return None

        parts = expression_name.split(".")
        first_part = parts[0]

        imported_target = self.imports.get(
            first_part,
        )

        if imported_target is not None:
            remaining_parts = parts[1:]

            return ".".join(
                [
                    imported_target,
                    *remaining_parts,
                ],
            )

        if len(parts) == 1:
            return (
                f"{self.module_name}."
                f"{expression_name}"
            )

        return None


def analyze_fastapi_router_graph(
    repository_root: Path | str,
    *,
    max_python_files: int = (
        DEFAULT_MAX_PYTHON_FILES
    ),
    max_python_file_bytes: int = (
        DEFAULT_MAX_PYTHON_FILE_BYTES
    ),
) -> FastApiRouterAnalysis:
    """
    分析整个仓库的 FastAPI Router 注册关系。

    该函数不导入或执行仓库代码。
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

    python_files = python_files[
        :max_python_files
    ]

    router_definitions: list[
        FastApiRouterDefinitionEvidence
    ] = []

    registrations: list[
        FastApiRouterRegistrationEvidence
    ] = []

    local_routes: list[
        _LocalRouteDefinition
    ] = []

    scanned_python_file_count = 0
    parse_error_count = 0
    skipped_large_file_count = 0

    for file_path in python_files:
        try:
            file_size = file_path.stat().st_size
        except OSError:
            parse_error_count += 1
            continue

        if file_size > max_python_file_bytes:
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

        analyzer = _FastApiFileAnalyzer(
            module_name=module_name,
            relative_path=relative_path,
        )

        analyzer.visit(syntax_tree)

        router_definitions.extend(
            analyzer.router_definitions,
        )

        registrations.extend(
            analyzer.registrations,
        )

        local_routes.extend(
            analyzer.routes,
        )

        scanned_python_file_count += 1

    resolved_routes = _resolve_registered_routes(
        router_definitions=router_definitions,
        registrations=registrations,
        local_routes=local_routes,
    )

    return FastApiRouterAnalysis(
        scanned_python_file_count=(
            scanned_python_file_count
        ),
        parse_error_count=parse_error_count,
        skipped_large_file_count=(
            skipped_large_file_count
        ),
        analysis_truncated=analysis_truncated,
        router_definitions=tuple(
            sorted(
                router_definitions,
                key=lambda item: (
                    item.file_path.lower(),
                    item.line,
                    item.key.lower(),
                ),
            ),
        ),
        registrations=tuple(
            sorted(
                registrations,
                key=lambda item: (
                    item.file_path.lower(),
                    item.line,
                ),
            ),
        ),
        routes=tuple(resolved_routes),
    )


def _resolve_registered_routes(
    *,
    router_definitions: list[
        FastApiRouterDefinitionEvidence
    ],
    registrations: list[
        FastApiRouterRegistrationEvidence
    ],
    local_routes: list[_LocalRouteDefinition],
) -> list[FastApiResolvedRouteEvidence]:
    """
    沿 include_router 注册图拼接完整路径。
    """

    definition_by_key = {
        item.key: item
        for item in router_definitions
    }

    routes_by_router: dict[
        str,
        list[_LocalRouteDefinition],
    ] = {}

    for route in local_routes:
        routes_by_router.setdefault(
            route.router_key,
            [],
        ).append(route)

    registrations_by_parent: dict[
        str,
        list[FastApiRouterRegistrationEvidence],
    ] = {}

    child_router_keys: set[str] = set()

    for registration in registrations:
        registrations_by_parent.setdefault(
            registration.parent_router_key,
            [],
        ).append(registration)

        if registration.child_router_key:
            child_router_keys.add(
                registration.child_router_key,
            )

    application_roots = [
        item.key
        for item in router_definitions
        if item.router_kind
        == "fastapi_application"
    ]

    if application_roots:
        root_keys = application_roots
    else:
        root_keys = [
            item.key
            for item in router_definitions
            if item.key not in child_router_keys
        ]

    resolved_routes: list[
        FastApiResolvedRouteEvidence
    ] = []

    visited_router_keys: set[str] = set()

    for root_key in root_keys:
        _walk_router_graph(
            router_key=root_key,
            inherited_prefix="",
            inherited_complete=True,
            chain=(),
            definition_by_key=definition_by_key,
            routes_by_router=routes_by_router,
            registrations_by_parent=(
                registrations_by_parent
            ),
            active_path=set(),
            visited_router_keys=visited_router_keys,
            output=resolved_routes,
        )

    # 没有连接到 FastAPI 根节点的 Router 仍然保留，
    # 但标记 path_complete=False。
    for router_key in routes_by_router:
        if router_key in visited_router_keys:
            continue

        _walk_router_graph(
            router_key=router_key,
            inherited_prefix="",
            inherited_complete=False,
            chain=(),
            definition_by_key=definition_by_key,
            routes_by_router=routes_by_router,
            registrations_by_parent=(
                registrations_by_parent
            ),
            active_path=set(),
            visited_router_keys=visited_router_keys,
            output=resolved_routes,
        )

    unique_routes: dict[
        tuple[str, str, str, str, int],
        FastApiResolvedRouteEvidence,
    ] = {}

    for route in resolved_routes:
        key = (
            route.method,
            route.path,
            route.handler,
            route.file_path,
            route.line,
        )

        existing = unique_routes.get(key)

        if (
            existing is None
            or (
                route.path_complete
                and not existing.path_complete
            )
        ):
            unique_routes[key] = route

    return sorted(
        unique_routes.values(),
        key=lambda item: (
            item.path.lower(),
            item.method,
            item.file_path.lower(),
            item.line,
        ),
    )


def _walk_router_graph(
    *,
    router_key: str,
    inherited_prefix: str,
    inherited_complete: bool,
    chain: tuple[str, ...],
    definition_by_key: dict[
        str,
        FastApiRouterDefinitionEvidence,
    ],
    routes_by_router: dict[
        str,
        list[_LocalRouteDefinition],
    ],
    registrations_by_parent: dict[
        str,
        list[
            FastApiRouterRegistrationEvidence
        ],
    ],
    active_path: set[str],
    visited_router_keys: set[str],
    output: list[
        FastApiResolvedRouteEvidence
    ],
) -> None:
    """
    深度遍历 Router 注册图。

    active_path 用于防止错误代码造成循环注册。
    """

    if router_key in active_path:
        return

    active_path = {
        *active_path,
        router_key,
    }

    visited_router_keys.add(router_key)

    definition = definition_by_key.get(
        router_key,
    )

    if definition is None:
        router_prefix = inherited_prefix
        router_complete = False
    else:
        router_prefix = _join_route_paths(
            inherited_prefix,
            definition.prefix,
        )

        router_complete = (
            inherited_complete
            and definition.prefix_resolved
        )

    current_chain = (
        *chain,
        router_key,
    )

    for route in routes_by_router.get(
        router_key,
        [],
    ):
        full_path = _join_route_paths(
            router_prefix,
            route.local_path,
        )

        output.append(
            FastApiResolvedRouteEvidence(
                method=route.method,
                path=full_path,
                path_complete=(
                    router_complete
                    and route.path_resolved
                ),
                handler=route.handler,
                router_key=router_key,
                file_path=route.file_path,
                line=route.line,
                registration_chain=(
                    current_chain
                ),
            ),
        )

    for registration in registrations_by_parent.get(
        router_key,
        [],
    ):
        if registration.child_router_key is None:
            continue

        child_inherited_prefix = (
            _join_route_paths(
                router_prefix,
                registration.include_prefix,
            )
        )

        child_complete = (
            router_complete
            and registration.prefix_resolved
        )

        registration_description = (
            f"{registration.parent_router_key}"
            f" -> "
            f"{registration.child_router_key}"
            f" ({registration.file_path}:"
            f"{registration.line})"
        )

        _walk_router_graph(
            router_key=(
                registration.child_router_key
            ),
            inherited_prefix=(
                child_inherited_prefix
            ),
            inherited_complete=child_complete,
            chain=(
                *current_chain,
                registration_description,
            ),
            definition_by_key=definition_by_key,
            routes_by_router=routes_by_router,
            registrations_by_parent=(
                registrations_by_parent
            ),
            active_path=active_path,
            visited_router_keys=(
                visited_router_keys
            ),
            output=output,
        )


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
    """
    将相对导入转换成绝对模块路径。
    """

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

    remove_count = max(level - 1, 0)

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


def _evaluate_string_expression(
    expression: ast.expr,
    *,
    constants: dict[str, str],
) -> _StringExpression:
    """
    尝试静态解析路径字符串。

    无法解析时保留占位表达式并标记 resolved=False。
    """

    if (
        isinstance(expression, ast.Constant)
        and isinstance(expression.value, str)
    ):
        return _StringExpression(
            value=expression.value,
            resolved=True,
        )

    if isinstance(expression, ast.Name):
        constant_value = constants.get(
            expression.id,
        )

        if constant_value is not None:
            return _StringExpression(
                value=constant_value,
                resolved=True,
            )

        return _StringExpression(
            value=f"{{{expression.id}}}",
            resolved=False,
        )

    if isinstance(expression, ast.Attribute):
        expression_name = _expression_name(
            expression,
        )

        return _StringExpression(
            value=f"{{{expression_name}}}",
            resolved=False,
        )

    if (
        isinstance(expression, ast.BinOp)
        and isinstance(expression.op, ast.Add)
    ):
        left = _evaluate_string_expression(
            expression.left,
            constants=constants,
        )

        right = _evaluate_string_expression(
            expression.right,
            constants=constants,
        )

        return _StringExpression(
            value=left.value + right.value,
            resolved=(
                left.resolved
                and right.resolved
            ),
        )

    if isinstance(expression, ast.JoinedStr):
        parts: list[str] = []
        resolved = True

        for value in expression.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
                continue

            if isinstance(
                value,
                ast.FormattedValue,
            ):
                name = _expression_name(
                    value.value,
                )

                parts.append(f"{{{name}}}")
                resolved = False

        return _StringExpression(
            value="".join(parts),
            resolved=resolved,
        )

    expression_name = _expression_name(
        expression,
    )

    return _StringExpression(
        value=(
            f"{{{expression_name}}}"
            if expression_name
            else "{dynamic_prefix}"
        ),
        resolved=False,
    )


def _get_call_keyword_string(
    call: ast.Call,
    *,
    keyword_name: str,
    constants: dict[str, str],
) -> _StringExpression:
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue

        return _evaluate_string_expression(
            keyword.value,
            constants=constants,
        )

    return _StringExpression(
        value="",
        resolved=True,
    )


def _get_call_path_string(
    call: ast.Call,
    *,
    constants: dict[str, str],
) -> _StringExpression:
    if call.args:
        return _evaluate_string_expression(
            call.args[0],
            constants=constants,
        )

    return _get_call_keyword_string(
        call,
        keyword_name="path",
        constants=constants,
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


def _module_name_from_path(
    relative_path: str,
) -> str:
    path = Path(relative_path)

    parts = list(path.parts)

    if not parts:
        return ""

    parts[-1] = Path(parts[-1]).stem

    if parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts)


def _join_route_paths(
    *path_parts: str,
) -> str:
    normalized_parts = [
        part.strip("/")
        for part in path_parts
        if part and part != "/"
    ]

    if not normalized_parts:
        return "/"

    return "/" + "/".join(
        normalized_parts,
    )