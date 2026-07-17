import { useMutation } from "@tanstack/react-query"
import { useState, type ChangeEvent } from "react"

import {
  CodeSkillService,
  type CodeSkillChangedFilePublic,
  type CodeSkillChangedSymbolInput,
  type CodeSkillChangedSymbolPublic,
  type CodeSkillImpactedFilePublic,
  type CodeSkillImpactReferencePublic,
  type CodeSkillRecommendedTestPublic,
  type CodeSkillReviewChecklistItemPublic,
  type CodeSkillReviewEvidenceResponse,
  type CodeSkillRiskSignalPublic,
  type CodeSkillSymbolImpactPublic,
  type CodeSkillGenerateReviewReportResponse,
} from "@/client"

type CodeReviewWorkbenchProps = {
  knowledgeBaseId: string
}

type ReviewLanguage = "zh-CN" | "en-US"

const numberOrZero = (value?: number | null) => {
  return value ?? 0
}

const getRiskClassName = (riskLevel?: string) => {
  const normalizedLevel = String(riskLevel || "low").toLowerCase()

  if (normalizedLevel === "high") {
    return "border-red-500 bg-red-950/30 text-red-200"
  }

  if (normalizedLevel === "medium") {
    return "border-yellow-500 bg-yellow-950/30 text-yellow-100"
  }

  return "border-green-500 bg-green-950/30 text-green-100"
}

const getRiskLabel = (riskLevel?: string) => {
  const normalizedLevel = String(riskLevel || "low").toLowerCase()

  if (normalizedLevel === "high") {
    return "高风险"
  }

  if (normalizedLevel === "medium") {
    return "中风险"
  }

  return "低风险"
}

const getMergeRecommendationLabel = (
  recommendation?: string | null,
) => {
  const normalizedRecommendation = String(
    recommendation || "needs_review",
  ).toLowerCase()

  const labelMap: Record<string, string> = {
    approve: "可以合并",
    needs_review: "需要进一步审查",
    request_changes: "建议修改后再合并",
  }

  return (
    labelMap[normalizedRecommendation] ||
    normalizedRecommendation
  )
}

const getReviewPriorityLabel = (
  priority?: string | null,
) => {
  const normalizedPriority = String(
    priority || "medium",
  ).toLowerCase()

  const labelMap: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高",
  }

  return (
    labelMap[normalizedPriority] ||
    normalizedPriority
  )
}

const downloadReviewMarkdown = (
  markdown: string,
) => {
  const blob = new Blob(
    [markdown],
    {
      type: "text/markdown;charset=utf-8",
    },
  )

  const downloadUrl =
    window.URL.createObjectURL(blob)

  const downloadLink =
    window.document.createElement("a")

  downloadLink.href = downloadUrl
  downloadLink.download =
    "repoguard-review-report.md"

  downloadLink.click()

  window.URL.revokeObjectURL(
    downloadUrl,
  )
}

const formatReviewApiError = (error: unknown) => {
  if (!error || typeof error !== "object") {
    return String(error || "未知错误")
  }

  const candidate = error as {
    message?: string
    body?: {
      detail?: unknown
    }
  }

  if (candidate.body?.detail) {
    if (typeof candidate.body.detail === "string") {
      return candidate.body.detail
    }

    return JSON.stringify(candidate.body.detail, null, 2)
  }

  return candidate.message || JSON.stringify(error, null, 2)
}

type DownloadTextFileOptions = {
  content: string
  filename: string
  mimeType: string
}

const copyTextToClipboard = async (text: string) => {
  if (!text.trim()) {
    throw new Error("没有可复制的内容")
  }

  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
    return
  }

  const temporaryTextarea = document.createElement("textarea")

  temporaryTextarea.value = text
  temporaryTextarea.style.position = "fixed"
  temporaryTextarea.style.left = "-9999px"
  temporaryTextarea.style.top = "0"
  temporaryTextarea.setAttribute("readonly", "true")

  document.body.appendChild(temporaryTextarea)

  temporaryTextarea.focus()
  temporaryTextarea.select()

  const copiedSuccessfully = document.execCommand("copy")

  document.body.removeChild(temporaryTextarea)

  if (!copiedSuccessfully) {
    throw new Error("浏览器未允许复制，请检查剪贴板权限")
  }
}

const downloadTextFile = ({
  content,
  filename,
  mimeType,
}: DownloadTextFileOptions) => {
  if (!content.trim()) {
    throw new Error("没有可下载的内容")
  }

  const fileBlob = new Blob([content], {
    type: `${mimeType};charset=utf-8`,
  })

  const objectUrl = window.URL.createObjectURL(fileBlob)
  const downloadLink = document.createElement("a")

  downloadLink.href = objectUrl
  downloadLink.download = filename
  downloadLink.style.display = "none"

  document.body.appendChild(downloadLink)
  downloadLink.click()
  document.body.removeChild(downloadLink)

  window.URL.revokeObjectURL(objectUrl)
}

const sanitizeFilenamePart = (value: string) => {
  const sanitizedValue = value
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")

  return sanitizedValue || "unknown"
}

const buildEvidenceFileBaseName = (knowledgeBaseId: string) => {
  const safeKnowledgeBaseId = sanitizeFilenamePart(knowledgeBaseId)

  const timestamp = new Date()
    .toISOString()
    .replace(/[:.]/g, "-")

  return `repoguard-evidence-${safeKnowledgeBaseId}-${timestamp}`
}

