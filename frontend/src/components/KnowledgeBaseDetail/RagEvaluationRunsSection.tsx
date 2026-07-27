import {
  CollapsibleSection,
} from "./CollapsibleSection"
import {
  RagSourceList,
} from "./RagSourceList"
import {
  formatLatency,
  formatPercent,
} from "./knowledgeBaseFormatters"
import type {
  KnowledgeBaseEvaluationController,
} from "./useKnowledgeBaseEvaluation"

export function RagEvaluationRunsSection({
  evaluation,
}: {
  evaluation:
    KnowledgeBaseEvaluationController
}) {
  const query = evaluation.ragEvalRunsQuery

  return (
    <CollapsibleSection
      title="RAG 评测运行历史"
      description="按关键词、失败状态和失败类型筛选评测运行记录。"
      isOpen={evaluation.evalRunsOpen}
      onToggle={() => evaluation.setEvalRunsOpen((current) => !current)}
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <input
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            placeholder="搜索问题或回答"
            value={evaluation.evalRunKeyword}
            onChange={(event) => evaluation.setEvalRunKeyword(event.target.value)}
          />
          <select
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            value={evaluation.evalFailureType}
            onChange={(event) => evaluation.setEvalFailureType(event.target.value as typeof evaluation.evalFailureType)}
          >
            <option value="all">全部类型</option>
            <option value="keyword">关键词未命中</option>
            <option value="source">来源未命中</option>
            <option value="error">运行错误</option>
            <option value="zero">零分</option>
          </select>
          <label className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={evaluation.evalFailedOnly}
              onChange={(event) => evaluation.setEvalFailedOnly(event.target.checked)}
            />
            仅看失败
          </label>
          <button
            type="button"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            onClick={() => {
              evaluation.setEvalRunKeyword("")
              evaluation.setEvalFailureType("all")
              evaluation.setEvalFailedOnly(false)
            }}
          >
            清空筛选
          </button>
        </div>

        {query.isLoading ? (
          <div className="text-sm text-slate-600">正在加载评测历史...</div>
        ) : null}
        {query.isError ? (
          <pre className="whitespace-pre-wrap text-sm text-rose-600">
            {JSON.stringify(query.error, null, 2)}
          </pre>
        ) : null}

        {query.data ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-600">
              共 {query.data.count} 条记录。
            </div>
            {query.data.data.map((run) => (
              <details
                key={run.id}
                className="rounded-xl border border-slate-300 bg-white p-4"
              >
                <summary className="cursor-pointer text-sm font-medium text-slate-900">
                  {run.question}
                  {" ｜ "}
                  得分 {run.score ?? "-"}
                  {" ｜ "}
                  {formatLatency(run.latency_ms)}
                  {" ｜ "}
                  {run.is_failed ? "失败" : "正常"}
                </summary>

                <div className="mt-4 space-y-4">
                  {run.error_message ? (
                    <div className="text-sm text-rose-600">{run.error_message}</div>
                  ) : null}
                  <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                    <Meta label="关键词命中" value={run.keyword_hit ? "是" : "否"} />
                    <Meta label="来源命中" value={run.source_hit ? "是" : "否"} />
                    <Meta label="语义权重" value={String(run.semantic_weight ?? "-")} />
                    <Meta label="关键词权重" value={String(run.keyword_weight ?? "-")} />
                  </div>
                  <pre className="whitespace-pre-wrap rounded-lg border border-slate-300 bg-slate-50 p-3 text-sm text-slate-900">
                    {run.answer}
                  </pre>
                  <div>
                    <h4 className="mb-2 font-medium text-slate-900">引用来源</h4>
                    <RagSourceList sources={run.sources ?? []} />
                  </div>
                  <div className="text-xs text-slate-500">
                    关键词命中率展示：{formatPercent(run.keyword_hit ? 1 : 0)}
                  </div>
                </div>
              </details>
            ))}
          </div>
        ) : null}
      </div>
    </CollapsibleSection>
  )
}

function Meta({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-lg border border-slate-300 bg-slate-50 p-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="font-medium text-slate-900">{value}</div>
    </div>
  )
}
