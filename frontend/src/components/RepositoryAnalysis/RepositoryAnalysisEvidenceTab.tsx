import type {
  RepositoryAnalysisTaskPublic,
} from "@/client"

import {
  RepositoryAnalysisJsonView,
} from "./RepositoryAnalysisJsonView"

export function RepositoryAnalysisEvidenceTab({
  task,
}: {
  task: RepositoryAnalysisTaskPublic
}) {
  const items =
    extractEvidenceItems(
      task.evidence_json,
    )

  if (items.length === 0) {
    return (
      <RepositoryAnalysisJsonView
        value={
          task.evidence_json
        }
        emptyTitle="暂无 Evidence"
        emptyDescription={
          task.status === "completed"
            ? "任务已经完成，但没有返回 Evidence。"
            : "分析完成后，这里将展示证据 ID、文件路径和判断依据。"
        }
      />
    )
  }

  return (
    <div className="space-y-3">
      {items.map(
        (
          item,
          index,
        ) => (
          <EvidenceCard
            key={
              getStringField(
                item,
                "id",
              ) ||
              index
            }
            item={item}
            index={index}
          />
        ),
      )}
    </div>
  )
}

function EvidenceCard({
  item,
  index,
}: {
  item: Record<
    string,
    unknown
  >
  index: number
}) {
  const evidenceId =
    getStringField(
      item,
      "id",
    ) ||
    getStringField(
      item,
      "evidence_id",
    ) ||
    `Evidence ${index + 1}`

  const title =
    getStringField(
      item,
      "title",
    ) ||
    getStringField(
      item,
      "name",
    )

  const path =
    getStringField(
      item,
      "path",
    ) ||
    getStringField(
      item,
      "file_path",
    )

  const description =
    getStringField(
      item,
      "description",
    ) ||
    getStringField(
      item,
      "summary",
    ) ||
    getStringField(
      item,
      "reason",
    )

  return (
    <article className="rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs text-muted-foreground">
            {evidenceId}
          </p>

          {title && (
            <h3 className="mt-1 font-medium">
              {title}
            </h3>
          )}
        </div>
      </div>

      {path && (
        <p className="mt-3 break-all rounded bg-muted px-3 py-2 font-mono text-xs">
          {path}
        </p>
      )}

      {description && (
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6">
          {description}
        </p>
      )}

      <details className="mt-4">
        <summary className="cursor-pointer text-sm text-muted-foreground">
          查看完整 Evidence
        </summary>

        <pre className="mt-3 max-h-96 overflow-auto rounded-md bg-muted p-4 text-xs">
          {JSON.stringify(
            item,
            null,
            2,
          )}
        </pre>
      </details>
    </article>
  )
}

function extractEvidenceItems(
  value: unknown,
): Record<
  string,
  unknown
>[] {
  if (Array.isArray(value)) {
    return value.filter(
      isRecord,
    )
  }

  if (!isRecord(value)) {
    return []
  }

  for (const key of [
    "items",
    "evidence",
    "evidences",
    "data",
  ]) {
    const candidate =
      value[key]

    if (Array.isArray(candidate)) {
      return candidate.filter(
        isRecord,
      )
    }
  }

  return []
}

function getStringField(
  value: Record<
    string,
    unknown
  >,
  key: string,
): string | null {
  const candidate =
    value[key]

  return typeof candidate ===
    "string" &&
    candidate.trim()
    ? candidate
    : null
}

function isRecord(
  value: unknown,
): value is Record<
  string,
  unknown
> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  )
}