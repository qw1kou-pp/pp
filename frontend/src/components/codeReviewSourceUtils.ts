import type {
  CodeReviewSourceResolvedPublic,
} from "@/client"

export type ReviewSourceSnapshot = {
  provider:
    CodeReviewSourceResolvedPublic[
      "provider"
    ]

  source_url: string
  repository: string
  change_number: number
  title: string
  author?: string | null
  base_ref: string
  head_ref: string
  base_sha: string
  head_sha: string
  diff_hash: string
  fetched_at: string
}

export const toCodeReviewSourceSnapshot = (
  source: CodeReviewSourceResolvedPublic,
): ReviewSourceSnapshot => {
  return {
    provider:
      source.provider,

    source_url:
      source.source_url,

    repository:
      source.repository,

    change_number:
      source.change_number,

    title:
      source.title,

    author:
      source.author,

    base_ref:
      source.base_ref,

    head_ref:
      source.head_ref,

    base_sha:
      source.base_sha,

    head_sha:
      source.head_sha,

    diff_hash:
      source.diff_hash,

    fetched_at:
      source.fetched_at,
  }
}

export const formatCodeReviewSourceLabel = (
  source: Pick<
    CodeReviewSourceResolvedPublic,
    "provider" | "change_number"
  >,
): string => {
  if (
    source.provider === "gitlab"
  ) {
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

export const formatSourceDateTime = (
  value?: string | null,
): string => {
  if (!value) {
    return "时间未知"
  }

  const timestamp =
    Date.parse(value)

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

export const formatDiffSize = (
  diffText: string,
): string => {
  const byteCount =
    new TextEncoder().encode(
      diffText,
    ).byteLength

  if (byteCount < 1024) {
    return `${byteCount} B`
  }

  return (
    `${(
      byteCount / 1024
    ).toFixed(1)} KiB`
  )
}