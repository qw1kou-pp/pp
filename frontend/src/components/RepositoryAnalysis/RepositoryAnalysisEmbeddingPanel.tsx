import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  useEffect,
  useState,
} from "react"

import type {
  RepositoryAnalysisTaskPublic,
} from "@/client"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"

import {
  backfillRepositoryAnalysisEmbeddings,
  readRepositoryAnalysisEmbeddingStatus,
  type RepositoryAnalysisEmbeddingStatusPublic,
} from "./repositoryAnalysisKnowledgeBaseApi"
import {
  repositoryAnalysisKeys,
} from "./repositoryAnalysisQueries"
import {
  formatRepositoryAnalysisError,
} from "./repositoryAnalysisUi"

type Props = {
  task: RepositoryAnalysisTaskPublic
}

function buildEmbeddingQueryKey(
  taskId: string,
) {
  return [
    "repository-analysis",
    "embedding-status",
    taskId,
  ] as const
}

export function RepositoryAnalysisEmbeddingPanel({
  task,
}: Props) {
  const queryClient = useQueryClient()

  const {
    showSuccessToast,
    showErrorToast,
  } = useCustomToast()

  const [
    autoRunning,
    setAutoRunning,
  ] = useState(false)

  const [
    retryFailed,
    setRetryFailed,
  ] = useState(false)

  const embeddingQueryKey =
    buildEmbeddingQueryKey(
      task.id,
    )

  const embeddingQuery =
    useQuery({
      queryKey: embeddingQueryKey,

      queryFn: () =>
        readRepositoryAnalysisEmbeddingStatus(
          task.id,
        ),

      enabled: Boolean(
        task.knowledge_base_id,
      ),

      staleTime: 1_000,
    })

  const embeddingMutation =
    useMutation({
      mutationFn: (
        shouldRetryFailed: boolean,
      ) =>
        backfillRepositoryAnalysisEmbeddings(
          task.id,
          {
            limit: 10,
            retry_failed:
              shouldRetryFailed,
          },
        ),

      onSuccess: (result) => {
        queryClient.setQueryData(
          embeddingQueryKey,
          result,
        )

        if (result.ready_for_search) {
          void queryClient.invalidateQueries({
            queryKey:
              repositoryAnalysisKeys.detail(
                task.id,
              ),
          })

          void queryClient.invalidateQueries({
            queryKey:
              repositoryAnalysisKeys.lists(),
          })
        }
      },

      onError: (error) => {
        setAutoRunning(false)

        showErrorToast(
          formatRepositoryAnalysisError(
            error,
          ),
        )
      },
    })

  const embeddingStatus =
    embeddingQuery.data

  useEffect(() => {
    if (
      !autoRunning
      || embeddingMutation.isPending
      || !embeddingStatus
    ) {
      return
    }

    const remainingCount =
      embeddingStatus.pending_count
      + (
        retryFailed
          ? embeddingStatus.failed_count
          : 0
      )

    if (remainingCount <= 0) {
      setAutoRunning(false)

      if (
        embeddingStatus.ready_for_search
      ) {
        showSuccessToast(
          embeddingStatus.failed_count > 0
            ? "代码索引完成，但部分代码块生成失败"
            : "代码索引生成完成",
        )
      }

      return
    }

    const timerId =
      window.setTimeout(
        () => {
          embeddingMutation.mutate(
            retryFailed,
          )
        },
        300,
      )

    return () => {
      window.clearTimeout(
        timerId,
      )
    }
  }, [
    autoRunning,
    embeddingMutation.isPending,
    embeddingStatus,
    retryFailed,
    showSuccessToast,
  ])

  const startIndexing = (
    shouldRetryFailed: boolean,
  ) => {
    setRetryFailed(
      shouldRetryFailed,
    )

    setAutoRunning(true)

    void embeddingQuery.refetch()
  }

  if (!task.knowledge_base_id) {
    return null
  }

  if (embeddingQuery.isPending) {
    return (
      <section className="rounded-lg border p-4">
        <p className="text-sm text-muted-foreground">
          正在读取代码索引状态……
        </p>
      </section>
    )
  }

  if (
    embeddingQuery.isError
    || !embeddingStatus
  ) {
    return (
      <section className="rounded-lg border border-red-200 bg-red-50 p-4">
        <p className="text-sm text-red-700">
          代码索引状态加载失败。
        </p>

        <Button
          type="button"
          variant="outline"
          className="mt-3"
          onClick={() => {
            void embeddingQuery.refetch()
          }}
        >
          重新加载
        </Button>
      </section>
    )
  }

  return (
    <section className="rounded-lg border bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="font-medium">
            代码向量索引
          </h4>

          <p className="mt-1 text-sm text-muted-foreground">
            模型：
            {embeddingStatus.embedding_model}
          </p>
        </div>

        <span className="rounded-full border px-3 py-1 text-xs">
          {formatIndexStatus(
            embeddingStatus,
            autoRunning,
          )}
        </span>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span>
            索引进度
          </span>

          <span className="font-medium">
            {embeddingStatus.progress_percent}%
          </span>
        </div>

        <div className="h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full bg-violet-600 transition-all duration-300"
            style={{
              width:
                `${embeddingStatus.progress_percent}%`,
            }}
          />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <StatusValue
          label="全部代码块"
          value={
            embeddingStatus.total_count
          }
        />

        <StatusValue
          label="等待处理"
          value={
            embeddingStatus.pending_count
          }
        />

        <StatusValue
          label="索引成功"
          value={
            embeddingStatus.embedded_count
          }
        />

        <StatusValue
          label="索引失败"
          value={
            embeddingStatus.failed_count
          }
        />
      </div>

      {embeddingStatus.sample_error_message && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3">
          <p className="text-sm font-medium text-red-700">
            示例错误
          </p>

          <p className="mt-1 whitespace-pre-wrap break-words text-xs text-red-600">
            {
              embeddingStatus
                .sample_error_message
            }
          </p>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {embeddingStatus.pending_count > 0 && (
          <Button
            type="button"
            disabled={
              embeddingMutation.isPending
            }
            onClick={() => {
              startIndexing(false)
            }}
          >
            {autoRunning
              ? "正在生成索引"
              : "开始或继续索引"}
          </Button>
        )}

        {(
          embeddingStatus.failed_count > 0
          && embeddingStatus.pending_count
            === 0
        ) && (
          <Button
            type="button"
            variant="outline"
            disabled={
              embeddingMutation.isPending
            }
            onClick={() => {
              startIndexing(true)
            }}
          >
            重试失败项
          </Button>
        )}

        {autoRunning && (
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setAutoRunning(false)
            }}
          >
            暂停
          </Button>
        )}

        <Button
          type="button"
          variant="ghost"
          disabled={
            embeddingMutation.isPending
          }
          onClick={() => {
            void embeddingQuery.refetch()
          }}
        >
          刷新状态
        </Button>
      </div>

      {embeddingStatus.ready_for_search && (
        <p className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          当前仓库已经具备向量检索条件，
          可以进入下一步仓库问答。
        </p>
      )}
    </section>
  )
}

function StatusValue({
  label,
  value,
}: {
  label: string
  value: number
}) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">
        {label}
      </p>

      <p className="mt-1 text-lg font-semibold">
        {value}
      </p>
    </div>
  )
}

function formatIndexStatus(
  status:
    RepositoryAnalysisEmbeddingStatusPublic,
  autoRunning: boolean,
): string {
  if (autoRunning) {
    return "正在生成"
  }

  switch (status.index_status) {
    case "not_imported":
      return "尚未导入"

    case "pending":
      return "等待索引"

    case "completed":
      return "索引完成"

    case "completed_with_errors":
      return "部分失败"

    case "failed":
      return "索引失败"

    default:
      return status.index_status
  }
}