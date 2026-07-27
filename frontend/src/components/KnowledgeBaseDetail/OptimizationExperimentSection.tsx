import {
  getResultClassName,
  getResultLabel,
} from "./codeAgentOptimization"
import type {
  KnowledgeBaseEvaluationController,
} from "./useKnowledgeBaseEvaluation"

export function OptimizationExperimentSection({
  evaluation,
}: {
  evaluation:
    KnowledgeBaseEvaluationController
}) {
  const rows = evaluation.compareBatchRows
  const baseline = evaluation.baselineCompareBatch
  const optimized = evaluation.optimizedCompareBatch

  return (
    <section className="space-y-5 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          优化前后对比与实验报告
        </h2>
        <p className="text-sm leading-6 text-slate-600">
          选择两个 RAG vs Agent 批次，对比失败率、耗时、工具调用和来源增益，并生成 Markdown 报告。
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <BatchSelect
          label="优化前批次"
          value={evaluation.baselineCompareBatchId}
          rows={rows}
          onChange={evaluation.setBaselineCompareBatchId}
        />
        <BatchSelect
          label="优化后批次"
          value={evaluation.optimizedCompareBatchId}
          rows={rows}
          onChange={evaluation.setOptimizedCompareBatchId}
        />
      </div>

      {baseline && optimized ? (
        <div className="space-y-4">
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead className="bg-slate-100">
                <tr>
                  <th className="border border-slate-300 px-3 py-2 text-left">指标</th>
                  <th className="border border-slate-300 px-3 py-2 text-right">优化前</th>
                  <th className="border border-slate-300 px-3 py-2 text-right">优化后</th>
                  <th className="border border-slate-300 px-3 py-2 text-right">变化</th>
                  <th className="border border-slate-300 px-3 py-2 text-left">判断</th>
                  <th className="border border-slate-300 px-3 py-2 text-left">说明</th>
                </tr>
              </thead>
              <tbody>
                {evaluation.optimizationCompareRows.map((row) => (
                  <tr key={row.metric}>
                    <td className="border border-slate-300 px-3 py-2 font-medium">{row.metric}</td>
                    <td className="border border-slate-300 px-3 py-2 text-right">{row.beforeText}</td>
                    <td className="border border-slate-300 px-3 py-2 text-right">{row.afterText}</td>
                    <td className="border border-slate-300 px-3 py-2 text-right">{row.changeText}</td>
                    <td className={`border border-slate-300 px-3 py-2 ${getResultClassName(row.result)}`}>
                      {getResultLabel(row.result)}
                    </td>
                    <td className="border border-slate-300 px-3 py-2 text-slate-600">{row.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              onClick={evaluation.handleGenerateExperimentReport}
            >
              生成报告预览
            </button>
            <button
              type="button"
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50"
              onClick={evaluation.handleDownloadExperimentReport}
              disabled={!evaluation.experimentReportMarkdown.trim()}
            >
              下载前端 Markdown 报告
            </button>
            <button
              type="button"
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50"
              onClick={() => evaluation.exportBackendCodeAgentReportMutation.mutate()}
              disabled={evaluation.exportBackendCodeAgentReportMutation.isPending}
            >
              {evaluation.exportBackendCodeAgentReportMutation.isPending
                ? "后端报告生成中..."
                : "后端导出 Markdown 报告"}
            </button>
          </div>

          {evaluation.exportBackendCodeAgentReportMutation.isError ? (
            <pre className="whitespace-pre-wrap text-sm text-rose-600">
              {JSON.stringify(evaluation.exportBackendCodeAgentReportMutation.error, null, 2)}
            </pre>
          ) : null}

          {evaluation.experimentReportMarkdown ? (
            <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap rounded-lg border border-slate-300 bg-slate-50 p-3 text-xs text-slate-900">
              {evaluation.experimentReportMarkdown}
            </pre>
          ) : null}
        </div>
      ) : (
        <div className="text-sm text-slate-600">
          请选择优化前批次和优化后批次。
        </div>
      )}
    </section>
  )
}

function BatchSelect({
  label,
  value,
  rows,
  onChange,
}: {
  label: string
  value: string
  rows: KnowledgeBaseEvaluationController["compareBatchRows"]
  onChange: (value: string) => void
}) {
  return (
    <label className="space-y-1">
      <span className="text-sm text-slate-600">{label}</span>
      <select
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">请选择批次</option>
        {rows.map((batch) => (
          <option key={batch.id} value={batch.id}>
            {batch.name}｜{batch.ran}/{batch.total_cases}
          </option>
        ))}
      </select>
    </label>
  )
}
