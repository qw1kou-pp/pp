export const repositoryAnalysisStatuses = [
  "queued",
  "running",
  "completed",
  "failed",
  "expired",
] as const

export type RepositoryAnalysisStatus =
  (typeof repositoryAnalysisStatuses)[number]

export const repositoryAnalysisStages = [
  "queued",
  "claimed",
  "fetching_metadata",
  "resolving_commit",
  "downloading_snapshot",
  "scanning_repository",
  "analyzing_code",
  "tracing_backend_flows",
  "tracing_frontend_flows",
  "building_evidence",
  "generating_report",
  "completed",
  "failed",
  "expired",
] as const

export const repositoryAnalysisPipelineStages = [
  "queued",
  "claimed",
  "fetching_metadata",
  "resolving_commit",
  "downloading_snapshot",
  "scanning_repository",
  "analyzing_code",
  "tracing_backend_flows",
  "tracing_frontend_flows",
  "building_evidence",
  "generating_report",
  "completed",
] as const

export function getRepositoryAnalysisProgress(
  value: number | null | undefined,
): number {
  const normalized =
    Number(value ?? 0)

  if (
    !Number.isFinite(normalized)
  ) {
    return 0
  }

  return Math.min(
    100,
    Math.max(
      0,
      normalized,
    ),
  )
}

export type RepositoryAnalysisStage =
  (typeof repositoryAnalysisStages)[number]

export type RepositoryAnalysisStatusMeta = {
  label: string
  className: string
}

const statusMeta: Record<
  RepositoryAnalysisStatus,
  RepositoryAnalysisStatusMeta
> = {
  queued: {
    label: "等待处理",
    className:
      "border-slate-200 bg-slate-50 text-slate-700",
  },
  running: {
    label: "分析中",
    className:
      "border-blue-200 bg-blue-50 text-blue-700",
  },
  completed: {
    label: "已完成",
    className:
      "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  failed: {
    label: "失败",
    className:
      "border-red-200 bg-red-50 text-red-700",
  },
  expired: {
    label: "已过期",
    className:
      "border-amber-200 bg-amber-50 text-amber-700",
  },
}

const stageLabels: Record<
  RepositoryAnalysisStage,
  string
> = {
  queued: "等待处理",
  claimed: "已领取任务",
  fetching_metadata: "获取仓库信息",
  resolving_commit: "解析代码版本",
  downloading_snapshot: "下载仓库快照",
  scanning_repository: "扫描目录结构",
  analyzing_code: "分析代码",
  tracing_backend_flows: "分析后端调用链",
  tracing_frontend_flows: "分析前端调用链",
  building_evidence: "构建证据",
  generating_report: "生成报告",
  completed: "分析完成",
  failed: "分析失败",
  expired: "结果已过期",
}

export const repositoryAnalysisStageOrder =
  repositoryAnalysisStages

export function isRepositoryAnalysisStatus(
  value: unknown,
): value is RepositoryAnalysisStatus {
  return repositoryAnalysisStatuses.includes(
    value as RepositoryAnalysisStatus,
  )
}

export function isRepositoryAnalysisStage(
  value: unknown,
): value is RepositoryAnalysisStage {
  return repositoryAnalysisStages.includes(
    value as RepositoryAnalysisStage,
  )
}

export function isActiveRepositoryAnalysisStatus(
  status: string | null | undefined,
): boolean {
  return (
    status === "queued" ||
    status === "running"
  )
}

export function isTerminalRepositoryAnalysisStatus(
  status: string | null | undefined,
): boolean {
  return (
    status === "completed" ||
    status === "failed" ||
    status === "expired"
  )
}

export function getRepositoryAnalysisStatusMeta(
  status: string | null | undefined,
): RepositoryAnalysisStatusMeta {
  if (
    status &&
    isRepositoryAnalysisStatus(status)
  ) {
    return statusMeta[status]
  }

  return {
    label: status?.trim() || "未知状态",
    className:
      "border-slate-200 bg-slate-50 text-slate-700",
  }
}

export function getRepositoryAnalysisStageLabel(
  stage: string | null | undefined,
): string {
  if (
    stage &&
    isRepositoryAnalysisStage(stage)
  ) {
    return stageLabels[stage]
  }

  return stage?.trim() || "未知阶段"
}

export function formatRepositoryAnalysisDate(
  value: string | null | undefined,
): string {
  if (!value) {
    return "—"
  }

  const date = new Date(value)

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return value
  }

  return date.toLocaleString(
    "zh-CN",
    {
      hour12: false,
    },
  )
}

export function formatRepositoryCommitSha(
  value: string | null | undefined,
  length = 8,
): string {
  const normalizedValue =
    value?.trim()

  if (!normalizedValue) {
    return "—"
  }

  return normalizedValue.slice(
    0,
    Math.max(1, length),
  )
}

export function formatRepositoryAnalysisError(
  error: unknown,
): string {
  if (
    !error ||
    typeof error !== "object"
  ) {
    return String(
      error || "未知错误",
    )
  }

  const candidate = error as {
    message?: unknown
    body?: {
      detail?: unknown
    }
  }

  const detail =
    candidate.body?.detail

  if (
    typeof detail === "string" &&
    detail.trim()
  ) {
    return detail
  }

  if (
    detail &&
    typeof detail === "object"
  ) {
    const detailObject =
      detail as {
        code?: unknown
        message?: unknown
      }

    if (
      typeof detailObject.message === "string" &&
      detailObject.message.trim()
    ) {
      return detailObject.message
    }

    try {
      return JSON.stringify(
        detail,
        null,
        2,
      )
    } catch {
      return "请求失败"
    }
  }

  if (
    typeof candidate.message === "string" &&
    candidate.message.trim()
  ) {
    return candidate.message
  }

  try {
    return JSON.stringify(
      error,
      null,
      2,
    )
  } catch {
    return "请求失败"
  }
}