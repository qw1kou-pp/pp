import type {
  KnowledgeBaseEvaluationController,
} from "./useKnowledgeBaseEvaluation"

export function AgentSettingsSection({
  evaluation,
}: {
  evaluation:
    KnowledgeBaseEvaluationController
}) {
  const config =
    evaluation.appliedAgentConfig
  const mutation =
    evaluation.updateAgentSettingsMutation

  return (
    <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          当前 Agent 默认配置
        </h2>
        <p className="text-sm leading-6 text-slate-600">
          Agent Chat、单题对比和批量对比会优先使用这组参数。保存后刷新页面仍然生效。
        </p>
      </div>

      {evaluation.agentSettingsQuery.isLoading ? (
        <div className="text-sm text-slate-600">
          正在加载 Agent 配置...
        </div>
      ) : null}

      {evaluation.agentSettingsQuery.isError ? (
        <pre className="whitespace-pre-wrap text-sm text-rose-600">
          {JSON.stringify(
            evaluation.agentSettingsQuery.error,
            null,
            2,
          )}
        </pre>
      ) : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <ConfigCard
          label="top_k"
          value={config.topK}
        />
        <ConfigCard
          label="max_steps"
          value={config.maxSteps}
        />
        <ConfigCard
          label="semantic_weight"
          value={config.semanticWeight}
        />
        <ConfigCard
          label="keyword_weight"
          value={config.keywordWeight}
        />
      </div>

      <button
        type="button"
        className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
        onClick={
          evaluation.handleResetAgentConfig
        }
        disabled={mutation.isPending}
      >
        {mutation.isPending
          ? "正在保存..."
          : "恢复默认配置"}
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
    </section>
  )
}

function ConfigCard({
  label,
  value,
}: {
  label: string
  value: number
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
