import type {
  CodeReviewRunDetailPublic,
  CodeSkillGenerateReviewReportResponse,
} from "@/client"

export const buildGeneratedReviewFromHistory = (
  detail: CodeReviewRunDetailPublic,
): CodeSkillGenerateReviewReportResponse => {
  return {
    generation_status:
      detail.generation_status,

    review_report:
      detail.review_report ?? null,

    review_markdown:
      detail.review_markdown ?? null,

    evidence:
      detail.evidence,

    generation_trace:
      detail.generation_trace,

    generation_error:
      detail.generation_error ?? null,

    review_run_id:
      detail.id,

    saved_at:
      detail.created_at,
  }
}

type ReadReviewNumberParameterOptions = {
  parameters: Record<string, unknown>
  key: string
  fallback: number
  min: number
  max: number
}

export const readReviewNumberParameter = ({
  parameters,
  key,
  fallback,
  min,
  max,
}: ReadReviewNumberParameterOptions) => {
  const parsedValue = Number(
    parameters[key],
  )

  if (!Number.isFinite(parsedValue)) {
    return fallback
  }

  return Math.min(
    max,
    Math.max(
      min,
      parsedValue,
    ),
  )
}