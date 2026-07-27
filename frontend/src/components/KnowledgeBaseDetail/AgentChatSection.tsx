import type {
  AgentChatResponse,
} from "@/client"

import {
  RagSourceList,
} from "./RagSourceList"
import {
  formatKnowledgeBaseChatError,
} from "./knowledgeBaseChatTypes"

type AgentChatSectionProps = {
  question: string
  onQuestionChange: (
    value: string,
  ) => void
  onSubmit: () => void

  data?: AgentChatResponse
  isPending: boolean
  isError: boolean
  error: unknown
  repositoryScoped?: boolean

  repositoryFullName?:
    string

  resolvedCommitSha?:
    string
}

export function AgentChatSection({
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
}: AgentChatSectionProps) {
  return (
    <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          Agent Chat
        </h2>

        <p className="text-sm text-slate-600">
          {repositoryScoped ? (
            <>
              Agent 会调用代码工具分析当前仓库
              的固定 Commit，所有工具查询都会
              被限制在当前仓库分析任务范围内。
            </>
          ) : (
            <>
              Agent 会根据问题调用工具，例如
              查看文档列表、检索知识库，再生成
              最终回答。
            </>
          )}
        </p>
      </div>

      {repositoryScoped ? (
        <div className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-800">
          当前 Agent 范围：
          <span className="font-medium">
            {" "}
            {
              repositoryFullName
              || "当前仓库"
            }
          </span>

          {resolvedCommitSha ? (
            <>
              {" ｜ "}
              Commit：
              <span className="font-mono">
                {
                  resolvedCommitSha
                    .slice(
                      0,
                      12,
                    )
                }
              </span>
            </>
          ) : null}
        </div>
      ) : null}

      <textarea
        className="min-h-[110px] w-full rounded-xl border border-slate-300 bg-white px-3 py-3 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
        placeholder={
          repositoryScoped
            ? (
              "请输入仓库问题，例如："
              + "项目主入口在哪里？"
              + "这个函数在哪里定义和调用？"
            )
            : (
              "请输入 Agent 问题，例如："
              + "这个知识库有哪些文档？"
            )
        }
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
            ? "Agent 思考中..."
            : "发送给 Agent"}
        </button>

        {repositoryScoped ? (
          <>
            <button
              type="button"
              className="rounded-lg border px-3 py-1.5 text-sm"
              onClick={() => {
                onQuestionChange(
                  "请说明这个仓库的主要入口、核心模块和整体执行流程。",
                )
              }}
            >
              示例：仓库架构
            </button>

            <button
              type="button"
              className="rounded-lg border px-3 py-1.5 text-sm"
              onClick={() => {
                onQuestionChange(
                  "请找出当前仓库的主要 API 路由，并说明它们调用了哪些服务。",
                )
              }}
            >
              示例：调用链
            </button>

            <button
              type="button"
              className="rounded-lg border px-3 py-1.5 text-sm"
              onClick={() => {
                onQuestionChange(
                  "请分析当前仓库中可能存在的代码风险，并标明来源文件。",
                )
              }}
            >
              示例：代码风险
            </button>
          </>
        ) : (
          <>
            {/* 保留原来的知识库示例按钮 */}
          </>
        )}
      </div>

      {isError ? (
        <div className="whitespace-pre-wrap text-sm text-rose-600">
          Agent 调用失败：
          {formatKnowledgeBaseChatError(
            error,
          )}
        </div>
      ) : null}

      {data ? (
        <div className="space-y-4">
          <div className="space-y-2 rounded-xl border border-slate-300 bg-white p-4">
            <h3 className="font-semibold">
              Agent 最终回答
            </h3>

            <div className="whitespace-pre-wrap text-sm">
              {data.answer}
            </div>
          </div>

          <div className="space-y-2 rounded-xl border border-slate-300 bg-white p-4">
            <h3 className="font-semibold">
              工具调用过程
            </h3>

            {data.tool_calls.length === 0 ? (
              <div className="text-sm text-slate-600">
                暂无工具调用。
              </div>
            ) : (
              <div className="space-y-3">
                {data.tool_calls.map(
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
                )}
              </div>
            )}
          </div>

          <div className="space-y-3 rounded-xl border border-slate-300 bg-white p-4">
            <h3 className="font-semibold">
              Agent Sources
            </h3>

            <RagSourceList
              sources={data.sources}
              emptyText="Agent 没有返回来源资料。"
            />
          </div>

          <div className="space-y-2 rounded-xl border border-slate-300 bg-white p-4">
            <h3 className="font-semibold">
              Agent Trace
            </h3>

            {data.trace.length === 0 ? (
              <div className="text-sm text-slate-600">
                暂无 Trace。
              </div>
            ) : (
              <ol className="list-inside list-decimal space-y-1 text-sm">
                {data.trace.map(
                  (item, index) => (
                    <li
                      key={`${item}-${index}`}
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
    </section>
  )
}
