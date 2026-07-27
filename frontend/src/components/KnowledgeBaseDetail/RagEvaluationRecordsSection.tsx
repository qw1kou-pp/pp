import type React from "react"

import {
  formatLatency,
  formatPercent,
} from "./knowledgeBaseFormatters"
import type {
  KnowledgeBaseEvaluationController,
} from "./useKnowledgeBaseEvaluation"

export function RagEvaluationRecordsSection({
  evaluation,
}: {
  evaluation:
    KnowledgeBaseEvaluationController
}) {
  return (
    <section className="space-y-6 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <ParamGroups evaluation={evaluation} />
      <div className="border-t border-slate-200 pt-5">
        <EvalBatches evaluation={evaluation} />
      </div>
      <div className="border-t border-slate-200 pt-5">
        <FailureSummary evaluation={evaluation} />
      </div>
    </section>
  )
}

function ParamGroups({
  evaluation,
}: {
  evaluation: KnowledgeBaseEvaluationController
}) {
  const query = evaluation.ragEvalParamGroupsQuery

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-900">参数版本对比</h2>
      <p className="text-sm text-slate-600">
        按 top_k、语义权重和关键词权重分组，对比平均分、失败率、命中率和耗时。
      </p>
      {query.isLoading ? <div className="text-sm text-slate-600">正在加载参数对比...</div> : null}
      {query.isError ? <pre className="whitespace-pre-wrap text-sm text-rose-600">{JSON.stringify(query.error, null, 2)}</pre> : null}
      {query.data ? (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead className="bg-slate-100">
              <tr>
                <Th>参数组合</Th><Th>运行次数</Th><Th>平均分</Th><Th>失败率</Th><Th>关键词命中</Th><Th>来源命中</Th><Th>平均耗时</Th>
              </tr>
            </thead>
            <tbody>
              {query.data.data.map((group) => (
                <tr key={`${group.top_k}-${group.semantic_weight}-${group.keyword_weight}`}>
                  <Td>
                    <div className="font-medium">{group.preset_names?.join("、") || "未命名参数组"}</div>
                    <div className="text-xs text-slate-500">top_k={group.top_k} ｜ S={group.semantic_weight} ｜ K={group.keyword_weight}</div>
                  </Td>
                  <Td>{group.total_runs}</Td>
                  <Td>{group.average_score?.toFixed(2) ?? "-"}</Td>
                  <Td>{formatPercent(group.failure_rate)}</Td>
                  <Td>{formatPercent(group.keyword_hit_rate)}</Td>
                  <Td>{formatPercent(group.source_hit_rate)}</Td>
                  <Td>{formatLatency(group.average_latency_ms)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}

function EvalBatches({
  evaluation,
}: {
  evaluation: KnowledgeBaseEvaluationController
}) {
  const query = evaluation.ragEvalBatchesQuery
  const mutation = evaluation.deleteRagEvalBatchMutation

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-900">实验批次记录</h2>
      <p className="text-sm text-slate-600">
        每次运行全部评测都会生成实验批次，用于对比不同参数组合。
      </p>
      {query.isLoading ? <div className="text-sm text-slate-600">正在加载实验批次...</div> : null}
      {query.isError || mutation.isError ? <pre className="whitespace-pre-wrap text-sm text-rose-600">{JSON.stringify(query.error ?? mutation.error, null, 2)}</pre> : null}
      {query.data ? (
        <div className="space-y-2">
          {query.data.data.map((batch) => (
            <div key={batch.id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-300 bg-slate-50 p-3">
              <div>
                <div className="font-medium text-slate-900">{batch.name}</div>
                <div className="text-xs text-slate-500">
                  top_k={batch.top_k} ｜ S={batch.semantic_weight} ｜ K={batch.keyword_weight} ｜ 成功/失败 {batch.ran}/{batch.failed}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  平均分 {batch.average_score?.toFixed(2) ?? "-"} ｜ 关键词 {formatPercent(batch.keyword_hit_rate)} ｜ 来源 {formatPercent(batch.source_hit_rate)} ｜ {formatLatency(batch.average_latency_ms)}
                </div>
              </div>
              <button
                type="button"
                className="rounded border border-rose-200 bg-white px-2 py-1 text-xs text-rose-600 disabled:opacity-50"
                onClick={() => evaluation.handleDeleteRagEvalBatch(batch.id)}
                disabled={mutation.isPending}
              >
                删除
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function FailureSummary({
  evaluation,
}: {
  evaluation: KnowledgeBaseEvaluationController
}) {
  const query = evaluation.ragEvalFailureAnalysisQuery
  const data = query.data

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-900">失败样例概览</h2>
      <p className="text-sm text-slate-600">
        汇总关键词未命中、来源未命中、运行错误、低分和零分情况。
      </p>
      {query.isLoading ? <div className="text-sm text-slate-600">正在加载失败分析...</div> : null}
      {query.isError ? <pre className="whitespace-pre-wrap text-sm text-rose-600">{JSON.stringify(query.error, null, 2)}</pre> : null}
      {data ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Metric label="总运行数" value={data.total_runs} />
          <Metric label="失败数" value={data.failed_runs} />
          <Metric label="失败率" value={formatPercent(data.failure_rate)} />
          <Metric label="关键词未命中" value={data.keyword_miss_count} />
          <Metric label="来源未命中" value={data.source_miss_count} />
          <Metric label="错误数" value={data.error_count} />
          <Metric label="低分数" value={data.low_score_count} />
          <Metric label="零分数" value={data.zero_score_count} />
        </div>
      ) : null}
    </div>
  )
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="border border-slate-300 px-3 py-2 text-left">{children}</th>
}
function Td({ children }: { children: React.ReactNode }) {
  return <td className="border border-slate-300 px-3 py-2">{children}</td>
}
function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-300 bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-slate-900">{value}</div>
    </div>
  )
}
