import {
  formatLatency,
  formatPercent,
} from "./knowledgeBaseFormatters"
import type {
  KnowledgeBaseEvaluationController,
} from "./useKnowledgeBaseEvaluation"

export function EvaluationSummarySection({
  evaluation,
}: {
  evaluation:
    KnowledgeBaseEvaluationController
}) {
  const query =
    evaluation.ragEvalSummaryQuery
  const runMutation =
    evaluation.runAllRagEvalCasesMutation
  const data = query.data

  return (
    <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            评测统计概览
          </h2>
          <p className="text-sm text-slate-600">
            汇总最近 RAG 评测结果，观察得分、命中率和耗时。
          </p>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            onClick={() => {
              void evaluation.refreshSummary()
            }}
          >
            刷新统计
          </button>
          <button
            type="button"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50"
            onClick={
              evaluation.handleRunAllRagEvalCases
            }
            disabled={runMutation.isPending}
          >
            {runMutation.isPending
              ? "批量运行中..."
              : "运行全部评测"}
          </button>
        </div>
      </div>

      {query.isLoading ? (
        <div className="text-sm text-slate-600">
          正在加载评测统计...
        </div>
      ) : null}

      {query.isError || runMutation.isError ? (
        <pre className="whitespace-pre-wrap text-sm text-rose-600">
          {JSON.stringify(
            query.error
            ?? runMutation.error,
            null,
            2,
          )}
        </pre>
      ) : null}

      {runMutation.data ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          本次共 {runMutation.data.total_cases} 条样例，成功 {runMutation.data.ran} 条，失败 {runMutation.data.failed} 条。
        </div>
      ) : null}

      {data ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard
            label="总评测次数"
            value={String(data.total_runs)}
          />
          <MetricCard
            label="平均分"
            value={
              data.average_score === null
              || data.average_score === undefined
                ? "-"
                : data.average_score.toFixed(2)
            }
          />
          <MetricCard
            label="关键词命中率"
            value={formatPercent(
              data.keyword_hit_rate,
            )}
          />
          <MetricCard
            label="来源命中率"
            value={formatPercent(
              data.source_hit_rate,
            )}
          />
          <MetricCard
            label="平均耗时"
            value={formatLatency(
              data.average_latency_ms,
            )}
          />
          <MetricCard
            label="最高分"
            value={
              data.max_score === null
              || data.max_score === undefined
                ? "-"
                : data.max_score.toFixed(2)
            }
          />
          <MetricCard
            label="最低分"
            value={
              data.min_score === null
              || data.min_score === undefined
                ? "-"
                : data.min_score.toFixed(2)
            }
          />
          <MetricCard
            label="最新评测时间"
            value={
              data.latest_run_at
                ? new Date(
                  data.latest_run_at,
                ).toLocaleString()
                : "-"
            }
            compact
          />
        </div>
      ) : null}
    </section>
  )
}

function MetricCard({
  label,
  value,
  compact = false,
}: {
  label: string
  value: string
  compact?: boolean
}) {
  return (
    <div className="rounded-xl border border-slate-300 bg-slate-50 p-3">
      <div className="text-xs text-slate-500">
        {label}
      </div>
      <div className={
        compact
          ? "mt-1 text-sm font-medium text-slate-900"
          : "mt-1 text-xl font-semibold text-slate-900"
      }>
        {value}
      </div>
    </div>
  )
}
