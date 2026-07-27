import {
  repositoryChatSource,
} from "@/components/RepositoryAnalysis/repositoryChatHandoff"
import {
  repositoryReviewSource,
} from "@/components/repositoryReviewHandoff"

export type AppliedAgentConfig = {
  topK: number
  maxSteps: number
  semanticWeight: number
  keywordWeight: number
}

export type WorkspaceTab =
  | "overview"
  | "review"
  | "chat"
  | "evaluation"

export type KnowledgeBaseDetailSearch = {
  tab?: WorkspaceTab

  source?:
    | typeof repositoryReviewSource
    | typeof repositoryChatSource

  repositoryOwner?: string
  repositoryName?: string
  repositoryFullName?: string
  repositoryUrl?: string
  resolvedCommitSha?: string
  repositoryAnalysisTaskId?: string
  question?: string
}

export type RepositoryAwareRagSource = {
  repository_analysis_task_id?: string | null
  repository_relative_path?: string | null
  source_commit_sha?: string | null
}

export type ExpandableSectionKey =
  | "documents"
  | "ragHistory"
  | "agentHistory"
  | "compareHistory"
  | "evalRuns"
  | "agentParamTuning"

export type WorkspaceTabDefinition = {
  key: WorkspaceTab
  label: string
  description: string
}

export const WORKSPACE_TABS: readonly WorkspaceTabDefinition[] = [
  {
    key: "overview",
    label: "知识库概览",
    description: "上传、导入并管理知识库文档",
  },
  {
    key: "review",
    label: "代码审查",
    description: "分析 Diff、影响范围、风险和测试",
  },
  {
    key: "chat",
    label: "智能问答",
    description: "检索、RAG、Agent 与单题对比",
  },
  {
    key: "evaluation",
    label: "评测实验",
    description: "批量评测、调参、分析与报告",
  },
]

export function isWorkspaceTab(value: unknown): value is WorkspaceTab {
  return (
    typeof value === "string" &&
    WORKSPACE_TABS.some((tab) => tab.key === value)
  )
}

export function readOptionalSearchString(
  value: unknown,
): string | undefined {
  if (typeof value !== "string") {
    return undefined
  }

  const normalized = value.trim()
  return normalized || undefined
}

export function parseKnowledgeBaseDetailSearch(
  search: Record<string, unknown>,
): KnowledgeBaseDetailSearch {
  const source = readOptionalSearchString(search.source)

  const validatedSource =
    source === repositoryReviewSource
      ? repositoryReviewSource
      : source === repositoryChatSource
        ? repositoryChatSource
        : undefined

  return {
    tab: isWorkspaceTab(search.tab) ? search.tab : undefined,
    source: validatedSource,
    repositoryOwner: readOptionalSearchString(search.repositoryOwner),
    repositoryName: readOptionalSearchString(search.repositoryName),
    repositoryFullName: readOptionalSearchString(search.repositoryFullName),
    repositoryUrl: readOptionalSearchString(search.repositoryUrl),
    resolvedCommitSha: readOptionalSearchString(search.resolvedCommitSha),
    repositoryAnalysisTaskId: readOptionalSearchString(
      search.repositoryAnalysisTaskId,
    ),
    question: readOptionalSearchString(search.question)?.slice(0, 1000),
  }
}
