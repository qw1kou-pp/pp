import type {
  AgentChatResponse,
  RagChatResponse,
} from "@/client"

import {
  RagSourceList,
} from "./RagSourceList"
import {
  formatKnowledgeBaseChatError,
} from "./knowledgeBaseChatTypes"

type RagAgentSingleCompareData = {
  ragResult: RagChatResponse
  agentResult: AgentChatResponse
}

type RagAgentSingleCompareSectionProps = {
  question: string
  onQuestionChange: (
    value: string,
  ) => void
  onSubmit: () => void

  data?: RagAgentSingleCompareData
  isPending: boolean
  isError: boolean
  error: unknown
  repositoryScoped?: boolean

  repositoryFullName?:
    string

  resolvedCommitSha?:
    string
}

export function RagAgentSingleCompareSection({
  question,
  onQuestionChange,
  onSubmit,
  data,
  isPending,
  isError,
  error,

  repositoryScoped = false,
  repositoryFullName,
  resolvedCommitSha,
}: RagAgentSingleCompareSectionProps) {
  return (
    <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          RAG vs Agent 单题对比
        </h2>

        {repositoryScoped ? (
          <div className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-800">
            本次对比中，普通 RAG 和 Agent
            都只会使用
            <span className="font-medium">
              {" "}
              {
                repositoryFullName
                || "当前仓库"
              }
            </span>
            的固定 Commit 代码。

            {resolvedCommitSha ? (
              <span className="ml-1 font-mono">
                {
                  resolvedCommitSha
                    .slice(
                      0,
                      12,
                    )
                }
              </span>
            ) : null}
          </div>
        ) : null}

        <p className="text-sm leading-6 text-slate-600">
          对同一个问题同时运行普通 RAG 和 Agent，比较回答、来源、工具调用和耗时。
        </p>
      </div>

      <textarea
        className="min-h-[110px] w-full rounded-xl border border-slate-300 bg-white px-3 py-3 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
        placeholder="例如：请详细总结一下这个知识库主要讲了什么"
        value={question}
        onChange={(event) => {
          onQuestionChange(
            event.target.value,
          )
        }}
      />

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
          onClick={onSubmit}
          disabled={isPending}
        >
          {isPending
            ? "对比运行中..."
            : "同时运行 RAG 和 Agent"}
        </button>

        <button
          type="button"
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700"
          onClick={() => {
            onQuestionChange(
              "请详细总结一下这个知识库主要讲了什么",
            )
          }}
        >
          示例：总结知识库
        </button>

        <button
          type="button"
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700"
          onClick={() => {
            onQuestionChange(
              "FastAPI 的接口参数是怎么校验的？",
            )
          }}
        >
          示例：具体问题
        </button>
      </div>

      {isError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          对比运行失败：
          {formatKnowledgeBaseChatError(
            error,
          )}
        </div>
      ) : null}

      {data ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <CompareResultCard
            title="普通 RAG"
            result={data.ragResult}
          />

          <AgentCompareResultCard
            result={data.agentResult}
          />
        </div>
      ) : null}
    </section>
  )
}

function CompareResultCard({
  title,
  result,
}: {
  title: string
  result: RagChatResponse
}) {
  return (
    <article className="space-y-3 rounded-xl border border-slate-300 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">
          {title}
        </h3>

        <div className="text-xs text-slate-500">
          耗时：
          {result.latency_ms === null
          || result.latency_ms === undefined
            ? "-"
            : `${result.latency_ms} ms`}
        </div>
      </div>

      <div className="whitespace-pre-wrap rounded-lg border border-slate-200 p-3 text-sm">
        {result.answer}
      </div>

      <div className="text-xs text-slate-500">
        Sources 数量：
        {result.sources.length}
      </div>

      <details className="rounded-lg border border-slate-300 bg-white p-3">
        <summary className="cursor-pointer text-sm font-medium">
          查看 RAG Sources
        </summary>

        <div className="mt-3">
          <RagSourceList
            sources={result.sources}
            emptyText="普通 RAG 没有返回来源资料。"
          />
        </div>
      </details>

      <details className="rounded-lg border border-slate-300 bg-white p-3">
        <summary className="cursor-pointer text-sm font-medium">
          查看 RAG Trace
        </summary>

        <ol className="mt-3 list-inside list-decimal space-y-1 text-sm">
          {result.trace.map(
            (item, index) => (
              <li
                key={`${item}-${index}`}
              >
                {item}
              </li>
            ),
          )}
        </ol>
      </details>
    </article>
  )
}

function AgentCompareResultCard({
  result,
}: {
  result: AgentChatResponse
}) {
  return (
    <article className="space-y-3 rounded-xl border border-slate-300 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">
          Agent
        </h3>

        <div className="text-xs text-slate-500">
          耗时：
          {result.latency_ms === null
          || result.latency_ms === undefined
            ? "-"
            : `${result.latency_ms} ms`}
        </div>
      </div>

      <div className="whitespace-pre-wrap rounded-lg border border-slate-200 p-3 text-sm">
        {result.answer}
      </div>

      <div className="text-xs text-slate-500">
        Sources 数量：
        {result.sources.length}
        {" ｜ "}
        工具调用数量：
        {result.tool_calls.length}
      </div>

      <details
        className="rounded-lg border border-slate-300 bg-white p-3"
        open
      >
        <summary className="cursor-pointer text-sm font-medium">
          查看 Agent 工具调用
        </summary>

        <div className="mt-3 space-y-3">
          {result.tool_calls.length === 0 ? (
            <div className="text-sm text-slate-600">
              暂无工具调用。
            </div>
          ) : (
            result.tool_calls.map(
              (
                toolCall,
                index,
              ) => (
                <article
                  key={`${toolCall.tool_name}-${index}`}
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
            )
          )}
        </div>
      </details>

      <details className="rounded-lg border border-slate-300 bg-white p-3">
        <summary className="cursor-pointer text-sm font-medium">
          查看 Agent Sources
        </summary>

        <div className="mt-3">
          <RagSourceList
            sources={result.sources}
            emptyText="Agent 没有返回来源资料。"
          />
        </div>
      </details>

      <details className="rounded-lg border border-slate-300 bg-white p-3">
        <summary className="cursor-pointer text-sm font-medium">
          查看 Agent Trace
        </summary>

        <ol className="mt-3 list-inside list-decimal space-y-1 text-sm">
          {result.trace.map(
            (item, index) => (
              <li
                key={`${item}-${index}`}
              >
                {item}
              </li>
            ),
          )}
        </ol>
      </details>
    </article>
  )
}
