import type {
  RepositoryChatPrefill,
} from "@/components/RepositoryAnalysis/repositoryChatHandoff"
import {
  repositoryChatSource,
} from "@/components/RepositoryAnalysis/repositoryChatHandoff"
import type {
  CodeReviewRepositoryPrefill,
} from "@/components/repositoryReviewHandoff"
import {
  repositoryReviewSource,
} from "@/components/repositoryReviewHandoff"
import {
  useEffect,
  useMemo,
} from "react"

import type {
  KnowledgeBaseDetailSearch,
  WorkspaceTab,
} from "./knowledgeBaseDetailTypes"

type UseKnowledgeBaseDetailHandoffOptions = {
  search: KnowledgeBaseDetailSearch
  onEnsureTab: (
    tab: WorkspaceTab,
  ) => void
}

export function useKnowledgeBaseDetailHandoff({
  search,
  onEnsureTab,
}: UseKnowledgeBaseDetailHandoffOptions) {
  const repositoryReviewPrefill =
    useMemo<
      CodeReviewRepositoryPrefill | null
    >(() => {
      if (
        search.source
          !== repositoryReviewSource
        || !search.repositoryOwner
        || !search.repositoryName
        || !search.repositoryUrl
      ) {
        return null
      }

      return {
        repositoryOwner:
          search.repositoryOwner,

        repositoryName:
          search.repositoryName,

        repositoryUrl:
          search.repositoryUrl,

        resolvedCommitSha:
          search.resolvedCommitSha,
      }
    }, [
      search.source,
      search.repositoryOwner,
      search.repositoryName,
      search.repositoryUrl,
      search.resolvedCommitSha,
    ])

  const repositoryChatPrefill =
    useMemo<
      RepositoryChatPrefill | null
    >(() => {
      if (
        search.source
          !== repositoryChatSource
        || !search.repositoryFullName
        || !search.repositoryUrl
        || !search.resolvedCommitSha
        || !search.repositoryAnalysisTaskId
      ) {
        return null
      }

      return {
        repositoryFullName:
          search.repositoryFullName,

        repositoryUrl:
          search.repositoryUrl,

        resolvedCommitSha:
          search.resolvedCommitSha,

        repositoryAnalysisTaskId:
          search.repositoryAnalysisTaskId,

        question:
          search.question,
      }
    }, [
      search.source,
      search.repositoryFullName,
      search.repositoryUrl,
      search.resolvedCommitSha,
      search.repositoryAnalysisTaskId,
      search.question,
    ])

  const inferredTab:
    WorkspaceTab =
      repositoryChatPrefill
        ? "chat"
        : repositoryReviewPrefill
          ? "review"
          : "overview"

  const activeWorkspaceTab:
    WorkspaceTab =
      search.tab
      ?? inferredTab

  useEffect(() => {
    if (
      search.tab
      || inferredTab === "overview"
    ) {
      return
    }

    onEnsureTab(
      inferredTab,
    )
  }, [
    inferredTab,
    onEnsureTab,
    search.tab,
  ])

  return {
    activeWorkspaceTab,
    repositoryReviewPrefill,
    repositoryChatPrefill,
  }
}
