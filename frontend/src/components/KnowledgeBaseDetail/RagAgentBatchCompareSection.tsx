import type {
  KnowledgeBaseEvaluationController,
} from "./useKnowledgeBaseEvaluation"
import {
  formatLatency,
  formatNullableNumber,
} from "./knowledgeBaseFormatters"

export function RagAgentBatchCompareSection({
  evaluation,
}: {
  evaluation:
    KnowledgeBaseEvaluationController
}) {
  const mutation =
    evaluation
      .runRagAgentCompareEvalMutation
  const data = mutation.data

  return (
    <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          RAG vs Agent 批量对比评测
        </h2>
        <p className="text-sm leading-6 text-slate-600">
          使用当前知识库的评测样例，同时运行普通 RAG 和 Agent，比较耗时、来源数量和工具调用情况。
        </p>
      </div>

      <button
        type="button"
        className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
      >
        {mutation.isPending
          ? "批量对比运行中..."
          : "运行 RAG vs Agent 批量对比"}
      </button>

      {mutation.isError ? (
        <pre className="whitespace-pre-wrap text-sm text-rose-600">
          {JSON.stringify(
            mutation.error,
            null,
            2,
          )}
        </pre>
      ) : null}

      {data ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard
              label="样例数"
              value={String(
                data.summary.total_cases
                ?? data.count,
              )}
            />
            <MetricCard
              label="失败数"
              value={String(
                data.summary.failed
                ?? 0,
              )}
            />
            <MetricCard
              label="RAG 平均耗时"
              value={formatLatency(
                data.summary
                  .average_rag_latency_ms,
              )}
            />
            <MetricCard
              label="Agent 平均耗时"
              value={formatLatency(
                data.summary
                  .average_agent_latency_ms,
              )}
            />
            <MetricCard
              label="Agent 平均工具数"
              value={formatNullableNumber(
                data.summary
                  .average_agent_tool_call_count,
              )}
            />
            <MetricCard
              label="工具失败总数"
              value={String(
                data.summary
                  .total_agent_failed_tool_count
                ?? 0,
              )}
            />
            <MetricCard
              label="summarize_document"
              value={String(
                data.summary
                  .summarize_document_count
                ?? 0,
              )}
            />
            <MetricCard
              label="read_document_chunks"
              value={String(
                data.summary
                  .read_document_chunks_count
                ?? 0,
              )}
            />
          </div>

          <div className="space-y-3">
            {data.data.map(
              (item, index) => (
                <details
                  key={item.eval_case_id}
                  className="rounded-xl border border-slate-300 bg-white p-3"
                >
                  <summary className="cursor-pointer text-sm font-medium text-slate-900">
                    {index + 1}. {item.question}
                    {" ｜ "}
                    RAG {item.rag_latency_ms ?? "-"} ms
                    {" ｜ "}
                    Agent {item.agent_latency_ms ?? "-"} ms
                    {" ｜ "}
                    {item.is_failed
                      ? "有失败"
                      : "正常"}
                  </summary>

                  <div className="mt-3 grid grid-cols-1 gap-4 xl:grid-cols-2">
                    <AnswerColumn
                      title="普通 RAG"
                      answer={item.rag_answer}
                      error={
                        item.rag_error_message
                      }
                      meta={`Sources：${item.rag_sources_count ?? 0}`}
                    />
                    <AnswerColumn
                      title="Agent"
                      answer={item.agent_answer}
                      error={
                        item.agent_error_message
                      }
                      meta={`Sources：${item.agent_sources_count ?? 0} ｜ 工具调用：${item.agent_tool_call_count ?? 0} ｜ 工具失败：${item.agent_failed_tool_count ?? 0}`}
                    />
                  </div>
                </details>
              ),
            )}
          </div>
        </div>
      ) : null}
    </section>
  )
}

function MetricCard({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-xl border border-slate-300 bg-slate-50 p-3">
      <div className="text-xs text-slate-500">
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold text-slate-900">
        {value}
      </div>
    </div>
  )
}

function AnswerColumn({
  title,
  answer,
  error,
  meta,
}: {
  title: string
  answer?: string | null
  error?: string | null
  meta: string
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-slate-900">
        {title}
      </h3>
      {error ? (
        <div className="text-sm text-rose-600">
          {error}
        </div>
      ) : null}
      <div className="text-xs text-slate-500">
        {meta}
      </div>
      <div className="whitespace-pre-wrap rounded-lg border border-slate-300 bg-slate-50 p-3 text-sm text-slate-900">
        {answer || "暂无回答"}
      </div>
    </div>
  )
}
