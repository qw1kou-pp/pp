from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import RepositoryAnalysisTask
from app.services.github_repository_client import (
    GitHubRepositoryAcquisition,
)
from app.services.github_repository_snapshot import (
    GitHubRepositorySnapshot,
)
from app.services.repository_structure_scanner import (
    RepositoryScanResult,
)
from app.services.repository_code_analyzer import (
    RepositoryCodeAnalysis,
)
from app.services.repository_fastapi_router_analyzer import (
    FastApiRouterAnalysis,
)
from app.services.repository_backend_flow_analyzer import (
    RepositoryBackendFlowAnalysis,
)
from app.services.repository_frontend_flow_analyzer import (
    RepositoryFrontendFlowAnalysis,
)
from app.services.repository_analysis_compactor import (
    compact_repository_analysis_payload,
)


@dataclass(frozen=True, slots=True)
class RepositoryAnalysisOutput:
    """仓库分析处理器的统一输出。"""

    result_json: dict[str, Any]
    evidence_json: dict[str, Any]
    report_markdown: str


def build_repository_overview_analysis(
    *,
    task: RepositoryAnalysisTask,
    acquisition: GitHubRepositoryAcquisition,
    snapshot: GitHubRepositorySnapshot,
    scan: RepositoryScanResult,
    code_analysis: RepositoryCodeAnalysis,
    fastapi_router_analysis: FastApiRouterAnalysis,
    backend_flow_analysis: (
        RepositoryBackendFlowAnalysis
    ),
    frontend_flow_analysis: (
        RepositoryFrontendFlowAnalysis
    ),
) -> RepositoryAnalysisOutput:
    """
    根据真实 GitHub 元数据生成阶段性报告。

    当前已经访问 GitHub 并固定 Commit，
    但尚未下载和扫描仓库文件。
    """

    metadata = acquisition.metadata
    commit = acquisition.commit

    complexity = _assess_repository_complexity(
        scan,
    )

    deep_analysis = _build_deep_analysis_recommendation(
        scan,
    )

    result_json = {
        "schema_version": "1.0",
        "analysis_kind": "repository_overview",
        "repository": {
            "owner": metadata.owner,
            "name": metadata.name,
            "full_name": metadata.full_name,
            "html_url": metadata.html_url,
            "description": metadata.description,
            "default_branch": metadata.default_branch,
            "resolved_ref": commit.requested_ref,
            "resolved_commit_sha": commit.sha,
            "primary_language": (
                metadata.primary_language
            ),
            "topics": list(metadata.topics),
            "license_spdx_id": (
                metadata.license_spdx_id
            ),
            "archived": metadata.archived,
            "fork": metadata.fork,
        },
        "snapshot": {
            "source": snapshot.source,
            "commit_sha": snapshot.commit_sha,
            "compressed_bytes": (
                snapshot.compressed_bytes
            ),
            "uncompressed_bytes": (
                snapshot.uncompressed_bytes
            ),
            "file_count": snapshot.file_count,
        },
        "overview": {
            "project_title": scan.project_title,
            "project_summary": scan.project_summary,
            "readme_path": scan.readme_path,
        },
        "technology_stack": {
            "language_file_counts": (
                scan.language_file_counts
            ),
            "manifests": list(scan.manifests),
            "dependency_names": list(
                scan.dependency_names,
            ),
        },
        "architecture": {
            "tree": list(scan.tree),
            "module_paths": list(
                scan.module_paths,
            ),
            "entry_points": list(
                scan.entry_points,
            ),
        },
        "code_analysis": (
            code_analysis.to_dict()
        ),
        "fastapi_router_analysis": (
            fastapi_router_analysis.to_dict()
        ),
        "backend_flow_analysis": (
            backend_flow_analysis.to_dict()
        ),
        "frontend_flow_analysis": (
            frontend_flow_analysis.to_dict()
        ),
        "delivery": {
            "deployment_files": list(
                scan.deployment_files,
            ),
            "ci_files": list(scan.ci_files),
            "migration_paths": list(
                scan.migration_paths,
            ),
            "test_paths": list(
                scan.test_paths,
            ),
        },
        "scan_statistics": {
            "scanned_file_count": (
                scan.scanned_file_count
            ),
            "ignored_directory_count": (
                scan.ignored_directory_count
            ),
            "skipped_large_file_count": (
                scan.skipped_large_file_count
            ),
            "scan_truncated": (
                scan.scan_truncated
            ),
        },
        "learning_assessment": complexity,
        "deep_analysis_recommendation": (
            deep_analysis
        ),
        "capabilities": {
            "github_metadata_collected": True,
            "commit_resolved": True,
            "snapshot_downloaded": True,
            "snapshot_safely_extracted": True,
            "repository_scanned": True,
            "python_ast_analyzed": True,
            "frontend_patterns_analyzed": True,
            "backend_business_flows_traced": True,
            "frontend_business_flows_traced": True,
            "full_stack_flows_matched": True,
            "evidence_built_from_files": True,
            "llm_report_generated": False,
        },
        "next_stage": "llm_report_organization",
    }

    evidence_json = {
        "schema_version": "1.0",
        "status": "repository_scanned",
        "items": [
            {
                "id": "E-001",
                "type": "github_repository_metadata",
                "source": "github_rest_api",
                "facts": {
                    "full_name": metadata.full_name,
                    "description": metadata.description,
                    "default_branch": (
                        metadata.default_branch
                    ),
                    "primary_language": (
                        metadata.primary_language
                    ),
                    "topics": list(metadata.topics),
                    "archived": metadata.archived,
                    "fork": metadata.fork,
                },
            },
            {
                "id": "E-002",
                "type": "github_resolved_commit",
                "source": "github_rest_api",
                "facts": {
                    "requested_ref": (
                        commit.requested_ref
                    ),
                    "sha": commit.sha,
                    "message": commit.message,
                    "author_name": (
                        commit.author_name
                    ),
                    "authored_at": (
                        commit.authored_at
                    ),
                },
            },
            {
                "id": "E-003",
                "type": "github_repository_snapshot",
                "source": "github_zip",
                "facts": {
                    "commit_sha": snapshot.commit_sha,
                    "compressed_bytes": (
                        snapshot.compressed_bytes
                    ),
                    "uncompressed_bytes": (
                        snapshot.uncompressed_bytes
                    ),
                    "file_count": snapshot.file_count,
                    "safely_extracted": True,
                },
            },
            {
                "id": "E-004",
                "type": "repository_tree",
                "source": "repository_filesystem",
                "facts": {
                    "tree": list(scan.tree),
                    "module_paths": list(
                        scan.module_paths,
                    ),
                },
            },
            {
                "id": "E-005",
                "type": "language_distribution",
                "source": "file_extensions",
                "facts": {
                    "file_counts": (
                        scan.language_file_counts
                    ),
                },
            },
            {
                "id": "E-006",
                "type": "dependency_manifests",
                "source": "repository_filesystem",
                "facts": {
                    "manifests": list(
                        scan.manifests,
                    ),
                    "dependencies": list(
                        scan.dependency_names,
                    ),
                },
            },
            {
                "id": "E-007",
                "type": "readme",
                "source": "repository_file",
                "file_path": scan.readme_path,
                "facts": {
                    "project_title": (
                        scan.project_title
                    ),
                    "project_summary": (
                        scan.project_summary
                    ),
                    "excerpt": scan.readme_excerpt,
                },
            },
            {
                "id": "E-008",
                "type": "entry_points",
                "source": "repository_filesystem",
                "facts": {
                    "paths": list(
                        scan.entry_points,
                    ),
                },
            },
            {
                "id": "E-009",
                "type": "deployment_configuration",
                "source": "repository_filesystem",
                "facts": {
                    "paths": list(
                        scan.deployment_files,
                    ),
                },
            },
            {
                "id": "E-010",
                "type": "continuous_integration",
                "source": "repository_filesystem",
                "facts": {
                    "paths": list(scan.ci_files),
                },
            },
            {
                "id": "E-011",
                "type": "database_migrations",
                "source": "repository_filesystem",
                "facts": {
                    "paths": list(
                        scan.migration_paths,
                    ),
                },
            },
            {
                "id": "E-012",
                "type": "test_structure",
                "source": "repository_filesystem",
                "facts": {
                    "paths": list(
                        scan.test_paths,
                    ),
                },
            },
            {
                "id": "E-013",
                "type": "scan_statistics",
                "source": "repository_scanner",
                "facts": {
                    "scanned_file_count": (
                        scan.scanned_file_count
                    ),
                    "ignored_directory_count": (
                        scan.ignored_directory_count
                    ),
                    "skipped_large_file_count": (
                        scan.skipped_large_file_count
                    ),
                    "scan_truncated": (
                        scan.scan_truncated
                    ),
                },
            },
            {
                "id": "E-014",
                "type": "backend_routes",
                "source": "python_ast",
                "facts": {
                    "routes": [
                        {
                            "method": item.method,
                            "path": item.path,
                            "handler": item.handler,
                            "file_path": item.file_path,
                            "line": item.line,
                        }
                        for item
                        in code_analysis.backend_routes
                    ],
                },
            },
            {
                "id": "E-015",
                "type": "data_models",
                "source": "python_ast",
                "facts": {
                    "models": [
                        {
                            "name": item.name,
                            "model_kind": (
                                item.model_kind
                            ),
                            "fields": list(
                                item.fields,
                            ),
                            "file_path": (
                                item.file_path
                            ),
                            "line": item.line,
                        }
                        for item
                        in code_analysis.data_models
                    ],
                },
            },
            {
                "id": "E-016",
                "type": "python_call_edges",
                "source": "python_ast",
                "facts": {
                    "edges": [
                        {
                            "caller": item.caller,
                            "callee": item.callee,
                            "file_path": (
                                item.file_path
                            ),
                            "line": item.line,
                        }
                        for item
                        in code_analysis.call_edges[
                           :500
                           ]
                    ],
                    "truncated": (
                            len(
                                code_analysis.call_edges
                            )
                            > 500
                    ),
                },
            },
            {
                "id": "E-017",
                "type": "frontend_routes",
                "source": (
                    "javascript_typescript_static_scan"
                ),
                "facts": {
                    "routes": [
                        {
                            "path": item.path,
                            "source_kind": (
                                item.source_kind
                            ),
                            "file_path": (
                                item.file_path
                            ),
                            "line": item.line,
                        }
                        for item
                        in code_analysis.frontend_routes
                    ],
                },
            },
            {
                "id": "E-018",
                "type": "frontend_api_calls",
                "source": (
                    "javascript_typescript_static_scan"
                ),
                "facts": {
                    "calls": [
                        {
                            "method": item.method,
                            "url": item.url,
                            "source_kind": (
                                item.source_kind
                            ),
                            "file_path": (
                                item.file_path
                            ),
                            "line": item.line,
                        }
                        for item
                        in code_analysis.frontend_api_calls
                    ],
                },
            },
            {
                "id": "E-019",
                "type": "possible_business_flows",
                "source": "deterministic_path_matching",
                "facts": {
                    "flows": [
                        {
                            "frontend_method": (
                                item.frontend_method
                            ),
                            "frontend_url": (
                                item.frontend_url
                            ),
                            "frontend_file_path": (
                                item.frontend_file_path
                            ),
                            "frontend_line": (
                                item.frontend_line
                            ),
                            "backend_method": (
                                item.backend_method
                            ),
                            "backend_path": (
                                item.backend_path
                            ),
                            "backend_handler": (
                                item.backend_handler
                            ),
                            "backend_file_path": (
                                item.backend_file_path
                            ),
                            "backend_line": (
                                item.backend_line
                            ),
                        }
                        for item
                        in code_analysis.business_flows
                    ],
                },
            },
            {
                "id": "E-020",
                "type": "fastapi_router_registration_graph",
                "source": "python_ast",
                "facts": {
                    "router_definitions": [
                        {
                            "key": item.key,
                            "router_kind": (
                                item.router_kind
                            ),
                            "prefix": item.prefix,
                            "prefix_resolved": (
                                item.prefix_resolved
                            ),
                            "file_path": (
                                item.file_path
                            ),
                            "line": item.line,
                        }
                        for item
                        in fastapi_router_analysis.router_definitions
                    ],
                    "registrations": [
                        {
                            "parent_router_key": (
                                item.parent_router_key
                            ),
                            "child_router_key": (
                                item.child_router_key
                            ),
                            "include_prefix": (
                                item.include_prefix
                            ),
                            "prefix_resolved": (
                                item.prefix_resolved
                            ),
                            "file_path": (
                                item.file_path
                            ),
                            "line": item.line,
                        }
                        for item
                        in fastapi_router_analysis.registrations
                    ],
                    "resolved_routes": [
                        {
                            "method": item.method,
                            "path": item.path,
                            "path_complete": (
                                item.path_complete
                            ),
                            "handler": item.handler,
                            "file_path": (
                                item.file_path
                            ),
                            "line": item.line,
                            "registration_chain": list(
                                item.registration_chain,
                            ),
                        }
                        for item
                        in fastapi_router_analysis.routes
                    ],
                },
            },
            {
                "id": "E-021",
                "type": "backend_business_flows",
                "source": "python_ast_call_graph",
                "facts": {
                    "route_flows": [
                        {
                            "method": item.method,
                            "path": item.path,
                            "path_complete": (
                                item.path_complete
                            ),
                            "handler": item.handler,
                            "handler_resolved": (
                                item.handler_resolved
                            ),
                            "call_paths": [
                                {
                                    "steps": [
                                        {
                                            "order": step.order,
                                            "symbol": (
                                                step.symbol
                                            ),
                                            "name": step.name,
                                            "kind": step.kind,
                                            "layer": step.layer,
                                            "file_path": (
                                                step.file_path
                                            ),
                                            "line": step.line,
                                        }
                                        for step
                                        in path.steps
                                    ],
                                    "terminal_reason": (
                                        path.terminal_reason
                                    ),
                                }
                                for path
                                in item.call_paths
                            ],
                            "model_usages": [
                                {
                                    "caller": model.caller,
                                    "model": model.model,
                                    "usage_kind": (
                                        model.usage_kind
                                    ),
                                    "file_path": (
                                        model.file_path
                                    ),
                                    "line": model.line,
                                }
                                for model
                                in item.model_usages
                            ],
                            "database_operations": [
                                {
                                    "caller": operation.caller,
                                    "operation_kind": (
                                        operation.operation_kind
                                    ),
                                    "expression": (
                                        operation.expression
                                    ),
                                    "file_path": (
                                        operation.file_path
                                    ),
                                    "line": operation.line,
                                }
                                for operation
                                in item.database_operations
                            ],
                            "paths_truncated": (
                                item.paths_truncated
                            ),
                        }
                        for item
                        in backend_flow_analysis.route_flows
                    ],
                },
            },
            {
                "id": "E-022",
                "type": "frontend_and_full_stack_flows",
                "source": (
                    "javascript_typescript_static_call_graph"
                ),
                "facts": {
                    "statistics": {
                        "scanned_frontend_file_count": (
                            frontend_flow_analysis
                                .scanned_frontend_file_count
                        ),
                        "skipped_large_file_count": (
                            frontend_flow_analysis
                                .skipped_large_file_count
                        ),
                        "read_error_count": (
                            frontend_flow_analysis
                                .read_error_count
                        ),
                        "analysis_truncated": (
                            frontend_flow_analysis
                                .analysis_truncated
                        ),
                    },
                    "pages": [
                        {
                            "route_path": (
                                item.route_path
                            ),
                            "component_symbol": (
                                item.component_symbol
                            ),
                            "source_kind": (
                                item.source_kind
                            ),
                            "file_path": (
                                item.file_path
                            ),
                            "line": item.line,
                        }
                        for item
                        in frontend_flow_analysis.pages
                    ],
                    "http_operations": [
                        {
                            "operation_name": (
                                item.operation_name
                            ),
                            "method": item.method,
                            "path": item.path,
                            "source_kind": (
                                item.source_kind
                            ),
                            "file_path": (
                                item.file_path
                            ),
                            "line": item.line,
                        }
                        for item
                        in frontend_flow_analysis.http_operations
                    ],
                    "full_stack_flows": [
                        {
                            "frontend_route": (
                                item.frontend_route
                            ),
                            "frontend_component": (
                                item.frontend_component
                            ),
                            "frontend_call_chain": list(
                                item.frontend_call_chain,
                            ),
                            "http_method": (
                                item.http_method
                            ),
                            "request_path": (
                                item.request_path
                            ),
                            "client_operation": (
                                item.client_operation
                            ),
                            "backend_path": (
                                item.backend_path
                            ),
                            "backend_handler": (
                                item.backend_handler
                            ),
                            "backend_match_kind": (
                                item.backend_match_kind
                            ),
                            "backend_path_complete": (
                                item.backend_path_complete
                            ),
                            "backend_call_paths": [
                                list(path)
                                for path
                                in item.backend_call_paths
                            ],
                            "data_models": list(
                                item.data_models,
                            ),
                            "database_operations": list(
                                item.database_operations,
                            ),
                        }
                        for item
                        in frontend_flow_analysis.full_stack_flows[
                           :200
                           ]
                    ],
                    "full_stack_flows_truncated": (
                            len(
                                frontend_flow_analysis
                                    .full_stack_flows
                            )
                            > 200
                    ),
                },
            },
        ],
    }

    report_markdown = _build_chinese_report(
        task=task,
        acquisition=acquisition,
        snapshot=snapshot,
        scan=scan,
        code_analysis=code_analysis,
        fastapi_router_analysis=fastapi_router_analysis,
        backend_flow_analysis=backend_flow_analysis,
        frontend_flow_analysis=frontend_flow_analysis,
    )

    if task.report_language == "en-US":
        report_markdown = _build_english_report(
            task=task,
            acquisition=acquisition,
            snapshot=snapshot,
            scan=scan,
            code_analysis=code_analysis,
        )

    compacted_payload = (
        compact_repository_analysis_payload(
            result_json=result_json,
            evidence_json=evidence_json,
            report_markdown=report_markdown,
        )
    )

    return RepositoryAnalysisOutput(
        result_json=(
            compacted_payload.result_json
        ),
        evidence_json=(
            compacted_payload.evidence_json
        ),
        report_markdown=(
            compacted_payload.report_markdown
        ),
    )


