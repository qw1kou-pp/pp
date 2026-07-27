export type RagSourceItem = {
  chunk_id: string
  original_filename: string
  chunk_index: number
  content: string
  content_length?: number | null
  match_count?: number | null
  similarity?: number | null
  retrieval_type?: string | null
  repository_analysis_task_id?: string | null
  repository_relative_path?: string | null
  source_commit_sha?: string | null
}

type RagSourceListProps = {
  sources: readonly RagSourceItem[]
  emptyText?: string
}

export function RagSourceList({
  sources,
  emptyText = "暂无引用来源。",
}: RagSourceListProps) {
  if (sources.length === 0) {
    return <div className="text-sm text-slate-600">{emptyText}</div>
  }

  return (
    <div className="space-y-3">
      {sources.map((source, index) => {
        const sourcePath =
          source.repository_relative_path || source.original_filename
        const metadata = buildSourceMetadata(source)

        return (
          <article
            key={source.chunk_id}
            className="rounded-lg border border-slate-300 bg-slate-50 p-3 text-slate-900"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 text-sm font-medium">
                <span className="text-slate-500">[{index + 1}]</span>{" "}
                <span className="break-all">{sourcePath}</span>
                {" ｜ "}Chunk {source.chunk_index}
              </div>

              {metadata ? (
                <div className="text-xs text-slate-600">{metadata}</div>
              ) : null}
            </div>

            {source.source_commit_sha ? (
              <p className="mt-2 break-all font-mono text-xs text-slate-500">
                Commit：{source.source_commit_sha}
              </p>
            ) : null}

            <pre className="mt-3 whitespace-pre-wrap break-words font-sans text-sm text-slate-900">
              {source.content}
            </pre>
          </article>
        )
      })}
    </div>
  )
}

function buildSourceMetadata(source: RagSourceItem): string {
  const parts: string[] = []

  if (source.retrieval_type) {
    parts.push(formatRetrievalType(source.retrieval_type))
  }

  if (
    source.similarity !== null &&
    source.similarity !== undefined &&
    Number.isFinite(source.similarity)
  ) {
    parts.push(`相似度：${source.similarity.toFixed(4)}`)
  }

  if (source.match_count !== null && source.match_count !== undefined) {
    parts.push(`关键词命中：${source.match_count}`)
  }

  if (source.content_length !== null && source.content_length !== undefined) {
    parts.push(`长度：${source.content_length}`)
  }

  return parts.join(" ｜ ")
}

function formatRetrievalType(retrievalType: string): string {
  switch (retrievalType) {
    case "hybrid":
      return "混合检索"
    case "semantic":
      return "语义检索"
    case "keyword":
      return "关键词检索"
    default:
      return retrievalType
  }
}
