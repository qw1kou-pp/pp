import type {
  KnowledgeBaseSearchResults,
} from "@/client"

import {
  formatKnowledgeBaseChatError,
} from "./knowledgeBaseChatTypes"

type KeywordSearchSectionProps = {
  query: string
  onQueryChange: (
    value: string,
  ) => void
  onSearch: () => void

  data?: KnowledgeBaseSearchResults
  isPending: boolean
  isError: boolean
  error: unknown
}

export function KeywordSearchSection({
  query,
  onQueryChange,
  onSearch,
  data,
  isPending,
  isError,
  error,
}: KeywordSearchSectionProps) {
  return (
    <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          关键词检索
        </h2>

        <p className="text-sm leading-6 text-slate-600">
          根据输入的关键词匹配当前知识库中的代码块，适合查找函数名、类名、文件名和错误信息。
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
          placeholder="例如：FastAPI 路由"
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
            : "检索"}
        </button>
      </div>

      {isError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          检索失败：
          {formatKnowledgeBaseChatError(
            error,
          )}
        </div>
      ) : null}

      {data ? (
        <div className="space-y-3">
          <div className="text-sm text-slate-600">
            共找到 {data.count} 条结果，当前展示 {data.data.length} 条。
          </div>

          {data.data.length === 0 ? (
            <div className="text-sm text-slate-600">
              暂无匹配结果。
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
                      命中次数：
                      {
                        result.match_count
                        ?? 0
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
