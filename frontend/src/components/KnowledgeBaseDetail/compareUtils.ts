export const readField = <T>(
  item: unknown,
  snakeName: string,
  camelName: string,
  fallback: T,
): T => {
  if (
    !item
    || typeof item !== "object"
  ) {
    return fallback
  }

  const record =
    item as Record<string, unknown>

  const value =
    record[snakeName]
    ?? record[camelName]

  if (
    value === null
    || value === undefined
  ) {
    return fallback
  }

  return value as T
}

export const readArrayField = <T>(
  item: unknown,
  snakeName: string,
  camelName: string,
  fallback: T[] = [],
): T[] => {
  const value = readField<unknown>(
    item,
    snakeName,
    camelName,
    fallback,
  )

  return Array.isArray(value)
    ? value as T[]
    : fallback
}

export const readNumberField = (
  item: unknown,
  snakeName: string,
  camelName: string,
  fallback: number | null = null,
): number | null => {
  const value = readField<unknown>(
    item,
    snakeName,
    camelName,
    fallback,
  )

  return typeof value === "number"
    && Number.isFinite(value)
    ? value
    : fallback
}

export const getToolName = (
  toolCall: unknown,
) =>
  readField<string>(
    toolCall,
    "tool_name",
    "toolName",
    "-",
  )

export const getToolSuccess = (
  toolCall: unknown,
) =>
  readField<boolean>(
    toolCall,
    "success",
    "success",
    false,
  )

export const getSummaryValue = <T>(
  summary: unknown,
  snakeName: string,
  camelName: string,
  fallback: T,
): T => {
  return readField<T>(
    summary,
    snakeName,
    camelName,
    fallback,
  )
}

export const downloadTextFile = ({
  filename,
  content,
  mimeType =
    "text/markdown;charset=utf-8",
}: {
  filename: string
  content: string
  mimeType?: string
}) => {
  const blob = new Blob(
    [content],
    { type: mimeType },
  )
  const url =
    URL.createObjectURL(blob)

  const link =
    document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()

  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export const downloadBase64File = ({
  filename,
  contentBase64,
  mimeType,
}: {
  filename: string
  contentBase64: string
  mimeType: string
}) => {
  const binaryString =
    window.atob(contentBase64)
  const bytes =
    new Uint8Array(
      binaryString.length,
    )

  for (
    let index = 0;
    index < binaryString.length;
    index += 1
  ) {
    bytes[index] =
      binaryString.charCodeAt(index)
  }

  const blob = new Blob(
    [bytes],
    { type: mimeType },
  )
  const url =
    URL.createObjectURL(blob)

  const link =
    document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()

  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