def _format_language_counts(
    language_counts: dict[str, int],
) -> str:
    if not language_counts:
        return "- 暂未识别代码语言"

    return "\n".join(
        (
            f"- {language}："
            f"{file_count} 个文件"
        )
        for language, file_count
        in language_counts.items()
    )


def _build_chinese_report(
    *,
    task: RepositoryAnalysisTask,
    acquisition: GitHubRepositoryAcquisition,
    snapshot: GitHubRepositorySnapshot,
    scan: RepositoryScanResult,
    code_analysis: RepositoryCodeAnalysis,
    fastapi_router_analysis: FastApiRouterAnalysis,
    backend_flow_analysis: RepositoryBackendFlowAnalysis,
    frontend_flow_analysis: RepositoryFrontendFlowAnalysis,
) -> str:
    metadata = acquisition.metadata
    commit = acquisition.commit

    project_summary = (
        scan.project_summary
        or metadata.description
        or "当前未从 README 或 GitHub 元数据中提取到明确简介。"
    )

    languages = _format_language_counts(
        scan.language_file_counts,
    )

    manifests = _format_markdown_items(
        scan.manifests,
        empty_text="未识别到常见依赖清单",
    )

    modules = _format_markdown_items(
        scan.module_paths,
        empty_text="未识别到明显的主要模块目录",
    )

    entry_points = _format_markdown_items(
        scan.entry_points,
        empty_text="未识别到常见程序入口",
    )

    backend_route_lines = [
        (
            f"- `{item.method} {item.path}` "
            f"→ `{item.handler}` "
            f"（`{item.file_path}:{item.line}`，"
            f"完整路径：`{item.path_complete}`）"
        )
        for item
        in fastapi_router_analysis.routes[:40]
    ]

    backend_routes = (
        "\n".join(backend_route_lines)
        if backend_route_lines
        else "- 暂未识别到 FastAPI 路由"
    )

    backend_flow_sections: list[str] = []

    for route_flow in (
        backend_flow_analysis.route_flows[:20]
    ):
        route_title = (
            f"### `{route_flow.method} "
            f"{route_flow.path}`"
        )

        lines = [
            route_title,
            "",
            (
                f"- Handler："
                f"`{route_flow.handler}`"
            ),
            (
                f"- Handler 已解析："
                f"`{route_flow.handler_resolved}`"
            ),
        ]

        if route_flow.call_paths:
            lines.extend(
                [
                    "",
                    "静态调用路径：",
                ],
            )

            for path_index, call_path in enumerate(
                route_flow.call_paths[:5],
                start=1,
            ):
                chain = " → ".join(
                    (
                        f"{step.name}"
                        f"[{step.layer}]"
                    )
                    for step
                    in call_path.steps
                )

                lines.append(
                    (
                        f"- 路径 {path_index}："
                        f"{chain}"
                    ),
                )
        else:
            lines.extend(
                [
                    "",
                    "- 未解析到内部调用路径",
                ],
            )

        if route_flow.model_usages:
            lines.extend(
                [
                    "",
                    "涉及的数据模型：",
                ],
            )

            for model in (
                route_flow.model_usages[:10]
            ):
                lines.append(
                    (
                        f"- `{model.model}` "
                        f"（{model.usage_kind}，"
                        f"`{model.file_path}:"
                        f"{model.line}`）"
                    ),
                )

        if route_flow.database_operations:
            lines.extend(
                [
                    "",
                    "可能的数据库操作：",
                ],
            )

            for operation in (
                route_flow
                .database_operations[:15]
            ):
                lines.append(
                    (
                        f"- "
                        f"`{operation.expression}` "
                        f"→ "
                        f"`{operation.operation_kind}` "
                        f"（`{operation.file_path}:"
                        f"{operation.line}`）"
                    ),
                )

        backend_flow_sections.append(
            "\n".join(lines),
        )

    backend_flows_markdown = (
        "\n\n".join(
            backend_flow_sections,
        )
        if backend_flow_sections
        else "- 暂未生成后端业务调用链"
    )

    full_stack_flow_sections: list[str] = []

    for flow in (
            frontend_flow_analysis.full_stack_flows[:20]
    ):
        frontend_chain = " → ".join(
            symbol.split(":")[-1]
            for symbol
            in flow.frontend_call_chain
        )

        if not frontend_chain:
            frontend_chain = "未解析"

        if flow.backend_call_paths:
            backend_chain = " → ".join(
                symbol.split(".")[-1]
                for symbol
                in flow.backend_call_paths[0]
            )
        else:
            backend_chain = "未解析到后端内部调用链"

        models_text = (
            "、".join(
                f"`{model}`"
                for model
                in flow.data_models
            )
            if flow.data_models
            else "未识别"
        )

        database_text = (
            "、".join(
                f"`{operation}`"
                for operation
                in flow.database_operations
            )
            if flow.database_operations
            else "未识别"
        )

        lines = [
            (
                f"### `{flow.frontend_route}`"
            ),
            "",
            (
                f"- 前端调用：{frontend_chain}"
            ),
            (
                f"- HTTP 请求："
                f"`{flow.http_method} "
                f"{flow.request_path}`"
            ),
            (
                f"- Client 操作："
                f"`{flow.client_operation}`"
            ),
            (
                f"- 后端路由："
                f"`{flow.backend_path or '未匹配'}`"
            ),
            (
                f"- 后端 Handler："
                f"`{flow.backend_handler or '未匹配'}`"
            ),
            (
                f"- 匹配方式："
                f"`{flow.backend_match_kind}`"
            ),
            (
                f"- 后端调用：{backend_chain}"
            ),
            (
                f"- 数据模型：{models_text}"
            ),
            (
                f"- 数据库操作：{database_text}"
            ),
        ]

        full_stack_flow_sections.append(
            "\n".join(lines),
        )

    full_stack_flows_markdown = (
        "\n\n".join(
            full_stack_flow_sections,
        )
        if full_stack_flow_sections
        else (
            "- 暂未恢复出完整的前端到后端业务闭环"
        )
    )

    model_lines = [
        (
            f"- `{item.name}` "
            f"（{item.model_kind}，"
            f"`{item.file_path}:{item.line}`）"
        )
        for item
        in code_analysis.data_models[:30]
    ]

    models = (
        "\n".join(model_lines)
        if model_lines
        else "- 暂未识别到 SQLModel 或 Pydantic 模型"
    )

    frontend_call_lines = [
        (
            f"- `{item.method} {item.url}` "
            f"（`{item.file_path}:{item.line}`）"
        )
        for item
        in code_analysis.frontend_api_calls[:30]
    ]

    frontend_calls = (
        "\n".join(frontend_call_lines)
        if frontend_call_lines
        else "- 暂未识别到 fetch 或 axios 请求"
    )

    business_flow_lines = [
        (
            f"- `{item.frontend_method} "
            f"{item.frontend_url}` "
            f"→ `{item.backend_handler}` "
            f"→ `{item.backend_method} "
            f"{item.backend_path}`"
        )
        for item
        in code_analysis.business_flows[:30]
    ]

    business_flows = (
        "\n".join(business_flow_lines)
        if business_flow_lines
        else (
            "- 暂未通过 URL 和 HTTP 方法匹配到"
            "明确的前后端请求闭环"
        )
    )

    deployment = _format_markdown_items(
        scan.deployment_files,
        empty_text="未识别到常见部署配置",
    )

    ci_files = _format_markdown_items(
        scan.ci_files,
        empty_text="未识别到常见 CI 配置",
    )

    tests = _format_markdown_items(
        scan.test_paths,
        empty_text="未识别到明显测试文件",
        limit=20,
    )

    migrations = _format_markdown_items(
        scan.migration_paths,
        empty_text="未识别到数据库迁移结构",
        limit=20,
    )

    complexity = _assess_repository_complexity(
        scan,
    )

    recommendation = (
        _build_deep_analysis_recommendation(
            scan,
        )
    )

    recommendation_text = (
        "建议进入深度分析"
        if recommendation["recommended"]
        else "可根据需要进入深度分析"
    )

    scan_notice = (
        "本次扫描达到文件数量上限，"
        "以下结果来自确定性采样。"
        if scan.scan_truncated
        else "本次扫描未触发文件数量截断。"
    )

    return f"""# {scan.project_title} 仓库概览

> 分析仓库：`{metadata.full_name}`
>
> 固定 Commit：`{commit.sha}`
>
> 当前报告基于 GitHub 元数据、固定 Commit 快照和确定性文件扫描。
> 尚未调用大模型进行深层调用链和业务逻辑解释。

## 一、项目方向

{project_summary}

证据来源：

- GitHub 仓库元数据 `[E-001]`
- README：`{scan.readme_path or "未识别"}` `[E-007]`

## 二、主要技术栈

### 文件语言分布

{languages}

### 依赖与构建清单

{manifests}

以上信息分别来自 `[E-005]` 和 `[E-006]`。

## 三、目录与模块结构

{modules}

主要目录树证据见 `[E-004]`。

## 四、可能的程序入口

{entry_points}

这些入口只是根据文件名称和位置识别，
下一阶段才会继续追踪函数、路由和调用关系。

## 五、后端 API 路由

{backend_routes}

证据来源：FastAPI Router 注册图 `[E-020]`。

其中“完整路径=False”表示部分前缀来自动态配置，
静态分析无法确认其最终运行值。

## 六、后端业务调用链

{backend_flows_markdown}

证据来源：Python AST、Import 解析和调用图遍历 `[E-021]`。

> 这些结果是静态分析结果。动态依赖注入、运行时分派、
> 工厂模式和反射调用可能无法完整恢复。

## 前后端业务闭环

{full_stack_flows_markdown}

证据来源：前端静态调用图、生成客户端请求配置、
FastAPI Router 注册图和后端调用图 `[E-022]`。

> `exact` 表示前后端路径完整匹配；
> `suffix` 表示忽略统一 API 前缀后唯一匹配；
> `unmatched` 表示当前静态信息不足，系统没有强行猜测。

## 七、数据模型

{models}

证据来源：Python AST `[E-015]`。

## 八、前端 API 请求

{frontend_calls}

证据来源：JavaScript/TypeScript 静态扫描 `[E-018]`。

## 九、可能的业务请求闭环

{business_flows}

以上闭环根据 HTTP 方法和路径确定性匹配 `[E-019]`，
尚未经过浏览器或运行时请求验证。

## 十、部署方式

{deployment}

## 十一、持续集成

{ci_files}

## 十二、数据库与迁移

{migrations}

## 十三、测试结构

{tests}

## 十四、仓库规模

- 快照文件数量：`{snapshot.file_count}`
- 实际扫描文件数量：`{scan.scanned_file_count}`
- 忽略目录数量：`{scan.ignored_directory_count}`
- 跳过的大文件数量：`{scan.skipped_large_file_count}`
- 扫描是否截断：`{scan.scan_truncated}`

{scan_notice}

## 十五、学习难度初步判断

- 难度：**{complexity["label"]}**
- 启发式分数：`{complexity["score"]}`

判断依据：

{chr(10).join(f"- {reason}" for reason in complexity["reasons"])}

> 该判断只基于文件规模、语言数量和目录结构，
> 不代表项目代码质量。

## 十六、是否值得继续分析

结论：**{recommendation_text}**

原因：

{chr(10).join(f"- {reason}" for reason in recommendation["reasons"]) or "- 当前可分析结构较少"}

## 十七、当前限制

本阶段尚未完成：

- 函数级调用链追踪
- API 路由与 Service 映射
- 数据模型关系分析
- 前后端请求闭环分析
- 关键业务流程解释
- 代码风险和架构问题分析
- 大模型辅助报告组织

下一阶段将以入口文件、路由、Service 和模型文件为起点，
进行深度架构与业务调用链分析。
"""


