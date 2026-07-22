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
        ],
    }

    report_markdown = _build_chinese_report(
        task=task,
        acquisition=acquisition,
        snapshot=snapshot,
        scan=scan,
        code_analysis=code_analysis,
    )

    if task.report_language == "en-US":
        report_markdown = _build_english_report(
            task=task,
            acquisition=acquisition,
            snapshot=snapshot,
            scan=scan,
            code_analysis=code_analysis,
        )

    return RepositoryAnalysisOutput(
        result_json=result_json,
        evidence_json=evidence_json,
        report_markdown=report_markdown,
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
            f"（`{item.file_path}:{item.line}`）"
        )
        for item
        in code_analysis.backend_routes[:30]
    ]

    backend_routes = (
        "\n".join(backend_route_lines)
        if backend_route_lines
        else "- 暂未识别到 FastAPI 路由"
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

证据来源：Python AST `[E-014]`。

## 六、数据模型

{models}

证据来源：Python AST `[E-015]`。

## 七、前端 API 请求

{frontend_calls}

证据来源：JavaScript/TypeScript 静态扫描 `[E-018]`。

## 八、可能的业务请求闭环

{business_flows}

以上闭环根据 HTTP 方法和路径确定性匹配 `[E-019]`，
尚未经过浏览器或运行时请求验证。

## 九、部署方式

{deployment}

## 十、持续集成

{ci_files}

## 十一、数据库与迁移

{migrations}

## 十二、测试结构

{tests}

## 十三、仓库规模

- 快照文件数量：`{snapshot.file_count}`
- 实际扫描文件数量：`{scan.scanned_file_count}`
- 忽略目录数量：`{scan.ignored_directory_count}`
- 跳过的大文件数量：`{scan.skipped_large_file_count}`
- 扫描是否截断：`{scan.scan_truncated}`

{scan_notice}

## 十四、学习难度初步判断

- 难度：**{complexity["label"]}**
- 启发式分数：`{complexity["score"]}`

判断依据：

{chr(10).join(f"- {reason}" for reason in complexity["reasons"])}

> 该判断只基于文件规模、语言数量和目录结构，
> 不代表项目代码质量。

## 十五、是否值得继续分析

结论：**{recommendation_text}**

原因：

{chr(10).join(f"- {reason}" for reason in recommendation["reasons"]) or "- 当前可分析结构较少"}

## 十六、当前限制

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


