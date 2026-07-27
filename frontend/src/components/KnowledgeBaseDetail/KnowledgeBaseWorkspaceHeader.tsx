import { Link } from "@tanstack/react-router"

type KnowledgeBaseHeaderData = {
  id: string
  name: string
  description?: string | null
}

type KnowledgeBaseWorkspaceHeaderProps = {
  knowledgeBase: KnowledgeBaseHeaderData
  documentCount: number
}

export function KnowledgeBaseWorkspaceHeader({
  knowledgeBase,
  documentCount,
}: KnowledgeBaseWorkspaceHeaderProps) {
  return (
    <>
      <Link
        to="/knowledge-bases"
        className="inline-flex items-center text-sm font-medium text-slate-900 transition hover:text-sky-700"
      >
        ← 返回知识库列表
      </Link>

      <header className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-2">
            <div className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700">
              Knowledge Base Workspace
            </div>

            <div>
              <h1 className="break-words text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">
                {knowledgeBase.name}
              </h1>

              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-900">
                {knowledgeBase.description || "暂无描述"}
              </p>
            </div>
          </div>

          <div className="flex max-w-full flex-wrap gap-2 text-xs">
            <span className="rounded-full border border-slate-600 bg-slate-50 px-3 py-1.5 text-slate-600">
              文档 {documentCount} 个
            </span>

            <span className="max-w-full truncate rounded-full border border-slate-600 bg-slate-50 px-3 py-1.5 font-mono text-slate-900">
              ID：{knowledgeBase.id}
            </span>
          </div>
        </div>
      </header>
    </>
  )
}
