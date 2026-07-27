import type {
  RepositoryAnalysisTaskPublic,
} from "@/client"

export const repositoryChatSource =
  "repository-analysis-chat" as const

export type RepositoryChatPrefill = {
  repositoryFullName: string
  repositoryUrl: string

  resolvedCommitSha: string

  repositoryAnalysisTaskId: string

  question?: string
}

export function buildRepositoryChatQuestion(
  task: RepositoryAnalysisTaskPublic,
): string {
  const commit =
    task.resolved_commit_sha
      ?.slice(0, 12) ||
    "未知"

  return (
    `请基于仓库 ${task.repository_full_name} `
    + `在 Commit ${commit} 的代码，`
    + "说明项目的整体架构、主要入口和关键调用链，"
    + "并在回答中标明来源文件。"
  )
}