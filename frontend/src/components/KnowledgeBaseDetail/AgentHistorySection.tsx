import type {
  AgentRunsPublic,
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

type AgentHistorySectionProps = {
  isOpen: boolean
  onToggle: () => void

  keyword: string
  onKeywordChange: (
    value: string,
  ) => void
  onRefresh: () => void

  data?: AgentRunsPublic
  isLoading: boolean
  isError: boolean
  error: unknown

  expandedRunIds:
    readonly string[]
  onToggleRun: (
    runId: string,
  ) => void

  onDelete: (
    runId: string,
  ) => void
  isDeletePending: boolean
  isDeleteError: boolean
  deleteError: unknown
}

export function AgentHistorySection({
  isOpen,
  onToggle,
  keyword,
  onKeywordChange,
  onRefresh,
  data,
  isLoading,
  isError,
  error,
  expandedRunIds,
  onToggleRun,
  onDelete,
  isDeletePending,
  isDeleteError,
  deleteError,
}: AgentHistorySectionProps) {
  return (
    <CollapsibleSection
      title={
        repositoryScoped
          ? "当前仓库 Agent 历史"
          : "Agent 历史记录"
      }
      description={
        repositoryScoped
          ? (
            "仅显示当前仓库分析任务和"
            + "固定 Commit 对应的 Agent 历史。"
          )
          : (
            "查看 Agent 的问题、回答、"
            + "工具调用、来源和执行过程。"
          )
      }
      isOpen={isOpen}
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

      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
          placeholder="搜索 Agent 历史，例如：FastAPI / embedding / RAG"
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
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
            onClick={() => {
              onKeywordChange("")
            }}
          >
            清空
          </button>
        ) : null}
      </div>

      {isLoading ? (
        <div className="text-sm text-slate-600">
          正在加载 Agent 历史记录...
        </div>
      ) : null}

      {isError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          Agent 历史加载失败：
          {formatKnowledgeBaseChatError(
            error,
          )}
        </div>
      ) : null}

      {isDeleteError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          删除 Agent 历史失败：
          {formatKnowledgeBaseChatError(
            deleteError,
          )}
        </div>
      ) : null}

      {data ? (
        <div className="space-y-3">
          <div className="text-sm text-slate-600">
            共 {data.count} 条 Agent 历史记录。
          </div>

          {data.data.length === 0 ? (
            <div className="text-sm text-slate-600">
              暂无 Agent 历史记录。
            </div>
          ) : (
            data.data.map((run) => {
              const expanded =
                expandedRunIds.includes(
                  run.id,
                )

              return (
                <article
                  key={run.id}
                  className="space-y-3 rounded-xl border border-slate-300 bg-white p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <div className="break-words text-sm font-semibold">
                        {run.question}
                      </div>

                      <div className="text-xs text-slate-500">
                        top_k={run.top_k}
                        {" ｜ "}
                        max_steps={run.max_steps}
                        {" ｜ "}
                        S={run.semantic_weight}
                        {" ｜ "}
                        K={run.keyword_weight}
                        {" ｜ "}
                        耗时：
                        {run.latency_ms === null
                        || run.latency_ms === undefined
                          ? "-"
                          : `${run.latency_ms} ms`}
                      </div>

                      {run.source_commit_sha
                      || run.repository_analysis_task_id ? (
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-violet-700">
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

                      {run.created_at ? (
                        <div className="text-xs text-slate-500">
                          创建时间：
                          {new Date(
                            run.created_at,
                          ).toLocaleString()}
                        </div>
                      ) : null}

                      {run.error_message ? (
                        <div className="text-xs text-rose-600">
                          错误：{run.error_message}
                        </div>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-600"
                        onClick={() => {
                          onToggleRun(run.id)
                        }}
                      >
                        {expanded
                          ? "收起"
                          : "展开"}
                      </button>

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
                  </div>

                  <div className="whitespace-pre-wrap border-t border-slate-200 pt-3 text-sm">
                    {run.answer.length > 300
                    && !expanded
                      ? `${run.answer.slice(
                        0,
                        300,
                      )}...`
                      : run.answer}
                  </div>

                  {expanded ? (
                    <div className="space-y-4 border-t border-slate-200 pt-3">
                      <div className="space-y-2">
                        <h3 className="text-sm font-semibold">
                          工具调用过程
                        </h3>

                        {(run.tool_calls?.length ?? 0) === 0 ? (
                          <div className="text-sm text-slate-600">
                            暂无工具调用。
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {run.tool_calls?.map(
                              (
                                toolCall,
                                index,
                              ) => (
                                <article
                                  key={`${run.id}-${toolCall.tool_name}-${index}`}
                                  className="space-y-2 rounded-lg border border-slate-300 p-3"
                                >
                                  <div className="text-sm font-medium">
                                    {index + 1}. {toolCall.tool_name}
                                  </div>

                                  <pre className="whitespace-pre-wrap break-words text-xs text-slate-600">
                                    参数：
                                    {JSON.stringify(
                                      toolCall.arguments,
                                      null,
                                      2,
                                    )}
                                  </pre>

                                  <div className="text-xs text-slate-600">
                                    状态：
                                    {toolCall.success
                                      ? "成功"
                                      : "失败"}
                                  </div>

                                  <div className="whitespace-pre-wrap text-sm">
                                    {toolCall.observation}
                                  </div>
                                </article>
                              ),
                            )}
                          </div>
                        )}
                      </div>

                      <div className="space-y-2">
                        <h3 className="text-sm font-semibold">
                          Sources
                        </h3>

                        <RagSourceList
                          sources={run.sources ?? []}
                          emptyText="当前 Agent 历史没有来源资料。"
                        />
                      </div>

                      <div className="space-y-2">
                        <h3 className="text-sm font-semibold">
                          Trace
                        </h3>

                        {(run.trace?.length ?? 0) === 0 ? (
                          <div className="text-sm text-slate-600">
                            暂无 Trace。
                          </div>
                        ) : (
                          <ol className="list-inside list-decimal space-y-1 text-sm">
                            {run.trace?.map(
                              (
                                item,
                                index,
                              ) => (
                                <li
                                  key={`${run.id}-${item}-${index}`}
                                >
                                  {item}
                                </li>
                              ),
                            )}
                          </ol>
                        )}
                      </div>
                    </div>
                  ) : null}
                </article>
              )
            })
          )}
        </div>
      ) : null}
    </CollapsibleSection>
  )
}
