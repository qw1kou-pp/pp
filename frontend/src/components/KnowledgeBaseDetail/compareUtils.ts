export const readField = <T>(
  item: any,
  snakeName: string,
  camelName: string,
  fallback: T,
): T => {
  const value = item?.[snakeName] ?? item?.[camelName]

  if (value === null || value === undefined) {
    return fallback
  }

  return value as T
}

export const readArrayField = <T>(
  item: any,
  snakeName: string,
  camelName: string,
): T[] => {
  const value = item?.[snakeName] ?? item?.[camelName]

  if (!Array.isArray(value)) {
    return []
  }

  return value as T[]
}

export const readNumberField = (
  item: any,
  snakeName: string,
  camelName: string,
): number | null => {
  const value = item?.[snakeName] ?? item?.[camelName]

  if (typeof value !== "number") {
    return null
  }

  return value
}

export const getToolName = (toolCall: any) =>
  readField<string>(toolCall, "tool_name", "toolName", "-")

export const getToolSuccess = (toolCall: any) =>
  readField<boolean>(toolCall, "success", "success", false)

export const getSummaryValue = <T>(
  summary: any,
  snakeName: string,
  camelName: string,
  fallback: T,
): T => {
  const value = summary?.[snakeName] ?? summary?.[camelName]

  if (value === null || value === undefined) {
    return fallback
  }

  return value as T
}

export const downloadTextFile = ({
  filename,
  content,
  mimeType = "text/markdown;charset=utf-8",
}: {
  filename: string
  content: string
  mimeType?: string
}) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)

  const link = document.createElement("a")
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
  const binaryString = window.atob(contentBase64)
  const bytes = new Uint8Array(binaryString.length)

  for (let index = 0; index < binaryString.length; index += 1) {
    bytes[index] = binaryString.charCodeAt(index)
  }

  const blob = new Blob([bytes], { type: mimeType })
  const url = URL.createObjectURL(blob)

  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()

  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}