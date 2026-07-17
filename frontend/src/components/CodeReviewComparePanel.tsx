import {
  useMutation,
  useQuery,
} from "@tanstack/react-query"
import {
  useEffect,
  useMemo,
  useState,
} from "react"

import {
  CodeSkillService,
  type CodeReviewCompareResponse,
} from "@/client"

import {
  canCompareReviewRuns,
  formatMetricChange,
  formatReviewRunLabel,
  formatValueChange,
  getLatestReviewPair,
  getTrendLabel,
  sortReviewRunsNewestFirst,
  type ReviewCompareTrend,
  type ReviewRunCompareOption,
} from "./codeReviewCompareUtils"

type CodeReviewComparePanelProps = {
  knowledgeBaseId: string
}

type CompareSelection = {
  baseReviewRunId: string
  targetReviewRunId: string
}

type ReviewReference =
  CodeReviewCompareResponse["base_review"]

type ReviewValueChange =
  CodeReviewCompareResponse[
    "overall_change"
  ]["risk"]

type ReviewMetricChange =
  CodeReviewCompareResponse[
    "metric_changes"
  ]["changed_file_count"]

type FindingChangeItem =
  CodeReviewCompareResponse[
    "finding_changes"
  ]["added"][number]

type TestChangeItem =
  CodeReviewCompareResponse[
    "test_changes"
  ]["added"][number]

type TraceMetricChange =
  NonNullable<
    CodeReviewCompareResponse[
      "trace_changes"
    ]["duration_ms"]
  >

const formatCompareApiError = (
  error: unknown,
): string => {
  if (
    !error ||
    typeof error !== "object"
  ) {
    return String(
      error || "未知错误",
    )
  }

  const candidate = error as {
    message?: string
    body?: {
      detail?: unknown
    }
  }

  if (candidate.body?.detail) {
    if (
      typeof candidate.body.detail
      === "string"
    ) {
      return candidate.body.detail
    }

    return JSON.stringify(
      candidate.body.detail,
      null,
      2,
    )
  }

  return (
    candidate.message ||
    JSON.stringify(
      error,
      null,
      2,
    )
  )
}

const formatReviewDateTime = (
  value?: string | null,
): string => {
  if (!value) {
    return "时间未知"
  }

  const timestamp =
    Date.parse(value)

  if (Number.isNaN(timestamp)) {
    return value
  }

  return new Date(
    timestamp,
  ).toLocaleString(
    "zh-CN",
    {
      hour12: false,
    },
  )
}

const getTrendClassName = (
  trend: ReviewCompareTrend,
): string => {
  if (trend === "increased") {
    return (
      "border-rose-200 " +
      "bg-rose-50 text-rose-700"
    )
  }

  if (trend === "decreased") {
    return (
      "border-emerald-200 " +
      "bg-emerald-50 " +
      "text-emerald-700"
    )
  }

  if (trend === "changed") {
    return (
      "border-amber-200 " +
      "bg-amber-50 text-amber-700"
    )
  }

  if (trend === "unavailable") {
    return (
      "border-slate-200 " +
      "bg-slate-50 text-slate-500"
    )
  }

  return (
    "border-slate-200 " +
    "bg-slate-50 text-slate-700"
  )
}

const formatFindingSeverity = (
  severity?: string | null,
): string => {
  if (severity === "high") {
    return "高风险"
  }

  if (severity === "medium") {
    return "中风险"
  }

  if (severity === "low") {
    return "低风险"
  }

  return severity || "未标注"
}

const getFindingSeverityClassName = (
  severity?: string | null,
): string => {
  if (severity === "high") {
    return (
      "border-rose-200 " +
      "bg-rose-50 text-rose-700"
    )
  }

  if (severity === "medium") {
    return (
      "border-amber-200 " +
      "bg-amber-50 text-amber-700"
    )
  }

  if (severity === "low") {
    return (
      "border-emerald-200 " +
      "bg-emerald-50 " +
      "text-emerald-700"
    )
  }

  return (
    "border-slate-200 " +
    "bg-slate-50 text-slate-600"
  )
}

