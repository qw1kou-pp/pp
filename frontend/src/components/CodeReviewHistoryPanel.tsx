import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  useEffect,
  useState,
} from "react"

import {
  CodeSkillService,
  type CodeReviewRunDetailPublic,
} from "@/client"

import {
  CodeReviewHistorySource,
} from "./CodeReviewHistorySource"

type GenerationStatusFilter =
  | ""
  | "completed"
  | "evidence_only"

type RiskLevelFilter =
  | ""
  | "low"
  | "medium"
  | "high"

type CodeReviewHistoryPanelProps = {
  knowledgeBaseId: string

  activeReviewRunId?: string | null

  onRestore: (
    detail: CodeReviewRunDetailPublic,
  ) => void

  onDeleted?: (
    reviewRunId: string,
  ) => void
}

const PAGE_SIZE = 10

export const codeReviewRunsQueryKey = (
  knowledgeBaseId: string,
) =>
  [
    "code-review-runs",
    knowledgeBaseId,
  ] as const

const formatApiError = (
  error: unknown,
) => {
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
  const detail =
    candidate.body?.detail

  if (
    typeof detail
    === "string"
  ) {
    return detail
  }

  if (
    detail
    && typeof detail
      === "object"
  ) {
    const detailObject =
      detail as {
        code?: unknown
        message?: unknown
      }

    const message =
      detailObject.message

    if (
      typeof message
      === "string"
      && message.trim()
    ) {
      return message
    }

    return JSON.stringify(
      detail,
      null,
      2,
    )
  }

  return (
    candidate.message
    || JSON.stringify(
      error,
      null,
      2,
    )
  )
}

//   if (candidate.body?.detail) {
//     if (
//       typeof candidate.body.detail
//       === "string"
//     ) {
//       return candidate.body.detail
//     }
//
//     return JSON.stringify(
//       candidate.body.detail,
//       null,
//       2,
//     )
//   }



const formatCreatedAt = (
  value: string,
) => {
  const date = new Date(value)

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return value
  }

  return date.toLocaleString(
    "zh-CN",
    {
      hour12: false,
    },
  )
}

const getGenerationStatusLabel = (
  status: string,
) => {
  if (status === "completed") {
    return "完整报告"
  }

  if (status === "evidence_only") {
    return "仅 Evidence"
  }

  return status
}

const getGenerationStatusClassName = (
  status: string,
) => {
  if (status === "completed") {
    return (
      "border-emerald-200 " +
      "bg-emerald-50 " +
      "text-emerald-700"
    )
  }

  return (
    "border-amber-200 " +
    "bg-amber-50 " +
    "text-amber-700"
  )
}

const getRiskLabel = (
  riskLevel?: string | null,
) => {
  if (riskLevel === "high") {
    return "高风险"
  }

  if (riskLevel === "medium") {
    return "中风险"
  }

  if (riskLevel === "low") {
    return "低风险"
  }

  return "未评估"
}

const getRiskClassName = (
  riskLevel?: string | null,
) => {
  if (riskLevel === "high") {
    return (
      "border-rose-200 " +
      "bg-rose-50 " +
      "text-rose-700"
    )
  }

  if (riskLevel === "medium") {
    return (
      "border-amber-200 " +
      "bg-amber-50 " +
      "text-amber-700"
    )
  }

  if (riskLevel === "low") {
    return (
      "border-emerald-200 " +
      "bg-emerald-50 " +
      "text-emerald-700"
    )
  }

  return (
    "border-slate-200 " +
    "bg-slate-50 " +
    "text-slate-600"
  )
}

const getMergeRecommendationLabel = (
  recommendation?: string | null,
) => {
  if (recommendation === "approve") {
    return "可以合并"
  }

  if (
    recommendation ===
    "request_changes"
  ) {
    return "建议修改"
  }

  if (
    recommendation ===
    "needs_review"
  ) {
    return "需要审查"
  }

  return "暂无建议"
}

