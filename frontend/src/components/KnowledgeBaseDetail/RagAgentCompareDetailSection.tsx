import {
  readArrayField,
  readField,
  readNumberField,
} from "./compareUtils"

type RagAgentCompareDetailSectionProps = {
  isOpen: boolean
  selectedCompareBatchId: string | null
  batchDetailData: any
  isLoading: boolean
  isError: boolean
  error: unknown
  onClose: () => void
}

const SourceList = ({
  title,
  sources,
}: {
  title: string
  sources: any[]
}) => {
  return (
    <details className="border rounded p-3">
      <summary className="cursor-pointer text-sm">{title}</summary>

      <div className="space-y-3 mt-3">
        {sources.length === 0 ? (
          <div className="text-sm text-gray-500">暂无来源。</div>
        ) : (
          sources.map((source, sourceIndex) => {
            const chunkId = readField<string>(
              source,
              "chunk_id",
              "chunkId",
              `${sourceIndex}`,
            )
            const filename = readField<string>(
              source,
              "original_filename",
              "originalFilename",
              "-",
            )
            const chunkIndex = readField<number>(
              source,
              "chunk_index",
              "chunkIndex",
              0,
            )
            const matchCount = readField<number>(
              source,
              "match_count",
              "matchCount",
              0,
            )
            const similarity = readNumberField(
              source,
              "similarity",
              "similarity",
            )
            const content = readField<string>(
              source,
              "content",
              "content",
              "",
            )

            return (
              <div
                key={`${chunkId}-${sourceIndex}`}
                className="border rounded p-3 space-y-2"
              >
                <div className="text-sm font-medium">
                  [{sourceIndex + 1}] {filename}
                </div>

                <div className="text-xs text-gray-500">
                  chunk_index：{chunkIndex} ｜ match_count：{matchCount} ｜
                  similarity：
                  {similarity === null || similarity === undefined
                    ? "-"
                    : similarity.toFixed(4)}
                </div>

                <div className="text-sm whitespace-pre-wrap">{content}</div>
              </div>
            )
          })
        )}
      </div>
    </details>
  )
}

const TraceList = ({
  title,
  trace,
}: {
  title: string
  trace: string[]
}) => {
  return (
    <details className="border rounded p-3">
      <summary className="cursor-pointer text-sm">{title}</summary>

      {trace.length === 0 ? (
        <div className="text-sm text-gray-500 mt-3">暂无 trace。</div>
      ) : (
        <ol className="list-decimal list-inside text-sm space-y-1 mt-3">
          {trace.map((traceItem, traceIndex) => (
            <li key={`${traceItem}-${traceIndex}`}>{traceItem}</li>
          ))}
        </ol>
      )}
    </details>
  )
}

const AgentToolCallList = ({
  toolCalls,
}: {
  toolCalls: any[]
}) => {
  return (
    <details className="border rounded p-3" open>
      <summary className="cursor-pointer text-sm">查看 Agent 工具调用</summary>

      <div className="space-y-3 mt-3">
        {toolCalls.length === 0 ? (
          <div className="text-sm text-gray-500">暂无工具调用。</div>
        ) : (
          toolCalls.map((toolCall, toolIndex) => {
            const toolName = readField<string>(
              toolCall,
              "tool_name",
              "toolName",
              "-",
            )
            const success = readField<boolean>(
              toolCall,
              "success",
              "success",
              false,
            )
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
                  参数：{JSON.stringify(argumentsValue, null, 2)}
                </div>

                <div className="text-sm whitespace-pre-wrap">
                  {observation}
                </div>
              </div>
            )
          })
        )}
      </div>
    </details>
  )
}

