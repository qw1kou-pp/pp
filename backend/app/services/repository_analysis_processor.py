from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import RepositoryAnalysisTask


@dataclass(frozen=True, slots=True)
class RepositoryAnalysisOutput:
    """
    一次仓库分析处理完成后的统一输出。

    Worker 不关心分析器内部如何获取 GitHub 内容，
    只需要接收这三个最终结果并保存到数据库。
    """

    result_json: dict[str, Any]
    evidence_json: dict[str, Any]
    report_markdown: str


def build_placeholder_repository_analysis(
    task: RepositoryAnalysisTask,
) -> RepositoryAnalysisOutput:
    """
    生成异步任务闭环验证使用的占位分析结果。

    当前不会访问 GitHub，也不会读取仓库代码。
    后续将用正式仓库分析流水线替换该函数。
    """

    repository_data = {
        "owner": task.repository_owner,
        "name": task.repository_name,
        "full_name": task.repository_full_name,
        "canonical_url": task.canonical_url,
        "requested_ref": task.requested_ref,
        "default_branch": task.default_branch,
        "resolved_commit_sha": task.resolved_commit_sha,
    }

    result_json = {
        "schema_version": "1.0",
        "analysis_kind": "pipeline_placeholder",
        "repository": repository_data,
        "overview": {
            "status": "pipeline_verified",
            "summary": (
                "异步任务已被 Worker 成功领取并处理，"
                "但当前尚未获取或分析 GitHub 仓库内容。"
            ),
        },
        "capabilities": {
            "github_metadata_collected": False,
            "snapshot_downloaded": False,
            "repository_scanned": False,
            "evidence_built": False,
            "llm_report_generated": False,
        },
        "next_stage": "github_repository_acquisition",
    }

    evidence_json = {
        "schema_version": "1.0",
        "status": "not_collected",
        "repository": task.repository_full_name,
        "items": [],
        "notice": (
            "当前是任务流水线占位结果，"
            "尚未从仓库文件中提取 Evidence。"
        ),
    }

    if task.report_language == "en-US":
        report_markdown = _build_english_placeholder_report(
            task,
        )
    else:
        report_markdown = _build_chinese_placeholder_report(
            task,
        )

    return RepositoryAnalysisOutput(
        result_json=result_json,
        evidence_json=evidence_json,
        report_markdown=report_markdown,
    )


def _build_chinese_placeholder_report(
    task: RepositoryAnalysisTask,
) -> str:
    """
    生成中文占位报告。
    """

    return f"""# {task.repository_full_name} 仓库分析任务

> 当前报告用于验证 RepoGuard 的异步仓库分析任务闭环。
> 系统尚未下载或扫描该 GitHub 仓库，因此本报告不代表真实仓库分析结果。

## 当前已完成

- GitHub 仓库地址已经标准化
- 分析任务已经写入 PostgreSQL
- Worker 已经成功领取任务
- 任务状态和进度已经完成流转
- 结构化结果、Evidence 容器和 Markdown 报告已经落库

## 尚未执行

- 获取 GitHub 仓库元数据
- 获取默认分支和固定 Commit
- 下载固定 Commit 对应的仓库快照
- 扫描目录结构、语言、依赖和入口文件
- 构建仓库级 Evidence
- 调用大模型组织最终分析报告

## 仓库信息

- 仓库：`{task.repository_full_name}`
- 标准地址：{task.canonical_url}
- 分析模式：`{task.analysis_mode}`
- 报告语言：`{task.report_language}`

## 下一阶段

下一阶段将接入 GitHub 公共仓库元数据获取和固定 Commit 解析。
"""


def _build_english_placeholder_report(
    task: RepositoryAnalysisTask,
) -> str:
    """
    Generate the English placeholder report.
    """

    return f"""# Repository analysis task: {task.repository_full_name}

> This report verifies the RepoGuard asynchronous task pipeline.
> The GitHub repository has not been downloaded or scanned yet,
> so this is not a real repository analysis report.

## Completed

- The GitHub repository URL was normalized
- The analysis task was persisted in PostgreSQL
- The workers successfully claimed the task
- Task status and progress transitions were persisted
- Structured result, evidence container, and Markdown were saved

## Not completed yet

- GitHub repository metadata acquisition
- Default branch and immutable commit resolution
- Repository snapshot download
- Repository structure and dependency scanning
- Deterministic evidence construction
- LLM-assisted report organization

## Repository

- Repository: `{task.repository_full_name}`
- Canonical URL: {task.canonical_url}
- Analysis mode: `{task.analysis_mode}`
- Report language: `{task.report_language}`

## Next stage

The next stage will add GitHub metadata acquisition
and immutable commit resolution.
"""