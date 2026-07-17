import { CollapsibleSection } from "./CollapsibleSection"
import { readArrayField, readField } from "./compareUtils"

type RagAgentCompareHistorySectionProps = {
  isOpen: boolean
  onToggle: () => void

  batchesData: any
  isLoading: boolean
  isError: boolean
  error: unknown

  selectedCompareBatchId: string | null
  onSelectBatch: (batchId: string) => void

  onExportMarkdown: (batchId: string) => void
  onExportDocx: (batchId: string) => void
  onExportPdf: (batchId: string) => void
  onDeleteBatch: (batchId: string) => void

  isExportMarkdownPending: boolean
  isExportDocxPending: boolean
  isExportPdfPending: boolean
  isDeletePending: boolean

  exportMarkdownError: unknown
  exportDocxError: unknown
  exportPdfError: unknown

  isExportMarkdownError: boolean
  isExportDocxError: boolean
  isExportPdfError: boolean
}

const formatNumber = (value: number | null | undefined, suffix = "") => {
  if (value === null || value === undefined) {
    return "-"
  }

  if (Number.isInteger(value)) {
    return `${value}${suffix}`
  }

  return `${value.toFixed(2)}${suffix}`
}

const formatDateTime = (value: string | null | undefined) => {
  if (!value) {
    return "-"
  }

  return new Date(value).toLocaleString()
}

