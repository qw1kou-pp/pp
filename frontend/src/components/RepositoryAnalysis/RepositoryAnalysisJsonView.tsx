type RepositoryAnalysisJsonViewProps = {
  value: unknown
  emptyTitle: string
  emptyDescription: string
}

export function RepositoryAnalysisJsonView({
  value,
  emptyTitle,
  emptyDescription,
}: RepositoryAnalysisJsonViewProps) {
  if (
    value === null ||
    value === undefined
  ) {
    return (
      <JsonEmptyState
        title={emptyTitle}
        description={
          emptyDescription
        }
      />
    )
  }

  if (isJsonObject(value)) {
    const entries =
      Object.entries(value)

    if (entries.length === 0) {
      return (
        <JsonEmptyState
          title={emptyTitle}
          description={
            emptyDescription
          }
        />
      )
    }

    return (
      <div className="space-y-4">
        {entries.map(
          ([key, item]) => (
            <section
              key={key}
              className="rounded-lg border p-4"
            >
              <h3 className="break-all font-medium">
                {formatJsonKey(
                  key,
                )}
              </h3>

              <div className="mt-3">
                <JsonValue
                  value={item}
                />
              </div>
            </section>
          ),
        )}
      </div>
    )
  }

  return (
    <JsonValue value={value} />
  )
}

function JsonValue({
  value,
}: {
  value: unknown
}) {
  if (
    typeof value === "string"
  ) {
    return (
      <p className="whitespace-pre-wrap break-words text-sm leading-6">
        {value}
      </p>
    )
  }

  if (
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return (
      <p className="font-mono text-sm">
        {String(value)}
      </p>
    )
  }

  if (
    value === null ||
    value === undefined
  ) {
    return (
      <span className="text-sm text-muted-foreground">
        —
      </span>
    )
  }

  return (
    <pre className="max-h-[32rem] overflow-auto rounded-md bg-muted p-4 text-xs leading-5">
      {safeStringify(value)}
    </pre>
  )
}

function JsonEmptyState({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center rounded-lg border border-dashed px-6 text-center">
      <h3 className="font-medium">
        {title}
      </h3>

      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        {description}
      </p>
    </div>
  )
}

function isJsonObject(
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

function safeStringify(
  value: unknown,
): string {
  try {
    return JSON.stringify(
      value,
      null,
      2,
    )
  } catch {
    return String(value)
  }
}

function formatJsonKey(
  value: string,
): string {
  return value
    .replace(
      /_/g,
      " ",
    )
    .replace(
      /\b\w/g,
      (letter) =>
        letter.toUpperCase(),
    )
}