import {
  AlertTriangle,
  Check,
  Circle,
} from "lucide-react"

import type {
  RepositoryAnalysisTaskPublic,
} from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

import {
  formatRepositoryAnalysisDate,
  formatRepositoryCommitSha,
  getRepositoryAnalysisProgress,
  getRepositoryAnalysisStageLabel,
  getRepositoryAnalysisStatusMeta,
  repositoryAnalysisPipelineStages,
} from "./repositoryAnalysisUi"

type RepositoryAnalysisProgressTabProps = {
  task: RepositoryAnalysisTaskPublic
}

export function RepositoryAnalysisProgressTab({
  task,
}: RepositoryAnalysisProgressTabProps) {
  const status =
    getRepositoryAnalysisStatusMeta(
      task.status,
    )

  const progress =
    getRepositoryAnalysisProgress(
      task.progress_percent,
    )

  const currentStageIndex =
    repositoryAnalysisPipelineStages.indexOf(
      task.stage as (
        typeof repositoryAnalysisPipelineStages
      )[number],
    )

  return (
    <div className="space-y-6">
      <section className="rounded-lg border p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm text-muted-foreground">
              当前阶段
            </p>

            <h3 className="mt-1 text-lg font-semibold">
              {getRepositoryAnalysisStageLabel(
                task.stage,
              )}
            </h3>
          </div>

          <Badge
            variant="outline"
            className={
              status.className
            }
          >
            {status.label}
          </Badge>
        </div>

        <div className="mt-5">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span>
              分析进度
            </span>

            <span className="font-medium">
              {progress}%
            </span>
          </div>

          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-500"
              style={{
                width: `${progress}%`,
              }}
            />
          </div>
        </div>
      </section>

      {(task.status === "failed" ||
        task.error_message) && (
        <section className="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
          <div className="flex gap-3">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-destructive" />

            <div>
              <h3 className="font-medium text-destructive">
                仓库分析失败
              </h3>

              {task.error_code && (
                <p className="mt-2 font-mono text-xs">
                  {task.error_code}
                </p>
              )}

              <p className="mt-2 whitespace-pre-wrap text-sm">
                {task.error_message ||
                  "仓库分析过程中发生未知错误。"}
              </p>
            </div>
          </div>
        </section>
      )}

      <section>
        <h3 className="font-medium">
          执行阶段
        </h3>

        <div className="mt-4 space-y-2">
          {repositoryAnalysisPipelineStages.map(
            (
              stage,
              index,
            ) => {
              const completed =
                currentStageIndex >= 0 &&
                index <
                  currentStageIndex

              const current =
                stage === task.stage

              return (
                <div
                  key={stage}
                  className={cn(
                    "flex items-center gap-3 rounded-md border px-3 py-2",
                    current &&
                      "border-primary bg-primary/5",
                  )}
                >
                  <StageIcon
                    completed={
                      completed
                    }
                    current={
                      current
                    }
                  />

                  <span
                    className={cn(
                      "text-sm",
                      !completed &&
                        !current &&
                        "text-muted-foreground",
                    )}
                  >
                    {getRepositoryAnalysisStageLabel(
                      stage,
                    )}
                  </span>
                </div>
              )
            },
          )}
        </div>
      </section>

      <section>
        <h3 className="font-medium">
          任务信息
        </h3>

        <dl className="mt-4 grid gap-4 rounded-lg border p-4 sm:grid-cols-2">
          <MetadataItem
            label="仓库"
            value={
              task.repository_full_name
            }
          />

          <MetadataItem
            label="默认分支"
            value={
              task.default_branch ||
              "—"
            }
          />

          <MetadataItem
            label="固定 Commit"
            value={formatRepositoryCommitSha(
              task.resolved_commit_sha,
              12,
            )}
          />

          <MetadataItem
            label="报告语言"
            value={
              task.report_language
            }
          />

          <MetadataItem
            label="创建时间"
            value={formatRepositoryAnalysisDate(
              task.created_at,
            )}
          />

          <MetadataItem
            label="开始时间"
            value={formatRepositoryAnalysisDate(
              task.started_at,
            )}
          />

          <MetadataItem
            label="完成时间"
            value={formatRepositoryAnalysisDate(
              task.completed_at,
            )}
          />

          <MetadataItem
            label="更新时间"
            value={formatRepositoryAnalysisDate(
              task.updated_at,
            )}
          />
        </dl>
      </section>
    </div>
  )
}

function StageIcon({
  completed,
  current,
}: {
  completed: boolean
  current: boolean
}) {
  if (completed) {
    return (
      <span className="flex size-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
        <Check className="size-4" />
      </span>
    )
  }

  return (
    <span
      className={cn(
        "flex size-6 items-center justify-center rounded-full border",
        current &&
          "border-primary text-primary",
      )}
    >
      <Circle className="size-3 fill-current" />
    </span>
  )
}

function MetadataItem({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">
        {label}
      </dt>

      <dd className="mt-1 break-all text-sm font-medium">
        {value}
      </dd>
    </div>
  )
}