import type {
  CodeReviewPublicationPublic,
} from "@/client"

export type GitHubReviewEvent =
  | "COMMENT"
  | "APPROVE"
  | "REQUEST_CHANGES"

export type PublicationApiErrorDetail = {
  code: string
  message: string
  retryable: boolean
  context: Record<
    string,
    unknown
  >
}

export const GITHUB_REVIEW_EVENTS:
  readonly GitHubReviewEvent[] = [
    "COMMENT",
    "APPROVE",
    "REQUEST_CHANGES",
  ]

export const normalizeGitHubReviewEvent = (
  value?: string | null,
): GitHubReviewEvent => {
  const normalizedValue = String(
    value || "",
  )
    .trim()
    .toUpperCase()

  if (
    normalizedValue === "APPROVE"
  ) {
    return "APPROVE"
  }

  if (
    normalizedValue
    === "REQUEST_CHANGES"
  ) {
    return "REQUEST_CHANGES"
  }

  return "COMMENT"
}

export const getGitHubReviewEventLabel = (
  event?: string | null,
): string => {
  const normalizedEvent =
    normalizeGitHubReviewEvent(
      event,
    )

  const labelMap: Record<
    GitHubReviewEvent,
    string
  > = {
    COMMENT:
      "COMMENT · 仅发表评论",

    APPROVE:
      "APPROVE · 批准合并",

    REQUEST_CHANGES:
      "REQUEST_CHANGES · 请求修改",
  }

  return labelMap[
    normalizedEvent
  ]
}

export const getGitHubReviewEventDescription = (
  event?: string | null,
): string => {
  const normalizedEvent =
    normalizeGitHubReviewEvent(
      event,
    )

  const descriptionMap: Record<
    GitHubReviewEvent,
    string
  > = {
    COMMENT:
      "发布普通 Review 评论，不批准也不阻止合并。",

    APPROVE:
      "在 GitHub 上将该提交标记为已批准。",

    REQUEST_CHANGES:
      "在 GitHub 上明确要求修改，通常会阻止直接合并。",
  }

  return descriptionMap[
    normalizedEvent
  ]
}

export const getPublicationStatusLabel = (
  status?: string | null,
): string => {
  const normalizedStatus = String(
    status || "",
  ).toLowerCase()

  if (
    normalizedStatus
    === "succeeded"
  ) {
    return "发布成功"
  }

  if (
    normalizedStatus
    === "failed"
  ) {
    return "发布失败"
  }

  if (
    normalizedStatus
    === "publishing"
  ) {
    return "正在发布"
  }

  return normalizedStatus || "未知状态"
}

export const getPublicationStatusClassName = (
  status?: string | null,
): string => {
  const normalizedStatus = String(
    status || "",
  ).toLowerCase()

  if (
    normalizedStatus
    === "succeeded"
  ) {
    return (
      "border-emerald-200 " +
      "bg-emerald-50 " +
      "text-emerald-700"
    )
  }

  if (
    normalizedStatus
    === "failed"
  ) {
    return (
      "border-rose-200 " +
      "bg-rose-50 " +
      "text-rose-700"
    )
  }

  return (
    "border-amber-200 " +
    "bg-amber-50 " +
    "text-amber-700"
  )
}

export const formatPublicationDateTime = (
  value?: string | null,
): string => {
  if (!value) {
    return "时间未知"
  }

  const timestamp = Date.parse(
    value,
  )

  if (
    Number.isNaN(
      timestamp,
    )
  ) {
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

export const getPublicationLink = (
  publication:
    CodeReviewPublicationPublic,
): string | null => {
  return (
    publication
      .external_review_url
    || publication
      .target_source_url
    || null
  )
}

export const readPublicationApiError = (
  error: unknown,
): PublicationApiErrorDetail => {
  const defaultError:
    PublicationApiErrorDetail = {
      code:
        "UNKNOWN_PUBLICATION_ERROR",

      message:
        "GitHub Review 操作失败。",

      retryable:
        false,

      context: {},
    }

  if (
    !error
    || typeof error !== "object"
  ) {
    return {
      ...defaultError,
      message: String(
        error
        || defaultError.message,
      ),
    }
  }

  const candidate = error as {
    message?: string

    body?: {
      detail?: unknown
    }
  }

  const detail =
    candidate.body?.detail

  if (
    detail
    && typeof detail === "object"
  ) {
    const detailObject =
      detail as {
        code?: unknown
        message?: unknown
        retryable?: unknown
        context?: unknown
      }

    return {
      code:
        String(
          detailObject.code
          || defaultError.code,
        ),

      message:
        String(
          detailObject.message
          || candidate.message
          || defaultError.message,
        ),

      retryable:
        detailObject.retryable
        === true,

      context:
        detailObject.context
        && typeof (
          detailObject.context
        ) === "object"
          ? detailObject.context as Record<
              string,
              unknown
            >
          : {},
    }
  }

  if (
    typeof detail
    === "string"
  ) {
    return {
      ...defaultError,
      message: detail,
    }
  }

  return {
    ...defaultError,

    message:
      candidate.message
      || defaultError.message,
  }
}