from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import RepositoryAnalysisTask
from app.services.github_repository_client import (
    GitHubRepositoryAcquisition,
)


@dataclass(frozen=True, slots=True)
class RepositoryAnalysisOutput:
    """仓库分析处理器的统一输出。"""

    result_json: dict[str, Any]
    evidence_json: dict[str, Any]
    report_markdown: str


def build_repository_metadata_analysis(
    *,
    task: RepositoryAnalysisTask,
    acquisition: GitHubRepositoryAcquisition,
) -> RepositoryAnalysisOutput:
    """
    根据真实 GitHub 元数据生成阶段性报告。

    当前已经访问 GitHub 并固定 Commit，
    但尚未下载和扫描仓库文件。
    """

    metadata = acquisition.metadata
    commit = acquisition.commit

    result_json = {
        "schema_version": "1.0",
        "analysis_kind": "github_metadata_only",
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
        "statistics": {
            "size_kb": metadata.size_kb,
            "stargazers_count": (
                metadata.stargazers_count
            ),
            "forks_count": metadata.forks_count,
            "open_issues_count": (
                metadata.open_issues_count
            ),
        },
        "timestamps": {
            "created_at": metadata.created_at,
            "updated_at": metadata.updated_at,
            "pushed_at": metadata.pushed_at,
            "commit_authored_at": (
                commit.authored_at
            ),
            "commit_committed_at": (
                commit.committed_at
            ),
        },
        "capabilities": {
            "github_metadata_collected": True,
            "commit_resolved": True,
            "snapshot_downloaded": False,
            "repository_scanned": False,
            "evidence_built_from_files": False,
            "llm_report_generated": False,
        },
        "next_stage": "repository_snapshot_download",
    }

    evidence_json = {
        "schema_version": "1.0",
        "status": "metadata_only",
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
        ],
        "notice": (
            "当前 Evidence 只来自 GitHub REST API，"
            "尚未从仓库文件中提取证据。"
        ),
    }

    report_markdown = _build_chinese_report(
        task=task,
        acquisition=acquisition,
    )

    if task.report_language == "en-US":
        report_markdown = _build_english_report(
            task=task,
            acquisition=acquisition,
        )

    return RepositoryAnalysisOutput(
        result_json=result_json,
        evidence_json=evidence_json,
        report_markdown=report_markdown,
    )


def _build_chinese_report(
    *,
    task: RepositoryAnalysisTask,
    acquisition: GitHubRepositoryAcquisition,
) -> str:
    metadata = acquisition.metadata
    commit = acquisition.commit

    description = (
        metadata.description
        or "GitHub 未提供仓库简介。"
    )

    language = (
        metadata.primary_language
        or "暂未识别"
    )

    topics = (
        "、".join(metadata.topics)
        if metadata.topics
        else "暂无"
    )

    return f"""# {metadata.full_name} 仓库初步分析

> 当前报告基于 GitHub 仓库元数据和固定 Commit。
> 系统尚未下载和扫描仓库文件，因此架构、业务逻辑和部署方式将在下一阶段补充。

## 仓库概况

- 仓库：`{metadata.full_name}`
- 简介：{description}
- 主要语言：`{language}`
- 默认分支：`{metadata.default_branch}`
- Topics：{topics}
- 是否归档：`{metadata.archived}`
- 是否 Fork：`{metadata.fork}`

## 固定分析版本

- 请求 Ref：`{commit.requested_ref}`
- Commit SHA：`{commit.sha}`
- Commit 信息：{commit.message}
- Commit 作者：{commit.author_name or "未知"}

## 当前证据

- `E-001`：GitHub 仓库元数据
- `E-002`：GitHub 固定 Commit 信息

## 当前限制

以下内容尚未分析：

- README 与项目定位
- 文件目录与架构分层
- 依赖、框架和技术栈
- 入口文件和执行流程
- Docker、CI 与部署配置
- 测试结构与核心业务模块

## 下一阶段

下一阶段将下载 Commit `{commit.sha}` 对应的仓库快照，并开始确定性文件扫描。
"""


def _build_english_report(
    *,
    task: RepositoryAnalysisTask,
    acquisition: GitHubRepositoryAcquisition,
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

## Current limitation

Repository files, architecture, dependencies,
deployment configuration, tests, and business modules
have not been analyzed yet.

## Next stage

The next stage will download the repository snapshot
for commit `{commit.sha}`.
"""