function ReviewReferenceCard({
  label,
  review,
}: {
  label: string
  review: ReviewReference
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>

      <div className="mt-2 font-medium text-slate-900">
        {review.title}
      </div>

      <div className="mt-2 space-y-1 text-xs text-slate-500">
        <div>
          创建时间：
          {formatReviewDateTime(
            review.created_at,
          )}
        </div>

        <div className="break-all">
          Review ID：{review.id}
        </div>

        <div>
          Diff：
          {review.diff_hash
            ? review.diff_hash.slice(
                0,
                12,
              )
            : "暂无"}
        </div>
      </div>
    </div>
  )
}

function ValueChangeCard({
  label,
  change,
}: {
  label: string
  change: ReviewValueChange
}) {
  const trend =
    change.trend as ReviewCompareTrend

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">
        {label}
      </div>

      <div className="mt-2 font-medium text-slate-900">
        {formatValueChange(
          change,
        )}
      </div>

      <span
        className={[
          "mt-3 inline-flex",
          "rounded-full border",
          "px-2.5 py-1 text-xs",
          getTrendClassName(
            trend,
          ),
        ].join(" ")}
      >
        {getTrendLabel(
          trend,
        )}
      </span>
    </div>
  )
}

function MetricChangeCard({
  label,
  change,
}: {
  label: string
  change: ReviewMetricChange
}) {
  const trend =
    change.trend as ReviewCompareTrend

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">
        {label}
      </div>

      <div className="mt-2 text-lg font-semibold text-slate-900">
        {formatMetricChange(
          change,
        )}
      </div>

      <span
        className={[
          "mt-3 inline-flex",
          "rounded-full border",
          "px-2.5 py-1 text-xs",
          getTrendClassName(
            trend,
          ),
        ].join(" ")}
      >
        {getTrendLabel(
          trend,
        )}
      </span>
    </div>
  )
}

function FindingItemCard({
  finding,
}: {
  finding: FindingChangeItem
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="font-medium text-slate-900">
          {finding.title}
        </div>

        {finding.severity ? (
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
            {finding.severity}
          </span>
        ) : null}
      </div>

      {finding.category ? (
        <div className="mt-2 text-xs text-slate-500">
          分类：{finding.category}
        </div>
      ) : null}

      {finding.description ? (
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
          {finding.description}
        </p>
      ) : null}

      {finding.recommendation ? (
        <div className="mt-3 rounded-lg border border-blue-100 bg-blue-50 p-3">
          <div className="text-xs font-medium text-blue-700">
            修复建议
          </div>

          <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-blue-800">
            {finding.recommendation}
          </p>
        </div>
      ) : null}
    </div>
  )
}

function FindingChangeGroup({
  title,
  description,
  findings,
  emptyText,
  tone,
}: {
  title: string
  description: string
  findings: FindingChangeItem[]
  emptyText: string
  tone:
    | "added"
    | "resolved"
    | "persisting"
}) {
  const toneClassName = {
    added:
      "border-rose-200 bg-rose-50 text-rose-700",
    resolved:
      "border-emerald-200 bg-emerald-50 text-emerald-700",
    persisting:
      "border-amber-200 bg-amber-50 text-amber-700",
  }[tone]

  return (
    <details
      open={tone !== "persisting"}
      className="rounded-xl border border-slate-200 bg-slate-50"
    >
      <summary className="cursor-pointer list-none p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="font-medium text-slate-900">
              {title}
            </div>

            <div className="mt-1 text-sm text-slate-500">
              {description}
            </div>
          </div>

          <span
            className={[
              "rounded-full border",
              "px-2.5 py-1 text-xs",
              toneClassName,
            ].join(" ")}
          >
            {findings.length} 项
          </span>
        </div>
      </summary>

      <div className="space-y-3 border-t border-slate-200 p-4">
        {findings.length > 0 ? (
          findings.map((finding) => (
            <FindingItemCard
              key={finding.fingerprint}
              finding={finding}
            />
          ))
        ) : (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
            {emptyText}
          </div>
        )}
      </div>
    </details>
  )
}

function TestItemCard({
  testItem,
}: {
  testItem: TestChangeItem
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="font-medium text-slate-900">
        {testItem.title}
      </div>

      <div className="mt-2 flex flex-wrap gap-2 text-xs">
        {testItem.test_type ? (
          <span className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-violet-700">
            {testItem.test_type}
          </span>
        ) : null}

        {testItem.file_path ? (
          <span className="break-all rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-600">
            {testItem.file_path}
          </span>
        ) : null}
      </div>

      {testItem.reason ? (
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
          {testItem.reason}
        </p>
      ) : null}

      <div className="mt-3 break-all text-xs text-slate-400">
        指纹：
        {testItem.fingerprint
          ? testItem.fingerprint.slice(
              0,
              16,
            )
          : "暂无"}
      </div>
    </div>
  )
}