def _build_english_report(
    *,
    task: RepositoryAnalysisTask,
    acquisition: GitHubRepositoryAcquisition,
    snapshot: GitHubRepositorySnapshot,
    scan: RepositoryScanResult,
    code_analysis: RepositoryCodeAnalysis,
) -> str:
    metadata = acquisition.metadata
    commit = acquisition.commit

    description = (
        metadata.description
        or "No repository description was provided."
    )

    language = (
        metadata.primary_language
        or "Not detected"
    )

    topics = (
        ", ".join(metadata.topics)
        if metadata.topics
        else "None"
    )

    return f"""# Initial analysis: {metadata.full_name}

> This report is based on GitHub metadata and an immutable commit.
> Repository files have not been downloaded or scanned yet.

## Repository

- Repository: `{metadata.full_name}`
- Description: {description}
- Primary language: `{language}`
- Default branch: `{metadata.default_branch}`
- Topics: {topics}
- Archived: `{metadata.archived}`
- Fork: `{metadata.fork}`

## Immutable analysis version

- Requested ref: `{commit.requested_ref}`
- Commit SHA: `{commit.sha}`
- Commit message: {commit.message}
- Commit author: {commit.author_name or "Unknown"}

## Evidence

- `E-001`: GitHub repository metadata
- `E-002`: Resolved GitHub commit
- `E-003`：Commit ZIP snapshot

## Current limitation

Repository files, architecture, dependencies,
deployment configuration, tests, and business modules
have not been analyzed yet.

## Next stage

The next stage will download the repository snapshot
for commit `{commit.sha}`.
"""

