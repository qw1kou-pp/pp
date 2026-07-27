export function formatPercent(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "-"
  }

  return `${(value * 100).toFixed(1)}%`
}

export function formatLatency(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "-"
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}s`
  }

  return `${value.toFixed(0)}ms`
}

export function formatSignedLatency(value: number): string {
  if (!Number.isFinite(value)) {
    return "-"
  }

  if (value === 0) {
    return "0ms"
  }

  return `${value > 0 ? "+" : "-"}${formatLatency(Math.abs(value))}`
}

export function formatToolUsage(value?: string | null): string {
  if (!value) {
    return "-"
  }

  try {
    const parsed = JSON.parse(value) as Record<string, number>
    const entries = Object.entries(parsed)

    if (entries.length === 0) {
      return "-"
    }

    return entries
      .sort((left, right) => right[1] - left[1])
      .map(([toolName, count]) => `${toolName}×${count}`)
      .join("，")
  } catch {
    return value
  }
}

export function formatSignedNumber(value: number, suffix = ""): string {
  if (!Number.isFinite(value)) {
    return "-"
  }

  if (value > 0) {
    return `+${value.toFixed(2)}${suffix}`
  }

  if (value < 0) {
    return `${value.toFixed(2)}${suffix}`
  }

  return `0${suffix}`
}

export function formatSignedPercentPoint(value: number): string {
  if (!Number.isFinite(value)) {
    return "-"
  }

  if (value > 0) {
    return `+${(value * 100).toFixed(1)} 个百分点`
  }

  if (value < 0) {
    return `${(value * 100).toFixed(1)} 个百分点`
  }

  return "0 个百分点"
}

export function formatNullableNumber(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "-"
  }

  return value.toFixed(2)
}

export function formatReportDateTime(value?: string | null): string {
  if (!value) {
    return "-"
  }

  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? "-" : date.toLocaleString()
}

export function safeMarkdownText(value: unknown): string {
  if (value === null || value === undefined) {
    return "-"
  }

  return String(value)
    .replace(/\|/g, "\\|")
    .replace(/\n/g, " ")
    .trim()
}

export function formatFileSize(size: number): string {
  if (!Number.isFinite(size) || size < 0) {
    return "-"
  }

  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }

  if (size < 1024 * 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`
  }

  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`
}