function TestChangeGroup({
  title,
  description,
  testItems,
  emptyText,
  tone,
}: {
  title: string
  description: string
  testItems: TestChangeItem[]
  emptyText: string
  tone:
    | "added"
    | "removed"
    | "persisting"
}) {
  const toneClassName = {
    added:
      "border-blue-200 bg-blue-50 text-blue-700",

    removed:
      "border-slate-300 bg-slate-100 text-slate-600",

    persisting:
      "border-violet-200 bg-violet-50 text-violet-700",
  }[tone]

  return (
    <details
      open={tone !== "persisting"}
      className="rounded-xl border border-slate-200 bg-slate-50"
    >
      <summary className="cursor-pointer list-none p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="font-medium text-slate-900">
              {title}
            </div>

            <div className="mt-1 text-sm text-slate-500">
              {description}
            </div>
          </div>

          <span
            className={[
              "rounded-full border",
              "px-2.5 py-1 text-xs",
              toneClassName,
            ].join(" ")}
          >
            {testItems.length} 项
          </span>
        </div>
      </summary>

      <div className="space-y-3 border-t border-slate-200 p-4">
        {testItems.length > 0 ? (
          testItems.map(
            (testItem) => (
              <TestItemCard
                key={
                  testItem.fingerprint
                }
                testItem={testItem}
              />
            ),
          )
        ) : (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
            {emptyText}
          </div>
        )}
      </div>
    </details>
  )
}

function TraceMetricCard({
  label,
  change,
  unit = "",
}: {
  label: string
  change:
    | TraceMetricChange
    | null
    | undefined
  unit?: string
}) {
  if (!change) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="text-sm text-slate-500">
          {label}
        </div>

        <div className="mt-2 text-sm text-slate-400">
          缺少可比较数据
        </div>
      </div>
    )
  }

  const trend =
    change.trend as ReviewCompareTrend

  let changeDescription =
    "保持不变"

  if (change.delta > 0) {
    changeDescription =
      `增加 ${change.delta}${unit}`
  } else if (change.delta < 0) {
    changeDescription =
      `减少 ${Math.abs(
        change.delta,
      )}${unit}`
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">
        {label}
      </div>

      <div className="mt-2 font-medium text-slate-900">
        {change.base_value}
        {unit}
        {" → "}
        {change.target_value}
        {unit}
      </div>

      <div className="mt-1 text-sm text-slate-500">
        {changeDescription}
      </div>

      <span
        className={[
          "mt-3 inline-flex",
          "rounded-full border",
          "px-2.5 py-1 text-xs",
          getTrendClassName(
            trend,
          ),
        ].join(" ")}
      >
        {getTrendLabel(
          trend,
        )}
      </span>
    </div>
  )
}