def _assess_repository_complexity(
    scan: RepositoryScanResult,
) -> dict[str, Any]:
    """
    根据仓库规模和结构给出初步学习难度。

    这是启发式判断，不是代码质量评价。
    """

    language_count = len(
        scan.language_file_counts,
    )

    manifest_count = len(scan.manifests)
    module_count = len(scan.module_paths)

    score = 0
    reasons: list[str] = []

    if scan.scanned_file_count >= 1_000:
        score += 2
        reasons.append("仓库文件数量较多")
    elif scan.scanned_file_count >= 300:
        score += 1
        reasons.append("仓库具有一定规模")

    if language_count >= 4:
        score += 2
        reasons.append("涉及多种编程语言")
    elif language_count >= 2:
        score += 1
        reasons.append("涉及前后端或多语言结构")

    if manifest_count >= 4:
        score += 1
        reasons.append("存在多个依赖或构建系统")

    if module_count >= 8:
        score += 1
        reasons.append("主要模块数量较多")

    if scan.deployment_files:
        score += 1
        reasons.append("包含部署配置")

    if scan.migration_paths:
        score += 1
        reasons.append("包含数据库迁移结构")

    if score >= 6:
        level = "high"
        label = "较高"
    elif score >= 3:
        level = "medium"
        label = "中等"
    else:
        level = "low"
        label = "较低"

    if not reasons:
        reasons.append(
            "当前扫描到的仓库结构相对简单",
        )

    return {
        "level": level,
        "label": label,
        "score": score,
        "reasons": reasons,
        "notice": (
            "该结果只根据文件规模、语言和目录结构"
            "进行启发式判断。"
        ),
    }


