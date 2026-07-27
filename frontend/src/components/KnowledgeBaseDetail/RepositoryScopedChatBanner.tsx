import type { RepositoryChatPrefill } from "@/components/RepositoryAnalysis/repositoryChatHandoff"

type RepositoryScopedChatBannerProps = {
  prefill: RepositoryChatPrefill
}

export function RepositoryScopedChatBanner({
  prefill,
}: RepositoryScopedChatBannerProps) {
  const safeRepositoryUrl = resolveSafeRepositoryUrl(prefill.repositoryUrl)

  return (
    <section className="rounded-2xl border border-violet-200 bg-violet-50/60 p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-violet-700">
            Repository scoped chat
          </p>

          <h2 className="mt-2 text-lg font-semibold text-slate-900">
            当前问答已限定到固定仓库版本
          </h2>

          <p className="mt-2 text-sm leading-6 text-slate-600">
            普通 RAG 和 Code Agent 都只会读取
            当前仓库分析任务导入的固定 Commit
            代码，不会混入当前知识库中的其他
            仓库或普通文档。
          </p>
        </div>

        {safeRepositoryUrl ? (
          <a
            href={safeRepositoryUrl}
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium text-violet-700 hover:underline"
          >
            打开 GitHub 仓库
          </a>
        ) : null}
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <MetadataItem label="仓库" value={prefill.repositoryFullName} />
        <MetadataItem
          label="固定 Commit"
          value={prefill.resolvedCommitSha}
          monospace
        />
        <MetadataItem
          label="分析任务"
          value={prefill.repositoryAnalysisTaskId}
          monospace
        />
      </dl>
    </section>
  )
}

function MetadataItem({
  label,
  value,
  monospace = false,
}: {
  label: string
  value: string
  monospace?: boolean
}) {
  return (
    <div className="rounded-lg border border-violet-100 bg-white p-3">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd
        className={`mt-1 break-all text-slate-800 ${
          monospace ? "font-mono" : "font-medium"
        }`}
      >
        {value}
      </dd>
    </div>
  )
}

function resolveSafeRepositoryUrl(value: string): string | null {
  try {
    const parsed = new URL(value)

    if (parsed.protocol !== "https:") {
      return null
    }

    return parsed.toString()
  } catch {
    return null
  }
}
