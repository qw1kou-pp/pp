import {
  getToolName,
  getToolSuccess,
  readArrayField,
  readField,
  readNumberField,
} from "./compareUtils"

const buildRagAgentFailureAnalysis = (batchDetail: any) => {
  const items = readArrayField<any>(batchDetail, "data", "data")

  const totalCases = items.length

  const failedItems = items.filter((item) =>
    readField<boolean>(item, "is_failed", "isFailed", false),
  )

  const agentToolFailedItems = items.filter((item) => {
    const failedToolCount = readField<number>(
      item,
      "agent_failed_tool_count",
      "agentFailedToolCount",
      0,
    )

    return failedToolCount > 0
  })

  const ragNoSourcesItems = items.filter((item) => {
    const sourcesCount = readField<number>(
      item,
      "rag_sources_count",
      "ragSourcesCount",
      0,
    )

    return sourcesCount === 0
  })

  const agentNoSourcesItems = items.filter((item) => {
    const sourcesCount = readField<number>(
      item,
      "agent_sources_count",
      "agentSourcesCount",
      0,
    )

    return sourcesCount === 0
  })

  const agentNoToolItems = items.filter((item) => {
    const toolCount = readField<number>(
      item,
      "agent_tool_call_count",
      "agentToolCallCount",
      0,
    )

    return toolCount === 0
  })

  const slowAgentItems = items.filter((item) => {
    const ragLatency = readNumberField(item, "rag_latency_ms", "ragLatencyMs")
    const agentLatency = readNumberField(
      item,
      "agent_latency_ms",
      "agentLatencyMs",
    )

    if (ragLatency === null || agentLatency === null) {
      return false
    }

    return agentLatency > ragLatency * 2 || agentLatency - ragLatency > 3000
  })

  const latencyGaps = items
    .map((item) => {
      const ragLatency = readNumberField(item, "rag_latency_ms", "ragLatencyMs")
      const agentLatency = readNumberField(
        item,
        "agent_latency_ms",
        "agentLatencyMs",
      )

      if (ragLatency === null || agentLatency === null) {
        return null
      }

      return agentLatency - ragLatency
    })
    .filter((value): value is number => value !== null)

  const averageLatencyGap =
    latencyGaps.length === 0
      ? null
      : latencyGaps.reduce((sum, value) => sum + value, 0) / latencyGaps.length

  const failedToolNameCount: Record<string, number> = {}

  for (const item of items) {
    const toolCalls = readArrayField<any>(
      item,
      "agent_tool_calls",
      "agentToolCalls",
    )

    for (const toolCall of toolCalls) {
      if (getToolSuccess(toolCall)) {
        continue
      }

      const toolName = getToolName(toolCall)
      failedToolNameCount[toolName] = (failedToolNameCount[toolName] ?? 0) + 1
    }
  }

  const mostFailedTool =
    Object.entries(failedToolNameCount).sort((a, b) => b[1] - a[1])[0] ?? null

  const warningItems = items.filter((item) => {
    const isFailed = readField<boolean>(item, "is_failed", "isFailed", false)

    const agentFailedToolCount = readField<number>(
      item,
      "agent_failed_tool_count",
      "agentFailedToolCount",
      0,
    )

    const ragSourcesCount = readField<number>(
      item,
      "rag_sources_count",
      "ragSourcesCount",
      0,
    )

    const agentSourcesCount = readField<number>(
      item,
      "agent_sources_count",
      "agentSourcesCount",
      0,
    )

    const agentToolCallCount = readField<number>(
      item,
      "agent_tool_call_count",
      "agentToolCallCount",
      0,
    )

    const ragLatency = readNumberField(item, "rag_latency_ms", "ragLatencyMs")
    const agentLatency = readNumberField(
      item,
      "agent_latency_ms",
      "agentLatencyMs",
    )

    const isSlow =
      ragLatency !== null &&
      agentLatency !== null &&
      (agentLatency > ragLatency * 2 || agentLatency - ragLatency > 3000)

    return (
      isFailed ||
      agentFailedToolCount > 0 ||
      ragSourcesCount === 0 ||
      agentSourcesCount === 0 ||
      agentToolCallCount === 0 ||
      isSlow
    )
  })

  return {
    totalCases,
    failedCount: failedItems.length,
    agentToolFailedCount: agentToolFailedItems.length,
    ragNoSourcesCount: ragNoSourcesItems.length,
    agentNoSourcesCount: agentNoSourcesItems.length,
    agentNoToolCount: agentNoToolItems.length,
    slowAgentCount: slowAgentItems.length,
    averageLatencyGap,
    mostFailedTool,
    warningItems,
  }
}