export const RagAgentCompareHistorySection = ({
  isOpen,
  onToggle,
  batchesData,
  isLoading,
  isError,
  error,
  selectedCompareBatchId,
  onSelectBatch,
  onExportMarkdown,
  onExportDocx,
  onExportPdf,
  onDeleteBatch,
  isExportMarkdownPending,
  isExportDocxPending,
  isExportPdfPending,
  isDeletePending,
  exportMarkdownError,
  exportDocxError,
  exportPdfError,
  isExportMarkdownError,
  isExportDocxError,
  isExportPdfError,
}: RagAgentCompareHistorySectionProps) => {
  const batches = readArrayField<any>(batchesData, "data", "data")

  return (
    <CollapsibleSection
      title="RAG vs Agent 对比历史记录"
      description="查看已经保存的批量对比实验，比较不同运行参数下 RAG 和 Agent 的耗时、工具调用和失败情况。"
      isOpen={isOpen}
      onToggle={onToggle}
    >
      {isLoading ? (
        <div className="text-sm text-gray-500">正在加载对比历史...</div>
      ) : null}

      {isError ? (
        <div className="text-sm text-red-500 whitespace-pre-wrap">
          加载对比历史失败：
          {JSON.stringify(error, null, 2)}
        </div>
      ) : null}

      {batchesData ? (
        <div className="space-y-3">
          {batches.length === 0 ? (
            <div className="text-sm text-gray-500">
              暂无 RAG vs Agent 对比历史。请先运行一次批量对比评测。
            </div>
          ) : (
            batches.map((batch) => {
              const batchId = readField<string>(batch, "id", "id", "")
              const name = readField<string>(batch, "name", "name", "-")
              const createdAt = readField<string | null>(
                batch,
                "created_at",
                "createdAt",
                null,
              )

              const topK = readField<number>(batch, "top_k", "topK", 0)
              const maxSteps = readField<number>(
                batch,
                "max_steps",
                "maxSteps",
                0,
              )
              const limit = readField<number>(batch, "limit", "limit", 0)
              const semanticWeight = readField<number>(
                batch,
                "semantic_weight",
                "semanticWeight",
                0,
              )
              const keywordWeight = readField<number>(
                batch,
                "keyword_weight",
                "keywordWeight",
                0,
              )

              const totalCases = readField<number>(
                batch,
                "total_cases",
                "totalCases",
                0,
              )
              const ran = readField<number>(batch, "ran", "ran", 0)
              const failed = readField<number>(
                batch,
                "failed",
                "failed",
                0,
              )

              const averageRagLatency = readField<number | null>(
                batch,
                "average_rag_latency_ms",
                "averageRagLatencyMs",
                null,
              )
              const averageAgentLatency = readField<number | null>(
                batch,
                "average_agent_latency_ms",
                "averageAgentLatencyMs",
                null,
              )
              const averageRagSources = readField<number | null>(
                batch,
                "average_rag_sources_count",
                "averageRagSourcesCount",
                null,
              )
              const averageAgentSources = readField<number | null>(
                batch,
                "average_agent_sources_count",
                "averageAgentSourcesCount",
                null,
              )
              const averageAgentToolCalls = readField<number | null>(
                batch,
                "average_agent_tool_call_count",
                "averageAgentToolCallCount",
                null,
              )
              const totalAgentFailedToolCount = readField<number>(
                batch,
                "total_agent_failed_tool_count",
                "totalAgentFailedToolCount",
                0,
              )

              const summarizeDocumentCount = readField<number>(
                batch,
                "summarize_document_count",
                "summarizeDocumentCount",
                0,
              )
              const readDocumentChunksCount = readField<number>(
                batch,
                "read_document_chunks_count",
                "readDocumentChunksCount",
                0,
              )
              const searchRagHistoryCount = readField<number>(
                batch,
                "search_rag_history_count",
                "searchRagHistoryCount",
                0,
              )

              return (
                <div
                  key={batchId}
                  className={`border rounded p-3 space-y-3 ${
                    selectedCompareBatchId === batchId
                      ? "border-blue-500"
                      : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold">{name}</div>

                      <div className="text-xs text-gray-500">
                        创建时间：{formatDateTime(createdAt)}
                      </div>

                      <div className="text-xs text-gray-500">
                        top_k：{topK} ｜ max_steps：{maxSteps} ｜ limit：
                        {limit} ｜ semantic_weight：{semanticWeight} ｜
                        keyword_weight：{keywordWeight}
                      </div>
                    </div>

                    <div className="text-xs text-gray-500">
                      ID：{batchId.slice(0, 8)}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
                    <div className="border rounded p-2">
                      <div className="text-xs text-gray-400">总样例</div>
                      <div className="text-base font-semibold">
                        {totalCases}
                      </div>
                    </div>

                    <div className="border rounded p-2">
                      <div className="text-xs text-gray-400">已运行</div>
                      <div className="text-base font-semibold">{ran}</div>
                    </div>

                    <div className="border rounded p-2">
                      <div className="text-xs text-gray-400">失败</div>
                      <div className="text-base font-semibold">{failed}</div>
                    </div>

                    <div className="border rounded p-2">
                      <div className="text-xs text-gray-400">RAG 平均耗时</div>
                      <div className="text-base font-semibold">
                        {formatNumber(averageRagLatency, " ms")}
                      </div>
                    </div>

                    <div className="border rounded p-2">
                      <div className="text-xs text-gray-400">
                        Agent 平均耗时
                      </div>
                      <div className="text-base font-semibold">
                        {formatNumber(averageAgentLatency, " ms")}
                      </div>
                    </div>

                    <div className="border rounded p-2">
                      <div className="text-xs text-gray-400">
                        Agent 工具失败
                      </div>
                      <div className="text-base font-semibold">
                        {totalAgentFailedToolCount}
                      </div>
                    </div>

                    <div className="border rounded p-2">
                      <div className="text-xs text-gray-400">
                        Agent 平均工具
                      </div>
                      <div className="text-base font-semibold">
                        {formatNumber(averageAgentToolCalls)}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-gray-500">
                    <div className="border rounded p-2">
                      RAG 平均 sources：
                      {formatNumber(averageRagSources)}
                      {" ｜ "}
                      Agent 平均 sources：
                      {formatNumber(averageAgentSources)}
                    </div>

                    <div className="border rounded p-2">
                      summarize_document：{summarizeDocumentCount}
                      {" ｜ "}
                      read_document_chunks：{readDocumentChunksCount}
                      {" ｜ "}
                      search_rag_history：{searchRagHistoryCount}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      className="border rounded px-3 py-1 text-sm"
                      onClick={() => onSelectBatch(batchId)}
                    >
                      查看详情
                    </button>

                    <button
                      className="border rounded px-3 py-1 text-sm"
                      onClick={() => onExportMarkdown(batchId)}
                      disabled={isExportMarkdownPending}
                    >
                      导出 Markdown
                    </button>

                    <button
                      className="border rounded px-3 py-1 text-sm"
                      onClick={() => onExportDocx(batchId)}
                      disabled={isExportDocxPending}
                    >
                      导出 Word
                    </button>

                    <button
                      className="border rounded px-3 py-1 text-sm"
                      onClick={() => onExportPdf(batchId)}
                      disabled={isExportPdfPending}
                    >
                      导出文字版 PDF
                    </button>

                    <button
                      className="border rounded px-3 py-1 text-sm text-red-500"
                      onClick={() => {
                        if (confirm("确定删除这次对比记录吗？")) {
                          onDeleteBatch(batchId)
                        }
                      }}
                      disabled={isDeletePending}
                    >
                      删除
                    </button>
                  </div>
                </div>
              )
            })
          )}

          {isExportMarkdownError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              导出 Markdown 报告失败：
              {JSON.stringify(exportMarkdownError, null, 2)}
            </div>
          ) : null}

          {isExportDocxError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              导出 Word 报告失败：
              {JSON.stringify(exportDocxError, null, 2)}
            </div>
          ) : null}

          {isExportPdfError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              导出 PDF 报告失败：
              {JSON.stringify(exportPdfError, null, 2)}
            </div>
          ) : null}
        </div>
      ) : null}
    </CollapsibleSection>
  )
}