export const RagAgentCompareDetailSection = ({
  isOpen,
  selectedCompareBatchId,
  batchDetailData,
  isLoading,
  isError,
  error,
  onClose,
}: RagAgentCompareDetailSectionProps) => {
  if (!isOpen || !selectedCompareBatchId) {
    return null
  }

  const batch = readField<any>(batchDetailData, "batch", "batch", null)
  const items = readArrayField<any>(batchDetailData, "data", "data")
  const count = readField<number>(batchDetailData, "count", "count", 0)

  const batchName = batch
    ? readField<string>(batch, "name", "name", "-")
    : "-"

  const createdAt = batch
    ? readField<string | null>(batch, "created_at", "createdAt", null)
    : null

  return (
    <div className="border rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">对比批次详情</h2>
          <p className="text-sm text-gray-500">
            查看该批次中每个评测问题的 RAG 回答、Agent 回答和 Agent 工具调用链。
          </p>
        </div>

        <button
          className="border rounded px-3 py-1 text-sm"
          onClick={onClose}
        >
          关闭详情
        </button>
      </div>

      {isLoading ? (
        <div className="text-sm text-gray-500">正在加载批次详情...</div>
      ) : null}

      {isError ? (
        <div className="text-sm text-red-500 whitespace-pre-wrap">
          加载批次详情失败：
          {JSON.stringify(error, null, 2)}
        </div>
      ) : null}

      {batchDetailData ? (
        <div className="space-y-4">
          <div className="border rounded p-3 space-y-2">
            <div className="text-sm font-semibold">{batchName}</div>

            <div className="text-xs text-gray-500">
              创建时间：
              {createdAt ? new Date(createdAt).toLocaleString() : "-"}
            </div>

            <div className="text-xs text-gray-500">
              共 {count} 条评测样例
            </div>
          </div>

          {items.map((item, index) => {
            const itemId = readField<string>(item, "id", "id", `${index}`)
            const question = readField<string>(
              item,
              "question",
              "question",
              "",
            )
            const ragLatency = readField<number | null>(
              item,
              "rag_latency_ms",
              "ragLatencyMs",
              null,
            )
            const agentLatency = readField<number | null>(
              item,
              "agent_latency_ms",
              "agentLatencyMs",
              null,
            )
            const agentToolNames = readArrayField<string>(
              item,
              "agent_tool_names",
              "agentToolNames",
            )
            const isFailed = readField<boolean>(
              item,
              "is_failed",
              "isFailed",
              false,
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

            const ragAnswer = readField<string | null>(
              item,
              "rag_answer",
              "ragAnswer",
              null,
            )
            const agentAnswer = readField<string | null>(
              item,
              "agent_answer",
              "agentAnswer",
              null,
            )

            const ragSources = readArrayField<any>(
              item,
              "rag_sources",
              "ragSources",
            )
            const agentSources = readArrayField<any>(
              item,
              "agent_sources",
              "agentSources",
            )
            const agentToolCalls = readArrayField<any>(
              item,
              "agent_tool_calls",
              "agentToolCalls",
            )
            const ragTrace = readArrayField<string>(
              item,
              "rag_trace",
              "ragTrace",
            )
            const agentTrace = readArrayField<string>(
              item,
              "agent_trace",
              "agentTrace",
            )

            return (
              <details key={itemId} className="border rounded p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  {index + 1}. {question}
                  {" ｜ "}
                  RAG：{ragLatency ?? "-"} ms
                  {" ｜ "}
                  Agent：{agentLatency ?? "-"} ms
                  {" ｜ "}
                  工具：{agentToolNames.join(", ") || "-"}
                  {" ｜ "}
                  {isFailed ? "有失败" : "正常"}
                </summary>

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4">
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold">普通 RAG</h3>

                    {ragErrorMessage ? (
                      <div className="text-sm text-red-500 whitespace-pre-wrap">
                        {ragErrorMessage}
                      </div>
                    ) : null}

                    <div className="text-xs text-gray-500">
                      耗时：{ragLatency ?? "-"} ms ｜ Sources：
                      {ragSourcesCount}
                    </div>

                    <div className="text-sm whitespace-pre-wrap border rounded p-3">
                      {ragAnswer || "暂无回答"}
                    </div>

                    <SourceList title="查看 RAG Sources" sources={ragSources} />

                    <TraceList title="查看 RAG Trace" trace={ragTrace} />
                  </div>

                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold">Agent</h3>

                    {agentErrorMessage ? (
                      <div className="text-sm text-red-500 whitespace-pre-wrap">
                        {agentErrorMessage}
                      </div>
                    ) : null}

                    <div className="text-xs text-gray-500">
                      耗时：{agentLatency ?? "-"} ms ｜ Sources：
                      {agentSourcesCount} ｜ 工具调用：
                      {agentToolCallCount} ｜ 工具失败：
                      {agentFailedToolCount}
                    </div>

                    <div className="text-sm whitespace-pre-wrap border rounded p-3">
                      {agentAnswer || "暂无回答"}
                    </div>

                    <AgentToolCallList toolCalls={agentToolCalls} />

                    <SourceList
                      title="查看 Agent Sources"
                      sources={agentSources}
                    />

                    <TraceList title="查看 Agent Trace" trace={agentTrace} />
                  </div>
                </div>
              </details>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}