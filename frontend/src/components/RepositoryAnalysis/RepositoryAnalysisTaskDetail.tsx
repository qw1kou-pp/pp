import {
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  AlertCircle,
  FileJson,
  ListTree,
  RefreshCw,
  ScrollText,
} from "lucide-react"
import {
  useEffect,
} from "react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"

import {
  repositoryAnalysisDetailQueryOptions,
  syncRepositoryAnalysisTaskToLists,
} from "./repositoryAnalysisQueries"
import {
  RepositoryAnalysisEvidenceTab,
} from "./RepositoryAnalysisEvidenceTab"
import {
  RepositoryAnalysisOverviewTab,
} from "./RepositoryAnalysisOverviewTab"
import {
  RepositoryAnalysisProgressTab,
} from "./RepositoryAnalysisProgressTab"
import {
  RepositoryAnalysisRetentionPanel,
} from "./RepositoryAnalysisRetentionPanel"
import {
  RepositoryAnalysisReportTab,
} from "./RepositoryAnalysisReportTab"
import {
  formatRepositoryAnalysisError,
} from "./repositoryAnalysisUi"
import {
  RepositoryAnalysisRelatedActionsTab,
} from "./RepositoryAnalysisRelatedActionsTab"

export type RepositoryAnalysisDetailTab =
  | "progress"
  | "overview"
  | "evidence"
  | "report"
  | "related"

type RepositoryAnalysisTaskDetailProps = {
  selectedTaskId: string | null
  activeTab:
    RepositoryAnalysisDetailTab
  onActiveTabChange: (
    tab:
      RepositoryAnalysisDetailTab,
  ) => void
}

export function RepositoryAnalysisTaskDetail({
  selectedTaskId,
  activeTab,
  onActiveTabChange,
}: RepositoryAnalysisTaskDetailProps) {
  const queryClient =
    useQueryClient()

  const query = useQuery(
    repositoryAnalysisDetailQueryOptions(
      selectedTaskId,
    ),
  )

  useEffect(() => {
    if (!query.data) {
      return
    }

    syncRepositoryAnalysisTaskToLists(
      queryClient,
      query.data,
    )
  }, [
    query.data,
    queryClient,
  ])

  if (!selectedTaskId) {
    return (
      <DetailEmptyState />
    )
  }

  if (
    query.isPending &&
    !query.data
  ) {
    return (
      <DetailSkeleton />
    )
  }

  if (
    query.error &&
    !query.data
  ) {
    return (
      <DetailError
        error={query.error}
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  }

  const task =
    query.data

  if (!task) {
    return (
      <DetailEmptyState />
    )
  }

  return (
    <Card className="min-h-[38rem]">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <CardTitle className="break-all">
              {task.repository_full_name}
            </CardTitle>

            <CardDescription className="mt-1 break-all">
              {task.canonical_url}
            </CardDescription>
          </div>

          <Button
            type="button"
            variant="outline"
            size="icon"
            title="刷新任务详情"
            disabled={
              query.isFetching
            }
            onClick={() => {
              void query.refetch()
            }}
          >
            <RefreshCw
              className={
                query.isFetching
                  ? "animate-spin"
                  : undefined
              }
            />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        <RepositoryAnalysisRetentionPanel
          task={task}
        />

        <Tabs
          value={activeTab}
          onValueChange={(value) => {
            onActiveTabChange(
              value as RepositoryAnalysisDetailTab,
            )
          }}
        >
          <TabsList className="grid h-auto w-full grid-cols-2 gap-1 md:grid-cols-5">
            <TabsTrigger value="progress">
              进度
            </TabsTrigger>

            <TabsTrigger value="overview">
              概览
            </TabsTrigger>

            <TabsTrigger value="evidence">
              Evidence
            </TabsTrigger>

            <TabsTrigger value="report">
              报告
            </TabsTrigger>

            <TabsTrigger value="related">
              关联功能
            </TabsTrigger>
          </TabsList>

          <TabsContent
            value="progress"
            className="mt-6"
          >
            <RepositoryAnalysisProgressTab
              task={task}
            />
          </TabsContent>

          <TabsContent
            value="overview"
            className="mt-6"
          >
            <RepositoryAnalysisOverviewTab
              task={task}
            />
          </TabsContent>

          <TabsContent
            value="evidence"
            className="mt-6"
          >
            <RepositoryAnalysisEvidenceTab
              task={task}
            />
          </TabsContent>

          <TabsContent
            value="report"
            className="mt-6"
          >
            <RepositoryAnalysisReportTab
              task={task}
            />
          </TabsContent>

          <TabsContent
            value="related"
            className="mt-6"
          >
            <RepositoryAnalysisRelatedActionsTab
              task={task}
            />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

function DetailEmptyState() {
  return (
    <Card className="min-h-[38rem]">
      <CardContent className="flex min-h-[38rem] items-center justify-center">
        <div className="text-center">
          <ListTree className="mx-auto size-9 text-muted-foreground" />

          <h3 className="mt-4 font-medium">
            选择一个任务
          </h3>

          <p className="mt-2 text-sm text-muted-foreground">
            从左侧选择任务查看分析进度和结果。
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

function DetailSkeleton() {
  return (
    <Card className="min-h-[38rem]">
      <CardHeader>
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </CardHeader>

      <CardContent className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </CardContent>
    </Card>
  )
}

function DetailError({
  error,
  onRetry,
}: {
  error: unknown
  onRetry: () => void
}) {
  return (
    <Card className="min-h-[38rem]">
      <CardContent className="flex min-h-[38rem] items-center justify-center">
        <div className="max-w-lg text-center">
          <AlertCircle className="mx-auto size-9 text-destructive" />

          <h3 className="mt-4 font-medium text-destructive">
            任务详情加载失败
          </h3>

          <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
            {formatRepositoryAnalysisError(
              error,
            )}
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
      </CardContent>
    </Card>
  )
}