export function CodeReviewHistoryPanel({
  knowledgeBaseId,
  activeReviewRunId,
  onRestore,
  onDeleted,
}: CodeReviewHistoryPanelProps) {
  const queryClient =
    useQueryClient()

  const [page, setPage] =
    useState(0)

  const [
    generationStatus,
    setGenerationStatus,
  ] =
    useState<GenerationStatusFilter>("")

  const [
    riskLevel,
    setRiskLevel,
  ] =
    useState<RiskLevelFilter>("")

  const reviewRunsQuery =
    useQuery({
      queryKey: [
        ...codeReviewRunsQueryKey(
          knowledgeBaseId,
        ),
        page,
        generationStatus,
        riskLevel,
      ],

      queryFn: () =>
        CodeSkillService
          .readCodeReviewRuns({
            knowledgeBaseId,
            skip:
              page * PAGE_SIZE,
            limit:
              PAGE_SIZE,

            generationStatus:
              generationStatus ||
              undefined,

            riskLevel:
              riskLevel ||
              undefined,
          }),
    })

  const restoreMutation =
    useMutation({
      mutationFn: (
        reviewRunId: string,
      ) =>
        CodeSkillService
          .readCodeReviewRunDetail({
            knowledgeBaseId,
            reviewRunId,
          }),

      onSuccess: (
        detail,
      ) => {
        onRestore(detail)
      },
    })

  const deleteMutation =
    useMutation({
      mutationFn: (
        reviewRunId: string,
      ) =>
        CodeSkillService
          .deleteCodeReviewRun({
            knowledgeBaseId,
            reviewRunId,
          }),

      onSuccess: async (
        _result,
        deletedReviewRunId,
      ) => {
        onDeleted?.(
          deletedReviewRunId,
        )

        const currentPageCount =
          reviewRunsQuery.data
            ?.data.length ?? 0

        if (
          page > 0 &&
          currentPageCount === 1
        ) {
          setPage(
            (currentPage) =>
              Math.max(
                currentPage - 1,
                0,
              ),
          )

          return
        }

        await queryClient
          .invalidateQueries({
            queryKey:
              codeReviewRunsQueryKey(
                knowledgeBaseId,
              ),
          })
      },
    })

  const totalCount =
    reviewRunsQuery.data
      ?.count ?? 0

  const totalPages =
    Math.max(
      1,
      Math.ceil(
        totalCount /
          PAGE_SIZE,
      ),
    )

  useEffect(() => {
    const lastPageIndex =
      Math.max(
        totalPages - 1,
        0,
      )

    if (
      page >
      lastPageIndex
    ) {
      setPage(
        lastPageIndex,
      )
    }
  }, [
    page,
    totalPages,
  ])

  const handleDelete = (
    reviewRunId: string,
  ) => {
    const confirmed =
      window.confirm(
        "确定删除这条代码审查历史吗？删除后无法恢复。",
      )

    if (!confirmed) {
      return
    }

    deleteMutation.mutate(
      reviewRunId,
    )
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-medium text-slate-900">
            Review 历史
          </h3>

          <p className="mt-1 text-xs text-slate-500">
            查看并恢复此前保存的
            Diff、Evidence、报告和生成参数。
          </p>
        </div>

        <button
          type="button"
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
          disabled={
            reviewRunsQuery.isFetching
          }
          onClick={() => {
            void reviewRunsQuery.refetch()
          }}
        >
          {reviewRunsQuery.isFetching
            ? "刷新中..."
            : "刷新历史"}
        </button>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="block text-slate-500">
            生成状态
          </span>

          <select
            className="w-full rounded-lg border border-slate-500 bg-white px-3 py-2 outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            value={generationStatus}
            onChange={(event) => {
              setGenerationStatus(
                event.target.value as
                  GenerationStatusFilter,
              )

              setPage(0)
            }}
          >
            <option value="">
              全部状态
            </option>

            <option value="completed">
              完整报告
            </option>

            <option value="evidence_only">
              仅 Evidence
            </option>
          </select>
        </label>

        <label className="space-y-1 text-sm">
          <span className="block text-slate-500">
            风险等级
          </span>

          <select
            className="w-full rounded-lg border border-slate-500 bg-white px-3 py-2 outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            value={riskLevel}
            onChange={(event) => {
              setRiskLevel(
                event.target.value as
                  RiskLevelFilter,
              )

              setPage(0)
            }}
          >
            <option value="">
              全部风险
            </option>

            <option value="high">
              高风险
            </option>

            <option value="medium">
              中风险
            </option>

            <option value="low">
              低风险
            </option>
          </select>
        </label>
      </div>

      {reviewRunsQuery.isPending ? (
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
          正在加载 Review 历史...
        </div>
      ) : null}

      {reviewRunsQuery.isError ? (
        <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4">
          <div className="font-medium text-rose-700">
            Review 历史加载失败
          </div>

          <pre className="mt-2 whitespace-pre-wrap text-xs text-rose-700">
            {formatApiError(
              reviewRunsQuery.error,
            )}
          </pre>
        </div>
      ) : null}

      {restoreMutation.isError ? (
        <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4">
          <div className="font-medium text-rose-700">
            历史详情加载失败
          </div>

          <pre className="mt-2 whitespace-pre-wrap text-xs text-rose-700">
            {formatApiError(
              restoreMutation.error,
            )}
          </pre>
        </div>
      ) : null}

      {deleteMutation.isError ? (
        <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4">
          <div className="font-medium text-rose-700">
            删除历史失败
          </div>

          <pre className="mt-2 whitespace-pre-wrap text-xs text-rose-700">
            {formatApiError(
              deleteMutation.error,
            )}
          </pre>
        </div>
      ) : null}

      {reviewRunsQuery.data ? (
        <div className="mt-4 space-y-3">
          <div className="text-sm text-slate-500">
            共 {totalCount} 条记录，
            当前第 {page + 1} /
            {totalPages} 页。
          </div>

          {reviewRunsQuery.data
            .data.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
              当前筛选条件下没有
              Review 历史。
            </div>
          ) : (
            reviewRunsQuery.data
              .data.map(
                (reviewRun) => {
                  const isActive =
                    activeReviewRunId ===
                    reviewRun.id

                  const isRestoring =
                    restoreMutation.isPending &&
                    restoreMutation.variables ===
                      reviewRun.id

                  const isDeleting =
                    deleteMutation.isPending &&
                    deleteMutation.variables ===
                      reviewRun.id

                  return (
                    <article
                      key={reviewRun.id}
                      className={`rounded-xl border p-4 transition ${
                        isActive
                          ? "border-sky-300 bg-sky-50/70 ring-2 ring-sky-100"
                          : "border-slate-200 bg-white hover:border-slate-300"
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="break-all font-medium text-slate-900">
                            {
                              reviewRun.title
                            }
                          </div>

                          <div className="mt-1 text-xs text-slate-500">
                            {formatCreatedAt(
                              reviewRun.created_at,
                            )}
                          </div>

                          <CodeReviewHistorySource
                            source={
                              reviewRun.source
                            }
                            compact
                          />
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <span
                            className={`rounded-full border px-2.5 py-1 text-xs font-medium ${getGenerationStatusClassName(
                              reviewRun.generation_status,
                            )}`}
                          >
                            {getGenerationStatusLabel(
                              reviewRun.generation_status,
                            )}
                          </span>



                          <span
                            className={`rounded-full border px-2.5 py-1 text-xs font-medium ${getRiskClassName(
                              reviewRun.risk_level,
                            )}`}
                          >
                            {getRiskLabel(
                              reviewRun.risk_level,
                            )}
                          </span>
                        </div>
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600 md:grid-cols-5">
                        <div>
                          文件：
                          {
                            reviewRun.changed_file_count
                          }
                        </div>

                        <div>
                          符号：
                          {
                            reviewRun.changed_symbol_count
                          }
                        </div>

                        <div>
                          Findings：
                          {
                            reviewRun.finding_count
                          }
                        </div>

                        <div>
                          测试：
                          {
                            reviewRun.recommended_test_count
                          }
                        </div>

                        <div>
                          {getMergeRecommendationLabel(
                            reviewRun.merge_recommendation,
                          )}
                        </div>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="rounded-lg bg-sky-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
                          disabled={
                            restoreMutation.isPending ||
                            deleteMutation.isPending
                          }
                          onClick={() =>
                            restoreMutation.mutate(
                              reviewRun.id,
                            )
                          }
                        >
                          {isRestoring
                            ? "正在恢复..."
                            : isActive
                              ? "当前已打开"
                              : "查看并恢复"}
                        </button>

                        <button
                          type="button"
                          className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-sm font-medium text-rose-600 transition hover:bg-rose-50 disabled:opacity-50"
                          disabled={
                            restoreMutation.isPending ||
                            deleteMutation.isPending
                          }
                          onClick={() =>
                            handleDelete(
                              reviewRun.id,
                            )
                          }
                        >
                          {isDeleting
                            ? "删除中..."
                            : "删除"}
                        </button>
                      </div>
                    </article>
                  )
                },
              )
          )}

          <div className="flex items-center justify-between gap-3 border-t border-slate-200 pt-3">
            <button
              type="button"
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={
                page === 0 ||
                reviewRunsQuery.isFetching
              }
              onClick={() =>
                setPage(
                  (currentPage) =>
                    Math.max(
                      currentPage - 1,
                      0,
                    ),
                )
              }
            >
              上一页
            </button>

            <span className="text-sm text-slate-500">
              {page + 1} / {totalPages}
            </span>

            <button
              type="button"
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={
                page + 1 >= totalPages ||
                reviewRunsQuery.isFetching
              }
              onClick={() =>
                setPage(
                  (currentPage) =>
                    currentPage + 1,
                )
              }
            >
              下一页
            </button>
          </div>
        </div>
      ) : null}
    </section>
  )
}