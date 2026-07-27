import type React from "react"

import {
  formatLatency,
  formatPercent,
  formatToolUsage,
} from "./knowledgeBaseFormatters"
import {
  getAdviceLevelClassName,
} from "./codeAgentOptimization"
import type {
  KnowledgeBaseEvaluationController,
} from "./useKnowledgeBaseEvaluation"

export function CodeEvalAnalysisSection({
  evaluation,
}: {
  evaluation:
    KnowledgeBaseEvaluationController
}) {
  const typeQuery =
    evaluation
      .codeEvalTypeCompareSummaryQuery
  const failureQuery =
    evaluation
      .ragAgentCompareFailureAnalysisQuery
  const batches =
    evaluation.compareBatchRows

  return (
    <section className="space-y-6 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          Code RAG / Code Agent 分析
        </h2>
        <p className="text-sm leading-6 text-slate-600">
          按任务类型比较命中率、耗时和工具使用，并根据异常样例生成优化建议。
        </p>
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-medium text-slate-900">
            分任务类型统计
          </h3>
          <button
            type="button"
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm"
            onClick={() => {
              void evaluation.refreshCodeTypeSummary()
            }}
          >
            刷新统计
          </button>
        </div>

        {typeQuery.isLoading ? (
          <div className="text-sm text-slate-600">
            正在加载统计结果...
          </div>
        ) : null}

        {typeQuery.isError ? (
          <pre className="whitespace-pre-wrap text-sm text-rose-600">
            {JSON.stringify(
              typeQuery.error,
              null,
              2,
            )}
          </pre>
        ) : null}

        {typeQuery.data ? (
          typeQuery.data.data.length === 0 ? (
            <div className="text-sm text-slate-600">
              暂无可统计的 Code Eval 对比结果。
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead className="bg-slate-100">
                  <tr>
                    <Header>任务类型</Header>
                    <Header align="right">样例数</Header>
                    <Header align="right">已对比</Header>
                    <Header align="right">RAG 文件命中</Header>
                    <Header align="right">Agent 文件命中</Header>
                    <Header align="right">RAG 关键词命中</Header>
                    <Header align="right">Agent 关键词命中</Header>
                    <Header align="right">RAG 耗时</Header>
                    <Header align="right">Agent 耗时</Header>
                    <Header align="right">Agent 平均工具数</Header>
                    <Header>工具分布</Header>
                  </tr>
                </thead>
                <tbody>
                  {typeQuery.data.data.map((item) => (
                    <tr key={item.case_type}>
                      <Cell>
                        {item.case_type_label}
                        <div className="text-xs text-slate-500">
                          {item.case_type}
                        </div>
                      </Cell>
                      <Cell align="right">{item.total_cases}</Cell>
                      <Cell align="right">{item.compared_cases}</Cell>
                      <Cell align="right">{formatPercent(item.rag_source_hit_rate)}</Cell>
                      <Cell align="right">{formatPercent(item.agent_source_hit_rate)}</Cell>
                      <Cell align="right">{formatPercent(item.rag_keyword_hit_rate)}</Cell>
                      <Cell align="right">{formatPercent(item.agent_keyword_hit_rate)}</Cell>
                      <Cell align="right">{formatLatency(item.rag_avg_latency_ms)}</Cell>
                      <Cell align="right">{formatLatency(item.agent_avg_latency_ms)}</Cell>
                      <Cell align="right">
                        {item.agent_avg_tool_calls === null || item.agent_avg_tool_calls === undefined
                          ? "-"
                          : item.agent_avg_tool_calls.toFixed(2)}
                      </Cell>
                      <Cell>{formatToolUsage(item.agent_tool_usage_json)}</Cell>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : null}
      </div>

      <div className="space-y-3 border-t border-slate-200 pt-5">
        <h3 className="font-medium text-slate-900">
          RAG vs Agent 失败案例分析
        </h3>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <select
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            value={evaluation.failureCaseTypeFilter}
            onChange={(event) => {
              evaluation.setFailureCaseTypeFilter(event.target.value)
            }}
          >
            <option value="">全部任务类型</option>
            <option value="file_overview">文件概览</option>
            <option value="symbol_definition">符号定义</option>
            <option value="symbol_reference">引用定位</option>
            <option value="code_logic">代码逻辑</option>
            <option value="bug_location">Bug 定位</option>
            <option value="unknown">未分类</option>
          </select>

          <select
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            value={evaluation.failureBatchIdFilter}
            onChange={(event) => {
              evaluation.setFailureBatchIdFilter(event.target.value)
            }}
          >
            <option value="">全部对比批次</option>
            {batches.map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.name}
              </option>
            ))}
          </select>

          <div className="flex gap-2">
            <button
              type="button"
              className="rounded border border-slate-300 bg-white px-3 py-2 text-sm"
              onClick={() => {
                void evaluation.refreshCompareFailureAnalysis()
              }}
            >
              刷新分析
            </button>
            <button
              type="button"
              className="rounded border border-slate-300 bg-white px-3 py-2 text-sm"
              onClick={() => {
                evaluation.setFailureCaseTypeFilter("")
                evaluation.setFailureBatchIdFilter("")
              }}
            >
              清空筛选
            </button>
          </div>
        </div>

        {failureQuery.isLoading ? (
          <div className="text-sm text-slate-600">
            正在加载失败案例分析...
          </div>
        ) : null}

        {failureQuery.isError ? (
          <pre className="whitespace-pre-wrap text-sm text-rose-600">
            {JSON.stringify(failureQuery.error, null, 2)}
          </pre>
        ) : null}

        {failureQuery.data ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Metric label="分析样例数" value={failureQuery.data.total_items} />
              <Metric label="异常样例数" value={failureQuery.data.failed_items} />
              <Metric
                label="异常率"
                value={failureQuery.data.total_items === 0
                  ? "-"
                  : formatPercent(failureQuery.data.failed_items / failureQuery.data.total_items)}
              />
              <Metric label="原因类型数" value={failureQuery.data.reason_stats.length} />
            </div>

            <div className="space-y-2">
              {failureQuery.data.data.slice(0, 12).map((item) => (
                <details
                  key={item.id}
                  className="rounded-lg border border-slate-300 bg-slate-50 p-3"
                >
                  <summary className="cursor-pointer text-sm font-medium text-slate-900">
                    {item.question}
                    {" ｜ "}
                    {item.failure_reason_labels?.join("、") || "未归因"}
                  </summary>
                  <div className="mt-3 grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
                    <Answer title="RAG 回答" value={item.rag_answer} error={item.rag_error_message} />
                    <Answer title="Agent 回答" value={item.agent_answer} error={item.agent_error_message} />
                  </div>
                </details>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="space-y-3 border-t border-slate-200 pt-5">
        <h3 className="font-medium text-slate-900">
          Code Agent 自动优化建议
        </h3>
        <div className="space-y-3">
          {evaluation.codeAgentOptimizationAdvice.map((advice, index) => (
            <div
              key={`${advice.title}-${index}`}
              className={`space-y-2 rounded-lg border p-3 ${getAdviceLevelClassName(advice.level)}`}
            >
              <div className="font-medium">
                {index + 1}. {advice.title}
              </div>
              <div className="text-sm">
                <span className="font-medium">判断依据：</span>
                {advice.reason}
              </div>
              <div className="text-sm">
                <span className="font-medium">优化建议：</span>
                {advice.suggestion}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function Header({
  children,
  align = "left",
}: {
  children: React.ReactNode
  align?: "left" | "right"
}) {
  return (
    <th className={`border border-slate-300 px-3 py-2 ${align === "right" ? "text-right" : "text-left"}`}>
      {children}
    </th>
  )
}

function Cell({
  children,
  align = "left",
}: {
  children: React.ReactNode
  align?: "left" | "right"
}) {
  return (
    <td className={`border border-slate-300 px-3 py-2 ${align === "right" ? "text-right" : "text-left"}`}>
      {children}
    </td>
  )
}

function Metric({
  label,
  value,
}: {
  label: string
  value: string | number
}) {
  return (
    <div className="rounded-lg border border-slate-300 bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-slate-900">{value}</div>
    </div>
  )
}

function Answer({
  title,
  value,
  error,
}: {
  title: string
  value?: string | null
  error?: string | null
}) {
  return (
    <div className="space-y-2">
      <div className="font-medium text-slate-900">{title}</div>
      {error ? <div className="text-rose-600">{error}</div> : null}
      <pre className="whitespace-pre-wrap rounded border border-slate-300 bg-white p-2 text-xs text-slate-900">
        {value || "无"}
      </pre>
    </div>
  )
}
