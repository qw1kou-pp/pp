import type {
  RagChatResponse,
} from "@/client"

import {
  RagSourceList,
} from "./RagSourceList"
import {
  formatKnowledgeBaseChatError,
} from "./knowledgeBaseChatTypes"

type RagChatSectionProps = {
  question: string
  onQuestionChange: (
    value: string,
  ) => void
  onSubmit: () => void

  data?: RagChatResponse
  isPending: boolean
  isError: boolean
  error: unknown

  repositoryScoped?: boolean
}

export function RagChatSection({
  question,
  onQuestionChange,
  onSubmit,
  data,
  isPending,
  isError,
  error,
  repositoryScoped = false,
}: RagChatSectionProps) {
  return (
    <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          {repositoryScoped
            ? "固定仓库版本问答"
            : "RAG 问答"}
        </h2>

        <p className="text-sm leading-6 text-slate-600">
          {repositoryScoped
            ? "只检索当前仓库分析任务导入的固定 Commit 代码，并返回文件路径和引用片段。"
            : "先从当前知识库检索相关代码块，再基于检索证据生成回答。"}
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <textarea
          className="min-h-[110px] min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-3 py-3 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
          placeholder="例如：这个项目的主要入口和关键调用链是什么？"
          value={question}
          onChange={(event) => {
            onQuestionChange(
              event.target.value,
            )
          }}
        />

        <button
          type="button"
          className="self-end rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
          onClick={onSubmit}
          disabled={isPending}
        >
          {isPending
            ? "回答中..."
            : "提问"}
        </button>
      </div>

      {isError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          问答失败：
          {formatKnowledgeBaseChatError(
            error,
          )}
        </div>
      ) : null}

      {data ? (
        <div className="space-y-4">
          <div className="space-y-3 rounded-xl border border-slate-300 bg-slate-50 p-4 text-slate-900">
            <div className="font-medium">
              回答
            </div>

            <pre className="whitespace-pre-wrap break-words font-sans text-sm text-slate-900">
              {data.answer}
            </pre>
          </div>

          <div className="space-y-3 rounded-xl border border-slate-300 bg-white p-4">
            <div className="font-medium">
              引用来源
            </div>

            <RagSourceList
              sources={data.sources}
              emptyText="暂无引用来源。说明当前范围内没有检索到相关代码块。"
            />
          </div>

          <div className="space-y-2 rounded-xl border border-slate-300 bg-white p-4">
            <div className="font-medium">
              执行过程 Trace
            </div>

            <div className="text-sm text-slate-600">
              {data.trace.length > 0
                ? data.trace.join(
                  " → ",
                )
                : "暂无 Trace。"}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}