export function CodeReviewComparePanel({
  knowledgeBaseId,
}: CodeReviewComparePanelProps) {
  const [
    baseReviewRunId,
    setBaseReviewRunId,
  ] = useState("")

  const [
    targetReviewRunId,
    setTargetReviewRunId,
  ] = useState("")

  const reviewRunsQuery = useQuery({
    queryKey: [
      "code-review-runs",
      knowledgeBaseId,
      "compare-options",
    ],

    queryFn: () =>
      CodeSkillService
        .readCodeReviewRuns({
          knowledgeBaseId,
          skip: 0,
          limit: 100,
        }),

    staleTime: 30_000,
  })

  const reviewRuns =
    useMemo<
      ReviewRunCompareOption[]
    >(
      () =>
        sortReviewRunsNewestFirst(
          (
            reviewRunsQuery
              .data?.data ?? []
          ).map(
            (reviewRun) => ({
              id:
                reviewRun.id,
              title:
                reviewRun.title,
              created_at:
                reviewRun.created_at,
              risk_level:
                reviewRun.risk_level,
              generation_status:
                reviewRun
                  .generation_status,
            }),
          ),
        ),
      [
        reviewRunsQuery.data,
      ],
    )

  const latestReviewPair =
    useMemo(
      () =>
        getLatestReviewPair(
          reviewRuns,
        ),
      [reviewRuns],
    )

  useEffect(() => {
    const reviewRunIds =
      new Set(
        reviewRuns.map(
          (reviewRun) =>
            reviewRun.id,
        ),
      )

    setBaseReviewRunId(
      (currentValue) => {
        if (
          currentValue &&
          reviewRunIds.has(
            currentValue,
          )
        ) {
          return currentValue
        }

        return (
          latestReviewPair
            ?.base.id ?? ""
        )
      },
    )

    setTargetReviewRunId(
      (currentValue) => {
        if (
          currentValue &&
          reviewRunIds.has(
            currentValue,
          )
        ) {
          return currentValue
        }

        return (
          latestReviewPair
            ?.target.id ?? ""
        )
      },
    )
  }, [
    latestReviewPair,
    reviewRuns,
  ])

  const compareMutation =
    useMutation({
      mutationFn: ({
        baseReviewRunId:
          selectedBaseId,
        targetReviewRunId:
          selectedTargetId,
      }: CompareSelection) =>
        CodeSkillService
          .compareCodeReviewRuns({
            knowledgeBaseId,

            requestBody: {
              base_review_run_id:
                selectedBaseId,

              target_review_run_id:
                selectedTargetId,
            },
          }),

      onSuccess: () => {
        window
          .requestAnimationFrame(
            () => {
              document
                .getElementById(
                  "code-review-compare-result",
                )
                ?.scrollIntoView({
                  behavior:
                    "smooth",
                  block:
                    "start",
                })
            },
          )
      },
    })

  const canCompareSelected =
    canCompareReviewRuns(
      baseReviewRunId,
      targetReviewRunId,
    )

  const handleCompareLatest =
    () => {
      if (!latestReviewPair) {
        return
      }

      const nextSelection = {
        baseReviewRunId:
          latestReviewPair.base.id,

        targetReviewRunId:
          latestReviewPair.target.id,
      }

      setBaseReviewRunId(
        nextSelection
          .baseReviewRunId,
      )

      setTargetReviewRunId(
        nextSelection
          .targetReviewRunId,
      )

      compareMutation.reset()

      compareMutation.mutate(
        nextSelection,
      )
    }

  const handleCompareSelected =
    () => {
      if (
        !canCompareSelected
      ) {
        return
      }

      compareMutation.reset()

      compareMutation.mutate({
        baseReviewRunId,
        targetReviewRunId,
      })
    }

  const result =
    compareMutation.data

  return (
    <section className="space-y-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">
            Review 对比
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            A 为基准版本，B
            为目标版本。所有变化均按照
            A → B 解释。
          </p>
        </div>

        <button
          type="button"
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={
            reviewRunsQuery
              .isFetching
          }
          onClick={() => {
            void reviewRunsQuery
              .refetch()
          }}
        >
          {reviewRunsQuery
            .isFetching
            ? "刷新中..."
            : "刷新记录"}
        </button>
      </div>

      {reviewRunsQuery
        .isPending ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
          正在加载 Review
          历史记录...
        </div>
      ) : null}

      {reviewRunsQuery
        .isError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
          <div className="font-medium text-rose-700">
            Review
            历史加载失败
          </div>

          <pre className="mt-2 whitespace-pre-wrap text-xs text-rose-600">
            {formatCompareApiError(
              reviewRunsQuery.error,
            )}
          </pre>
        </div>
      ) : null}

      {!reviewRunsQuery
        .isPending &&
      !reviewRunsQuery
        .isError &&
      reviewRuns.length < 2 ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          至少需要两条 Review
          历史记录才能进行对比。请先生成两次代码审查。
        </div>
      ) : null}

      {reviewRuns.length >= 2 ? (
        <>
          <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-medium text-blue-900">
                  快速对比最近两次
                </div>

                <div className="mt-1 text-sm text-blue-700">
                  系统自动使用倒数第二次作为
                  A，最新一次作为 B。
                </div>
              </div>

              <button
                type="button"
                className="rounded-lg border border-blue-600 bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={
                  compareMutation
                    .isPending ||
                  !latestReviewPair
                }
                onClick={
                  handleCompareLatest
                }
              >
                {compareMutation
                  .isPending
                  ? "正在对比..."
                  : "比较最近两次"}
              </button>
            </div>
          </div>

          <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div>
              <div className="font-medium text-slate-900">
                自定义对比
              </div>

              <div className="mt-1 text-sm text-slate-500">
                手动选择任意两条已加载的
                Review 历史记录。
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <label className="space-y-1.5 text-sm">
                <span className="font-medium text-slate-700">
                  基准 Review A
                </span>

                <select
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900"
                  value={
                    baseReviewRunId
                  }
                  disabled={
                    compareMutation
                      .isPending
                  }
                  onChange={(
                    event,
                  ) => {
                    setBaseReviewRunId(
                      event
                        .target
                        .value,
                    )

                    compareMutation
                      .reset()
                  }}
                >
                  <option value="">
                    请选择基准 Review
                  </option>

                  {reviewRuns.map(
                    (reviewRun) => (
                      <option
                        key={
                          reviewRun.id
                        }
                        value={
                          reviewRun.id
                        }
                      >
                        {formatReviewRunLabel(
                          reviewRun,
                        )}
                        {" · "}
                        {formatReviewDateTime(
                          reviewRun
                            .created_at,
                        )}
                      </option>
                    ),
                  )}
                </select>
              </label>

              <label className="space-y-1.5 text-sm">
                <span className="font-medium text-slate-700">
                  目标 Review B
                </span>

                <select
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900"
                  value={
                    targetReviewRunId
                  }
                  disabled={
                    compareMutation
                      .isPending
                  }
                  onChange={(
                    event,
                  ) => {
                    setTargetReviewRunId(
                      event
                        .target
                        .value,
                    )

                    compareMutation
                      .reset()
                  }}
                >
                  <option value="">
                    请选择目标 Review
                  </option>

                  {reviewRuns.map(
                    (reviewRun) => (
                      <option
                        key={
                          reviewRun.id
                        }
                        value={
                          reviewRun.id
                        }
                      >
                        {formatReviewRunLabel(
                          reviewRun,
                        )}
                        {" · "}
                        {formatReviewDateTime(
                          reviewRun
                            .created_at,
                        )}
                      </option>
                    ),
                  )}
                </select>
              </label>
            </div>

            {baseReviewRunId &&
            targetReviewRunId &&
            baseReviewRunId ===
              targetReviewRunId ? (
              <div className="text-sm text-amber-700">
                基准 Review A 和目标
                Review B
                不能选择同一条记录。
              </div>
            ) : null}

            <button
              type="button"
              className="w-fit rounded-lg border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={
                compareMutation
                  .isPending ||
                !canCompareSelected
              }
              onClick={
                handleCompareSelected
              }
            >
              {compareMutation
                .isPending
                ? "正在对比..."
                : "开始自定义对比"}
            </button>
          </div>
        </>
      ) : null}

      {compareMutation
        .isError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
          <div className="font-medium text-rose-700">
            Review 对比失败
          </div>

          <pre className="mt-2 whitespace-pre-wrap text-xs text-rose-600">
            {formatCompareApiError(
              compareMutation.error,
            )}
          </pre>
        </div>
      ) : null}

      {result ? (
        <div
          id="code-review-compare-result"
          className="scroll-mt-6 space-y-5 border-t border-slate-200 pt-5"
        >
          <div>
            <h4 className="text-lg font-semibold text-slate-900">
              对比结果
            </h4>

            <p className="mt-1 text-sm text-slate-500">
              以下结论由历史快照进行确定性比较，不会重新调用
              LLM。
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ReviewReferenceCard
              label="基准 Review A"
              review={
                result.base_review
              }
            />

            <ReviewReferenceCard
              label="目标 Review B"
              review={
                result.target_review
              }
            />
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-sm font-medium text-slate-700">
              总体结论
            </div>

            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
              {
                result
                  .overall_change
                  .summary
              }
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ValueChangeCard
              label="风险等级"
              change={
                result
                  .overall_change
                  .risk
              }
            />

            <ValueChangeCard
              label="合并建议"
              change={
                result
                  .overall_change
                  .merge_recommendation
              }
            />

            <ValueChangeCard
              label="生成状态"
              change={
                result
                  .overall_change
                  .generation_status
              }
            />

            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-sm text-slate-500">
                Diff 对比
              </div>

              <div className="mt-2 font-medium text-slate-900">
                {result
                  .overall_change
                  .same_diff
                  ? "相同 Diff"
                  : "Diff 已变化"}
              </div>

              <span
                className={[
                  "mt-3 inline-flex",
                  "rounded-full border",
                  "px-2.5 py-1 text-xs",
                  result
                    .overall_change
                    .same_diff
                    ? "border-slate-200 bg-slate-50 text-slate-700"
                    : "border-blue-200 bg-blue-50 text-blue-700",
                ].join(" ")}
              >
                {result
                  .overall_change
                  .same_diff
                  ? "未变化"
                  : "已变化"}
              </span>
            </div>
          </div>

          <div>
            <h5 className="font-medium text-slate-900">
              统计变化
            </h5>

            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricChangeCard
                label="变更文件数"
                change={
                  result
                    .metric_changes
                    .changed_file_count
                }
              />

              <MetricChangeCard
                label="变更符号数"
                change={
                  result
                    .metric_changes
                    .changed_symbol_count
                }
              />

              <MetricChangeCard
                label="Finding 数"
                change={
                  result
                    .metric_changes
                    .finding_count
                }
              />

              <MetricChangeCard
                label="推荐测试数"
                change={
                  result
                    .metric_changes
                    .recommended_test_count
                }
              />
            </div>
          </div>
          <div className="space-y-3">
            <div>
              <h5 className="font-medium text-slate-900">
                Finding 差异
              </h5>

              <p className="mt-1 text-sm text-slate-500">
                根据 Finding
                内容指纹识别新增、已解决和持续存在的问题，不依赖
                LLM 生成的 Finding ID。
              </p>
            </div>

            <FindingChangeGroup
              title="新增 Findings"
              description="只在目标 Review B 中出现的问题。"
              findings={
                result
                  .finding_changes
                  .added
              }
              emptyText="目标版本没有新增 Finding。"
              tone="added"
            />

            <FindingChangeGroup
              title="已解决 Findings"
              description="基准 Review A 中存在，但目标 Review B 中已经消失的问题。"
              findings={
                result
                  .finding_changes
                  .resolved
              }
              emptyText="没有识别出已解决的 Finding。"
              tone="resolved"
            />

            <FindingChangeGroup
              title="持续存在的 Findings"
              description="在两次 Review 中都能够匹配到的问题。"
              findings={
                result
                  .finding_changes
                  .persisting
              }
              emptyText="没有持续存在的 Finding。"
              tone="persisting"
            />
          </div>
          <div className="space-y-3">
            <div>
              <h5 className="font-medium text-slate-900">
                测试建议差异
              </h5>

              <p className="mt-1 text-sm text-slate-500">
                比较两次审查中的测试文件、测试类型、标题和推荐原因。
              </p>
            </div>

            <TestChangeGroup
              title="新增测试建议"
              description="只在目标 Review B 中出现的测试建议。"
              testItems={
                result
                  .test_changes
                  .added
              }
              emptyText="目标版本没有新增测试建议。"
              tone="added"
            />

            <TestChangeGroup
              title="已移除测试建议"
              description="基准 Review A 中存在，但目标 Review B 中不再出现的建议。"
              testItems={
                result
                  .test_changes
                  .removed
              }
              emptyText="没有被移除的测试建议。"
              tone="removed"
            />

            <TestChangeGroup
              title="持续保留的测试建议"
              description="在两次 Review 中都能够匹配到的测试建议。"
              testItems={
                result
                  .test_changes
                  .persisting
              }
              emptyText="没有持续保留的测试建议。"
              tone="persisting"
            />
          </div>
          <div>
            <div>
              <h5 className="font-medium text-slate-900">
                生成 Trace 差异
              </h5>

              <p className="mt-1 text-sm text-slate-500">
                Trace
                仅用于观察生成过程，不参与风险等级和合并结论。
              </p>
            </div>

            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <ValueChangeCard
                label="模型"
                change={
                  result
                    .trace_changes
                    .model
                }
              />

              <TraceMetricCard
                label="生成耗时"
                change={
                  result
                    .trace_changes
                    .duration_ms
                }
                unit="ms"
              />

              <TraceMetricCard
                label="Evidence 数量"
                change={
                  result
                    .trace_changes
                    .evidence_item_count
                }
              />

              <TraceMetricCard
                label="输出字符数"
                change={
                  result
                    .trace_changes
                    .output_characters
                }
              />
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}