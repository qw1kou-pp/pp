import type {
  KnowledgeBaseEmbeddingBackfillResult,
  KnowledgeBaseSemanticSearchResults,
} from "@/client"

import {
  formatKnowledgeBaseChatError,
} from "./knowledgeBaseChatTypes"

type SemanticSearchSectionProps = {
  query: string
  onQueryChange: (
    value: string,
  ) => void
  onSearch: () => void
  onBackfillEmbeddings: () => void

  data?: KnowledgeBaseSemanticSearchResults
  isPending: boolean
  isError: boolean
  error: unknown

  backfillData?:
    KnowledgeBaseEmbeddingBackfillResult
  isBackfillPending: boolean
  isBackfillError: boolean
  backfillError: unknown
}

export function SemanticSearchSection({
  query,
  onQueryChange,
  onSearch,
  onBackfillEmbeddings,
  data,
  isPending,
  isError,
  error,
  backfillData,
  isBackfillPending,
  isBackfillError,
  backfillError,
}: SemanticSearchSectionProps) {
  return (
    <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          语义检索
        </h2>

        <p className="text-sm leading-6 text-slate-600">
          将问题转换为向量，并与知识库代码块的 Embedding 计算相似度。
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
          placeholder="例如：用户登录状态应该怎么保存？"
          value={query}
          onChange={(event) => {
            onQueryChange(
              event.target.value,
            )
          }}
          onKeyDown={(event) => {
            if (
              event.key === "Enter"
              && !event.nativeEvent.isComposing
            ) {
              onSearch()
            }
          }}
        />

        <button
          type="button"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
          onClick={onSearch}
          disabled={isPending}
        >
          {isPending
            ? "检索中..."
            : "语义检索"}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
          onClick={onBackfillEmbeddings}
          disabled={isBackfillPending}
        >
          {isBackfillPending
            ? "回填中..."
            : "回填旧数据 Embedding"}
        </button>

        <span className="text-xs text-slate-500">
          仅用于没有 Embedding 的普通旧文档。
        </span>
      </div>

      {isBackfillError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          Embedding 回填失败：
          {formatKnowledgeBaseChatError(
            backfillError,
          )}
        </div>
      ) : null}

      {backfillData ? (
        <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800">
          本次处理 {backfillData.processed} 个，成功 {backfillData.embedded} 个，失败 {backfillData.failed} 个，剩余 {backfillData.remaining} 个。模型：{backfillData.model}
        </div>
      ) : null}

      {isError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          语义检索失败：
          {formatKnowledgeBaseChatError(
            error,
          )}
        </div>
      ) : null}

      {data ? (
        <div className="space-y-3">
          <div className="text-sm text-slate-600">
            共找到 {data.count} 条语义检索结果。
          </div>

          {data.data.length === 0 ? (
            <div className="text-sm text-slate-600">
              暂无语义检索结果。请确认当前知识库已生成 Embedding。
            </div>
          ) : (
            data.data.map(
              (result) => (
                <article
                  key={
                    result.chunk_id
                  }
                  className="space-y-2 rounded-lg border border-slate-300 bg-slate-50 p-3 text-slate-900"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="break-all text-sm font-medium">
                      来源文件：
                      {
                        result.original_filename
                      }
                      {" ｜ "}
                      Chunk {
                        result.chunk_index
                      }
                    </div>

                    <div className="text-xs text-slate-600">
                      相似度：
                      {
                        result.similarity.toFixed(
                          4,
                        )
                      }
                      {" ｜ "}
                      长度：
                      {
                        result.content_length
                      }
                    </div>
                  </div>

                  <pre className="whitespace-pre-wrap break-words font-sans text-sm text-slate-900">
                    {result.content}
                  </pre>
                </article>
              ),
            )
          )}
        </div>
      ) : null}
    </section>
  )
}
