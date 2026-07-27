import {
  useMutation,
  useQueryClient,
} from "@tanstack/react-query"
import {
  Bookmark,
  CheckCircle2,
  Clock3,
  TriangleAlert,
} from "lucide-react"

import type {
  RepositoryAnalysisTaskPublic,
} from "@/client"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"

import {
  repositoryAnalysisKeys,
  saveRepositoryAnalysisTask,
  syncRepositoryAnalysisTaskToLists,
} from "./repositoryAnalysisQueries"
import {
  formatRepositoryAnalysisDate,
  formatRepositoryAnalysisError,
} from "./repositoryAnalysisUi"

type RepositoryAnalysisRetentionPanelProps = {
  task: RepositoryAnalysisTaskPublic
}

export function RepositoryAnalysisRetentionPanel({
  task,
}: RepositoryAnalysisRetentionPanelProps) {
  const queryClient = useQueryClient()

  const {
    showSuccessToast,
    showErrorToast,
  } = useCustomToast()

  const saveMutation = useMutation({
    mutationFn: () =>
      saveRepositoryAnalysisTask(
        task.id,
      ),

    onSuccess: (savedTask) => {
      queryClient.setQueryData(
        repositoryAnalysisKeys.detail(
          savedTask.id,
        ),
        savedTask,
      )

      syncRepositoryAnalysisTaskToLists(
        queryClient,
        savedTask,
      )

      void queryClient.invalidateQueries({
        queryKey:
          repositoryAnalysisKeys.lists(),
      })

      showSuccessToast(
        "仓库分析报告已保存为长期记录",
      )
    },

    onError: (error) => {
      showErrorToast(
        formatRepositoryAnalysisError(
          error,
        ),
      )
    },
  })

  if (task.is_saved) {
    return (
      <Alert className="border-emerald-200 bg-emerald-50/60 text-emerald-900">
        <CheckCircle2 />

        <AlertTitle>
          已保存为长期记录
        </AlertTitle>

        <AlertDescription className="text-emerald-800/80">
          该报告不会因为临时结果到期而失效。
          仓库快照仍会按照后台保留策略独立清理。
        </AlertDescription>
      </Alert>
    )
  }

  if (task.status === "expired") {
    return (
      <Alert variant="destructive">
        <TriangleAlert />

        <AlertTitle>
          临时结果已过期
        </AlertTitle>

        <AlertDescription>
          该任务已经过期，不能再保存为长期记录。
          需要长期保留时，请重新分析仓库并在完成后点击保存。
        </AlertDescription>
      </Alert>
    )
  }

  const expiryText = task.expires_at
    ? formatRepositoryAnalysisDate(
        task.expires_at,
      )
    : "暂未设置"

  if (task.status === "completed") {
    return (
      <Alert className="items-center sm:grid-cols-[1rem_minmax(0,1fr)_auto]">
        <Clock3 />

        <div className="col-start-2 min-w-0">
          <AlertTitle>
            当前是临时分析结果
          </AlertTitle>

          <AlertDescription>
            临时结果保留至 {expiryText}。保存后将转为长期记录，
            不再设置临时过期时间。
          </AlertDescription>
        </div>

        <LoadingButton
          type="button"
          size="sm"
          className="col-start-2 mt-2 w-full sm:col-start-3 sm:row-start-1 sm:row-span-2 sm:mt-0 sm:w-auto"
          loading={saveMutation.isPending}
          onClick={() => {
            saveMutation.mutate()
          }}
        >
          <Bookmark />
          {saveMutation.isPending
            ? "保存中"
            : "保存报告"}
        </LoadingButton>
      </Alert>
    )
  }

  return (
    <Alert>
      <Clock3 />

      <AlertTitle>
        临时任务
      </AlertTitle>

      <AlertDescription>
        当前任务将在 {expiryText} 到期。只有分析完成后，
        才能将报告保存为长期记录。
      </AlertDescription>
    </Alert>
  )
}