def _build_deep_analysis_recommendation(
    scan: RepositoryScanResult,
) -> dict[str, Any]:
    """
    判断该仓库是否值得进入深度分析。

    只衡量是否有足够结构可继续分析，
    不判断项目本身质量高低。
    """

    reasons: list[str] = []

    if scan.readme_path:
        reasons.append(
            "存在 README，可进一步分析项目定位",
        )

    if scan.entry_points:
        reasons.append(
            "识别到程序入口，可继续分析调用链",
        )

    if scan.manifests:
        reasons.append(
            "识别到依赖清单，可继续分析技术栈",
        )

    if scan.module_paths:
        reasons.append(
            "识别到主要模块，可继续分析架构",
        )

    if scan.test_paths:
        reasons.append(
            "存在测试结构，可继续分析质量保障方式",
        )

    if scan.deployment_files:
        reasons.append(
            "存在部署配置，可继续分析运行方式",
        )

    recommended = len(reasons) >= 3

    return {
        "recommended": recommended,
        "level": (
            "recommended"
            if recommended
            else "optional"
        ),
        "reasons": reasons,
    }

def _format_markdown_items(
    items: tuple[str, ...] | list[str],
    *,
    empty_text: str,
    limit: int = 30,
) -> str:
    if not items:
        return f"- {empty_text}"

    visible_items = list(items)[:limit]

    lines = [
        f"- `{item}`"
        for item in visible_items
    ]

    hidden_count = len(items) - len(visible_items)

    if hidden_count > 0:
        lines.append(
            f"- 另有 {hidden_count} 项未在概览中展开"
        )

    return "\n".join(lines)