const toMarkdownInline = (value: unknown) => {
  const normalizedValue = String(value ?? "")
    .replace(/\r?\n/g, " ")
    .replace(/`/g, "\\`")
    .trim()

  return normalizedValue || "-"
}

const buildReviewMarkdownContext = (
  reviewEvidence: CodeSkillReviewEvidenceResponse,
) => {
  const summary = reviewEvidence.change_summary

  const changedFiles = reviewEvidence.changed_files ?? []
  const changedSymbols = reviewEvidence.changed_symbols ?? []
  const impactedFiles = reviewEvidence.impacted_files_summary ?? []
  const recommendedTests = reviewEvidence.recommended_tests ?? []
  const riskSignals = reviewEvidence.risk_signals ?? []
  const reviewChecklist = reviewEvidence.review_checklist ?? []
  const evidenceTrace = reviewEvidence.evidence_trace ?? []
  const testGapNotes = reviewEvidence.test_gap_notes ?? []
  const limitations = reviewEvidence.limitations ?? []

  const markdownLines: string[] = [
    "# RepoGuard Review Evidence",
    "",
    "> 本文档由 RepoGuard 的确定性代码分析结果生成。",
    "> 其中的影响关系和风险信号用于辅助 Review，不等同于已确认的 Bug。",
    "",
    "## 1. Change Summary",
    "",
    `- Changed files: ${numberOrZero(summary.total_changed_files)}`,
    `- Added lines: ${numberOrZero(summary.total_added_lines)}`,
    `- Deleted lines: ${numberOrZero(summary.total_deleted_lines)}`,
    `- Changed symbols: ${numberOrZero(summary.total_changed_symbols)}`,
    `- References: ${numberOrZero(summary.total_references)}`,
    `- Impacted files: ${numberOrZero(summary.total_impacted_files)}`,
    `- Recommended tests: ${numberOrZero(
      summary.total_recommended_tests,
    )}`,
`- Risk signals: ${numberOrZero(summary.total_risk_signals)}`,
    `- Overall risk level: ${toMarkdownInline(summary.risk_level)}`,
    "",
    "## 2. Changed Files",
    "",
  ]

  if (changedFiles.length === 0) {
    markdownLines.push("- No changed files were parsed.")
  } else {
    changedFiles.forEach((changedFile, index) => {
      markdownLines.push(
        `${index + 1}. \`${toMarkdownInline(changedFile.file_path)}\``,
        `   - Change type: ${toMarkdownInline(changedFile.change_type)}`,
        `   - Added lines: ${changedFile.added_lines}`,
        `   - Deleted lines: ${changedFile.deleted_lines}`,
      )
    })
  }

  markdownLines.push("", "## 3. Changed Symbols", "")

  if (changedSymbols.length === 0) {
    markdownLines.push("- No changed symbols were located.")
  } else {
    changedSymbols.forEach((symbol, index) => {
      markdownLines.push(
        `${index + 1}. \`${toMarkdownInline(symbol.symbol_name)}\``,
        `   - File: \`${toMarkdownInline(symbol.file_path)}\``,
        `   - Type: ${toMarkdownInline(symbol.symbol_type)}`,
        `   - Line range: ${toMarkdownInline(symbol.line_range)}`,
        `   - Confidence: ${formatConfidence(symbol.confidence)}`,
        `   - Reason: ${toMarkdownInline(symbol.reason)}`,
      )
    })
  }

  markdownLines.push("", "## 4. Impacted Files", "")

  if (impactedFiles.length === 0) {
    markdownLines.push("- No explicit impacted files were found.")
  } else {
    impactedFiles.forEach((impactedFile, index) => {
      const impactedSymbolNames =
        impactedFile.impacted_symbol_names ?? []

      markdownLines.push(
        `${index + 1}. \`${toMarkdownInline(impactedFile.file_path)}\``,
        `   - Reference count: ${impactedFile.reference_count}`,
        `   - Confidence: ${formatConfidence(impactedFile.confidence)}`,
        `   - Related symbols: ${
          impactedSymbolNames.length > 0
            ? impactedSymbolNames
                .map((symbolName) => `\`${toMarkdownInline(symbolName)}\``)
                .join(", ")
            : "-"
        }`,
        `   - Reason: ${toMarkdownInline(impactedFile.reason)}`,
      )
    })
  }

  markdownLines.push("", "## 5. Recommended Tests", "")

  if (recommendedTests.length === 0) {
    markdownLines.push("- No related tests were recommended.")
  } else {
    recommendedTests.forEach((recommendedTest, index) => {
      const relatedSymbols =
        recommendedTest.related_symbols ?? []

      markdownLines.push(
        `${index + 1}. \`${toMarkdownInline(
          recommendedTest.test_file_path,
        )}\``,
        `   - Confidence: ${formatConfidence(
          recommendedTest.confidence,
        )}`,
        `   - Path match score: ${formatConfidence(
          recommendedTest.path_match_score,
        )}`,
        `   - Symbol matches: ${recommendedTest.symbol_match_count}`,
        `   - Related symbols: ${
          relatedSymbols.length > 0
            ? relatedSymbols
                .map((symbolName) => `\`${toMarkdownInline(symbolName)}\``)
                .join(", ")
            : "-"
        }`,
      )
    })
  }

  markdownLines.push("", "## 6. Test Gaps", "")

  if (testGapNotes.length === 0) {
    markdownLines.push("- No explicit test gap notes.")
  } else {
    testGapNotes.forEach((note) => {
      markdownLines.push(`- ${toMarkdownInline(note)}`)
    })
  }

  markdownLines.push("", "## 7. Risk Signals", "")

  if (riskSignals.length === 0) {
    markdownLines.push("- No deterministic risk signals were generated.")
  } else {
    riskSignals.forEach((riskSignal, index) => {
      markdownLines.push(
        `${index + 1}. **${toMarkdownInline(riskSignal.title)}**`,
        `   - Type: ${toMarkdownInline(riskSignal.risk_type)}`,
        `   - Level: ${toMarkdownInline(riskSignal.risk_level)}`,
        `   - Message: ${toMarkdownInline(riskSignal.message)}`,
      )

      const evidenceItems = riskSignal.evidence ?? []

      if (evidenceItems.length > 0) {
        markdownLines.push(
          `   - Evidence: ${evidenceItems
            .map((evidence) => toMarkdownInline(evidence))
            .join("; ")}`,
        )
      }
    })
  }

  markdownLines.push("", "## 8. Review Checklist", "")

  if (reviewChecklist.length === 0) {
    markdownLines.push("- No review checklist items were generated.")
  } else {
    reviewChecklist.forEach((checklistItem) => {
      markdownLines.push(
        `- [ ] **${toMarkdownInline(checklistItem.description)}**`,
        `  - Priority: ${toMarkdownInline(checklistItem.priority)}`,
        `  - Category: ${toMarkdownInline(checklistItem.category)}`,
        `  - Reason: ${toMarkdownInline(checklistItem.reason)}`,
      )
    })
  }

  markdownLines.push("", "## 9. Evidence Trace", "")

  if (evidenceTrace.length === 0) {
    markdownLines.push("- No pipeline trace was returned.")
  } else {
    evidenceTrace.forEach((traceStep, index) => {
      markdownLines.push(
        `${index + 1}. **${toMarkdownInline(traceStep.step)}**`,
        `   - Status: ${toMarkdownInline(traceStep.status)}`,
        `   - Duration: ${traceStep.duration_ms} ms`,
        `   - Summary: ${toMarkdownInline(traceStep.summary)}`,
      )
    })
  }

  markdownLines.push("", "## 10. Limitations", "")

  if (limitations.length === 0) {
    markdownLines.push("- No limitations were returned.")
  } else {
    limitations.forEach((limitation) => {
      markdownLines.push(`- ${toMarkdownInline(limitation)}`)
    })
  }

  return markdownLines.join("\n")
}

const getTraceStatusClassName = (status?: string | null) => {
  const normalizedStatus = String(status || "unknown").toLowerCase()

  if (normalizedStatus === "success") {
    return "border-green-500 bg-green-950/20 text-green-200"
  }

  if (normalizedStatus === "failed" || normalizedStatus === "error") {
    return "border-red-500 bg-red-950/20 text-red-200"
  }

  return "border-yellow-500 bg-yellow-950/20 text-yellow-200"
}

const normalizeCodeFilePath = (filePath?: string | null) => {
  return String(filePath || "")
    .replace(/\\/g, "/")
    .replace(/^\.?\//, "")
    .trim()
}

const codeFilePathsMatch = (
  firstPath?: string | null,
  secondPath?: string | null,
) => {
  const normalizedFirstPath = normalizeCodeFilePath(firstPath)
  const normalizedSecondPath = normalizeCodeFilePath(secondPath)

  if (!normalizedFirstPath || !normalizedSecondPath) {
    return false
  }

  if (normalizedFirstPath === normalizedSecondPath) {
    return true
  }

  return (
    normalizedFirstPath.endsWith(`/${normalizedSecondPath}`) ||
    normalizedSecondPath.endsWith(`/${normalizedFirstPath}`)
  )
}

const getChangeTypeLabel = (changeType?: string | null) => {
  const normalizedType = String(changeType || "modified").toLowerCase()

  const labelMap: Record<string, string> = {
    added: "新增文件",
    deleted: "删除文件",
    modified: "修改文件",
    renamed: "重命名文件",
  }

  return labelMap[normalizedType] || normalizedType
}

const getChangeTypeClassName = (changeType?: string | null) => {
  const normalizedType = String(changeType || "modified").toLowerCase()

  const classMap: Record<string, string> = {
    added: "border-green-500 bg-green-950/30 text-green-200",
    deleted: "border-red-500 bg-red-950/30 text-red-200",
    modified: "border-blue-500 bg-blue-950/30 text-blue-200",
    renamed: "border-purple-500 bg-purple-950/30 text-purple-200",
  }

  return (
    classMap[normalizedType] ||
    "border-gray-500 bg-gray-900 text-gray-200"
  )
}

const getSymbolTypeLabel = (symbolType?: string | null) => {
  const normalizedType = String(symbolType || "unknown").toLowerCase()

  const labelMap: Record<string, string> = {
    function: "函数",
    class: "类",
    method: "方法",
    variable: "变量",
    interface: "接口",
    module: "模块",
    file: "文件级定位",
    unknown: "未知符号",
  }

  return labelMap[normalizedType] || normalizedType
}

const formatConfidence = (confidence?: number | null) => {
  const normalizedConfidence = Math.max(
    0,
    Math.min(1, Number(confidence || 0)),
  )

  return `${(normalizedConfidence * 100).toFixed(0)}%`
}

const getConfidenceClassName = (confidence?: number | null) => {
  const normalizedConfidence = Number(confidence || 0)

  if (normalizedConfidence >= 0.8) {
    return "border-green-500 text-green-300"
  }

  if (normalizedConfidence >= 0.5) {
    return "border-yellow-500 text-yellow-200"
  }

  return "border-red-500 text-red-300"
}

const getChangedSymbolsForFile = ({
  changedFile,
  changedSymbols,
}: {
  changedFile: CodeSkillChangedFilePublic
  changedSymbols: CodeSkillChangedSymbolPublic[]
}) => {
  return changedSymbols.filter((symbol) =>
    codeFilePathsMatch(symbol.file_path, changedFile.file_path),
  )
}

const getChangedSymbolIdentity = (
  symbol?: CodeSkillChangedSymbolInput | null,
) => {
  if (!symbol) {
    return "unknown-symbol"
  }

  return [
    normalizeCodeFilePath(symbol.file_path),
    String(symbol.symbol_name || ""),
    String(symbol.symbol_type || ""),
    String(symbol.line_range || ""),
  ].join("::")
}

const getImpactReferenceTitle = (
  reference: CodeSkillImpactReferencePublic,
) => {
  if (reference.containing_symbol_name) {
    return reference.containing_symbol_name
  }

  return reference.file_path || reference.document_filename
}

const formatContainingSymbol = (
  reference: CodeSkillImpactReferencePublic,
) => {
  const symbolName = reference.containing_symbol_name
  const symbolType = reference.containing_symbol_type
  const lineRange = reference.containing_line_range

  if (!symbolName) {
    return "未定位到引用所在符号"
  }

  const resultParts = [getSymbolTypeLabel(symbolType), symbolName]

  if (lineRange) {
    resultParts.push(lineRange)
  }

  return resultParts.join(" · ")
}

const sortImpactReferences = (
  references: CodeSkillImpactReferencePublic[],
) => {
  return [...references].sort((firstReference, secondReference) => {
    const confidenceDifference =
      Number(secondReference.confidence || 0) -
      Number(firstReference.confidence || 0)

    if (confidenceDifference !== 0) {
      return confidenceDifference
    }

    return (
      Number(secondReference.occurrence_count || 0) -
      Number(firstReference.occurrence_count || 0)
    )
  })
}

const sortImpactedFiles = (
  impactedFiles: CodeSkillImpactedFilePublic[],
) => {
  return [...impactedFiles].sort((firstFile, secondFile) => {
    const referenceCountDifference =
      Number(secondFile.reference_count || 0) -
      Number(firstFile.reference_count || 0)

    if (referenceCountDifference !== 0) {
      return referenceCountDifference
    }

    return (
      Number(secondFile.confidence || 0) -
      Number(firstFile.confidence || 0)
    )
  })
}

const sortRecommendedTests = (
  recommendedTests: CodeSkillRecommendedTestPublic[],
) => {
  return [...recommendedTests].sort((firstTest, secondTest) => {
    const confidenceDifference =
      Number(secondTest.confidence || 0) -
      Number(firstTest.confidence || 0)

    if (confidenceDifference !== 0) {
      return confidenceDifference
    }

    return (
      Number(secondTest.symbol_match_count || 0) -
      Number(firstTest.symbol_match_count || 0)
    )
  })
}

const getPriorityLabel = (priority?: string | null) => {
  const normalizedPriority = String(priority || "medium").toLowerCase()

  if (normalizedPriority === "high") {
    return "高优先级"
  }

  if (normalizedPriority === "low") {
    return "低优先级"
  }

  return "中优先级"
}

const getPriorityClassName = (priority?: string | null) => {
  const normalizedPriority = String(priority || "medium").toLowerCase()

  if (normalizedPriority === "high") {
    return "border-red-500 bg-red-950/30 text-red-200"
  }

  if (normalizedPriority === "low") {
    return "border-green-500 bg-green-950/30 text-green-200"
  }

  return "border-yellow-500 bg-yellow-950/30 text-yellow-100"
}

export function CodeReviewWorkbench({
  knowledgeBaseId,
}: CodeReviewWorkbenchProps) {
  const [diffText, setDiffText] = useState("")
  const [maxReferencesPerSymbol, setMaxReferencesPerSymbol] = useState(20)
  const [maxTestFiles, setMaxTestFiles] = useState(20)
  const [minTestConfidence, setMinTestConfidence] = useState(0.2)
  const [reviewEvidence, setReviewEvidence] =
    useState<CodeSkillReviewEvidenceResponse | null>(null)

  const [generatedReview, setGeneratedReview] =
  useState<CodeSkillGenerateReviewReportResponse | null>(
    null,
  )

const [reviewLanguage, setReviewLanguage] =
  useState<ReviewLanguage>("zh-CN")

  const buildReviewEvidenceMutation = useMutation({
    mutationFn: () =>
      CodeSkillService.buildCodeSkillReviewEvidence({
        knowledgeBaseId,
        requestBody: {
          diff_text: diffText,
          max_references_per_symbol: maxReferencesPerSymbol,
          max_test_files: maxTestFiles,
          min_test_confidence: minTestConfidence,
          include_file_level_fallback: true,
          include_definition_chunk: false,
        },
      }),
    onSuccess: (data) => {
      setReviewEvidence(data)
    },
  })

  const generateReviewReportMutation = useMutation({
    mutationFn: () =>
      CodeSkillService.generateCodeSkillReviewReport({
        knowledgeBaseId,
        requestBody: {
          diff_text: diffText,
          max_references_per_symbol:
            maxReferencesPerSymbol,
          max_test_files: maxTestFiles,
          min_test_confidence:
            minTestConfidence,
          include_file_level_fallback: true,
          include_definition_chunk: false,
          language: reviewLanguage,
        },
      }),

    onSuccess: (data) => {
      setGeneratedReview(data)

      /*
       * generate-review-report 会返回完整 Evidence。
       * 因此生成报告成功或 evidence_only 时，
       * 都同步刷新原来的 Evidence 展示区。
       */
      setReviewEvidence(data.evidence)
    },
  })

  const isReviewBusy =
    buildReviewEvidenceMutation.isPending ||
    generateReviewReportMutation.isPending

  const handleDiffFileChange = async (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const selectedFile = event.target.files?.[0]

    if (!selectedFile) {
      return
    }

    const filename = selectedFile.name.toLowerCase()

    if (
      !filename.endsWith(".diff") &&
      !filename.endsWith(".patch") &&
      !filename.endsWith(".txt")
    ) {
      alert("请选择 .diff、.patch 或 .txt 文件")
      event.target.value = ""
      return
    }

    try {
      const content = await selectedFile.text()

      if (!content.trim()) {
        alert("选择的 diff 文件内容为空")
        return
      }

      setDiffText(content)
      setReviewEvidence(null)
      setGeneratedReview(null)

      buildReviewEvidenceMutation.reset()
      generateReviewReportMutation.reset()
      buildReviewEvidenceMutation.reset()
    } catch (error) {
      alert(`读取 diff 文件失败：${String(error)}`)
    } finally {
      event.target.value = ""
    }
  }

  const handleAnalyzeChange = () => {
    if (!diffText.trim()) {
      alert(
        "请先粘贴 git diff，或者上传 .diff / .patch 文件",
      )
      return
    }

    setReviewEvidence(null)
    setGeneratedReview(null)

    generateReviewReportMutation.reset()
    buildReviewEvidenceMutation.mutate()
  }

  const handleGenerateReviewReport = () => {
    if (!diffText.trim()) {
      alert(
        "请先粘贴 git diff，或者上传 .diff / .patch 文件",
      )
      return
    }

    setReviewEvidence(null)
    setGeneratedReview(null)

    buildReviewEvidenceMutation.reset()
    generateReviewReportMutation.mutate()
  }

  const changeSummary = reviewEvidence?.change_summary
  const changedFiles = reviewEvidence?.changed_files ?? []
  const changedSymbols = reviewEvidence?.changed_symbols ?? []
  const unresolvedFiles = reviewEvidence?.unresolved_files ?? []
  const symbolImpacts = reviewEvidence?.symbol_impacts ?? []
  const impactedFilesSummary =
    reviewEvidence?.impacted_files_summary ?? []
  const recommendedTests = reviewEvidence?.recommended_tests ?? []
  const testGapNotes = reviewEvidence?.test_gap_notes ?? []
  const uncoveredChangedFiles =
    reviewEvidence?.uncovered_changed_files ?? []
  const uncoveredSymbols = reviewEvidence?.uncovered_symbols ?? []
  const riskSignals = reviewEvidence?.risk_signals ?? []
  const reviewChecklist = reviewEvidence?.review_checklist ?? []

  const totalImpactReferences =
    changeSummary?.total_references ?? 0
  const totalImpactedFiles =
    changeSummary?.total_impacted_files ?? 0
  const impactedChangedSymbolCount = symbolImpacts.filter(
    (symbolImpact) =>
      Number(symbolImpact.total_references || 0) > 0,
  ).length

  return (
    <div className="border rounded p-4 space-y-5">
      <div>
        <h2 className="text-lg font-semibold">RepoGuard 变更审查工作台</h2>
        <p className="text-sm text-gray-500 mt-1">
          输入 git diff，系统将自动定位变更文件和符号、分析影响范围、
          推荐测试，并生成结构化 Review Evidence。
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="font-medium">Git Diff</label>
          <label className="border rounded px-3 py-1.5 text-sm cursor-pointer">
            上传 .diff / .patch
            <input
              type="file"
              className="hidden"
              accept=".diff,.patch,.txt,text/plain"
              onChange={handleDiffFileChange}
            />
          </label>
        </div>

        <textarea
          className="w-full min-h-[280px] border rounded p-3 bg-neutral-950 text-gray-100 font-mono text-xs"
          value={diffText}
          disabled={isReviewBusy}
          onChange={(event) => {
            setDiffText(event.target.value)
            setReviewEvidence(null)
            setGeneratedReview(null)
          }}
          placeholder={`diff --git a/backend/app/main.py b/backend/app/main.py
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -10,3 +10,4 @@
-old_line
+new_line`}
        />

        <div className="text-xs text-gray-500">
          当前 diff 长度：{diffText.length} 个字符
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <NumberField
          label="每个符号最大引用数"
          min={1}
          max={100}
          step={1}
          value={maxReferencesPerSymbol}
          onChange={setMaxReferencesPerSymbol}
        />

        <NumberField
          label="最大推荐测试数"
          min={1}
          max={100}
          step={1}
          value={maxTestFiles}
          onChange={setMaxTestFiles}
        />

        <NumberField
          label="测试最低置信度"
          min={0}
          max={1}
          step={0.05}
          value={minTestConfidence}
          onChange={setMinTestConfidence}
        />
        <label className="text-sm space-y-1">
          <span className="block text-gray-500">
            Review 报告语言
          </span>

          <select
            className="w-full border rounded px-3 py-2 bg-white text-gray-900"
            value={reviewLanguage}
            disabled={isReviewBusy}
            onChange={(event) => {
              setReviewLanguage(
                event.target.value as ReviewLanguage,
              )

              setGeneratedReview(null)
            }}
          >
            <option value="zh-CN">中文</option>
            <option value="en-US">English</option>
          </select>
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="border rounded px-4 py-2 font-medium disabled:opacity-50"
          disabled={
            isReviewBusy ||
            !diffText.trim()
          }
          onClick={handleAnalyzeChange}
        >
          {buildReviewEvidenceMutation.isPending
            ? "正在分析 Evidence..."
            : "分析 Review Evidence"}
        </button>

        <button
          type="button"
          className="border border-blue-500 bg-blue-950/30 text-blue-100 rounded px-4 py-2 font-medium disabled:opacity-50"
          disabled={
            isReviewBusy ||
            !diffText.trim()
          }
          onClick={handleGenerateReviewReport}
        >
          {generateReviewReportMutation.isPending
            ? "正在生成 AI Review..."
            : "生成 AI Review"}
        </button>

        <button
          type="button"
          className="border rounded px-4 py-2"
          disabled={
            isReviewBusy ||
            (!diffText &&
              !reviewEvidence &&
              !generatedReview)
          }
          onClick={() => {
            setDiffText("")
            setReviewEvidence(null)
            setGeneratedReview(null)

            buildReviewEvidenceMutation.reset()
            generateReviewReportMutation.reset()
          }}
        >
          清空
        </button>
      </div>
      {buildReviewEvidenceMutation.isError ? (
        <div className="border border-red-500 bg-red-950/30 rounded p-3">
          <div className="font-medium text-red-300">变更分析失败</div>
          <pre className="text-xs text-red-200 whitespace-pre-wrap mt-2">
            {formatReviewApiError(buildReviewEvidenceMutation.error)}
          </pre>
        </div>
      ) : null}

      {generateReviewReportMutation.isError ? (
        <div className="border border-red-500 bg-red-950/30 rounded p-3">
          <div className="font-medium text-red-300">
            AI Review 请求失败
          </div>

          <pre className="text-xs text-red-200 whitespace-pre-wrap mt-2">
            {formatReviewApiError(
              generateReviewReportMutation.error,
            )}
          </pre>
        </div>
      ) : null}

      {reviewEvidence && changeSummary ? (
        <>
          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-medium">变更摘要</h3>
              <span
                className={`border rounded px-3 py-1 text-sm ${getRiskClassName(
                  changeSummary.risk_level,
                )}`}
              >
                {getRiskLabel(changeSummary.risk_level)}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
              <SummaryCard
                label="变更文件"
                value={changeSummary.total_changed_files}
              />
              <SummaryCard
                label="新增行数"
                value={`+${changeSummary.total_added_lines ?? 0}`}
              />
              <SummaryCard
                label="删除行数"
                value={`-${changeSummary.total_deleted_lines ?? 0}`}
              />
              <SummaryCard
                label="变更符号"
                value={changeSummary.total_changed_symbols}
              />
              <SummaryCard
                label="影响文件"
                value={changeSummary.total_impacted_files}
              />
              <SummaryCard
                label="推荐测试"
                value={changeSummary.total_recommended_tests}
              />
              <SummaryCard
                label="风险信号"
                value={changeSummary.total_risk_signals}
              />
            </div>
          </section>

          {generatedReview ? (
            <GeneratedReviewPanel
              result={generatedReview}
            />
          ) : null}

          <section className="border rounded p-4 space-y-4">
            <div>
              <h3 className="font-medium">变更文件与符号定位</h3>
              <p className="text-sm text-gray-500 mt-1">
                根据 git diff 的文件路径和行号，将本次改动映射到知识库中的函数、
                类、方法或文件级代码范围。
              </p>
            </div>

            {changedFiles.length === 0 ? (
              <EmptyNotice>
                当前没有解析出变更文件。请检查输入内容是否为标准 git diff。
              </EmptyNotice>
            ) : (
              <div className="space-y-3">
                {changedFiles.map((changedFile, fileIndex) => {
                  const fileSymbols = getChangedSymbolsForFile({
                    changedFile,
                    changedSymbols,
                  })
                  const hunks = changedFile.hunks ?? []

                  return (
                    <details
                      key={`${changedFile.file_path}-${fileIndex}`}
                      className="border rounded overflow-hidden"
                      open={fileIndex === 0}
                    >
                      <summary className="cursor-pointer p-3 bg-neutral-900">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="font-mono text-sm break-all text-gray-100">
                              {changedFile.file_path}
                            </div>

                            {changedFile.old_path !== changedFile.new_path ? (
                              <div className="text-xs text-gray-500 mt-1 break-all">
                                {changedFile.old_path || "/dev/null"}
                                {" → "}
                                {changedFile.new_path || "/dev/null"}
                              </div>
                            ) : null}
                          </div>

                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <span
                              className={`border rounded px-2 py-1 ${getChangeTypeClassName(
                                changedFile.change_type,
                              )}`}
                            >
                              {getChangeTypeLabel(changedFile.change_type)}
                            </span>
                            <span className="border border-green-600 rounded px-2 py-1 text-green-300">
                              +{changedFile.added_lines}
                            </span>
                            <span className="border border-red-600 rounded px-2 py-1 text-red-300">
                              -{changedFile.deleted_lines}
                            </span>
                            <span className="border border-gray-600 rounded px-2 py-1 text-gray-300">
                              {fileSymbols.length} 个符号
                            </span>
                          </div>
                        </div>
                      </summary>

                      <div className="p-3 space-y-4">
                        <div className="space-y-2">
                          <div className="text-sm font-medium">Diff Hunk</div>

                          {hunks.length === 0 ? (
                            <div className="text-sm text-gray-500">
                              当前文件没有解析到 hunk 行号信息。
                            </div>
                          ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                              {hunks.map((hunk, hunkIndex) => (
                                <div
                                  key={`${changedFile.file_path}-hunk-${hunkIndex}`}
                                  className="border rounded p-3 text-sm space-y-1"
                                >
                                  <div className="font-mono text-xs">
                                    旧文件：{hunk.old_start}-
                                    {hunk.old_start +
                                      Math.max(hunk.old_count - 1, 0)}
                                  </div>
                                  <div className="font-mono text-xs">
                                    新文件：{hunk.new_start}-
                                    {hunk.new_start +
                                      Math.max(hunk.new_count - 1, 0)}
                                  </div>
                                  <div className="flex gap-3 text-xs">
                                    <span className="text-green-300">
                                      +{hunk.added_lines}
                                    </span>
                                    <span className="text-red-300">
                                      -{hunk.deleted_lines}
                                    </span>
                                    <span className="text-gray-400">
                                      上下文 {hunk.context_lines}
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          <div className="text-sm font-medium">变更符号</div>

                          {fileSymbols.length === 0 ? (
                            <EmptyNotice>
                              当前文件没有定位到明确的函数、类或方法。可能原因是
                              diff 行号与代码索引 line_range 不一致，或者该文件没有按
                              代码符号粒度生成 chunk。
                            </EmptyNotice>
                          ) : (
                            <div className="space-y-2">
                              {fileSymbols.map((symbol, symbolIndex) => (
                                <ChangedSymbolCard
                                  key={`${symbol.chunk_id || symbol.symbol_name}-${symbolIndex}`}
                                  symbol={symbol}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </details>
                  )
                })}
              </div>
            )}

            {unresolvedFiles.length > 0 ? (
              <div className="border border-red-500 bg-red-950/20 rounded p-3 space-y-2">
                <div className="font-medium text-red-200">
                  无法在知识库中定位的文件
                </div>
                <div className="text-xs text-gray-400">
                  这些文件出现在 diff 中，但没有匹配到当前知识库中的 Document。
                </div>
                <div className="space-y-1">
                  {unresolvedFiles.map((filePath) => (
                    <div
                      key={filePath}
                      className="font-mono text-xs text-red-100 break-all"
                    >
                      {filePath}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </section>

          <section className="border rounded p-4 space-y-5">
            <div>
              <h3 className="font-medium">影响范围证据链</h3>
              <p className="text-sm text-gray-500 mt-1">
                根据变更符号在知识库代码块中的引用情况，展示可能受影响的
                调用位置、所在函数和相关文件。该结果属于静态匹配证据，
                不等同于完整编译器调用图。
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <SummaryCard label="分析符号" value={symbolImpacts.length} />
              <SummaryCard
                label="引用证据"
                value={totalImpactReferences}
              />
              <SummaryCard
                label="受影响文件"
                value={totalImpactedFiles}
              />
              <SummaryCard
                label="产生影响的符号"
                value={impactedChangedSymbolCount}
              />
            </div>

            {symbolImpacts.length === 0 ? (
              <EmptyNotice>
                当前没有生成符号影响分析结果。可能原因是没有定位到明确的
                变更符号，或者变更符号名称不适合进行引用搜索。
              </EmptyNotice>
            ) : (
              <>
                {impactedChangedSymbolCount === 0 ? (
                  <EmptyNotice>
                    已定位变更符号，但未找到外部引用。这些符号可能没有被其他
                    代码直接引用，也可能通过动态调用、反射、依赖注入或字符串方式使用。
                  </EmptyNotice>
                ) : null}

                <div className="space-y-3">
                  {symbolImpacts.map((symbolImpact, impactIndex) => (
                    <SymbolImpactPanel
                      key={`${getChangedSymbolIdentity(
                        symbolImpact.changed_symbol,
                      )}-${impactIndex}`}
                      symbolImpact={symbolImpact}
                      defaultOpen={impactIndex === 0}
                    />
                  ))}
                </div>
              </>
            )}

            <div className="space-y-3">
              <div>
                <h4 className="font-medium">受影响文件总览</h4>
                <p className="text-xs text-gray-500 mt-1">
                  将所有变更符号的引用结果按文件合并，引用数量较多的文件优先展示。
                </p>
              </div>

              {impactedFilesSummary.length === 0 ? (
                <div className="border rounded p-3 text-sm text-gray-500">
                  当前未发现明确的受影响文件。这不代表变更完全没有影响。
                  动态调用、反射、依赖注入和字符串路由可能无法通过文本匹配发现。
                </div>
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                  {sortImpactedFiles(impactedFilesSummary).map(
                    (impactedFile, impactedFileIndex) => (
                      <ImpactedFileCard
                        key={`${impactedFile.file_path}-${impactedFileIndex}`}
                        impactedFile={impactedFile}
                      />
                    ),
                  )}
                </div>
              )}
            </div>
          </section>

          <section className="border rounded p-4 space-y-5">
            <div>
              <h3 className="font-medium">推荐测试与测试缺口</h3>
              <p className="text-sm text-gray-500 mt-1">
                根据变更文件路径、受影响文件和符号匹配结果，推荐优先运行的
                测试文件。该推荐不等同于真实覆盖率证明。
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <SummaryCard
                label="测试候选"
                value={changeSummary.total_test_candidates}
              />
              <SummaryCard
                label="推荐测试"
                value={recommendedTests.length}
              />
              <SummaryCard
                label="未覆盖文件"
                value={uncoveredChangedFiles.length}
              />
              <SummaryCard
                label="未覆盖符号"
                value={uncoveredSymbols.length}
              />
            </div>

            {recommendedTests.length === 0 ? (
              <EmptyNotice>
                当前没有找到满足置信度阈值的测试文件。请人工确认测试范围，
                并检查知识库中是否包含测试目录。
              </EmptyNotice>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                {sortRecommendedTests(recommendedTests).map(
                  (recommendedTest, testIndex) => (
                    <RecommendedTestCard
                      key={`${recommendedTest.test_file_path}-${testIndex}`}
                      recommendedTest={recommendedTest}
                    />
                  ),
                )}
              </div>
            )}

            {testGapNotes.length > 0 ? (
              <div className="border border-yellow-500 bg-yellow-950/20 rounded p-3 space-y-2">
                <div className="font-medium text-yellow-100">测试缺口提示</div>
                <ul className="list-disc pl-5 space-y-1 text-sm text-yellow-50">
                  {testGapNotes.map((note, noteIndex) => (
                    <li key={`${note}-${noteIndex}`}>{note}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>

          <section className="border rounded p-4 space-y-5">
            <div>
              <h3 className="font-medium">风险信号</h3>
              <p className="text-sm text-gray-500 mt-1">
                风险信号由确定性规则根据变更规模、影响范围、敏感路径和测试证据生成，
                表示需要重点复核的区域，不代表已经确认存在缺陷。
              </p>
            </div>

            {riskSignals.length === 0 ? (
              <div className="border border-green-500 bg-green-950/20 rounded p-3 text-sm text-green-100">
                当前规则没有识别到额外风险信号。仍需结合业务语义和测试结果进行人工审查。
              </div>
            ) : (
              <div className="space-y-3">
                {riskSignals.map((riskSignal, riskIndex) => (
                  <RiskSignalCard
                    key={`${riskSignal.risk_type}-${riskIndex}`}
                    riskSignal={riskSignal}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="border rounded p-4 space-y-5">
            <div>
              <h3 className="font-medium">Review Checklist</h3>
              <p className="text-sm text-gray-500 mt-1">
                根据当前证据自动生成的人工审查事项。此阶段先作为只读清单展示，
                后续再增加完成状态、备注和误报反馈。
              </p>
            </div>

            {reviewChecklist.length === 0 ? (
              <EmptyNotice>当前没有生成 Review Checklist。</EmptyNotice>
            ) : (
              <div className="space-y-3">
                {reviewChecklist.map((checklistItem, checklistIndex) => (
                  <ReviewChecklistItemCard
                    key={`${checklistItem.item_id}-${checklistIndex}`}
                    checklistItem={checklistItem}
                  />
                ))}
              </div>
            )}
          </section>
          <EvidenceOperationsPanel
            reviewEvidence={reviewEvidence}
            knowledgeBaseId={knowledgeBaseId}
          />
        </>
      ) : (
        <div className="text-sm text-gray-500">
          当前还没有分析结果。粘贴或上传 git diff 后，点击“分析本次变更”。
        </div>
      )}
    </div>
  )
}

function NumberField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (value: number) => void
}) {
  return (
    <label className="text-sm space-y-1">
      <span className="block text-gray-500">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        className="w-full border rounded px-3 py-2 bg-white text-gray-900"
        value={value}
        onChange={(event) => {
          const parsedValue = Number(event.target.value)
          const safeValue = Number.isFinite(parsedValue)
            ? Math.max(min, Math.min(max, parsedValue))
            : min
          onChange(safeValue)
        }}
      />
    </label>
  )
}

function SummaryCard({
  label,
  value,
}: {
  label: string
  value?: string | number | null
}) {
  const displayValue = value ?? 0

  return (
    <div className="border rounded p-3">
      <div className="text-xs text-gray-500">{label}</div>

      <div className="text-xl font-semibold mt-1">
        {displayValue}
      </div>
    </div>
  )
}

function EmptyNotice({ children }: { children: string }) {
  return (
    <div className="border border-yellow-500 bg-yellow-950/20 rounded p-3 text-sm text-yellow-100">
      {children}
    </div>
  )
}

function GeneratedReviewPanel({
  result,
}: {
  result: CodeSkillGenerateReviewReportResponse
}) {
  const report = result.review_report
  const markdown = result.review_markdown

  const findings = report?.findings ?? []
  const testPlan = report?.test_plan ?? []

  const manualReviewItems =
    report?.manual_review_items ?? []

  const uncertainties =
    report?.uncertainties ?? []

  const isCompleted =
    result.generation_status === "completed" &&
    report !== null &&
    report !== undefined

  const handleCopyMarkdown = async () => {
    if (!markdown) {
      return
    }

    try {
      await window.navigator.clipboard.writeText(
        markdown,
      )

      window.alert(
        "Review Markdown 已复制到剪贴板",
      )
    } catch (error) {
      window.alert(
        `复制失败：${String(error)}`,
      )
    }
  }

  return (
    <div className="border border-blue-600 rounded p-4 space-y-5 bg-blue-950/10">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-medium text-lg">
            AI Review 报告
          </h3>

          <p className="text-sm text-gray-500 mt-1">
            报告由 LLM 根据 RepoGuard Evidence
            生成，每条 Finding 均需引用
            Evidence ID。
          </p>
        </div>

        <span
          className={
            isCompleted
              ? "border border-green-500 bg-green-950/30 text-green-200 rounded px-3 py-1 text-sm"
              : "border border-yellow-500 bg-yellow-950/30 text-yellow-100 rounded px-3 py-1 text-sm"
          }
        >
          {isCompleted
            ? "生成完成"
            : "仅生成 Evidence"}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard
          label="生成模型"
          value={
            result.generation_trace.model ||
            "-"
          }
        />

        <SummaryCard
          label="生成耗时"
          value={`${result.generation_trace.duration_ms ?? 0} ms`}
        />

        <SummaryCard
          label="Evidence 数"
          value={
            result.generation_trace
              .evidence_item_count ?? 0
          }
        />

        <SummaryCard
          label="输出字符"
          value={
            result.generation_trace
              .output_characters ?? 0
          }
        />
      </div>

      {!isCompleted || !report ? (
        <div className="border border-yellow-500 bg-yellow-950/20 rounded p-3">
          <div className="font-medium text-yellow-200">
            LLM 没有生成有效报告
          </div>

          <div className="text-sm text-gray-300 mt-2 whitespace-pre-wrap">
            {result.generation_error ||
              "报告生成失败，但完整 Review Evidence 已保留。"}
          </div>
        </div>
      ) : (
        <>
          <div className="border rounded p-4 space-y-3">
            <h4 className="font-medium">
              执行摘要
            </h4>

            <div className="text-sm whitespace-pre-wrap text-gray-200">
              {report.executive_summary}
            </div>
          </div>

          <div className="border rounded p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h4 className="font-medium">
                总体评估
              </h4>

              <span
                className={`border rounded px-3 py-1 text-sm ${getRiskClassName(
                  report.overall_assessment
                    .risk_level,
                )}`}
              >
                {getRiskLabel(
                  report.overall_assessment
                    .risk_level,
                )}
              </span>
            </div>

            <div className="text-sm">
              <span className="font-medium">
                合并建议：
              </span>

              {getMergeRecommendationLabel(
                report.overall_assessment
                  .merge_recommendation,
              )}
            </div>

            <div className="text-sm whitespace-pre-wrap text-gray-300">
              {
                report.overall_assessment
                  .conclusion
              }
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="font-medium">
              审查发现
            </h4>

            {findings.length === 0 ? (
              <div className="border rounded p-3 text-sm text-gray-500">
                当前没有生成明确的 Finding。
              </div>
            ) : (
              findings.map(
                (finding, findingIndex) => (
                  <div
                    key={
                      finding.finding_id ||
                      `finding-${findingIndex}`
                    }
                    className="border rounded p-4 space-y-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">
                          {finding.finding_id}
                          {" · "}
                          {finding.title}
                        </div>

                        <div className="text-xs text-gray-500 mt-1">
                          类别：{finding.category}
                        </div>
                      </div>

                      <span
                        className={`border rounded px-2 py-1 text-xs ${getRiskClassName(
                          finding.severity,
                        )}`}
                      >
                        {getRiskLabel(
                          finding.severity,
                        )}
                      </span>
                    </div>

                    <div className="text-sm text-gray-300 whitespace-pre-wrap">
                      {finding.description}
                    </div>

                    <div className="text-sm">
                      <span className="font-medium">
                        建议：
                      </span>

                      {finding.recommendation}
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {finding.evidence_ids.map(
                        (evidenceId) => (
                          <span
                            key={evidenceId}
                            className="border border-blue-600 rounded px-2 py-1 font-mono text-xs text-blue-200"
                          >
                            {evidenceId}
                          </span>
                        ),
                      )}
                    </div>
                  </div>
                ),
              )
            )}
          </div>

          <div className="space-y-3">
            <h4 className="font-medium">
              测试计划
            </h4>

            {testPlan.length === 0 ? (
              <div className="border rounded p-3 text-sm text-gray-500">
                当前没有生成明确测试计划。
              </div>
            ) : (
              testPlan.map(
                (testItem, testIndex) => (
                  <div
                    key={`${testItem.test_file}-${testIndex}`}
                    className="border rounded p-3 space-y-2"
                  >
                    <div className="font-mono text-sm break-all">
                      {testItem.test_file}
                    </div>

                    <div className="text-xs text-gray-400">
                      优先级：
                      {getReviewPriorityLabel(
                        testItem.priority,
                      )}
                    </div>

                    <div className="text-sm text-gray-300">
                      {testItem.reason}
                    </div>

                    <div className="text-xs font-mono text-blue-200">
                      {testItem.evidence_ids.join(
                        " · ",
                      )}
                    </div>
                  </div>
                ),
              )
            )}
          </div>

          <div className="space-y-3">
            <h4 className="font-medium">
              人工复核事项
            </h4>

            {manualReviewItems.length === 0 ? (
              <div className="border rounded p-3 text-sm text-gray-500">
                当前没有生成人工复核事项。
              </div>
            ) : (
              manualReviewItems.map(
                (item, itemIndex) => (
                  <label
                    key={`manual-${itemIndex}`}
                    className="border rounded p-3 flex items-start gap-3"
                  >
                    <input
                      type="checkbox"
                      className="mt-1"
                    />

                    <div className="space-y-1">
                      <div className="text-sm">
                        {item.description}
                      </div>

                      <div className="text-xs text-gray-500">
                        优先级：
                        {getReviewPriorityLabel(
                          item.priority,
                        )}
                        {" · "}
                        Evidence：
                        {item.evidence_ids.join(
                          "、",
                        )}
                      </div>
                    </div>
                  </label>
                ),
              )
            )}
          </div>

          {uncertainties.length > 0 ? (
            <div className="border border-yellow-600 bg-yellow-950/20 rounded p-4 space-y-2">
              <h4 className="font-medium text-yellow-200">
                不确定性与限制
              </h4>

              {uncertainties.map(
                (uncertainty, index) => (
                  <div
                    key={`${uncertainty}-${index}`}
                    className="text-sm text-gray-300"
                  >
                    • {uncertainty}
                  </div>
                ),
              )}
            </div>
          ) : null}

          {markdown ? (
            <details className="border rounded">
              <summary className="cursor-pointer px-3 py-2 font-medium">
                查看和导出 Markdown 报告
              </summary>

              <div className="border-t p-3 space-y-3">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="border rounded px-3 py-1.5 text-sm"
                    onClick={handleCopyMarkdown}
                  >
                    复制 Markdown
                  </button>

                  <button
                    type="button"
                    className="border rounded px-3 py-1.5 text-sm"
                    onClick={() =>
                      downloadReviewMarkdown(
                        markdown,
                      )
                    }
                  >
                    下载 Markdown
                  </button>
                </div>

                <pre className="bg-neutral-950 text-gray-100 rounded p-3 text-xs whitespace-pre-wrap overflow-x-auto max-h-[700px]">
                  {markdown}
                </pre>
              </div>
            </details>
          ) : null}
        </>
      )}
    </div>
  )
}

function ChangedSymbolCard({
  symbol,
}: {
  symbol: CodeSkillChangedSymbolPublic
}) {
  return (
    <div className="border rounded p-3 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono font-medium text-gray-100 break-all">
            {symbol.symbol_name}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {getSymbolTypeLabel(symbol.symbol_type)}
            {" · "}
            {symbol.line_range || "未知行号"}
          </div>
        </div>

        <span
          className={`border rounded px-2 py-1 text-xs ${getConfidenceClassName(
            symbol.confidence,
          )}`}
        >
          定位置信度 {formatConfidence(symbol.confidence)}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
        <MetricBox
          label="符号范围"
          value={`${symbol.symbol_start_line ?? "-"} - ${symbol.symbol_end_line ?? "-"}`}
        />
        <MetricBox
          label="Diff 新文件范围"
          value={`${symbol.changed_hunk_new_start} - ${symbol.changed_hunk_new_end}`}
        />
        <MetricBox
          label="实际重叠范围"
          value={`${symbol.overlap_start_line ?? "-"} - ${symbol.overlap_end_line ?? "-"} · ${symbol.overlap_line_count} 行`}
        />
      </div>

      <div className="text-sm">
        <span className="font-medium">判断依据：</span>
        <span className="text-gray-400">{symbol.reason}</span>
      </div>

      <div className="text-xs text-gray-500 break-all">
        Document：{symbol.document_filename || "-"}
        {" · "}
        Chunk Index：{symbol.chunk_index ?? "-"}
      </div>
    </div>
  )
}

function SymbolImpactPanel({
  symbolImpact,
  defaultOpen = false,
}: {
  symbolImpact: CodeSkillSymbolImpactPublic
  defaultOpen?: boolean
}) {
  const changedSymbol = symbolImpact.changed_symbol
  const references = sortImpactReferences(symbolImpact.references ?? [])
  const impactedFiles = sortImpactedFiles(
    symbolImpact.impacted_files ?? [],
  )

  return (
    <details
      className="border rounded overflow-hidden"
      open={defaultOpen}
    >
      <summary className="cursor-pointer p-3 bg-neutral-900">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono font-medium text-gray-100 break-all">
              {changedSymbol.symbol_name}
            </div>
            <div className="text-xs text-gray-500 mt-1 break-all">
              {getSymbolTypeLabel(changedSymbol.symbol_type)}
              {" · "}
              {changedSymbol.file_path}
              {changedSymbol.line_range
                ? ` · ${changedSymbol.line_range}`
                : ""}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            <span className="border border-blue-500 rounded px-2 py-1 text-blue-200">
              {symbolImpact.total_references} 个引用
            </span>
            <span className="border border-purple-500 rounded px-2 py-1 text-purple-200">
              {symbolImpact.total_impacted_files} 个影响文件
            </span>
          </div>
        </div>
      </summary>

      <div className="p-3 space-y-5">
        <div className="space-y-2">
          <div className="font-medium text-sm">引用位置</div>

          {references.length === 0 ? (
            <EmptyNotice>
              没有找到该符号的明确引用位置。该符号可能没有外部调用，
              也可能通过当前文本匹配规则无法识别的方式使用。
            </EmptyNotice>
          ) : (
            <div className="space-y-2">
              {references.map((reference, referenceIndex) => (
                <ImpactReferenceCard
                  key={`${reference.chunk_id}-${referenceIndex}`}
                  reference={reference}
                />
              ))}
            </div>
          )}
        </div>

        <div className="space-y-2">
          <div className="font-medium text-sm">
            该符号对应的受影响文件
          </div>

          {impactedFiles.length === 0 ? (
            <div className="text-sm text-gray-500">
              当前没有汇总出受影响文件。
            </div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
              {impactedFiles.map((impactedFile, impactedFileIndex) => (
                <ImpactedFileCard
                  key={`${impactedFile.file_path}-${impactedFileIndex}`}
                  impactedFile={impactedFile}
                  compact
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </details>
  )
}

function ImpactReferenceCard({
  reference,
}: {
  reference: CodeSkillImpactReferencePublic
}) {
  const preview = String(reference.preview || "").trim()

  return (
    <div className="border rounded p-3 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono font-medium text-sm text-gray-100 break-all">
            {getImpactReferenceTitle(reference)}
          </div>
          <div className="font-mono text-xs text-gray-500 mt-1 break-all">
            {reference.file_path}
          </div>
          <div className="text-xs text-gray-400 mt-1">
            {formatContainingSymbol(reference)}
          </div>
        </div>

        <span
          className={`border rounded px-2 py-1 text-xs ${getConfidenceClassName(
            reference.confidence,
          )}`}
        >
          影响置信度 {formatConfidence(reference.confidence)}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
        <MetricBox
          label="变更符号"
          value={reference.changed_symbol_name}
        />
        <MetricBox
          label="引用出现次数"
          value={reference.occurrence_count}
        />
        <MetricBox label="Chunk Index" value={reference.chunk_index} />
        <MetricBox
          label="Document"
          value={reference.document_filename}
        />
      </div>

      <div className="text-sm">
        <span className="font-medium">匹配原因：</span>
        <span className="text-gray-400">{reference.reason}</span>
      </div>

      {preview ? (
        <details className="border rounded overflow-hidden">
          <summary className="cursor-pointer px-3 py-2 text-sm">
            查看引用代码预览
          </summary>
          <pre className="border-t p-3 bg-neutral-950 text-gray-100 text-xs whitespace-pre-wrap overflow-x-auto max-h-[320px]">
            {preview}
          </pre>
        </details>
      ) : (
        <div className="text-xs text-gray-500">
          当前引用没有返回代码预览。
        </div>
      )}
    </div>
  )
}

function ImpactedFileCard({
  impactedFile,
  compact = false,
}: {
  impactedFile: CodeSkillImpactedFilePublic
  compact?: boolean
}) {
  const impactedSymbolNames =
    impactedFile.impacted_symbol_names ?? []

  return (
    <div className="border rounded p-3 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono font-medium text-sm text-gray-100 break-all">
            {impactedFile.file_path}
          </div>
          {impactedFile.document_filename ? (
            <div className="text-xs text-gray-500 mt-1 break-all">
              Document：{impactedFile.document_filename}
            </div>
          ) : null}
        </div>

        <span
          className={`border rounded px-2 py-1 text-xs ${getConfidenceClassName(
            impactedFile.confidence,
          )}`}
        >
          {formatConfidence(impactedFile.confidence)}
        </span>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="border border-blue-500 rounded px-2 py-1 text-blue-200">
          {impactedFile.reference_count} 条引用证据
        </span>
        <span className="border border-purple-500 rounded px-2 py-1 text-purple-200">
          {impactedSymbolNames.length} 个相关符号
        </span>
      </div>

      {impactedSymbolNames.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {impactedSymbolNames.map((symbolName) => (
            <span
              key={symbolName}
              className="border rounded px-2 py-1 text-xs font-mono"
            >
              {symbolName}
            </span>
          ))}
        </div>
      ) : null}

      {!compact ? (
        <div className="text-sm">
          <span className="font-medium">影响依据：</span>
          <span className="text-gray-400">{impactedFile.reason}</span>
        </div>
      ) : null}
    </div>
  )
}

function RecommendedTestCard({
  recommendedTest,
}: {
  recommendedTest: CodeSkillRecommendedTestPublic
}) {
  const relatedChangedFiles =
    recommendedTest.related_changed_files ?? []
  const relatedImpactedFiles =
    recommendedTest.related_impacted_files ?? []
  const relatedSymbols = recommendedTest.related_symbols ?? []
  const matchedReasons = recommendedTest.matched_reasons ?? []
  const preview = String(recommendedTest.preview || "").trim()

  return (
    <div className="border rounded p-3 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono font-medium text-gray-100 break-all">
            {recommendedTest.test_file_path}
          </div>
          <div className="text-xs text-gray-500 mt-1 break-all">
            Document：{recommendedTest.document_filename}
          </div>
        </div>

        <span
          className={`border rounded px-2 py-1 text-xs ${getConfidenceClassName(
            recommendedTest.confidence,
          )}`}
        >
          推荐置信度 {formatConfidence(recommendedTest.confidence)}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
        <MetricBox
          label="路径匹配"
          value={formatConfidence(recommendedTest.path_match_score)}
        />
        <MetricBox
          label="符号命中"
          value={recommendedTest.symbol_match_count}
        />
        <MetricBox
          label="关联文件"
          value={relatedChangedFiles.length + relatedImpactedFiles.length}
        />
      </div>

      <TagGroup label="相关符号" values={relatedSymbols} />
      <TagGroup label="匹配原因" values={matchedReasons} />
      <TagGroup label="关联变更文件" values={relatedChangedFiles} mono />
      <TagGroup label="关联影响文件" values={relatedImpactedFiles} mono />

      {preview ? (
        <details className="border rounded overflow-hidden">
          <summary className="cursor-pointer px-3 py-2 text-sm">
            查看测试代码预览
          </summary>
          <pre className="border-t p-3 bg-neutral-950 text-gray-100 text-xs whitespace-pre-wrap overflow-x-auto max-h-[320px]">
            {preview}
          </pre>
        </details>
      ) : null}
    </div>
  )
}

function RiskSignalCard({
  riskSignal,
}: {
  riskSignal: CodeSkillRiskSignalPublic
}) {
  return (
    <div
      className={`border rounded p-3 space-y-3 ${getRiskClassName(
        riskSignal.risk_level,
      )}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-medium">{riskSignal.title}</div>
          <div className="text-xs opacity-80 mt-1">
            {riskSignal.risk_type}
          </div>
        </div>
        <span className="border rounded px-2 py-1 text-xs">
          {getRiskLabel(riskSignal.risk_level)}
        </span>
      </div>

      <div className="text-sm">{riskSignal.message}</div>
      <TagGroup label="证据" values={riskSignal.evidence ?? []} />
      <TagGroup
        label="关联文件"
        values={riskSignal.related_files ?? []}
        mono
      />
      <TagGroup
        label="关联符号"
        values={riskSignal.related_symbols ?? []}
        mono
      />
    </div>
  )
}

