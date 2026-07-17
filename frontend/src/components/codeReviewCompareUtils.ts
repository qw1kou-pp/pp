export type ReviewCompareTrend =
  | "increased"
  | "decreased"
  | "unchanged"
  | "changed"
  | "unavailable"

export type ReviewMetricTrend = "increased" | "decreased" | "unchanged"

export type ReviewRunCompareOption = {
  id: string
  title: string
  created_at?: string | null
  risk_level?: string | null
  generation_status?: string | null
}

export type ReviewMetricChangeLike = {
  base_value: number
  target_value: number
  delta: number
  trend: ReviewMetricTrend
}

export type ReviewValueChangeLike = {
  base_value?: string | null
  target_value?: string | null
  trend: ReviewCompareTrend
}

const REVIEW_VALUE_LABELS: Record<string, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",

  completed: "完整报告",
  evidence_only: "仅 Evidence",

  approve: "可以合并",
  needs_review: "需要复核",
  request_changes: "需要修改",
}

const TREND_LABELS: Record<ReviewCompareTrend, string> = {
  increased: "上升",
  decreased: "下降",
  unchanged: "不变",
  changed: "已变化",
  unavailable: "无法判断",
}

const readCreatedAtTimestamp = (value?: string | null): number => {
  if (!value) {
    return Number.NEGATIVE_INFINITY
  }

  const timestamp = Date.parse(value)

  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp
}

export const sortReviewRunsNewestFirst = <T extends ReviewRunCompareOption>(
  reviewRuns: readonly T[],
): T[] => {
  return [...reviewRuns].sort((left, right) => {
    const leftTimestamp = readCreatedAtTimestamp(left.created_at)

    const rightTimestamp = readCreatedAtTimestamp(right.created_at)

    if (leftTimestamp !== rightTimestamp) {
      return rightTimestamp - leftTimestamp
    }

    // 创建时间完全一致时，用 ID 保证排序稳定。
    return right.id.localeCompare(left.id)
  })
}

export const getLatestReviewPair = <T extends ReviewRunCompareOption>(
  reviewRuns: readonly T[],
): {
  base: T
  target: T
} | null => {
  const sortedReviewRuns = sortReviewRunsNewestFirst(reviewRuns)

  if (sortedReviewRuns.length < 2) {
    return null
  }

  return {
    // 倒数第二次生成的记录作为基准 A。
    base: sortedReviewRuns[1],

    // 最新生成的记录作为目标 B。
    target: sortedReviewRuns[0],
  }
}

export const canCompareReviewRuns = (
  baseReviewRunId: string | null | undefined,
  targetReviewRunId: string | null | undefined,
): boolean => {
  return Boolean(
    baseReviewRunId &&
      targetReviewRunId &&
      baseReviewRunId !== targetReviewRunId,
  )
}

export const formatMetricChange = (change: ReviewMetricChangeLike): string => {
  const prefix = `${change.base_value} → ` + `${change.target_value}`

  if (change.delta > 0) {
    return `${prefix}（增加 ` + `${change.delta}）`
  }

  if (change.delta < 0) {
    return `${prefix}（减少 ` + `${Math.abs(change.delta)}）`
  }

  return `${prefix}（不变）`
}

export const formatReviewValue = (value?: string | null): string => {
  if (!value) {
    return "暂无"
  }

  return REVIEW_VALUE_LABELS[value] ?? value
}

export const formatValueChange = (change: ReviewValueChangeLike): string => {
  return (
    `${formatReviewValue(change.base_value)} → ` +
    `${formatReviewValue(change.target_value)}`
  )
}

export const getTrendLabel = (trend: ReviewCompareTrend): string => {
  return TREND_LABELS[trend]
}

export const formatReviewRunLabel = (
  reviewRun: ReviewRunCompareOption,
): string => {
  const parts = [reviewRun.title]

  if (reviewRun.risk_level) {
    parts.push(formatReviewValue(reviewRun.risk_level))
  }

  if (reviewRun.generation_status) {
    parts.push(formatReviewValue(reviewRun.generation_status))
  }

  return parts.join(" · ")
}
