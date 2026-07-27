import type { QueryClient } from "@tanstack/react-query"
import { queryOptions } from "@tanstack/react-query"

import {
  RepositoryAnalysesService,
  type RepositoryAnalysisTaskCreate,
  type RepositoryAnalysisTaskPublic,
  type RepositoryAnalysisTasksPublic,
  type RepositoryAnalysisTaskSummaryPublic,
} from "@/client"

import {
  isActiveRepositoryAnalysisStatus,
  type RepositoryAnalysisStatus,
} from "./repositoryAnalysisUi"

export const repositoryAnalysisPollingIntervalMs =
  2500

export type RepositoryAnalysisListFilters = {
  skip?: number
  limit?: number
  status?: RepositoryAnalysisStatus | null
}

function normalizeRepositoryAnalysisListFilters(
  filters: RepositoryAnalysisListFilters,
) {
  return {
    skip: Math.max(
      0,
      filters.skip ?? 0,
    ),
    limit: Math.min(
      100,
      Math.max(
        1,
        filters.limit ?? 20,
      ),
    ),
    status:
      filters.status ?? null,
  }
}

export const repositoryAnalysisKeys = {
  all: [
    "repository-analyses",
  ] as const,

  lists: () =>
    [
      ...repositoryAnalysisKeys.all,
      "list",
    ] as const,

  list: (
    filters: RepositoryAnalysisListFilters = {},
  ) => {
    const normalizedFilters =
      normalizeRepositoryAnalysisListFilters(
        filters,
      )

    return [
      ...repositoryAnalysisKeys.lists(),
      normalizedFilters,
    ] as const
  },

  details: () =>
    [
      ...repositoryAnalysisKeys.all,
      "detail",
    ] as const,

  detail: (
    taskId: string,
  ) =>
    [
      ...repositoryAnalysisKeys.details(),
      taskId,
    ] as const,
}

export function repositoryAnalysisListQueryOptions(
  filters: RepositoryAnalysisListFilters = {},
) {
  const normalizedFilters =
    normalizeRepositoryAnalysisListFilters(
      filters,
    )

  return queryOptions({
    queryKey:
      repositoryAnalysisKeys.list(
        normalizedFilters,
      ),

    queryFn: () =>
      RepositoryAnalysesService
        .readRepositoryAnalyses({
          skip:
            normalizedFilters.skip,
          limit:
            normalizedFilters.limit,
          status:
            normalizedFilters.status ??
            undefined,
        }),

    staleTime: 5000,
  })
}

export function repositoryAnalysisDetailQueryOptions(
  taskId: string | null | undefined,
) {
  const normalizedTaskId =
    taskId?.trim() ?? ""

  return queryOptions({
    queryKey:
      repositoryAnalysisKeys.detail(
        normalizedTaskId,
      ),

    queryFn: () => {
      if (!normalizedTaskId) {
        throw new Error(
          "Repository analysis task ID is required",
        )
      }

      return RepositoryAnalysesService
        .readRepositoryAnalysis({
          taskId: normalizedTaskId,
        })
    },

    enabled:
      normalizedTaskId.length > 0,

    staleTime: 1000,

    refetchInterval: (query) =>
      getRepositoryAnalysisPollingInterval(
        query.state.data,
      ),

    refetchIntervalInBackground: false,
  })
}

export function createRepositoryAnalysisTask(
  request: RepositoryAnalysisTaskCreate,
) {
  return RepositoryAnalysesService
    .createRepositoryAnalysis({
      requestBody: request,
    })
}

export function saveRepositoryAnalysisTask(
  taskId: string,
) {
  const normalizedTaskId =
    taskId.trim()

  if (!normalizedTaskId) {
    throw new Error(
      "Repository analysis task ID is required",
    )
  }

  return RepositoryAnalysesService
    .saveRepositoryAnalysis({
      taskId: normalizedTaskId,
    })
}

export function getRepositoryAnalysisPollingInterval(
  task:
    | RepositoryAnalysisTaskPublic
    | undefined,
): number | false {
  if (
    task &&
    isActiveRepositoryAnalysisStatus(
      task.status,
    )
  ) {
    return repositoryAnalysisPollingIntervalMs
  }

  return false
}


export function syncRepositoryAnalysisTaskToLists(
  queryClient: QueryClient,
  task: RepositoryAnalysisTaskPublic,
) {
  const summary =
    repositoryAnalysisTaskToSummary(task)

  queryClient.setQueriesData<
    RepositoryAnalysisTasksPublic
  >(
    {
      queryKey:
        repositoryAnalysisKeys.lists(),
    },
    (current) => {
      if (!current) {
        return current
      }

      const taskExists =
        current.data.some(
          (item) =>
            item.id === task.id,
        )

      if (!taskExists) {
        return {
          ...current,
          count:
            current.count + 1,
          data: [
            summary,
            ...current.data,
          ],
        }
      }

      return {
        ...current,
        data: current.data.map(
          (item) =>
            item.id === task.id
              ? summary
              : item,
        ),
      }
    },
  )
}

function repositoryAnalysisTaskToSummary(
  task: RepositoryAnalysisTaskPublic,
): RepositoryAnalysisTaskSummaryPublic {
  return {
    id: task.id,
    repository_full_name:
      task.repository_full_name,
    canonical_url:
      task.canonical_url,
    analysis_mode:
      task.analysis_mode,
    status: task.status,
    stage: task.stage,
    progress_percent:
      task.progress_percent,
    is_saved: task.is_saved,
    knowledge_base_id:
      task.knowledge_base_id,
    error_code:
      task.error_code,
    error_message:
      task.error_message,
    expires_at:
      task.expires_at,
    created_at:
      task.created_at,
    started_at:
      task.started_at,
    completed_at:
      task.completed_at,
  }
}