function ReviewChecklistItemCard({
  checklistItem,
}: {
  checklistItem: CodeSkillReviewChecklistItemPublic
}) {
  return (
    <div className="border rounded p-3 space-y-3">
      <div className="flex items-start gap-3">
        <div className="text-xl leading-none" aria-hidden="true">
          □
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="font-medium">
                {checklistItem.description}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {checklistItem.category} · {checklistItem.item_id}
              </div>
            </div>

            <span
              className={`border rounded px-2 py-1 text-xs ${getPriorityClassName(
                checklistItem.priority,
              )}`}
            >
              {getPriorityLabel(checklistItem.priority)}
            </span>
          </div>

          <div className="text-sm text-gray-400 mt-3">
            <span className="font-medium text-gray-200">生成原因：</span>
            {checklistItem.reason}
          </div>

          <div className="mt-3 space-y-2">
            <TagGroup
              label="关联文件"
              values={checklistItem.related_files ?? []}
              mono
            />
            <TagGroup
              label="关联符号"
              values={checklistItem.related_symbols ?? []}
              mono
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function TagGroup({
  label,
  values,
  mono = false,
}: {
  label: string
  values: string[]
  mono?: boolean
}) {
  const normalizedValues = Array.from(
    new Set(values.map((value) => String(value).trim()).filter(Boolean)),
  )

  if (normalizedValues.length === 0) {
    return null
  }

  return (
    <div className="space-y-1">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="flex flex-wrap gap-2">
        {normalizedValues.map((value) => (
          <span
            key={value}
            className={`border rounded px-2 py-1 text-xs break-all ${
              mono ? "font-mono" : ""
            }`}
          >
            {value}
          </span>
        ))}
      </div>
    </div>
  )
}

function MetricBox({
  label,
  value,
}: {
  label: string
  value?: string | number | null
}) {
  const displayValue = value ?? 0

  return (
    <div className="border rounded p-2">
      <div className="text-gray-500">{label}</div>

      <div className="font-mono mt-1">
        {displayValue}
      </div>
    </div>
  )
}


function EvidenceOperationsPanel({
  reviewEvidence,
  knowledgeBaseId,
}: {
  reviewEvidence: CodeSkillReviewEvidenceResponse
  knowledgeBaseId: string
}) {
  const [actionMessage, setActionMessage] = useState("")
  const [actionError, setActionError] = useState("")

  const evidenceJson = JSON.stringify(
    reviewEvidence,
    null,
    2,
  )

  const evidenceMarkdown =
    buildReviewMarkdownContext(reviewEvidence)

  const fileBaseName =
    buildEvidenceFileBaseName(knowledgeBaseId)

  const evidenceTrace =
    reviewEvidence.evidence_trace ?? []

  const showActionSuccess = (message: string) => {
    setActionError("")
    setActionMessage(message)
  }

  const showActionError = (error: unknown) => {
    setActionMessage("")

    if (error instanceof Error) {
      setActionError(error.message)
      return
    }

    setActionError(String(error || "操作失败"))
  }

  const handleCopyEvidenceJson = async () => {
    try {
      await copyTextToClipboard(evidenceJson)
      showActionSuccess("Evidence JSON 已复制到剪贴板")
    } catch (error) {
      showActionError(error)
    }
  }

  const handleDownloadEvidenceJson = () => {
    try {
      downloadTextFile({
        content: evidenceJson,
        filename: `${fileBaseName}.json`,
        mimeType: "application/json",
      })

      showActionSuccess("Evidence JSON 下载已开始")
    } catch (error) {
      showActionError(error)
    }
  }

  const handleCopyEvidenceMarkdown = async () => {
    try {
      await copyTextToClipboard(evidenceMarkdown)
      showActionSuccess("Review Markdown 上下文已复制到剪贴板")
    } catch (error) {
      showActionError(error)
    }
  }

  const handleDownloadEvidenceMarkdown = () => {
    try {
      downloadTextFile({
        content: evidenceMarkdown,
        filename: `${fileBaseName}.md`,
        mimeType: "text/markdown",
      })

      showActionSuccess("Review Markdown 下载已开始")
    } catch (error) {
      showActionError(error)
    }
  }

  return (
    <div className="border rounded p-4 space-y-5">
      <div>
        <h3 className="font-medium">Evidence 操作区</h3>

        <p className="text-sm text-gray-500 mt-1">
          复制或下载本次分析证据，用于外部 Agent、PR Review、
          本地留档和后续报告生成。
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <button
          type="button"
          className="border rounded px-4 py-3 text-left hover:bg-neutral-900"
          onClick={handleCopyEvidenceJson}
        >
          <div className="font-medium">复制 Evidence JSON</div>

          <div className="text-xs text-gray-500 mt-1">
            复制完整结构化分析结果
          </div>
        </button>

        <button
          type="button"
          className="border rounded px-4 py-3 text-left hover:bg-neutral-900"
          onClick={handleDownloadEvidenceJson}
        >
          <div className="font-medium">下载 Evidence JSON</div>

          <div className="text-xs text-gray-500 mt-1">
            保存为可供程序再次处理的 JSON 文件
          </div>
        </button>

        <button
          type="button"
          className="border rounded px-4 py-3 text-left hover:bg-neutral-900"
          onClick={handleCopyEvidenceMarkdown}
        >
          <div className="font-medium">复制 Markdown 上下文</div>

          <div className="text-xs text-gray-500 mt-1">
            适合粘贴到 Codex、ChatGPT 或 PR 描述
          </div>
        </button>

        <button
          type="button"
          className="border rounded px-4 py-3 text-left hover:bg-neutral-900"
          onClick={handleDownloadEvidenceMarkdown}
        >
          <div className="font-medium">下载 Markdown</div>

          <div className="text-xs text-gray-500 mt-1">
            保存为便于人工阅读的 Review 上下文
          </div>
        </button>
      </div>

      {actionMessage ? (
        <div className="border border-green-500 bg-green-950/20 rounded p-3 text-sm text-green-200">
          {actionMessage}
        </div>
      ) : null}

      {actionError ? (
        <div className="border border-red-500 bg-red-950/20 rounded p-3 text-sm text-red-200">
          操作失败：{actionError}
        </div>
      ) : null}

      <div className="space-y-3">
        <div>
          <h4 className="font-medium">Evidence Trace</h4>

          <p className="text-xs text-gray-500 mt-1">
            展示 RepoGuard 各分析阶段的执行状态、耗时和结果摘要。
          </p>
        </div>

        {evidenceTrace.length === 0 ? (
          <div className="border rounded p-3 text-sm text-gray-500">
            当前 Evidence 没有返回执行 Trace。
          </div>
        ) : (
          <div className="space-y-2">
            {evidenceTrace.map((traceStep, traceIndex) => (
              <div
                key={`${traceStep.step}-${traceIndex}`}
                className="border rounded p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-mono font-medium text-sm">
                      {traceIndex + 1}. {traceStep.step}
                    </div>

                    <div className="text-sm text-gray-400 mt-1">
                      {traceStep.summary}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 text-xs">
                    <span
                      className={`border rounded px-2 py-1 ${getTraceStatusClassName(
                        traceStep.status,
                      )}`}
                    >
                      {traceStep.status}
                    </span>

                    <span className="border rounded px-2 py-1 text-gray-300">
                      {traceStep.duration_ms} ms
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <details className="border rounded overflow-hidden">
        <summary className="cursor-pointer px-3 py-2 font-medium">
          查看完整 Review Evidence JSON
        </summary>

        <pre className="border-t p-3 bg-neutral-950 text-gray-100 text-xs whitespace-pre-wrap overflow-x-auto max-h-[700px]">
          {evidenceJson}
        </pre>
      </details>

      <details className="border rounded overflow-hidden">
        <summary className="cursor-pointer px-3 py-2 font-medium">
          预览 Review Markdown 上下文
        </summary>

        <pre className="border-t p-3 bg-neutral-950 text-gray-100 text-xs whitespace-pre-wrap overflow-x-auto max-h-[700px]">
          {evidenceMarkdown}
        </pre>
      </details>
    </div>
  )
}