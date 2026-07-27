import { useQuery } from "@tanstack/react-query"
import {
  History,
  Inbox,
  RefreshCw,
} from "lucide-react"
import {
  useEffect,
  useMemo,
  useState,
} from "react"

import type {
  RepositoryAnalysisTaskSummaryPublic,
} from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

import {
  repositoryAnalysisListQueryOptions,
} from "./repositoryAnalysisQueries"
import {
  formatRepositoryAnalysisDate,
  getRepositoryAnalysisStageLabel,
  getRepositoryAnalysisStatusMeta,
} from "./repositoryAnalysisUi"

type TaskListFilter =
  | "all"
  | "active"
  | "completed"
  | "failed"
  | "expired"

type RepositoryAnalysisTaskListProps = {
  preferredTaskId: string | null
  selectedTaskId: string | null
  onSelectTask: (
    taskId: string,
  ) => void
  onClearSelection: () => void
}

export function RepositoryAnalysisTaskList({
  preferredTaskId,
  selectedTaskId,
  onSelectTask,
  onClearSelection,
}: RepositoryAnalysisTaskListProps) {
  const [filter, setFilter] =
    useState<TaskListFilter>(
      "all",
    )

  const {
    data,
    error,
    isPending,
    isFetching,
    refetch,
  } = useQuery(
    repositoryAnalysisListQueryOptions({
      skip: 0,
      limit: 100,
    }),
  )

  const tasks =
    data?.data ?? []

  const filteredTasks =
    useMemo(
      () =>
        filterRepositoryAnalysisTasks(
          tasks,
          filter,
        ),
      [
        tasks,
        filter,
      ],
    )

  useEffect(() => {
    if (isPending || error) {
      return
    }

    if (tasks.length === 0) {
      if (
        selectedTaskId !== null ||
        preferredTaskId !== null
      ) {
        onClearSelection()
      }
      return
    }

    const selectedTaskExists =
      selectedTaskId !== null &&
      tasks.some(
        (task) =>
          task.id === selectedTaskId,
      )

    if (selectedTaskExists) {
      const selectedTaskIsVisible =
        filteredTasks.some(
          (task) =>
            task.id === selectedTaskId,
        )

      if (
        filteredTasks.length > 0 &&
        !selectedTaskIsVisible
      ) {
        onSelectTask(
          filteredTasks[0].id,
        )
      }

      return
    }

    const preferredTask =
      preferredTaskId === null
        ? undefined
        : tasks.find(
            (task) =>
              task.id ===
              preferredTaskId,
          )

    const fallbackTask =
      preferredTask ??
      filteredTasks[0] ??
      tasks[0]

    onSelectTask(
      fallbackTask.id,
    )
  }, [
    error,
    filteredTasks,
    isPending,
    onClearSelection,
    onSelectTask,
    preferredTaskId,
    selectedTaskId,
    tasks,
  ])

  return (
    <Card className="min-h-[38rem]">
      <CardHeader className="gap-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <History className="size-5" />
              分析任务
            </CardTitle>

            <CardDescription className="mt-1">
              共 {data?.count ?? 0} 条记录
            </CardDescription>
          </div>

          <Button
            type="button"
            variant="outline"
            size="icon"
            title="刷新任务列表"
            disabled={isFetching}
            onClick={() => {
              void refetch()
            }}
          >
            <RefreshCw
              className={cn(
                isFetching &&
                  "animate-spin",
              )}
            />
          </Button>
        </div>

        <Select
          value={filter}
          onValueChange={(value) => {
            setFilter(
              value as TaskListFilter,
            )
          }}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>

          <SelectContent>
            <SelectItem value="all">
              全部任务
            </SelectItem>

            <SelectItem value="active">
              运行中
            </SelectItem>

            <SelectItem value="completed">
              已完成
            </SelectItem>

            <SelectItem value="failed">
              失败
            </SelectItem>

            <SelectItem value="expired">
              已过期
            </SelectItem>
          </SelectContent>
        </Select>
      </CardHeader>

      <CardContent>
        {isPending ? (
          <TaskListSkeleton />
        ) : error ? (
          <TaskListError
            onRetry={() => {
              void refetch()
            }}
          />
        ) : filteredTasks.length ===
          0 ? (
          <TaskListEmpty />
        ) : (
          <div className="space-y-2">
            {filteredTasks.map(
              (task) => (
                <TaskListItem
                  key={task.id}
                  task={task}
                  selected={
                    task.id ===
                    selectedTaskId
                  }
                  onSelect={() => {
                    onSelectTask(
                      task.id,
                    )
                  }}
                />
              ),
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

type TaskListItemProps = {
  task: RepositoryAnalysisTaskSummaryPublic
  selected: boolean
  onSelect: () => void
}

function TaskListItem({
  task,
  selected,
  onSelect,
}: TaskListItemProps) {
  const status =
    getRepositoryAnalysisStatusMeta(
      task.status,
    )

  const progress = Math.min(
    100,
    Math.max(
      0,
      task.progress_percent ?? 0,
    ),
  )

  return (
    <button
      type="button"
      className={cn(
        "w-full rounded-lg border p-3 text-left transition-colors",
        "hover:bg-muted/60",
        selected &&
          "border-primary bg-primary/5",
      )}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium">
            {task.repository_full_name}
          </p>

          <p className="mt-1 truncate text-xs text-muted-foreground">
            {getRepositoryAnalysisStageLabel(
              task.stage,
            )}
          </p>
        </div>

        <Badge
          variant="outline"
          className={status.className}
        >
          {status.label}
        </Badge>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-[width]"
          style={{
            width: `${progress}%`,
          }}
        />
      </div>

      <div className="mt-2 flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {progress}%
        </span>

        <span>
          {formatRepositoryAnalysisDate(
            task.created_at,
          )}
        </span>
      </div>

      {task.is_saved ? (
        <p className="mt-2 text-xs text-emerald-700">
          已保存为长期记录
        </p>
      ) : task.status === "expired" ? (
        <p className="mt-2 text-xs text-amber-700">
          临时记录已过期
        </p>
      ) : task.expires_at ? (
        <p className="mt-2 text-xs text-muted-foreground">
          临时保留至 {formatRepositoryAnalysisDate(
            task.expires_at,
          )}
        </p>
      ) : null}
    </button>
  )
}

function TaskListSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({
        length: 4,
      }).map((_, index) => (
        <div
          key={index}
          className="space-y-3 rounded-lg border p-3"
        >
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
          <Skeleton className="h-1.5 w-full" />
        </div>
      ))}
    </div>
  )
}

function TaskListEmpty() {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center rounded-lg border border-dashed px-6 text-center">
      <Inbox className="size-8 text-muted-foreground" />

      <p className="mt-4 font-medium">
        暂无匹配任务
      </p>

      <p className="mt-2 text-sm text-muted-foreground">
        提交一个公开 GitHub 仓库后，任务会显示在这里。
      </p>
    </div>
  )
}

function TaskListError({
  onRetry,
}: {
  onRetry: () => void
}) {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center rounded-lg border border-dashed px-6 text-center">
      <p className="font-medium text-destructive">
        任务列表加载失败
      </p>

      <Button
        type="button"
        variant="outline"
        className="mt-4"
        onClick={onRetry}
      >
        重新加载
      </Button>
    </div>
  )
}

function filterRepositoryAnalysisTasks(
  tasks:
    RepositoryAnalysisTaskSummaryPublic[],
  filter: TaskListFilter,
) {
  if (filter === "all") {
    return tasks
  }

  if (filter === "active") {
    return tasks.filter(
      (task) =>
        task.status === "queued" ||
        task.status === "running",
    )
  }

  return tasks.filter(
    (task) =>
      task.status === filter,
  )
}