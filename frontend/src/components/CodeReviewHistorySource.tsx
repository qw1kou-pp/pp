import type {
  CodeReviewSourceSnapshot,
} from "@/client"

type CodeReviewHistorySourceProps = {
  source:
    CodeReviewSourceSnapshot
    | null
    | undefined

  compact?: boolean
}

const getSourceLabel = (
  source: CodeReviewSourceSnapshot,
): string => {
  if (source.provider === "gitlab") {
    return (
      `GitLab MR !` +
      source.change_number
    )
  }

  return (
    `GitHub PR #` +
    source.change_number
  )
}

const formatFetchedAt = (
  value: string,
): string => {
  const timestamp = Date.parse(value)

  if (Number.isNaN(timestamp)) {
    return value
  }

  return new Date(
    timestamp,
  ).toLocaleString(
    "zh-CN",
    {
      hour12: false,
    },
  )
}

export function CodeReviewHistorySource({
  source,
  compact = false,
}: CodeReviewHistorySourceProps) {
  if (!source) {
    return compact ? null : (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
        此 Review 使用手动 Diff，
        没有关联远端 PR/MR。
      </div>
    )
  }

  if (compact) {
    return (
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full border border-slate-300 bg-slate-100 px-2 py-1 font-medium text-slate-700">
          {getSourceLabel(source)}
        </span>

        <span className="max-w-64 truncate text-slate-500">
          {source.repository}
        </span>

        <a
          href={source.source_url}
          target="_blank"
          rel="noreferrer"
          onClick={(event) => {
            event.stopPropagation()
          }}
          className="font-medium text-blue-600 hover:underline"
        >
          打开来源
        </a>
      </div>
    )
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
              {getSourceLabel(source)}
            </span>

            <span className="text-xs text-slate-500">
              历史来源快照
            </span>
          </div>

          <div className="mt-3 font-medium text-slate-900">
            {source.title}
          </div>

          <div className="mt-1 break-all text-sm text-slate-600">
            {source.repository}
          </div>
        </div>

        <a
          href={source.source_url}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-100"
        >
          打开原始 PR/MR
        </a>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg bg-slate-50 p-3">
          <div className="text-xs text-slate-500">
            分支
          </div>

          <div className="mt-1 break-all text-slate-800">
            {source.head_ref}
            {" → "}
            {source.base_ref}
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 p-3">
          <div className="text-xs text-slate-500">
            作者
          </div>

          <div className="mt-1 text-slate-800">
            {source.author || "未知"}
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 p-3">
          <div className="text-xs text-slate-500">
            Base / Head
          </div>

          <div className="mt-1 break-all text-slate-800">
            {source.base_sha.slice(
              0,
              8,
            )}
            {" / "}
            {source.head_sha.slice(
              0,
              8,
            )}
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 p-3">
          <div className="text-xs text-slate-500">
            获取时间
          </div>

          <div className="mt-1 text-slate-800">
            {formatFetchedAt(
              source.fetched_at,
            )}
          </div>
        </div>
      </div>

      <div className="mt-3 break-all text-xs text-slate-500">
        Diff Hash：
        {source.diff_hash}
      </div>
    </section>
  )
}