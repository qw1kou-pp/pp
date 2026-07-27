import type {
  RagRunsPublic,
} from "@/client"

import {
  CollapsibleSection,
} from "./CollapsibleSection"
import {
  RagSourceList,
} from "./RagSourceList"
import {
  formatKnowledgeBaseChatError,
} from "./knowledgeBaseChatTypes"

type RagHistorySectionProps = {
  isOpen: boolean
  onToggle: () => void

  keyword: string
  onKeywordChange: (
    value: string,
  ) => void
  onRefresh: () => void

  data?: RagRunsPublic
  isLoading: boolean
  isError: boolean
  error: unknown

  onDelete: (
    runId: string,
  ) => void
  isDeletePending: boolean
  isDeleteError: boolean
  deleteError: unknown
}

export function RagHistorySection({
  isOpen,
  onToggle,
  keyword,
  onKeywordChange,
  onRefresh,
  data,
  isLoading,
  isError,
  error,
  onDelete,
  isDeletePending,
  isDeleteError,
  deleteError,
}: RagHistorySectionProps) {
  return (
    <CollapsibleSection
      title={
        repositoryScoped
          ? "当前仓库 RAG 历史"
          : "RAG 问答历史"
      }
      description={
        repositoryScoped
          ? (
            "仅显示当前仓库分析任务和"
            + "固定 Commit 对应的 RAG 历史。"
          )
          : (
            "查看普通知识库 RAG 问答的"
            + "历史问题、回答、来源和执行过程。"
          )
      }
      isOpen={isOpen}
      onToggle={onToggle}
      onToggle={onToggle}
    >
      <div className="flex flex-wrap justify-end gap-2">
        <button
          type="button"
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700"
          onClick={onRefresh}
        >
          刷新历史
        </button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
          placeholder="搜索历史，例如：FastAPI、JWT、登录"
          value={keyword}
          onChange={(event) => {
            onKeywordChange(
              event.target.value,
            )
          }}
        />

        {keyword.trim() ? (
          <button
            type="button"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700"
            onClick={() => {
              onKeywordChange("")
            }}
          >
            清空
          </button>
        ) : null}
      </div>

      {isDeleteError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          删除失败：
          {formatKnowledgeBaseChatError(
            deleteError,
          )}
        </div>
      ) : null}

      {isLoading ? (
        <div className="text-sm text-slate-600">
          正在加载问答历史...
        </div>
      ) : null}

      {isError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          问答历史加载失败：
          {formatKnowledgeBaseChatError(
            error,
          )}
        </div>
      ) : null}

      {data ? (
        <div className="space-y-3">
          <div className="text-sm text-slate-600">
            共 {data.count} 条记录，当前展示 {data.data.length} 条。
          </div>

          {data.data.length === 0 ? (
            <div className="text-sm text-slate-600">
              暂无问答历史。
            </div>
          ) : (
            data.data.map(
              (run) => (
                <article
                  key={run.id}
                  className="space-y-3 rounded-xl border border-slate-300 bg-slate-50 p-4 text-slate-900"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="break-words text-sm font-medium">
                        问题：{run.question}
                      </div>

                      <div className="mt-1 text-xs text-slate-500">
                        检索方式：{run.retrieval_type}
                        {" ｜ "}
                        耗时：{run.latency_ms ?? "-"} ms
                      </div>

                      {run.source_commit_sha
                      || run.repository_analysis_task_id ? (
                        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                          {run.source_commit_sha ? (
                            <span>
                              Commit：
                              <span
                                className="font-mono"
                                title={
                                  run.source_commit_sha
                                }
                              >
                                {run.source_commit_sha.slice(
                                  0,
                                  12,
                                )}
                              </span>
                            </span>
                          ) : null}

                          {run.repository_analysis_task_id ? (
                            <span>
                              分析任务：
                              <span
                                className="font-mono"
                                title={
                                  run
                                    .repository_analysis_task_id
                                }
                              >
                                {run
                                  .repository_analysis_task_id
                                  .slice(
                                    0,
                                    8,
                                  )}
                              </span>
                            </span>
                          ) : null}
                        </div>
                      ) : null}
                    </div>

                    <button
                      type="button"
                      className="rounded border border-rose-200 px-2 py-1 text-xs text-rose-600 disabled:opacity-50"
                      onClick={() => {
                        onDelete(run.id)
                      }}
                      disabled={isDeletePending}
                    >
                      删除
                    </button>
                  </div>

                  {run.error_message ? (
                    <div className="text-xs text-rose-600">
                      错误：{run.error_message}
                    </div>
                  ) : null}

                  <div className="space-y-1">
                    <div className="text-sm font-medium text-slate-700">
                      回答
                    </div>

                    <pre className="whitespace-pre-wrap break-words font-sans text-sm text-slate-900">
                      {run.answer}
                    </pre>
                  </div>

                  <details className="space-y-2">
                    <summary className="cursor-pointer text-sm text-slate-600">
                      查看引用来源（{run.sources?.length ?? 0}）
                    </summary>

                    <div className="pt-2">
                      <RagSourceList
                        sources={run.sources ?? []}
                        emptyText="当前记录没有引用来源。"
                      />
                    </div>
                  </details>

                  <details>
                    <summary className="cursor-pointer text-sm text-slate-600">
                      查看执行过程 Trace
                    </summary>

                    <div className="pt-2 text-sm text-slate-600">
                      {(run.trace?.length ?? 0) > 0
                        ? run.trace?.join(
                          " → ",
                        )
                        : "暂无 Trace。"}
                    </div>
                  </details>

                  {run.created_at ? (
                    <div className="text-xs text-slate-500">
                      创建时间：
                      {new Date(
                        run.created_at,
                      ).toLocaleString()}
                    </div>
                  ) : null}
                </article>
              ),
            )
          )}
        </div>
      ) : null}
    </CollapsibleSection>
  )
}