type RagAgentFailureAnalysisSectionProps = {
  isOpen: boolean
  batchDetailData: any
}

export const RagAgentFailureAnalysisSection = ({
  isOpen,
  batchDetailData,
}: RagAgentFailureAnalysisSectionProps) => {
  if (!isOpen || !batchDetailData) {
    return null
  }

  const analysis = buildRagAgentFailureAnalysis(batchDetailData)

  return (
    <div className="border rounded-lg p-4 space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Agent 失败案例分析</h2>
        <p className="text-sm text-gray-500">
          根据当前选中的 RAG vs Agent 对比批次，自动分析失败样例、无来源样例、工具失败和高耗时问题。
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
        <div className="border rounded p-3">
          <div className="text-xs text-gray-400">总样例数</div>
          <div className="text-xl font-semibold">{analysis.totalCases}</div>
        </div>

        <div className="border rounded p-3">
          <div className="text-xs text-gray-400">失败样例数</div>
          <div className="text-xl font-semibold">{analysis.failedCount}</div>
        </div>

        <div className="border rounded p-3">
          <div className="text-xs text-gray-400">工具失败样例</div>
          <div className="text-xl font-semibold">
            {analysis.agentToolFailedCount}
          </div>
        </div>

        <div className="border rounded p-3">
          <div className="text-xs text-gray-400">RAG 无来源</div>
          <div className="text-xl font-semibold">
            {analysis.ragNoSourcesCount}
          </div>
        </div>

        <div className="border rounded p-3">
          <div className="text-xs text-gray-400">Agent 无来源</div>
          <div className="text-xl font-semibold">
            {analysis.agentNoSourcesCount}
          </div>
        </div>

        <div className="border rounded p-3">
          <div className="text-xs text-gray-400">Agent 无工具</div>
          <div className="text-xl font-semibold">
            {analysis.agentNoToolCount}
          </div>
        </div>

        <div className="border rounded p-3">
          <div className="text-xs text-gray-400">Agent 明显更慢</div>
          <div className="text-xl font-semibold">
            {analysis.slowAgentCount}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="border rounded p-3">
          <div className="text-xs text-gray-400">平均耗时差</div>
          <div className="text-lg font-semibold">
            {analysis.averageLatencyGap === null
              ? "-"
              : `${analysis.averageLatencyGap.toFixed(0)} ms`}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            计算方式：Agent 耗时 - RAG 耗时。数值越大，说明 Agent 的多步工具调用成本越高。
          </p>
        </div>

        <div className="border rounded p-3">
          <div className="text-xs text-gray-400">最常失败工具</div>
          <div className="text-lg font-semibold">
            {analysis.mostFailedTool
              ? `${analysis.mostFailedTool[0]}（${analysis.mostFailedTool[1]} 次）`
              : "-"}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            如果某个工具经常失败，优先检查该工具的参数解析、数据库查询和异常处理。
          </p>
        </div>
      </div>

      <div className="border rounded p-3 space-y-3">
        <div>
          <h3 className="text-base font-semibold">需要重点关注的样例</h3>
          <p className="text-sm text-gray-500">
            包括失败样例、无 sources 样例、Agent 工具失败、Agent 无工具调用，以及 Agent 明显慢于 RAG 的样例。
          </p>
        </div>

        {analysis.warningItems.length === 0 ? (
          <div className="text-sm text-gray-500">
            当前批次没有发现明显异常样例。
          </div>
        ) : (
          <div className="space-y-3">
            {analysis.warningItems.map((item: any, index: number) => {
              const question = readField<string>(
                item,
                "question",
                "question",
                "",
              )

              const isFailed = readField<boolean>(
                item,
                "is_failed",
                "isFailed",
                false,
              )

              const ragLatency = readNumberField(
                item,
                "rag_latency_ms",
                "ragLatencyMs",
              )

              const agentLatency = readNumberField(
                item,
                "agent_latency_ms",
                "agentLatencyMs",
              )

              const ragSourcesCount = readField<number>(
                item,
                "rag_sources_count",
                "ragSourcesCount",
                0,
              )

              const agentSourcesCount = readField<number>(
                item,
                "agent_sources_count",
                "agentSourcesCount",
                0,
              )

              const agentToolCallCount = readField<number>(
                item,
                "agent_tool_call_count",
                "agentToolCallCount",
                0,
              )

              const agentFailedToolCount = readField<number>(
                item,
                "agent_failed_tool_count",
                "agentFailedToolCount",
                0,
              )

              const agentToolNames = readArrayField<string>(
                item,
                "agent_tool_names",
                "agentToolNames",
              )

              const agentToolCalls = readArrayField<any>(
                item,
                "agent_tool_calls",
                "agentToolCalls",
              )

              const ragErrorMessage = readField<string | null>(
                item,
                "rag_error_message",
                "ragErrorMessage",
                null,
              )

              const agentErrorMessage = readField<string | null>(
                item,
                "agent_error_message",
                "agentErrorMessage",
                null,
              )

              const reasons: string[] = []

              if (isFailed) {
                reasons.push("整体标记失败")
              }

              if (agentFailedToolCount > 0) {
                reasons.push(`Agent 工具失败 ${agentFailedToolCount} 次`)
              }

              if (ragSourcesCount === 0) {
                reasons.push("RAG 无 sources")
              }

              if (agentSourcesCount === 0) {
                reasons.push("Agent 无 sources")
              }

              if (agentToolCallCount === 0) {
                reasons.push("Agent 没有调用工具")
              }

              if (
                ragLatency !== null &&
                agentLatency !== null &&
                (agentLatency > ragLatency * 2 ||
                  agentLatency - ragLatency > 3000)
              ) {
                reasons.push("Agent 明显慢于 RAG")
              }

              return (
                <details
                  key={readField<string>(item, "id", "id", `${index}`)}
                  className="border rounded p-3"
                >
                  <summary className="cursor-pointer text-sm font-medium">
                    {index + 1}. {question}
                    {" ｜ "}
                    {reasons.join("、") || "需要检查"}
                  </summary>

                  <div className="space-y-3 mt-3">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="border rounded p-2">
                        <div className="text-xs text-gray-400">RAG 耗时</div>
                        <div className="text-base font-semibold">
                          {ragLatency === null ? "-" : `${ragLatency} ms`}
                        </div>
                      </div>

                      <div className="border rounded p-2">
                        <div className="text-xs text-gray-400">Agent 耗时</div>
                        <div className="text-base font-semibold">
                          {agentLatency === null ? "-" : `${agentLatency} ms`}
                        </div>
                      </div>

                      <div className="border rounded p-2">
                        <div className="text-xs text-gray-400">RAG Sources</div>
                        <div className="text-base font-semibold">
                          {ragSourcesCount}
                        </div>
                      </div>

                      <div className="border rounded p-2">
                        <div className="text-xs text-gray-400">Agent Sources</div>
                        <div className="text-base font-semibold">
                          {agentSourcesCount}
                        </div>
                      </div>
                    </div>

                    <div className="text-sm">
                      <span className="font-medium">Agent 工具链：</span>
                      {agentToolNames.length === 0
                        ? "-"
                        : agentToolNames.join(" → ")}
                    </div>

                    {ragErrorMessage ? (
                      <div className="text-sm text-red-500 whitespace-pre-wrap">
                        RAG 错误：{ragErrorMessage}
                      </div>
                    ) : null}

                    {agentErrorMessage ? (
                      <div className="text-sm text-red-500 whitespace-pre-wrap">
                        Agent 错误：{agentErrorMessage}
                      </div>
                    ) : null}

                    {agentToolCalls.length > 0 ? (
                      <details className="border rounded p-3">
                        <summary className="cursor-pointer text-sm">
                          查看该样例的 Agent 工具调用
                        </summary>

                        <div className="space-y-3 mt-3">
                          {agentToolCalls.map(
                            (toolCall: any, toolIndex: number) => {
                              const toolName = getToolName(toolCall)
                              const success = getToolSuccess(toolCall)

                              const argumentsValue = readField<any>(
                                toolCall,
                                "arguments",
                                "arguments",
                                {},
                              )

                              const observation = readField<string>(
                                toolCall,
                                "observation",
                                "observation",
                                "",
                              )

                              return (
                                <div
                                  key={`${toolName}-${toolIndex}`}
                                  className="border rounded p-3 space-y-2"
                                >
                                  <div className="text-sm font-medium">
                                    {toolIndex + 1}. {toolName}
                                  </div>

                                  <div className="text-xs text-gray-500">
                                    状态：{success ? "成功" : "失败"}
                                  </div>

                                  <div className="text-xs whitespace-pre-wrap">
                                    参数：
                                    {JSON.stringify(argumentsValue, null, 2)}
                                  </div>

                                  <div className="text-sm whitespace-pre-wrap">
                                    {observation}
                                  </div>
                                </div>
                              )
                            },
                          )}
                        </div>
                      </details>
                    ) : null}
                  </div>
                </details>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}