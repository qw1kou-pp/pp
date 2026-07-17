import { CodeReviewWorkbench } from "@/components/CodeReviewWorkbench"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { useRef, useState, useEffect } from "react"
import type React from "react"
import { DocumentsService, KnowledgeBasesService } from "@/client"
import { CollapsibleSection } from "../../components/KnowledgeBaseDetail/CollapsibleSection"
import {
  downloadBase64File,
  downloadTextFile,
  getSummaryValue,
  getToolName,
  getToolSuccess,
  readArrayField,
  readField,
  readNumberField,
} from "../../components/KnowledgeBaseDetail/compareUtils"
import { RagAgentCompareDetailSection } from "../../components/KnowledgeBaseDetail/RagAgentCompareDetailSection"
import { RagAgentFailureAnalysisSection } from "../../components/KnowledgeBaseDetail/RagAgentFailureAnalysisSection"
import { RagAgentCompareHistorySection } from "../../components/KnowledgeBaseDetail/RagAgentCompareHistorySection"
import {
  AGENT_PARAM_PRESETS,
  AgentParamTuningSection,
  type AgentParamConfig,
} from "../../components/KnowledgeBaseDetail/AgentParamTuningSection"

type AppliedAgentConfig = {
  topK: number
  maxSteps: number
  semanticWeight: number
  keywordWeight: number
}

type WorkspaceTab = "overview" | "review" | "chat" | "evaluation"

const WORKSPACE_TABS: Array<{
  key: WorkspaceTab
  label: string
  description: string
}> = [
  {
    key: "overview",
    label: "知识库概览",
    description: "上传、导入并管理知识库文档",
  },
  {
    key: "review",
    label: "代码审查",
    description: "分析 Diff、影响范围、风险和测试",
  },
  {
    key: "chat",
    label: "智能问答",
    description: "检索、RAG、Agent 与单题对比",
  },
  {
    key: "evaluation",
    label: "评测实验",
    description: "批量评测、调参、分析与报告",
  },
]

export const Route = createFileRoute("/_layout/knowledge-bases/$knowledgeBaseId")({
  component: KnowledgeBaseDetailPage,
})

const formatPercent = (value?: number | null) => {
  if (value === null || value === undefined) {
    return "-"
  }

  return `${(value * 100).toFixed(1)}%`
}

const formatLatency = (value?: number | null) => {
  if (value === null || value === undefined) {
    return "-"
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}s`
  }

  return `${value.toFixed(0)}ms`
}

const formatToolUsage = (value?: string | null) => {
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
      .sort((a, b) => b[1] - a[1])
      .map(([toolName, count]) => `${toolName}×${count}`)
      .join("，")
  } catch {
    return value
  }
}

const getCodeEvalCaseType = (note?: string | null) => {
  if (!note) {
    return "unknown"
  }

  if (note.startsWith("code:")) {
    return note.replace("code:", "")
  }

  // 兼容旧版本自动生成的 note
  if (note.includes("代码文件列表") || note.includes("代码文件作用")) {
    return "file_overview"
  }

  if (note.includes("定义与作用")) {
    return "symbol_definition"
  }

  if (note.includes("引用定位")) {
    return "symbol_reference"
  }

  return "unknown"
}

const getCodeEvalCaseTypeLabel = (caseType: string) => {
  const labelMap: Record<string, string> = {
    file_overview: "文件概览",
    symbol_definition: "符号定义",
    symbol_reference: "引用定位",
    code_logic: "代码逻辑",
    bug_location: "Bug 定位",
    unknown: "未分类",
  }

  return labelMap[caseType] ?? caseType
}

const getCodeEvalCaseTypeClassName = (caseType: string) => {
  const classMap: Record<string, string> = {
    file_overview: "bg-blue-50 text-blue-700 border-blue-200",
    symbol_definition: "bg-green-50 text-green-700 border-green-200",
    symbol_reference: "bg-purple-50 text-purple-700 border-purple-200",
    code_logic: "bg-orange-50 text-orange-700 border-orange-200",
    bug_location: "bg-red-50 text-red-700 border-red-200",
    unknown: "bg-slate-50 text-slate-600 border-slate-600",
  }

  return classMap[caseType] ?? classMap.unknown
}

type CodeAgentOptimizationAdvice = {
  level: "high" | "medium" | "low"
  title: string
  reason: string
  suggestion: string
}

const getAdviceLevelClassName = (level: CodeAgentOptimizationAdvice["level"]) => {
  const classMap: Record<CodeAgentOptimizationAdvice["level"], string> = {
    high: "border-rose-200 bg-rose-50 text-red-100",
    medium: "border-amber-200 bg-amber-50 text-yellow-100",
    low: "border-sky-200 bg-sky-50 text-blue-100",
  }

  return classMap[level]
}

const getReasonCount = (failureAnalysisData: any, reason: string) => {
  const reasonStats = readArrayField<any>(
    failureAnalysisData,
    "reason_stats",
    "reasonStats",
    [],
  )

  const matchedReason = reasonStats.find((item) => {
    const currentReason = readField<string>(
      item,
      "reason",
      "reason",
      "",
    )

    return currentReason === reason
  })

  if (!matchedReason) {
    return 0
  }

  return readNumberField(matchedReason, "count", "count", 0)
}

const buildCodeAgentOptimizationAdvice = ({
  typeSummaryData,
  failureAnalysisData,
}: {
  typeSummaryData: any
  failureAnalysisData: any
}) => {
  const adviceList: CodeAgentOptimizationAdvice[] = []

  const typeRows = readArrayField<any>(
    typeSummaryData,
    "data",
    "data",
    [],
  )

  const totalFailureItems = readNumberField(
    failureAnalysisData,
    "failed_items",
    "failedItems",
    0,
  )

  const totalItems = readNumberField(
    failureAnalysisData,
    "total_items",
    "totalItems",
    0,
  )

  const agentNoToolCalls = getReasonCount(
    failureAnalysisData,
    "agent_no_tool_calls",
  )

  const agentToolFailed = getReasonCount(
    failureAnalysisData,
    "agent_tool_failed",
  )

  const agentSourceMiss = getReasonCount(
    failureAnalysisData,
    "agent_source_miss",
  )

  const agentKeywordMiss = getReasonCount(
    failureAnalysisData,
    "agent_keyword_miss",
  )

  const agentSlow = getReasonCount(
    failureAnalysisData,
    "agent_slow",
  )

  const agentNoSources = getReasonCount(
    failureAnalysisData,
    "agent_no_sources",
  )

  if (totalItems > 0 && totalFailureItems / totalItems >= 0.5) {
    adviceList.push({
      level: "high",
      title: "整体异常率偏高，建议先不要继续盲目调参",
      reason: `当前失败/异常样例为 ${totalFailureItems}/${totalItems}，异常率已经达到 ${(
        (totalFailureItems / totalItems) *
        100
      ).toFixed(1)}%。`,
      suggestion:
        "优先查看失败原因分布和具体失败样例，先判断是工具选择问题、检索问题，还是回答生成问题。不要只靠增加 max_steps 解决，否则可能只会增加耗时。",
    })
  }

  if (agentNoToolCalls > 0) {
    adviceList.push({
      level: "high",
      title: "Agent 存在无工具调用，可能退化成普通 RAG",
      reason: `失败分析中出现 ${agentNoToolCalls} 次 agent_no_tool_calls。`,
      suggestion:
        "检查 Agent 的 ReAct 选择原则和 fallback 规则。对于代码问题，应让函数、类、变量、调用关系、报错定位类问题优先进入 search_code 或 find_code_references，而不是直接 final_answer。",
    })
  }

  if (agentToolFailed > 0) {
    adviceList.push({
      level: "high",
      title: "Agent 工具调用存在失败，需要优先修工具链",
      reason: `失败分析中出现 ${agentToolFailed} 次 agent_tool_failed。`,
      suggestion:
        "优先检查 agent_tool_registry 中 handler 的参数解析、工具名注册、返回结构和异常处理。工具失败属于工程链路问题，应该先修复，再进行参数实验。",
    })
  }

  if (agentNoSources > 0) {
    adviceList.push({
      level: "high",
      title: "Agent 没有拿到 sources，说明检索链路可能没有生效",
      reason: `失败分析中出现 ${agentNoSources} 次 agent_no_sources。`,
      suggestion:
        "检查 search_code、find_code_references、read_code_file 是否正确把 sources 合并回 Agent 上下文。没有 sources 的 Agent 回答很容易变成泛泛总结。",
    })
  }

  if (agentSourceMiss > 0) {
    adviceList.push({
      level: "medium",
      title: "Agent 来源文件未命中，建议增强代码检索的关键词权重",
      reason: `失败分析中出现 ${agentSourceMiss} 次 agent_source_miss。`,
      suggestion:
        "代码任务里函数名、类名、文件名很重要。下一轮可以尝试 semantic_weight=0.65、keyword_weight=0.35，或者 semantic_weight=0.6、keyword_weight=0.4，并观察 symbol_definition / symbol_reference 的 source 命中率是否提升。",
    })
  }

  if (agentKeywordMiss > 0) {
    adviceList.push({
      level: "medium",
      title: "Agent 回答关键词未命中，可能找到了片段但总结不够贴合预期",
      reason: `失败分析中出现 ${agentKeywordMiss} 次 agent_keyword_miss。`,
      suggestion:
        "对于 symbol_definition 问题，回答中应明确给出函数/类名、文件名、作用；对于 code_logic 问题，应要求 Agent 在 search_code 后继续 read_code_file，避免只看局部 chunk。",
    })
  }

  if (agentSlow > 0) {
    adviceList.push({
      level: "medium",
      title: "Agent 明显慢于 RAG，需要控制工具调用成本",
      reason: `失败分析中出现 ${agentSlow} 次 agent_slow。`,
      suggestion:
        "检查是否重复调用 search_code / read_code_file。可以限制同一工具重复调用，或者只在 code_logic / 上下文不足类问题中调用 read_code_file。简单 file_overview 问题不一定需要 Agent 多步推理。",
    })
  }

  for (const row of typeRows) {
    const caseType = readField<string>(row, "case_type", "caseType", "unknown")
    const caseTypeLabel = readField<string>(
      row,
      "case_type_label",
      "caseTypeLabel",
      caseType,
    )

    const comparedCases = readNumberField(
      row,
      "compared_cases",
      "comparedCases",
      0,
    )

    if (comparedCases <= 0) {
      continue
    }

    const ragSourceHitRate = readNumberField(
      row,
      "rag_source_hit_rate",
      "ragSourceHitRate",
      0,
    )

    const agentSourceHitRate = readNumberField(
      row,
      "agent_source_hit_rate",
      "agentSourceHitRate",
      0,
    )

    const ragKeywordHitRate = readNumberField(
      row,
      "rag_keyword_hit_rate",
      "ragKeywordHitRate",
      0,
    )

    const agentKeywordHitRate = readNumberField(
      row,
      "agent_keyword_hit_rate",
      "agentKeywordHitRate",
      0,
    )

    const ragAvgLatency = readField<number | null>(
      row,
      "rag_avg_latency_ms",
      "ragAvgLatencyMs",
      null,
    )

    const agentAvgLatency = readField<number | null>(
      row,
      "agent_avg_latency_ms",
      "agentAvgLatencyMs",
      null,
    )

    const agentAvgToolCalls = readField<number | null>(
      row,
      "agent_avg_tool_calls",
      "agentAvgToolCalls",
      null,
    )

    if (
      caseType === "symbol_reference" &&
      agentSourceHitRate < 0.7
    ) {
      adviceList.push({
        level: "high",
        title: "引用定位类任务表现不足，应强化 find_code_references",
        reason: `${caseTypeLabel} 的 Agent 文件命中率为 ${formatPercent(
          agentSourceHitRate,
        )}，低于 70%。`,
        suggestion:
          "在 Agent prompt 和 fallback 中明确规定：当问题包含“在哪里调用、哪里使用、引用、出现、定义在哪里”等词时，优先调用 find_code_references，而不是普通 search_code。",
      })
    }

    if (
      caseType === "code_logic" &&
      agentKeywordHitRate < 0.7
    ) {
      adviceList.push({
        level: "medium",
        title: "代码逻辑类任务关键词命中偏低，应读取完整文件上下文",
        reason: `${caseTypeLabel} 的 Agent 关键词命中率为 ${formatPercent(
          agentKeywordHitRate,
        )}，说明回答可能缺少关键函数名、文件名或逻辑步骤。`,
        suggestion:
          "对于“完整逻辑、执行流程、实现流程、上下文”类问题，建议 search_code 后继续调用 read_code_file，再生成最终回答。",
      })
    }

    if (
      caseType === "file_overview" &&
      ragSourceHitRate >= 0.8 &&
      agentSourceHitRate >= 0.8 &&
      ragAvgLatency !== null &&
      agentAvgLatency !== null &&
      agentAvgLatency > ragAvgLatency * 2
    ) {
      adviceList.push({
        level: "low",
        title: "文件概览类任务普通 RAG 已经足够",
        reason: `${caseTypeLabel} 中 RAG 和 Agent 来源命中率都较高，但 Agent 平均耗时 ${formatLatency(
          agentAvgLatency,
        )}，明显高于 RAG 的 ${formatLatency(ragAvgLatency)}。`,
        suggestion:
          "文件概览类问题可以默认走普通 RAG 或 list_code_files，不必强制走多步 Agent。Agent 更适合 symbol_reference 和 code_logic 等复杂代码任务。",
      })
    }

    if (
      agentAvgToolCalls !== null &&
      agentAvgToolCalls < 1 &&
      ["symbol_definition", "symbol_reference", "code_logic"].includes(caseType)
    ) {
      adviceList.push({
        level: "medium",
        title: `${caseTypeLabel} 中 Agent 工具调用偏少`,
        reason: `${caseTypeLabel} 的 Agent 平均工具调用数为 ${agentAvgToolCalls.toFixed(
          2,
        )}，可能没有充分使用代码工具。`,
        suggestion:
          "检查 Planner prompt 中对应任务类型的工具选择描述，确保 symbol_definition 使用 search_code / find_code_references，code_logic 能继续 read_code_file。",
      })
    }

    if (
      agentSourceHitRate > ragSourceHitRate + 0.15 &&
      agentKeywordHitRate >= ragKeywordHitRate
    ) {
      adviceList.push({
        level: "low",
        title: `${caseTypeLabel} 中 Agent 相比 RAG 有明显优势`,
        reason: `Agent 文件命中率 ${formatPercent(
          agentSourceHitRate,
        )}，RAG 文件命中率 ${formatPercent(ragSourceHitRate)}。`,
        suggestion:
          "这类任务可以作为项目报告中的成功案例，展示 Code Agent 通过工具调用提升代码定位能力。",
      })
    }
  }

  if (adviceList.length === 0) {
    adviceList.push({
      level: "low",
      title: "当前没有明显优化风险",
      reason:
        "失败原因统计和分任务类型统计中没有发现突出的异常模式。",
      suggestion:
        "可以扩大评测样例数量，或者增加更难的 bug_location、跨文件调用关系类问题，进一步检验 Code Agent 的上限。",
    })
  }

  return adviceList
}

type OptimizationCompareResult = "better" | "worse" | "neutral"

type OptimizationCompareRow = {
  metric: string
  beforeText: string
  afterText: string
  changeText: string
  result: OptimizationCompareResult
  explanation: string
}

const getCompareBatchNumber = (
  batch: any,
  snakeKey: string,
  camelKey: string,
  defaultValue = 0,
) => {
  return readNumberField(batch, snakeKey, camelKey, defaultValue)
}

const getCompareBatchNullableNumber = (
  batch: any,
  snakeKey: string,
  camelKey: string,
) => {
  return readField<number | null>(batch, snakeKey, camelKey, null)
}

const formatSignedNumber = (value: number, suffix = "") => {
  if (value > 0) {
    return `+${value.toFixed(2)}${suffix}`
  }

  if (value < 0) {
    return `${value.toFixed(2)}${suffix}`
  }

  return `0${suffix}`
}

const formatSignedPercentPoint = (value: number) => {
  if (value > 0) {
    return `+${(value * 100).toFixed(1)} 个百分点`
  }

  if (value < 0) {
    return `${(value * 100).toFixed(1)} 个百分点`
  }

  return "0 个百分点"
}

const getResultClassName = (result: OptimizationCompareResult) => {
  const classMap: Record<OptimizationCompareResult, string> = {
    better: "text-emerald-600",
    worse: "text-rose-600",
    neutral: "text-slate-900",
  }

  return classMap[result]
}

const getResultLabel = (result: OptimizationCompareResult) => {
  const labelMap: Record<OptimizationCompareResult, string> = {
    better: "改善",
    worse: "变差",
    neutral: "基本不变",
  }

  return labelMap[result]
}

const buildOptimizationCompareRows = (
  beforeBatch: any | undefined,
  afterBatch: any | undefined,
): OptimizationCompareRow[] => {
  if (!beforeBatch || !afterBatch) {
    return []
  }

  const rows: OptimizationCompareRow[] = []

  const beforeRan = getCompareBatchNumber(beforeBatch, "ran", "ran", 0)
  const afterRan = getCompareBatchNumber(afterBatch, "ran", "ran", 0)

  const beforeFailed = getCompareBatchNumber(beforeBatch, "failed", "failed", 0)
  const afterFailed = getCompareBatchNumber(afterBatch, "failed", "failed", 0)

  const beforeFailureRate =
    beforeRan > 0 ? beforeFailed / beforeRan : null

  const afterFailureRate =
    afterRan > 0 ? afterFailed / afterRan : null

  if (beforeFailureRate !== null && afterFailureRate !== null) {
    const change = afterFailureRate - beforeFailureRate

    rows.push({
      metric: "失败率",
      beforeText: formatPercent(beforeFailureRate),
      afterText: formatPercent(afterFailureRate),
      changeText: formatSignedPercentPoint(change),
      result:
        change < -0.001 ? "better" : change > 0.001 ? "worse" : "neutral",
      explanation:
        "失败率越低越好。它可以反映优化后 Agent 是否减少了运行错误、工具失败或明显异常样例。",
    })
  }

  const beforeAgentLatency = getCompareBatchNullableNumber(
    beforeBatch,
    "average_agent_latency_ms",
    "averageAgentLatencyMs",
  )

  const afterAgentLatency = getCompareBatchNullableNumber(
    afterBatch,
    "average_agent_latency_ms",
    "averageAgentLatencyMs",
  )

  if (beforeAgentLatency !== null && afterAgentLatency !== null) {
    const change = afterAgentLatency - beforeAgentLatency

    rows.push({
      metric: "Agent 平均耗时",
      beforeText: formatLatency(beforeAgentLatency),
      afterText: formatLatency(afterAgentLatency),
      changeText: formatLatency(Math.abs(change)),
      result:
        change < -1 ? "better" : change > 1 ? "worse" : "neutral",
      explanation:
        change <= 0
          ? "优化后 Agent 平均耗时下降或持平，说明工具选择成本没有明显增加。"
          : "优化后 Agent 平均耗时上升，需要结合命中率提升判断是否值得。",
    })
  }

  const beforeToolCalls = getCompareBatchNullableNumber(
    beforeBatch,
    "average_agent_tool_call_count",
    "averageAgentToolCallCount",
  )

  const afterToolCalls = getCompareBatchNullableNumber(
    afterBatch,
    "average_agent_tool_call_count",
    "averageAgentToolCallCount",
  )

  if (beforeToolCalls !== null && afterToolCalls !== null) {
    const change = afterToolCalls - beforeToolCalls

    rows.push({
      metric: "Agent 平均工具调用数",
      beforeText: beforeToolCalls.toFixed(2),
      afterText: afterToolCalls.toFixed(2),
      changeText: formatSignedNumber(change),
      result:
        afterToolCalls >= 1 && afterToolCalls <= 4
          ? "better"
          : afterToolCalls > 5
            ? "worse"
            : "neutral",
      explanation:
        "工具调用数不是越多越好。合理范围内增加通常说明 Agent 没有退化成普通 RAG；过高则可能说明存在重复调用。",
    })
  }

  const beforeFailedTools = getCompareBatchNumber(
    beforeBatch,
    "total_agent_failed_tool_count",
    "totalAgentFailedToolCount",
    0,
  )

  const afterFailedTools = getCompareBatchNumber(
    afterBatch,
    "total_agent_failed_tool_count",
    "totalAgentFailedToolCount",
    0,
  )

  rows.push({
    metric: "Agent 工具失败总数",
    beforeText: String(beforeFailedTools),
    afterText: String(afterFailedTools),
    changeText: String(afterFailedTools - beforeFailedTools),
    result:
      afterFailedTools < beforeFailedTools
        ? "better"
        : afterFailedTools > beforeFailedTools
          ? "worse"
          : "neutral",
    explanation:
      "工具失败数越低越好。如果优化后工具失败仍然存在，应优先修 handler、参数解析和异常处理。",
  })

  const beforeRagSources = getCompareBatchNullableNumber(
    beforeBatch,
    "average_rag_sources_count",
    "averageRagSourcesCount",
  )

  const afterRagSources = getCompareBatchNullableNumber(
    afterBatch,
    "average_rag_sources_count",
    "averageRagSourcesCount",
  )

  const beforeAgentSources = getCompareBatchNullableNumber(
    beforeBatch,
    "average_agent_sources_count",
    "averageAgentSourcesCount",
  )

  const afterAgentSources = getCompareBatchNullableNumber(
    afterBatch,
    "average_agent_sources_count",
    "averageAgentSourcesCount",
  )

  if (
    beforeRagSources !== null &&
    afterRagSources !== null &&
    beforeAgentSources !== null &&
    afterAgentSources !== null
  ) {
    const beforeSourceGain = beforeAgentSources - beforeRagSources
    const afterSourceGain = afterAgentSources - afterRagSources
    const change = afterSourceGain - beforeSourceGain

    rows.push({
      metric: "Agent 相对 RAG 的 sources 增益",
      beforeText: beforeSourceGain.toFixed(2),
      afterText: afterSourceGain.toFixed(2),
      changeText: formatSignedNumber(change),
      result:
        change > 0.05 ? "better" : change < -0.05 ? "worse" : "neutral",
      explanation:
        "如果 Agent 相比 RAG 能拿到更多有效 sources，说明工具链可能带来了更强的代码定位能力。",
    })
  }

  const beforeSummarize = getCompareBatchNumber(
    beforeBatch,
    "summarize_document_count",
    "summarizeDocumentCount",
    0,
  )

  const afterSummarize = getCompareBatchNumber(
    afterBatch,
    "summarize_document_count",
    "summarizeDocumentCount",
    0,
  )

  const beforeReadChunks = getCompareBatchNumber(
    beforeBatch,
    "read_document_chunks_count",
    "readDocumentChunksCount",
    0,
  )

  const afterReadChunks = getCompareBatchNumber(
    afterBatch,
    "read_document_chunks_count",
    "readDocumentChunksCount",
    0,
  )

  rows.push({
    metric: "深度阅读类工具调用",
    beforeText: `${beforeSummarize + beforeReadChunks}`,
    afterText: `${afterSummarize + afterReadChunks}`,
    changeText: String(afterSummarize + afterReadChunks - beforeSummarize - beforeReadChunks),
    result:
      afterSummarize + afterReadChunks > beforeSummarize + beforeReadChunks
        ? "better"
        : afterSummarize + afterReadChunks < beforeSummarize + beforeReadChunks
          ? "worse"
          : "neutral",
    explanation:
      "深度阅读类工具调用增加，通常说明 Agent 更愿意读取上下文；但如果耗时明显变高，需要继续限制重复调用。",
  })

  return rows
}

const safeMarkdownText = (value: unknown) => {
  if (value === null || value === undefined) {
    return "-"
  }

  return String(value)
    .replace(/\|/g, "\\|")
    .replace(/\n/g, " ")
    .trim()
}

const formatReportDateTime = (value?: string | null) => {
  if (!value) {
    return "-"
  }

  return new Date(value).toLocaleString()
}

const buildBatchSummaryMarkdown = (batch: any, label: string) => {
  if (!batch) {
    return `### ${label}\n\n未选择批次。\n`
  }

  const failed = readNumberField(batch, "failed", "failed", 0)
  const ran = readNumberField(batch, "ran", "ran", 0)
  const failureRate = ran > 0 ? failed / ran : null

  return [
    `### ${label}`,
    "",
    `- 批次名称：${readField<string>(batch, "name", "name", "-")}`,
    `- 批次 ID：${readField<string>(batch, "id", "id", "-")}`,
    `- 创建时间：${formatReportDateTime(
      readField<string | null>(batch, "created_at", "createdAt", null),
    )}`,
    `- 样例数量：${readNumberField(batch, "total_cases", "totalCases", 0)}`,
    `- 成功运行：${ran}`,
    `- 失败数量：${failed}`,
    `- 失败率：${failureRate === null ? "-" : formatPercent(failureRate)}`,
    `- 参数：top_k=${readNumberField(batch, "top_k", "topK", 0)}，max_steps=${readNumberField(
      batch,
      "max_steps",
      "maxSteps",
      0,
    )}，semantic_weight=${readNumberField(
      batch,
      "semantic_weight",
      "semanticWeight",
      0,
    )}，keyword_weight=${readNumberField(
      batch,
      "keyword_weight",
      "keywordWeight",
      0,
    )}`,
    `- RAG 平均耗时：${formatLatency(
      readField<number | null>(
        batch,
        "average_rag_latency_ms",
        "averageRagLatencyMs",
        null,
      ),
    )}`,
    `- Agent 平均耗时：${formatLatency(
      readField<number | null>(
        batch,
        "average_agent_latency_ms",
        "averageAgentLatencyMs",
        null,
      ),
    )}`,
    `- Agent 平均工具调用数：${formatNullableNumber(
      readField<number | null>(
        batch,
        "average_agent_tool_call_count",
        "averageAgentToolCallCount",
        null,
      ),
    )}`,
    `- Agent 工具失败总数：${readNumberField(
      batch,
      "total_agent_failed_tool_count",
      "totalAgentFailedToolCount",
      0,
    )}`,
    "",
  ].join("\n")
}

const formatNullableNumber = (value?: number | null) => {
  if (value === null || value === undefined) {
    return "-"
  }

  return value.toFixed(2)
}

const buildCodeAgentExperimentReportMarkdown = ({
  knowledgeBase,
  baselineCompareBatch,
  optimizedCompareBatch,
  optimizationCompareRows,
  typeSummaryData,
  failureAnalysisData,
  adviceList,
}: {
  knowledgeBase: any
  baselineCompareBatch: any
  optimizedCompareBatch: any
  optimizationCompareRows: OptimizationCompareRow[]
  typeSummaryData: any
  failureAnalysisData: any
  adviceList: CodeAgentOptimizationAdvice[]
}) => {
  const typeRows = readArrayField<any>(
    typeSummaryData,
    "data",
    "data",
    [],
  )

  const reasonStats = readArrayField<any>(
    failureAnalysisData,
    "reason_stats",
    "reasonStats",
    [],
  )

  const failureCases = readArrayField<any>(
    failureAnalysisData,
    "data",
    "data",
    [],
  )

  const betterCount = optimizationCompareRows.filter(
    (row) => row.result === "better",
  ).length

  const worseCount = optimizationCompareRows.filter(
    (row) => row.result === "worse",
  ).length

  const neutralCount = optimizationCompareRows.filter(
    (row) => row.result === "neutral",
  ).length

  const autoConclusion =
    betterCount > worseCount
      ? "本轮优化整体呈现正向效果。改善项多于变差项，可以继续保留当前 Agent 工具选择策略，并进一步观察具体任务类型的提升情况。"
      : worseCount > betterCount
        ? "本轮优化存在一定副作用。建议重点查看失败案例分析，判断是工具调用过多导致耗时上升，还是检索权重变化导致命中率下降。"
        : "本轮优化效果暂不明显。建议扩大评测样例数量，增加跨文件调用关系、代码逻辑解释和 Bug 定位类任务。"

  const lines: string[] = []

  lines.push("# Code RAG / Code Agent 实验报告")
  lines.push("")
  lines.push(`生成时间：${new Date().toLocaleString()}`)
  lines.push("")
  lines.push("## 1. 实验对象")
  lines.push("")
  lines.push(`- 知识库名称：${readField<string>(knowledgeBase, "name", "name", "-")}`)
  lines.push(`- 知识库 ID：${readField<string>(knowledgeBase, "id", "id", "-")}`)
  lines.push(
    `- 知识库描述：${readField<string | null>(
      knowledgeBase,
      "description",
      "description",
      "-",
    ) || "-"}`,
  )
  lines.push("")

  lines.push("## 2. 实验批次信息")
  lines.push("")
  lines.push(buildBatchSummaryMarkdown(baselineCompareBatch, "优化前批次"))
  lines.push(buildBatchSummaryMarkdown(optimizedCompareBatch, "优化后批次"))

  lines.push("## 3. 优化前后总体对比")
  lines.push("")
  lines.push("| 指标 | 优化前 | 优化后 | 变化 | 判断 |")
  lines.push("|---|---:|---:|---:|---|")

  for (const row of optimizationCompareRows) {
    lines.push(
      `| ${safeMarkdownText(row.metric)} | ${safeMarkdownText(
        row.beforeText,
      )} | ${safeMarkdownText(row.afterText)} | ${safeMarkdownText(
        row.changeText,
      )} | ${safeMarkdownText(getResultLabel(row.result))} |`,
    )
  }

  lines.push("")
  lines.push(`自动结论：${autoConclusion}`)
  lines.push("")

  lines.push("## 4. 分任务类型统计")
  lines.push("")
  lines.push("| 任务类型 | 样例数 | 已对比 | RAG 文件命中 | Agent 文件命中 | RAG 关键词命中 | Agent 关键词命中 | RAG 耗时 | Agent 耗时 | Agent 平均工具数 |")
  lines.push("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

  if (typeRows.length === 0) {
    lines.push("| 暂无数据 | - | - | - | - | - | - | - | - | - |")
  } else {
    for (const row of typeRows) {
      lines.push(
        `| ${safeMarkdownText(
          readField<string>(row, "case_type_label", "caseTypeLabel", "-"),
        )} | ${readNumberField(row, "total_cases", "totalCases", 0)} | ${readNumberField(
          row,
          "compared_cases",
          "comparedCases",
          0,
        )} | ${formatPercent(
          readNumberField(row, "rag_source_hit_rate", "ragSourceHitRate", 0),
        )} | ${formatPercent(
          readNumberField(row, "agent_source_hit_rate", "agentSourceHitRate", 0),
        )} | ${formatPercent(
          readNumberField(row, "rag_keyword_hit_rate", "ragKeywordHitRate", 0),
        )} | ${formatPercent(
          readNumberField(row, "agent_keyword_hit_rate", "agentKeywordHitRate", 0),
        )} | ${formatLatency(
          readField<number | null>(
            row,
            "rag_avg_latency_ms",
            "ragAvgLatencyMs",
            null,
          ),
        )} | ${formatLatency(
          readField<number | null>(
            row,
            "agent_avg_latency_ms",
            "agentAvgLatencyMs",
            null,
          ),
        )} | ${formatNullableNumber(
          readField<number | null>(
            row,
            "agent_avg_tool_calls",
            "agentAvgToolCalls",
            null,
          ),
        )} |`,
      )
    }
  }

  lines.push("")

  lines.push("## 5. 失败原因统计")
  lines.push("")
  lines.push(
    `- 分析样例数：${readNumberField(
      failureAnalysisData,
      "total_items",
      "totalItems",
      0,
    )}`,
  )
  lines.push(
    `- 异常样例数：${readNumberField(
      failureAnalysisData,
      "failed_items",
      "failedItems",
      0,
    )}`,
  )
  lines.push("")
  lines.push("| 失败原因 | 次数 |")
  lines.push("|---|---:|")

  if (reasonStats.length === 0) {
    lines.push("| 暂无明显失败原因 | - |")
  } else {
    for (const item of reasonStats) {
      lines.push(
        `| ${safeMarkdownText(
          readField<string>(item, "reason_label", "reasonLabel", "-"),
        )} | ${readNumberField(item, "count", "count", 0)} |`,
      )
    }
  }

  lines.push("")

  lines.push("## 6. 代表性失败案例")
  lines.push("")

  if (failureCases.length === 0) {
    lines.push("当前筛选范围内暂无失败案例。")
  } else {
    failureCases.slice(0, 8).forEach((item, index) => {
      const labels = readArrayField<string>(
        item,
        "failure_reason_labels",
        "failureReasonLabels",
        [],
      )

      lines.push(`### 6.${index + 1} ${safeMarkdownText(readField<string>(item, "question", "question", "-"))}`)
      lines.push("")
      lines.push(`- 任务类型：${readField<string>(item, "case_type_label", "caseTypeLabel", "-")}`)
      lines.push(`- 失败原因：${labels.length > 0 ? labels.join("、") : "-"}`)
      lines.push(`- RAG 来源命中：${readField<boolean | null>(item, "rag_source_hit", "ragSourceHit", null) ? "是" : "否"}`)
      lines.push(`- Agent 来源命中：${readField<boolean | null>(item, "agent_source_hit", "agentSourceHit", null) ? "是" : "否"}`)
      lines.push(`- RAG 关键词命中率：${formatPercent(readNumberField(item, "rag_keyword_hit_rate", "ragKeywordHitRate", 0))}`)
      lines.push(`- Agent 关键词命中率：${formatPercent(readNumberField(item, "agent_keyword_hit_rate", "agentKeywordHitRate", 0))}`)
      lines.push("")
    })
  }

  lines.push("")

  lines.push("## 7. 自动优化建议")
  lines.push("")

  if (adviceList.length === 0) {
    lines.push("暂无自动优化建议。")
  } else {
    adviceList.forEach((advice, index) => {
      lines.push(`### 7.${index + 1} ${advice.title}`)
      lines.push("")
      lines.push(`- 优先级：${advice.level}`)
      lines.push(`- 判断依据：${advice.reason}`)
      lines.push(`- 优化建议：${advice.suggestion}`)
      lines.push("")
    })
  }

  lines.push("## 8. 下一轮实验建议")
  lines.push("")
  lines.push("- 如果 Agent 来源未命中较多，建议尝试 semantic_weight=0.65、keyword_weight=0.35。")
  lines.push("- 如果 symbol_reference 表现较差，建议继续强化 find_code_references 的触发规则。")
  lines.push("- 如果 code_logic 表现较差，建议 search_code 后继续 read_code_file。")
  lines.push("- 如果 Agent 耗时明显升高，建议限制重复工具调用，并控制 read_code_file 的触发条件。")
  lines.push("")

  return lines.join("\n")
}


const buildAgentParamRecommendation = (tuningResults: any[]) => {
  if (!tuningResults || tuningResults.length === 0) {
    return null
  }

  const rows = tuningResults.map(({ preset, result }) => {
    const summary = readField<any>(result, "summary", "summary", {})

    const failed = getSummaryValue<number>(
      summary,
      "failed",
      "failed",
      0,
    )

    const averageRagLatency = getSummaryValue<number | null>(
      summary,
      "average_rag_latency_ms",
      "averageRagLatencyMs",
      null,
    )

    const averageAgentLatency = getSummaryValue<number | null>(
      summary,
      "average_agent_latency_ms",
      "averageAgentLatencyMs",
      null,
    )

    const averageRagSourcesCount = getSummaryValue<number | null>(
      summary,
      "average_rag_sources_count",
      "averageRagSourcesCount",
      null,
    )

    const averageAgentSourcesCount = getSummaryValue<number | null>(
      summary,
      "average_agent_sources_count",
      "averageAgentSourcesCount",
      null,
    )

    const averageAgentToolCallCount = getSummaryValue<number | null>(
      summary,
      "average_agent_tool_call_count",
      "averageAgentToolCallCount",
      null,
    )

    const totalAgentFailedToolCount = getSummaryValue<number>(
      summary,
      "total_agent_failed_tool_count",
      "totalAgentFailedToolCount",
      0,
    )

    const summarizeDocumentCount = getSummaryValue<number>(
      summary,
      "summarize_document_count",
      "summarizeDocumentCount",
      0,
    )

    const readDocumentChunksCount = getSummaryValue<number>(
      summary,
      "read_document_chunks_count",
      "readDocumentChunksCount",
      0,
    )

    const latencyGap =
      averageRagLatency === null || averageAgentLatency === null
        ? null
        : averageAgentLatency - averageRagLatency

    const sourceGain =
      averageRagSourcesCount === null || averageAgentSourcesCount === null
        ? null
        : averageAgentSourcesCount - averageRagSourcesCount

    const latencyPenalty =
      averageAgentLatency === null ? 1000 : averageAgentLatency / 1000

    const toolCountPenalty =
      averageAgentToolCallCount === null ? 20 : averageAgentToolCallCount * 5

    const failurePenalty = failed * 100
    const failedToolPenalty = totalAgentFailedToolCount * 80

    const usefulToolBonus =
      summarizeDocumentCount * 3 + readDocumentChunksCount * 2

    const sourceBonus =
      sourceGain === null ? 0 : Math.max(0, sourceGain) * 3

    const score =
      failurePenalty +
      failedToolPenalty +
      latencyPenalty +
      toolCountPenalty -
      usefulToolBonus -
      sourceBonus

    return {
      preset,
      summary,
      failed,
      averageRagLatency,
      averageAgentLatency,
      averageRagSourcesCount,
      averageAgentSourcesCount,
      averageAgentToolCallCount,
      totalAgentFailedToolCount,
      summarizeDocumentCount,
      readDocumentChunksCount,
      latencyGap,
      sourceGain,
      score,
    }
  })

  const sortedRows = [...rows].sort((a, b) => a.score - b.score)

  const best = sortedRows[0]
  const worst = sortedRows[sortedRows.length - 1]

  const stableRows = rows.filter(
    (row) => row.failed === 0 && row.totalAgentFailedToolCount === 0,
  )

  const fastest = [...rows].sort((a, b) => {
    const aLatency = a.averageAgentLatency ?? Number.POSITIVE_INFINITY
    const bLatency = b.averageAgentLatency ?? Number.POSITIVE_INFINITY

    return aLatency - bLatency
  })[0]

  const mostToolUse = [...rows].sort((a, b) => {
    const aCount = a.averageAgentToolCallCount ?? 0
    const bCount = b.averageAgentToolCallCount ?? 0

    return bCount - aCount
  })[0]

  const mostSourceGain = [...rows].sort((a, b) => {
    const aGain = a.sourceGain ?? -999
    const bGain = b.sourceGain ?? -999

    return bGain - aGain
  })[0]

  const suggestions: string[] = []

  if (stableRows.length === 0) {
    suggestions.push(
      "当前所有参数组都存在失败样例或工具失败，建议先检查 Agent 工具调用链和失败样例，而不是继续扩大 max_steps。",
    )
  } else {
    suggestions.push(
      `共有 ${stableRows.length} 组参数没有出现失败样例和工具失败，可以优先从这些稳定配置中选择。`,
    )
  }

  if (best.averageAgentLatency !== null && fastest.averageAgentLatency !== null) {
    if (best.preset.name !== fastest.preset.name) {
      suggestions.push(
        `最快配置是“${fastest.preset.name}”，但综合推荐是“${best.preset.name}”，说明最低耗时不一定代表整体最优。`,
      )
    } else {
      suggestions.push(
        `“${best.preset.name}”同时也是当前 Agent 平均耗时较低的配置，适合作为默认配置候选。`,
      )
    }
  }

  if (
    mostToolUse.averageAgentToolCallCount !== null &&
    mostToolUse.averageAgentToolCallCount > 3
  ) {
    suggestions.push(
      `“${mostToolUse.preset.name}”的平均工具调用数较高，需要检查是否存在重复调用或不必要的多步 ReAct。`,
    )
  }

  if (
    mostSourceGain.sourceGain !== null &&
    mostSourceGain.sourceGain > 0
  ) {
    suggestions.push(
      `“${mostSourceGain.preset.name}”相比普通 RAG 获取了更多 sources，适合观察它是否带来更完整的回答。`,
    )
  }

  if (best.totalAgentFailedToolCount > 0) {
    suggestions.push(
      "综合推荐配置仍然存在工具失败，建议优先查看失败案例分析面板，定位具体失败工具。",
    )
  }

  if (best.averageAgentToolCallCount !== null && best.averageAgentToolCallCount < 1) {
    suggestions.push(
      "推荐配置中 Agent 平均工具调用数偏低，说明 Agent 可能退化成普通 RAG，需要检查 Planner 是否正常选择工具。",
    )
  }

  return {
    rows,
    sortedRows,
    best,
    worst,
    fastest,
    mostToolUse,
    mostSourceGain,
    suggestions,
  }
}

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }

  return `${(size / 1024 / 1024).toFixed(1)} MB`
}




function KnowledgeBaseDetailPage() {
  const { knowledgeBaseId } = Route.useParams()
  const queryClient = useQueryClient()
  const [activeWorkspaceTab, setActiveWorkspaceTab] =
    useState<WorkspaceTab>("overview")

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [codeEvalMaxFiles, setCodeEvalMaxFiles] = useState(20)
  const [codeEvalMaxSymbols, setCodeEvalMaxSymbols] = useState(40)
  const [runningEvalCaseIds, setRunningEvalCaseIds] = useState<Set<string>>(
    () => new Set(),
  )
  const [selectedRepositoryZip, setSelectedRepositoryZip] = useState<File | null>(null)
  const [expandedDocumentId, setExpandedDocumentId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [chatQuestion, setChatQuestion] = useState("")
  const [semanticQuery, setSemanticQuery] = useState("")
  const [ragRunKeyword, setRagRunKeyword] = useState("")
  const [evalQuestion, setEvalQuestion] = useState("")
  const [evalKeywords, setEvalKeywords] = useState("")
  const [evalSourceFilename, setEvalSourceFilename] = useState("")
  const [evalNote, setEvalNote] = useState("")
  const [evalCaseRunErrors, setEvalCaseRunErrors] = useState<
    Record<string, unknown>
  >({})
  const [ragTopK, setRagTopK] = useState(5)
  const [ragSemanticWeight, setRagSemanticWeight] = useState(0.75)
  const [ragKeywordWeight, setRagKeywordWeight] = useState(0.25)
  const [evalBatchName, setEvalBatchName] = useState("")
  const [evalBatchNote, setEvalBatchNote] = useState("")
  const [agentQuestion, setAgentQuestion] = useState("")
  const [compareQuestion, setCompareQuestion] = useState("")
  const [selectedCompareBatchId, setSelectedCompareBatchId] = useState<
    string | null
  >(null)
  const [agentParamConfig, setAgentParamConfig] = useState<AgentParamConfig>({
    topK: 5,
    maxSteps: 5,
    limit: 10,
    semanticWeight: 0.75,
    keywordWeight: 0.25,
  })
  const [appliedAgentConfig, setAppliedAgentConfig] =
    useState<AppliedAgentConfig>({
      topK: 5,
      maxSteps: 5,
      semanticWeight: 0.75,
      keywordWeight: 0.25,
    })
  const [agentRunKeyword, setAgentRunKeyword] = useState("")
  const [expandedAgentRunIds, setExpandedAgentRunIds] = useState<string[]>([])
  const [failureCaseTypeFilter, setFailureCaseTypeFilter] = useState("")
  const [failureBatchIdFilter, setFailureBatchIdFilter] = useState("")
  const [experimentReportMarkdown, setExperimentReportMarkdown] = useState("")
  const [baselineCompareBatchId, setBaselineCompareBatchId] = useState("")
  const [optimizedCompareBatchId, setOptimizedCompareBatchId] = useState("")
  const [presetName, setPresetName] = useState("")
  const [presetNote, setPresetNote] = useState("")
  const [evalRunKeyword, setEvalRunKeyword] = useState("")
  const [evalFailedOnly, setEvalFailedOnly] = useState(false)
  const [evalFailureType, setEvalFailureType] = useState<
    "all" | "keyword" | "source" | "error" | "zero"
  >("all")
  type ExpandableSectionKey =
  | "documents"
  | "ragHistory"
  | "agentHistory"
  | "compareHistory"
  | "evalRuns"
  | "agentParamTuning"

  const [expandedSections, setExpandedSections] = useState<
    Record<ExpandableSectionKey, boolean>
  >({
    documents: false,
    ragHistory: false,
    agentHistory: false,
    compareHistory: false,
    evalRuns: false,
    agentParamTuning: false,
  })

  const toggleSection = (sectionKey: ExpandableSectionKey) => {
    setExpandedSections((previous) => ({
      ...previous,
      [sectionKey]: !previous[sectionKey],
    }))
  }

  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const repositoryZipInputRef = useRef<HTMLInputElement | null>(null)

  const {
    data: knowledgeBase,
    isPending: isKnowledgeBasePending,
    isError: isKnowledgeBaseError,
  } = useQuery({
    queryKey: ["knowledge-base", knowledgeBaseId],
    queryFn: () =>
      KnowledgeBasesService.readKnowledgeBase({
        id: knowledgeBaseId,
      }),
  })

  const {
    data: documents,
    isPending: isDocumentsPending,
    isError: isDocumentsError,
  } = useQuery({
    queryKey: ["documents", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readDocumentsByKnowledgeBase({
        knowledgeBaseId,
        skip: 0,
        limit: 100,
      }),
  })

  const {
    data: chunks,
    isPending: isChunksPending,
    isError: isChunksError,
  } = useQuery({
    queryKey: ["document-chunks", expandedDocumentId],
    enabled: expandedDocumentId !== null,
    queryFn: () => {
      if (!expandedDocumentId) {
        throw new Error("Document id is required")
      }

      return DocumentsService.readDocumentChunks({
        documentId: expandedDocumentId,
        skip: 0,
        limit: 100,
      })
    },
  })

  const ragRunsQuery = useQuery({
    queryKey: ["rag-runs", knowledgeBaseId, ragRunKeyword],
    queryFn: () =>
      DocumentsService.readKnowledgeBaseRagRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword: ragRunKeyword.trim() || undefined,
      }),
    enabled: expandedSections.ragHistory,
  })

  const ragEvalCasesQuery = useQuery({
    queryKey: ["rag-eval-cases", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalCases({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
      }),
  })

  const ragEvalRunsQuery = useQuery({
    queryKey: [
      "rag-eval-runs",
      knowledgeBaseId,
      evalRunKeyword,
      evalFailedOnly,
      evalFailureType,
    ],
    queryFn: () =>
      DocumentsService.readRagEvalRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword: evalRunKeyword.trim() || undefined,
        failedOnly: evalFailedOnly || undefined,
        keywordHit: evalFailureType === "keyword" ? false : undefined,
        sourceHit: evalFailureType === "source" ? false : undefined,
        errorOnly: evalFailureType === "error" ? true : undefined,
        maxScore: evalFailureType === "zero" ? 0 : undefined,
      }),
    enabled: expandedSections.evalRuns,
  })

  const ragEvalSummaryQuery = useQuery({
    queryKey: ["rag-eval-summary", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalSummary({
        knowledgeBaseId,
        limit: 200,
      }),
  })

  const ragEvalParamGroupsQuery = useQuery({
    queryKey: ["rag-eval-param-groups", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalParamGroups({
        knowledgeBaseId,
        limit: 500,
      }),
  })


  const ragRetrievalPresetsQuery = useQuery({
    queryKey: ["rag-retrieval-presets", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagRetrievalPresets({
        knowledgeBaseId,
        skip: 0,
        limit: 50,
      }),
  })

  const ragEvalFailureAnalysisQuery = useQuery({
    queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalFailureAnalysis({
        knowledgeBaseId,
        limit: 200,
        recentLimit: 10,
      }),
  })


  const ragEvalBatchesQuery = useQuery({
    queryKey: ["rag-eval-batches", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalBatches({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
      }),
  })

  const agentRunsQuery = useQuery({
    queryKey: ["agent-runs", knowledgeBaseId, agentRunKeyword],
    queryFn: () =>
      DocumentsService.readAgentRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword: agentRunKeyword.trim() || undefined,
      }),
    enabled: expandedSections.agentHistory,
  })

  const ragAgentCompareBatchesQuery = useQuery({
    queryKey: ["rag-agent-compare-batches", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagAgentCompareBatches({
        knowledgeBaseId,
        skip: 0,
        limit: 50,
      }),
  })

  const ragAgentCompareBatchDetailQuery = useQuery({
    queryKey: ["rag-agent-compare-batch", selectedCompareBatchId],
    queryFn: () =>
      DocumentsService.readRagAgentCompareBatch({
        batchId: selectedCompareBatchId as string,
      }),
    enabled: expandedSections.compareHistory && Boolean(selectedCompareBatchId),
  })

  const agentSettingsQuery = useQuery({
    queryKey: ["knowledge-base-agent-settings", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readKnowledgeBaseAgentSettings({
        knowledgeBaseId,
      }),
  })

  const codeEvalTypeCompareSummaryQuery = useQuery({
    queryKey: ["code-eval-type-compare-summary", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.getCodeEvalTypeCompareSummary({
        knowledgeBaseId,
      }),
  })

  const ragAgentCompareFailureAnalysisQuery = useQuery({
    queryKey: ["rag-agent-compare-failure-analysis", knowledgeBaseId, failureBatchIdFilter, failureCaseTypeFilter],
    queryFn: () =>
      DocumentsService.readRagAgentCompareFailureAnalysis({
        knowledgeBaseId,
        batchId: failureBatchIdFilter || undefined,
        caseType: failureCaseTypeFilter || undefined,
        limit: 50,
      }),
  })

  const compareBatchRows = ragAgentCompareBatchesQuery.data?.data ?? []

  const baselineCompareBatch = compareBatchRows.find(
    (batch) => batch.id === baselineCompareBatchId,
  )

  const optimizedCompareBatch = compareBatchRows.find(
    (batch) => batch.id === optimizedCompareBatchId,
  )

  const optimizationCompareRows = buildOptimizationCompareRows(
    baselineCompareBatch,
    optimizedCompareBatch,
  )

  const codeAgentOptimizationAdvice = buildCodeAgentOptimizationAdvice({
    typeSummaryData: codeEvalTypeCompareSummaryQuery.data,
    failureAnalysisData: ragAgentCompareFailureAnalysisQuery.data,
  })

  useEffect(() => {
    if (!agentSettingsQuery.data) {
      return
    }

    const settings = agentSettingsQuery.data as any

    setAppliedAgentConfig({
      topK: readField<number>(settings, "top_k", "topK", 5),
      maxSteps: readField<number>(settings, "max_steps", "maxSteps", 5),
      semanticWeight: readField<number>(
        settings,
        "semantic_weight",
        "semanticWeight",
        0.75,
      ),
      keywordWeight: readField<number>(
        settings,
        "keyword_weight",
        "keywordWeight",
        0.25,
      ),
    })
  }, [agentSettingsQuery.data])

  const uploadDocumentMutation = useMutation({
    mutationFn: (file: File) =>
      DocumentsService.uploadDocument({
        knowledgeBaseId,
        formData: {
          file,
        },
      }),
    onSuccess: () => {
      setSelectedFile(null)

      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }

      queryClient.invalidateQueries({
        queryKey: ["documents", knowledgeBaseId],
      })
    },
  })

  const uploadCodeRepositoryZipMutation = useMutation({
    mutationFn: (file: File) =>
      DocumentsService.uploadCodeRepositoryZip({
        knowledgeBaseId,
        formData: {
          file,
        },
      }),
    onSuccess: () => {
      setSelectedRepositoryZip(null)

      if (repositoryZipInputRef.current) {
        repositoryZipInputRef.current.value = ""
      }

      queryClient.invalidateQueries({
        queryKey: ["documents", knowledgeBaseId],
      })
    },
  })

  const deleteDocumentMutation = useMutation({
    mutationFn: (documentId: string) =>
      DocumentsService.deleteDocument({
        documentId,
      }),
    onSuccess: () => {
      setExpandedDocumentId(null)

      queryClient.invalidateQueries({
        queryKey: ["documents", knowledgeBaseId],
      })
    },
  })

  const searchKnowledgeBaseMutation = useMutation({
    mutationFn: (query: string) =>
      DocumentsService.searchKnowledgeBaseChunks({
        knowledgeBaseId,
        requestBody: {
          query,
          limit: 10,
        },
      }),
  })

  const semanticSearchKnowledgeBaseMutation = useMutation({
    mutationFn: (query: string) =>
      DocumentsService.semanticSearchKnowledgeBaseChunks({
        knowledgeBaseId,
        requestBody: {
          query,
          top_k: 5,
        },
      }),
  })

  const backfillEmbeddingsMutation = useMutation({
    mutationFn: () =>
      DocumentsService.backfillKnowledgeBaseEmbeddings({
        knowledgeBaseId,
        requestBody: {
          limit: 20,
          retry_failed: true,
          force: false,
        },
      }),
  })

  const chatKnowledgeBaseMutation = useMutation({
    mutationFn: (question: string) => {
      const settings = getRetrievalSettings()

      return DocumentsService.chatWithKnowledgeBase({
        knowledgeBaseId,
        requestBody: {
          question,
          top_k: settings.topK,
          semantic_weight: settings.semanticWeight,
          keyword_weight: settings.keywordWeight,
        },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-runs", knowledgeBaseId],
      })
    },
  })


  const compareRagAgentMutation = useMutation({
    mutationFn: async (question: string) => {
      const settings = getRetrievalSettings()

      const [ragResult, agentResult] = await Promise.all([
        DocumentsService.chatWithKnowledgeBase({
          knowledgeBaseId,
          requestBody: {
            question,
            top_k: appliedAgentConfig.topK,
            semantic_weight: appliedAgentConfig.semanticWeight,
            keyword_weight: appliedAgentConfig.keywordWeight,
          } as any,
        }),

        DocumentsService.agentChatWithKnowledgeBase({
          knowledgeBaseId,
          requestBody: {
            question,
            top_k: appliedAgentConfig.topK,
            max_steps: appliedAgentConfig.maxSteps,
            semantic_weight: appliedAgentConfig.semanticWeight,
            keyword_weight: appliedAgentConfig.keywordWeight,
          } as any,
        }),
      ])

      return {
        ragResult,
        agentResult,
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-runs", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["agent-runs", knowledgeBaseId],
      })
    },
  })

  const deleteRagRunMutation = useMutation({
    mutationFn: (ragRunId: string) =>
      DocumentsService.deleteRagRun({
        ragRunId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-runs", knowledgeBaseId],
      })
    },
  })

  const createRagEvalCaseMutation = useMutation({
    mutationFn: () =>
      DocumentsService.createRagEvalCase({
        knowledgeBaseId,
        requestBody: {
          question: evalQuestion.trim(),
          expected_keywords: evalKeywords
            .split(/[,，\n]/)
            .map((item) => item.trim())
            .filter(Boolean),
          expected_source_filename: evalSourceFilename.trim() || null,
          note: evalNote.trim() || null,
        },
      }),
    onSuccess: () => {
      setEvalQuestion("")
      setEvalKeywords("")
      setEvalSourceFilename("")
      setEvalNote("")

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-cases", knowledgeBaseId],
      })
    },
  })

  const runRagEvalCaseMutation = useMutation({
    mutationFn: (evalCaseId: string) =>
      DocumentsService.runRagEvalCase({
        evalCaseId,
        requestBody: {
          top_k: 5,
          semantic_weight: 0.75,
          keyword_weight: 0.25,
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-runs", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-summary", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-param-groups", knowledgeBaseId],
      })
    },
  })


  const deleteRagEvalCaseMutation = useMutation({
    mutationFn: (evalCaseId: string) =>
      DocumentsService.deleteRagEvalCase({
        evalCaseId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-cases", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-runs", knowledgeBaseId],
      })
    },
  })

 const runAllRagEvalCasesMutation = useMutation({
   mutationFn: () => {
     const settings = getRetrievalSettings()

     return DocumentsService.runAllRagEvalCases({
       knowledgeBaseId,
       requestBody: {
         top_k: settings.topK,
         limit: 100,
         semantic_weight: settings.semanticWeight,
         keyword_weight: settings.keywordWeight,
         batch_name: evalBatchName.trim() || null,
         batch_note: evalBatchNote.trim() || null,
       },
     })
   },
   onSuccess: () => {
     setEvalBatchName("")
     setEvalBatchNote("")

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-runs", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-summary", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-param-groups", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-batches", knowledgeBaseId],
     })
   },
 })

 const seedCodeEvalCasesMutation = useMutation({
   mutationFn: () =>
     DocumentsService.seedCodeEvalCases({
       knowledgeBaseId,
       maxFiles: codeEvalMaxFiles,
       maxSymbols: codeEvalMaxSymbols,
     }),
   onSuccess: () => {
     queryClient.invalidateQueries({
       queryKey: ["rag-eval-cases", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-summary", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-param-groups", knowledgeBaseId],
     })
   },
 })


  const createRagRetrievalPresetMutation = useMutation({
    mutationFn: () => {
      const settings = getRetrievalSettings()

      return DocumentsService.createRagRetrievalPreset({
        knowledgeBaseId,
        requestBody: {
          name: presetName.trim(),
          top_k: settings.topK,
          semantic_weight: settings.semanticWeight,
          keyword_weight: settings.keywordWeight,
          note: presetNote.trim() || null,
        },
      })
    },
    onSuccess: () => {
      setPresetName("")
      setPresetNote("")

      queryClient.invalidateQueries({
        queryKey: ["rag-retrieval-presets", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-param-groups", knowledgeBaseId],
      })
    },
  })

  const deleteRagRetrievalPresetMutation = useMutation({
    mutationFn: (presetId: string) =>
      DocumentsService.deleteRagRetrievalPreset({
        presetId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-retrieval-presets", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-param-groups", knowledgeBaseId],
      })
    },
  })

  const getRetrievalSettings = () => {
    const topK = Math.min(Math.max(Number(ragTopK) || 5, 1), 20)
    const semanticWeight = Math.min(
      Math.max(Number(ragSemanticWeight) || 0, 0),
      1,
    )
    const keywordWeight = Math.min(
      Math.max(Number(ragKeywordWeight) || 0, 0),
      1,
    )

    if (semanticWeight + keywordWeight <= 0) {
      return {
        topK,
        semanticWeight: 0.75,
        keywordWeight: 0.25,
      }
    }

    return {
      topK,
      semanticWeight,
      keywordWeight,
    }
  }


  const deleteRagEvalBatchMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.deleteRagEvalBatch({
        batchId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-batches", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-runs", knowledgeBaseId],
      })
    },
  })

  const agentChatMutation = useMutation({
    mutationFn: (question: string) => {
      const settings = getRetrievalSettings()

      return DocumentsService.agentChatWithKnowledgeBase({
        knowledgeBaseId,
        requestBody: {
          question,
          top_k: appliedAgentConfig.topK,
          max_steps: appliedAgentConfig.maxSteps,
          semantic_weight: appliedAgentConfig.semanticWeight,
          keyword_weight: appliedAgentConfig.keywordWeight,
        } as any,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["agent-runs", knowledgeBaseId],
      })
    },
  })

  const deleteAgentRunMutation = useMutation({
    mutationFn: (agentRunId: string) =>
      DocumentsService.deleteAgentRun({
        agentRunId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["agent-runs", knowledgeBaseId],
      })
    },
  })


  const runRagAgentCompareEvalMutation = useMutation({
    mutationFn: () =>
      DocumentsService.runRagAgentCompareEval({
        knowledgeBaseId,
        requestBody: {
          name: `RAG vs Agent Compare ${new Date().toLocaleString()}`,
          top_k: appliedAgentConfig.topK,
          max_steps: appliedAgentConfig.maxSteps,
          limit: 10,
          semantic_weight: appliedAgentConfig.semanticWeight,
          keyword_weight: appliedAgentConfig.keywordWeight,
        } as any,
      }),
    onSuccess: (data) => {
      const compareBatchId = readField<string | null>(
        data as any,
        "compare_batch_id",
        "compareBatchId",
        null,
      )

      if (compareBatchId) {
        setSelectedCompareBatchId(compareBatchId)
        setFailureBatchIdFilter(compareBatchId)
        setOptimizedCompareBatchId(compareBatchId)
      }

      queryClient.invalidateQueries({
        queryKey: ["rag-agent-compare-batches", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["code-eval-type-compare-summary", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-agent-compare-failure-analysis", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: [
          "rag-agent-compare-failure-analysis",
          knowledgeBaseId,
          failureBatchIdFilter,
          failureCaseTypeFilter,
        ],
      })
    },
  })


  const runAgentParamTuningMutation = useMutation({
    mutationFn: async () => {
      const results = []

      for (const preset of AGENT_PARAM_PRESETS) {
        const result = await DocumentsService.runRagAgentCompareEval({
          knowledgeBaseId,
          requestBody: {
            name: `参数优化 - ${preset.name} - ${new Date().toLocaleString()}`,
            top_k: preset.topK,
            max_steps: preset.maxSteps,
            limit: preset.limit,
            semantic_weight: preset.semanticWeight,
            keyword_weight: preset.keywordWeight,
          } as any,
        })

        results.push({
          preset,
          result,
        })
      }

      return results
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-agent-compare-batches", knowledgeBaseId],
      })
    },
  })

  const agentParamRecommendation = runAgentParamTuningMutation.data
    ? buildAgentParamRecommendation(runAgentParamTuningMutation.data)
    : null

  const deleteRagAgentCompareBatchMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.deleteRagAgentCompareBatch({
        batchId,
      }),
    onSuccess: () => {
      setSelectedCompareBatchId(null)

      queryClient.invalidateQueries({
        queryKey: ["rag-agent-compare-batches", knowledgeBaseId],
      })
    },
  })

  const updateAgentSettingsMutation = useMutation({
    mutationFn: ({
      config,
      name,
    }: {
      config: AppliedAgentConfig
      name?: string
    }) =>
      DocumentsService.updateKnowledgeBaseAgentSettings({
        knowledgeBaseId,
        requestBody: {
          top_k: config.topK,
          max_steps: config.maxSteps,
          semantic_weight: config.semanticWeight,
          keyword_weight: config.keywordWeight,
        } as any,
      }),
    onSuccess: (data, variables) => {
      const settings = data as any

      const nextConfig = {
        topK: readField<number>(settings, "top_k", "topK", variables.config.topK),
        maxSteps: readField<number>(
          settings,
          "max_steps",
          "maxSteps",
          variables.config.maxSteps,
        ),
        semanticWeight: readField<number>(
          settings,
          "semantic_weight",
          "semanticWeight",
          variables.config.semanticWeight,
        ),
        keywordWeight: readField<number>(
          settings,
          "keyword_weight",
          "keywordWeight",
          variables.config.keywordWeight,
        ),
      }

      setAppliedAgentConfig(nextConfig)

      queryClient.invalidateQueries({
        queryKey: ["knowledge-base-agent-settings", knowledgeBaseId],
      })

      alert(
        `已保存并应用 Agent 配置：${variables.name ?? "自定义配置"}\n` +
          `top_k=${nextConfig.topK}, max_steps=${nextConfig.maxSteps}, ` +
          `semantic_weight=${nextConfig.semanticWeight}, keyword_weight=${nextConfig.keywordWeight}`,
      )
    },
  })


  const exportRagAgentCompareReportMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.readRagAgentCompareBatchReport({
        batchId,
      }),
    onSuccess: (data) => {
      const report = data as any

      const filename = readField<string>(
        report,
        "filename",
        "filename",
        "rag_agent_compare_report.md",
      )

      const content = readField<string>(
        report,
        "content",
        "content",
        "",
      )

      downloadTextFile({
        filename,
        content,
      })
    },
  })

  const exportRagAgentCompareDocxReportMutation = useMutation({
  mutationFn: (batchId: string) =>
    DocumentsService.readRagAgentCompareBatchDocxReport({
      batchId,
    }),
  onSuccess: (data) => {
    const report = data as any

    const filename = readField<string>(
      report,
      "filename",
      "filename",
      "rag_agent_compare_report.docx",
    )

    const mimeType = readField<string>(
      report,
      "mime_type",
      "mimeType",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    const contentBase64 = readField<string>(
      report,
      "content_base64",
      "contentBase64",
      "",
    )

    downloadBase64File({
      filename,
      mimeType,
      contentBase64,
    })
  },
})

  const exportRagAgentComparePdfReportMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.readRagAgentCompareBatchPdfReport({
        batchId,
      }),
    onSuccess: (data) => {
      const report = data as any

      const filename = readField<string>(
        report,
        "filename",
        "filename",
        "rag_agent_compare_report.pdf",
      )

      const mimeType = readField<string>(
        report,
        "mime_type",
        "mimeType",
        "application/pdf",
      )

      const contentBase64 = readField<string>(
        report,
        "content_base64",
        "contentBase64",
        "",
      )

      downloadBase64File({
        filename,
        mimeType,
        contentBase64,
      })
    },
  })


  const exportBackendCodeAgentReportMutation = useMutation({
    mutationFn: () =>
      DocumentsService.readCodeAgentExperimentReport({
        knowledgeBaseId,
        baselineBatchId: baselineCompareBatchId,
        optimizedBatchId: optimizedCompareBatchId,
        failureLimit: 8,
      }),
    onSuccess: (data) => {
      downloadTextFile({
        filename: data.filename,
        content: data.content,
      })
    },
  })


  const handleUpload = () => {
    if (!selectedFile) {
      alert("请先选择文件")
      return
    }

    uploadDocumentMutation.mutate(selectedFile)
  }

  const handleUploadRepositoryZip = () => {
    if (!selectedRepositoryZip) {
      alert("请先选择代码仓库 zip 文件")
      return
    }

    uploadCodeRepositoryZipMutation.mutate(selectedRepositoryZip)
  }

  const handleToggleChunks = (documentId: string) => {
    if (expandedDocumentId === documentId) {
      setExpandedDocumentId(null)
      return
    }

    setExpandedDocumentId(documentId)
  }

  const handleSearch = () => {
    const query = searchQuery.trim()

    if (!query) {
      alert("请输入要检索的内容")
      return
    }

    searchKnowledgeBaseMutation.mutate(query)
  }

  const handleDeleteRagRun = (ragRunId: string) => {
    const confirmed = window.confirm("确定要删除这条 RAG 问答历史吗？")

    if (!confirmed) {
      return
    }

    deleteRagRunMutation.mutate(ragRunId)
  }

  const handleSemanticSearch = () => {
    const query = semanticQuery.trim()

    if (!query) {
      alert("请输入要语义检索的内容")
      return
    }

    semanticSearchKnowledgeBaseMutation.mutate(query)
  }

  const handleBackfillEmbeddings = () => {
    backfillEmbeddingsMutation.mutate()
  }

  const handleChat = () => {
    const question = chatQuestion.trim()

    if (!question) {
      alert("请输入要提问的内容")
      return
    }

    chatKnowledgeBaseMutation.mutate(question)
  }

  const handleAgentChat = () => {
    const question = agentQuestion.trim()

    if (!question) {
      alert("请输入 Agent 问题")
      return
    }

    agentChatMutation.mutate(question)
  }

  const handleToggleAgentRun = (agentRunId: string) => {
    setExpandedAgentRunIds((currentIds) => {
      if (currentIds.includes(agentRunId)) {
        return currentIds.filter((id) => id !== agentRunId)
      }

      return [...currentIds, agentRunId]
    })
  }

  const handleDeleteAgentRun = (agentRunId: string) => {
    const confirmed = window.confirm("确定要删除这条 Agent 历史记录吗？")

    if (!confirmed) {
      return
    }

    deleteAgentRunMutation.mutate(agentRunId)
  }

  const handleCreateRagEvalCase = () => {
    if (!evalQuestion.trim()) {
      alert("请输入评测问题")
      return
    }

    createRagEvalCaseMutation.mutate()
  }

  const handleRunRagEvalCase = async (evalCaseId: string) => {
    setRunningEvalCaseIds((previous) => {
      const next = new Set(previous)
      next.add(evalCaseId)
      return next
    })

    setEvalCaseRunErrors((previous) => {
    const next = { ...previous }
    delete next[evalCaseId]
    return next
  })

    try {
      await runRagEvalCaseMutation.mutateAsync(evalCaseId)
    } catch (error) {
      setEvalCaseRunErrors((previous) => ({
        ...previous,
        [evalCaseId]: error,
      }))
    } finally {
      setRunningEvalCaseIds((previous) => {
        const next = new Set(previous)
        next.delete(evalCaseId)
        return next
      })
    }
  }

  const handleRunAllRagEvalCases = () => {
    const confirmed = window.confirm(
      "确定要运行当前知识库下的全部评测样例吗？这可能需要等待一段时间。"
    )

    if (!confirmed) {
      return
    }

    runAllRagEvalCasesMutation.mutate()
  }


  const handleDeleteRagEvalBatch = (batchId: string) => {
    const confirmed = window.confirm(
      "确定要删除这条实验批次记录吗？对应评测结果不会删除，只会解除和该批次的关联。"
    )

    if (!confirmed) {
      return
    }

    deleteRagEvalBatchMutation.mutate(batchId)
  }

  const handleCreateRagRetrievalPreset = () => {
    if (!presetName.trim()) {
      alert("请输入参数预设名称")
      return
    }

    createRagRetrievalPresetMutation.mutate()
  }

  const handleApplyRagRetrievalPreset = (preset: {
    top_k: number
    semantic_weight: number
    keyword_weight: number
  }) => {
    setRagTopK(preset.top_k)
    setRagSemanticWeight(preset.semantic_weight)
    setRagKeywordWeight(preset.keyword_weight)
  }

  const handleDeleteRagRetrievalPreset = (presetId: string) => {
    const confirmed = window.confirm("确定要删除这个参数预设吗？")

    if (!confirmed) {
      return
    }

    deleteRagRetrievalPresetMutation.mutate(presetId)
  }


  const handleDeleteRagEvalCase = (evalCaseId: string) => {
    const confirmed = window.confirm("确定要删除这条评测样例吗？")

    if (!confirmed) {
      return
    }

    deleteRagEvalCaseMutation.mutate(evalCaseId)
  }


  const handleCompareRagAgent = () => {
    const question = compareQuestion.trim()

    if (!question) {
      alert("请输入对比问题")
      return
    }

    compareRagAgentMutation.mutate(question)
  }

  const handleApplyRecommendedAgentConfig = () => {
    if (!agentParamRecommendation) {
      alert("暂无可应用的推荐配置，请先运行 Agent 参数优化实验")
      return
    }

    const bestPreset = agentParamRecommendation.best.preset

    const nextConfig = {
      topK: bestPreset.topK,
      maxSteps: bestPreset.maxSteps,
      limit: bestPreset.limit,
      semanticWeight: bestPreset.semanticWeight,
      keywordWeight: bestPreset.keywordWeight,
    }
    setAgentParamConfig(nextConfig)

    updateAgentSettingsMutation.mutate({
    name: bestPreset.name,
    config: {
      top_k: nextConfig.topK,
      max_steps: nextConfig.maxSteps,
      semantic_weight: nextConfig.semanticWeight,
      keyword_weight: nextConfig.keywordWeight,
    },
  } as any)
}

  const handleResetAgentConfig = () => {
    updateAgentSettingsMutation.mutate({
      name: "默认配置",
      config: {
        topK: 5,
        maxSteps: 5,
        semanticWeight: 0.75,
        keywordWeight: 0.25,
      },
    })
  }

  const handleGenerateCodeAgentExperimentReport = () => {
    if (!baselineCompareBatch || !optimizedCompareBatch) {
      alert("请先在优化前后对比表中选择优化前批次和优化后批次")
      return
    }

    const markdown = buildCodeAgentExperimentReportMarkdown({
      knowledgeBase,
      baselineCompareBatch,
      optimizedCompareBatch,
      optimizationCompareRows,
      typeSummaryData: codeEvalTypeCompareSummaryQuery.data,
      failureAnalysisData: ragAgentCompareFailureAnalysisQuery.data,
      adviceList: codeAgentOptimizationAdvice,
    })

    setExperimentReportMarkdown(markdown)
  }

  const handleDownloadCodeAgentExperimentReport = () => {
    if (!experimentReportMarkdown.trim()) {
      alert("请先生成实验报告预览")
      return
    }

    const safeKnowledgeBaseName = String(knowledgeBase.name || "knowledge-base")
      .replace(/[\\/:*?"<>|]/g, "_")
      .slice(0, 50)

    downloadTextFile({
      filename: `code-rag-agent-report-${safeKnowledgeBaseName}-${new Date()
        .toISOString()
        .slice(0, 10)}.md`,
      content: experimentReportMarkdown,
    })
  }

  const handleDownload = async (documentId: string, filename: string) => {
    const token = localStorage.getItem("access_token")

    if (!token) {
      alert("请先登录")
      return
    }

    const response = await fetch(
      `${import.meta.env.VITE_API_URL}/api/v1/documents/${documentId}/download`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    if (!response.ok) {
      alert("下载失败")
      return
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)

    const link = window.document.createElement("a")
    link.href = url
    link.download = filename
    link.click()

    window.URL.revokeObjectURL(url)
  }

  if (isKnowledgeBasePending || isDocumentsPending) {
    return <div className="p-6">正在加载知识库详情...</div>
  }

  if (isKnowledgeBaseError) {
    return <div className="p-6">知识库加载失败</div>
  }

  if (isDocumentsError) {
    return <div className="p-6">文档列表加载失败</div>
  }

  if (!knowledgeBase || !documents) {
    return <div className="p-6">暂无数据</div>
  }

  return (
    <div className="min-h-screen bg-slate-50/70">
      <div className="mx-auto max-w-[1440px] space-y-6 px-4 py-6 md:px-6 lg:px-8">
        <Link
          to="/knowledge-bases"
          className="inline-flex items-center text-sm font-medium text-slate-900 transition hover:text-sky-700"
        >
          ← 返回知识库列表
        </Link>

        <header className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 space-y-2">
              <div className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700">
                Knowledge Base Workspace
              </div>
              <div>
                <h1 className="break-words text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">
                  {knowledgeBase.name}
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-900">
                  {knowledgeBase.description || "暂无描述"}
                </p>
              </div>
            </div>

            <div className="flex max-w-full flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-slate-600 bg-slate-50 px-3 py-1.5 text-slate-600">
                文档 {documents.data.length} 个
              </span>
              <span className="max-w-full truncate rounded-full border border-slate-600 bg-slate-50 px-3 py-1.5 font-mono text-slate-900">
                ID：{knowledgeBase.id}
              </span>
            </div>
          </div>
        </header>

        <nav
          className="sticky top-2 z-20 rounded-2xl border border-slate-600 bg-white/95 p-2 shadow-sm backdrop-blur"
          aria-label="知识库工作区"
        >
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {WORKSPACE_TABS.map((tab) => {
              const isActive = activeWorkspaceTab === tab.key

              return (
                <button
                  key={tab.key}
                  type="button"
                  aria-selected={isActive}
                  onClick={() => setActiveWorkspaceTab(tab.key)}
                  className={`rounded-xl px-3 py-3 text-left transition ${
                    isActive
                      ? "bg-sky-600 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <div className="text-sm font-medium">{tab.label}</div>
                  <div
                    className={`mt-1 hidden text-xs leading-5 md:block ${
                      isActive ? "text-sky-100" : "text-slate-400"
                    }`}
                  >
                    {tab.description}
                  </div>
                </button>
              )
            })}
          </div>
        </nav>

        {activeWorkspaceTab === "overview" ? (
          <div className="space-y-6">
      <div className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">上传与导入</h2>
          <p className="text-sm text-slate-900">
            支持上传 pdf、txt、md、docx 以及 py、ts、tsx、js、jsx、java、go 等代码文件。
          </p>
        </div>

        <div className="flex gap-3 items-center">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,.docx,.py,.ts,.tsx,.js,.jsx,.java,.go,.c,.cpp,.h,.hpp,.cs,.rs,.vue,.html,.css,.scss,.json,.yaml,.yml,.toml,.zip,.rar,application/zip,application/x-zip-compressed,application/x-rar-compressed,application/vnd.rar"
            onChange={(event) => {
              const file = event.target.files?.[0] || null
              setSelectedFile(file)
            }}
          />

          <button
            className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={handleUpload}
            disabled={uploadDocumentMutation.isPending}
          >
            {uploadDocumentMutation.isPending ? "上传中..." : "上传"}
          </button>
        </div>

        {selectedFile ? (
          <div className="text-sm text-slate-900">
            当前选择：{selectedFile.name}，大小：
            {formatFileSize(selectedFile.size)}
          </div>
        ) : null}

        {uploadDocumentMutation.isError ? (
          <div className="text-sm text-rose-600">
            上传失败，请检查文件类型、文件大小或登录状态。
          </div>
        ) : null}
        <div className="border-t pt-4 space-y-3">
          <div>
            <h3 className="font-medium text-slate-900">导入代码仓库</h3>
            <p className="text-sm text-slate-900">
              支持上传项目 zip，后端会自动忽略 node_modules、.git、dist、build 等目录，
              并解析其中的 py、ts、tsx、js、java、go 等代码文件。
            </p>
          </div>

          <div className="flex gap-3 items-center">
            <input
              ref={repositoryZipInputRef}
              type="file"
              accept=".zip,.rar,application/zip,application/x-rar-compressed,application/vnd.rar"
              onChange={(event) => {
                const file = event.target.files?.[0] || null
                setSelectedRepositoryZip(file)
              }}
            />

            <button
              className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={handleUploadRepositoryZip}
              disabled={uploadCodeRepositoryZipMutation.isPending}
            >
              {uploadCodeRepositoryZipMutation.isPending
                ? "解析仓库中..."
                : "上传代码仓库"}
            </button>
          </div>

          {selectedRepositoryZip ? (
            <div className="text-sm text-slate-900">
              当前选择：{selectedRepositoryZip.name}，大小：
              {formatFileSize(selectedRepositoryZip.size)}
            </div>
          ) : null}

          {uploadCodeRepositoryZipMutation.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              上传代码仓库失败：
              {JSON.stringify(uploadCodeRepositoryZipMutation.error, null, 2)}
            </div>
          ) : null}

          {uploadCodeRepositoryZipMutation.data ? (
            <div className="text-sm text-emerald-700">
              代码仓库解析完成，共导入 {uploadCodeRepositoryZipMutation.data.count} 个代码文件。
            </div>
          ) : null}
        </div>
      </div>

          </div>
        ) : null}

        {activeWorkspaceTab === "review" ? (
          <CodeReviewWorkbench knowledgeBaseId={knowledgeBaseId} />
        ) : null}

        {activeWorkspaceTab === "chat" ? (
          <div className="space-y-6">
      <div className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">知识库检索测试</h2>
          <p className="text-sm text-slate-900">
            这里先用关键词检索 DocumentChunk，后面可以替换成向量检索。
          </p>
        </div>

        <div className="flex gap-3">
          <input
            className="flex-1 rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="请输入关键词，例如：FastAPI 路由"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleSearch()
              }
            }}
          />

          <button
            className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={handleSearch}
            disabled={searchKnowledgeBaseMutation.isPending}
          >
            {searchKnowledgeBaseMutation.isPending ? "检索中..." : "检索"}
          </button>
        </div>

        {searchKnowledgeBaseMutation.isError ? (
          <div className="text-sm text-rose-600">检索失败，请检查后端接口。</div>
        ) : null}

        {searchKnowledgeBaseMutation.data ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-900">
              共找到 {searchKnowledgeBaseMutation.data.count} 条结果，当前展示{" "}
              {searchKnowledgeBaseMutation.data.data.length} 条。
            </div>

            {searchKnowledgeBaseMutation.data.data.length === 0 ? (
              <div className="text-sm text-slate-900">暂无匹配结果</div>
            ) : (
              searchKnowledgeBaseMutation.data.data.map((result) => (
                <div
                  key={result.chunk_id}
                  className="border border-slate-600 rounded p-3 bg-slate-50 text-slate-900 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">
                      来源文件：{result.original_filename} ｜ Chunk{" "}
                      {result.chunk_index}
                    </div>

                    <div className="text-xs text-slate-900">
                      命中次数：{result.match_count} ｜ 长度：
                      {result.content_length}
                    </div>
                  </div>

                  <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                    {result.content}
                  </pre>
                </div>
              ))
            )}
          </div>
        ) : null}
      </div>

      <div className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">语义检索测试</h2>
          <p className="text-sm text-slate-900">
            这里会把你的问题转成 embedding，然后和 DocumentChunk 的 embedding
            计算相似度，返回语义最接近的 chunk。
          </p>
        </div>

        <div className="flex gap-3">
          <input
            className="flex-1 rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="请输入问题，例如：用户登录状态应该怎么保存？"
            value={semanticQuery}
            onChange={(event) => setSemanticQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleSemanticSearch()
              }
            }}
          />

          <button
            className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={handleSemanticSearch}
            disabled={semanticSearchKnowledgeBaseMutation.isPending}
          >
            {semanticSearchKnowledgeBaseMutation.isPending
              ? "检索中..."
              : "语义检索"}
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button
            className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={handleBackfillEmbeddings}
            disabled={backfillEmbeddingsMutation.isPending}
          >
            {backfillEmbeddingsMutation.isPending
              ? "回填中..."
              : "回填旧数据 Embedding"}
          </button>

          <span className="text-xs text-slate-900">
            如果旧文档没有 embedding，可以先点击这里回填。
          </span>
        </div>

        {backfillEmbeddingsMutation.isError ? (
          <div className="text-sm text-rose-600">
            Embedding 回填失败，请检查后端日志或 API Key。
          </div>
        ) : null}

        {backfillEmbeddingsMutation.data ? (
          <div className="text-sm text-slate-900">
            回填结果：本次处理 {backfillEmbeddingsMutation.data.processed} 个，
            成功 {backfillEmbeddingsMutation.data.embedded} 个，失败{" "}
            {backfillEmbeddingsMutation.data.failed} 个，剩余{" "}
            {backfillEmbeddingsMutation.data.remaining} 个。模型：
            {backfillEmbeddingsMutation.data.model}
          </div>
        ) : null}

        {semanticSearchKnowledgeBaseMutation.isError ? (
          <div className="text-sm text-rose-600">
            语义检索失败，请检查后端 semantic-search 接口或 embedding 配置。
          </div>
        ) : null}

        {semanticSearchKnowledgeBaseMutation.data ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-900">
              共找到 {semanticSearchKnowledgeBaseMutation.data.count}
              条语义检索结果。
            </div>

            {semanticSearchKnowledgeBaseMutation.data.data.length === 0 ? (
              <div className="text-sm text-slate-900">
                暂无语义检索结果。可能是当前知识库还没有生成 embedding。
              </div>
            ) : (
              semanticSearchKnowledgeBaseMutation.data.data.map((result) => (
                <div
                  key={result.chunk_id}
                  className="border border-slate-600 rounded p-3 bg-slate-50 text-slate-900 space-y-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium">
                      来源文件：{result.original_filename} ｜ Chunk{" "}
                      {result.chunk_index}
                    </div>

                    <div className="text-xs text-slate-900">
                      相似度：{result.similarity.toFixed(4)} ｜ 长度：
                      {result.content_length}
                    </div>
                  </div>

                  <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                    {result.content}
                  </pre>
                </div>
              ))
            )}
          </div>
        ) : null}
      </div>

      <div className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">RAG 问答测试</h2>
          <p className="text-sm text-slate-900">
            这里会先从当前知识库检索相关 chunk，再基于检索结果生成回答。
            当前版本是 RAG Chat v0，先返回资料型回答，后续可以接入大模型。
          </p>
        </div>

        <div className="flex gap-3">
          <input
            className="flex-1 rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="请输入问题，例如：这份文档主要讲了什么？"
            value={chatQuestion}
            onChange={(event) => setChatQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleChat()
              }
            }}
          />

          <button
            className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={handleChat}
            disabled={chatKnowledgeBaseMutation.isPending}
          >
            {chatKnowledgeBaseMutation.isPending ? "回答中..." : "提问"}
          </button>
        </div>

        {chatKnowledgeBaseMutation.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            问答失败：{JSON.stringify(chatKnowledgeBaseMutation.error, null, 2)}
          </div>
        ) : null}

        {chatKnowledgeBaseMutation.data ? (
          <div className="space-y-4">
            <div className="border border-slate-600 rounded p-4 bg-slate-50 text-slate-900 space-y-3">
              <div className="font-medium">回答</div>

              <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                {chatKnowledgeBaseMutation.data.answer}
              </pre>
            </div>

            <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
              <div className="font-medium">引用来源</div>

              {chatKnowledgeBaseMutation.data.sources.length === 0 ? (
                <div className="text-sm text-slate-900">
                  暂无引用来源。说明当前知识库没有检索到相关 chunk。
                </div>
              ) : (
                chatKnowledgeBaseMutation.data.sources.map((source) => (
                  <div
                    key={source.chunk_id}
                    className="border border-slate-600 rounded p-3 bg-slate-50 text-slate-900 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium">
                        来源文件：{source.original_filename} ｜ Chunk{" "}
                        {source.chunk_index}
                      </div>

                      <div className="text-xs text-slate-900">
                        {source.retrieval_type === "hybrid" ? (
                          <>
                            检索方式：混合检索 ｜ 相似度：
                            {source.similarity?.toFixed(4)} ｜ 关键词命中：
                            {source.match_count} ｜ 长度：{source.content_length}
                          </>
                        ) : source.retrieval_type === "semantic" ? (
                          <>
                            检索方式：语义检索 ｜ 相似度：
                            {source.similarity?.toFixed(4)} ｜ 长度：{source.content_length}
                          </>
                        ) : (
                          <>
                            检索方式：关键词检索 ｜ 命中次数：{source.match_count} ｜ 长度：
                            {source.content_length}
                          </>
                        )}
                      </div>
                    </div>

                    <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                      {source.content}
                    </pre>
                  </div>
                ))
              )}
            </div>

            <div className="border rounded p-4 space-y-2">
              <div className="font-medium">执行过程 Trace</div>

              <div className="text-sm text-slate-900">
                {chatKnowledgeBaseMutation.data.trace.join(" → ")}
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <CollapsibleSection
        title="RAG 问答历史"
        description="查看普通 RAG Chat 的历史问题、回答、sources 和 trace。"
        isOpen={expandedSections.ragHistory}
        onToggle={() => toggleSection("ragHistory")}
      >
        <div className="flex justify-end">

          <button
            className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={() =>
              queryClient.invalidateQueries({
                queryKey: ["rag-runs", knowledgeBaseId],
              })
            }
          >
            刷新历史
          </button>
        </div>

        <div className="flex gap-3">
          <input
            className="flex-1 rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="搜索历史记录，例如：FastAPI、JWT、登录、hybrid"
            value={ragRunKeyword}
            onChange={(event) => setRagRunKeyword(event.target.value)}
          />

          {ragRunKeyword.trim() ? (
            <button
              className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() => setRagRunKeyword("")}
            >
              清空
            </button>
          ) : null}
        </div>

        {deleteRagRunMutation.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            删除失败：
            {JSON.stringify(deleteRagRunMutation.error, null, 2)}
          </div>
        ) : null}

        {ragRunsQuery.isLoading ? (
          <div className="text-sm text-slate-900">正在加载问答历史...</div>
        ) : null}

        {ragRunsQuery.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            问答历史加载失败：
            {JSON.stringify(ragRunsQuery.error, null, 2)}
          </div>
        ) : null}

        {ragRunsQuery.data ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-900">
              共 {ragRunsQuery.data.count} 条记录，当前展示{" "}
              {ragRunsQuery.data.data.length} 条。
            </div>

            {ragRunsQuery.data.data.length === 0 ? (
              <div className="text-sm text-slate-900">
                暂无问答历史。你可以先在上面的 RAG 问答测试里提一个问题。
              </div>
            ) : (
              ragRunsQuery.data.data.map((run) => (
                <div
                  key={run.id}
                  className="border border-slate-600 rounded p-4 bg-slate-50 text-slate-900 space-y-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium">问题：{run.question}</div>

                    <div className="flex items-center gap-3">
                      <div className="text-xs text-slate-900">
                        检索方式：{run.retrieval_type} ｜ 耗时：
                        {run.latency_ms ?? "-"} ms
                      </div>

                      <button
                        className="border border-rose-200 text-rose-600 rounded px-2 py-1 text-xs"
                        onClick={() => handleDeleteRagRun(run.id)}
                        disabled={deleteRagRunMutation.isPending}
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="text-sm font-medium text-slate-700">回答</div>
                    <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                      {run.answer}
                    </pre>
                  </div>

                  <details className="space-y-2">
                    <summary className="cursor-pointer text-sm text-slate-600">
                      查看引用来源（{run.sources.length}）
                    </summary>

                    <div className="space-y-2 pt-2">
                      {run.sources.length === 0 ? (
                        <div className="text-sm text-slate-900">
                          当前记录没有引用来源。
                        </div>
                      ) : (
                        run.sources.map((source) => (
                          <div
                            key={source.chunk_id}
                            className="border border-slate-600 rounded p-3 bg-white text-slate-900 space-y-2"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="text-sm font-medium">
                                来源文件：{source.original_filename} ｜ Chunk{" "}
                                {source.chunk_index}
                              </div>

                              <div className="text-xs text-slate-900">
                                {source.retrieval_type === "hybrid" ? (
                                  <>
                                    混合检索 ｜ 相似度：
                                    {source.similarity?.toFixed(4)} ｜ 关键词命中：
                                    {source.match_count} ｜ 长度：
                                    {source.content_length}
                                  </>
                                ) : source.retrieval_type === "semantic" ? (
                                  <>
                                    语义检索 ｜ 相似度：
                                    {source.similarity?.toFixed(4)} ｜ 长度：
                                    {source.content_length}
                                  </>
                                ) : (
                                  <>
                                    关键词检索 ｜ 命中次数：{source.match_count} ｜
                                    长度：{source.content_length}
                                  </>
                                )}
                              </div>
                            </div>

                            <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                              {source.content}
                            </pre>
                          </div>
                        ))
                      )}
                    </div>
                  </details>

                  <details>
                    <summary className="cursor-pointer text-sm text-slate-600">
                      查看执行过程 Trace
                    </summary>

                    <div className="pt-2 text-sm text-slate-900">
                      {run.trace.length > 0 ? run.trace.join(" → ") : "暂无 trace"}
                    </div>
                  </details>

                  {run.created_at ? (
                    <div className="text-xs text-slate-900">
                      创建时间：{new Date(run.created_at).toLocaleString()}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        ) : null}
      </CollapsibleSection>

      <div className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Agent Chat 测试区</h2>
          <p className="text-sm text-slate-900">
            Agent 会根据问题调用工具，例如查看文档列表、检索知识库，再生成最终回答。
          </p>
        </div>

        <div className="space-y-2">
          <textarea
            className="min-h-[110px] w-full rounded-xl border border-slate-600 bg-white px-3 py-3 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="请输入 Agent 问题，例如：这个知识库有哪些文档？或者：请总结这个知识库主要讲了什么"
            value={agentQuestion}
            onChange={(event) => setAgentQuestion(event.target.value)}
          />

          <div className="flex items-center gap-2">
            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={handleAgentChat}
              disabled={agentChatMutation.isPending}
            >
              {agentChatMutation.isPending ? "Agent 思考中..." : "发送给 Agent"}
            </button>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() => setAgentQuestion("这个知识库有哪些文档？")}
            >
              示例：查看文档
            </button>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() => setAgentQuestion("请总结一下这个知识库主要讲了什么")}
            >
              示例：总结知识库
            </button>
          </div>
        </div>

        {agentChatMutation.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            Agent 调用失败：
            {JSON.stringify(agentChatMutation.error, null, 2)}
          </div>
        ) : null}

        {agentChatMutation.data ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-600 bg-white p-3 space-y-2">
              <h3 className="text-base font-semibold">Agent 最终回答</h3>
              <div className="text-sm whitespace-pre-wrap">
                {agentChatMutation.data.answer}
              </div>
            </div>

            <div className="rounded-xl border border-slate-600 bg-white p-3 space-y-2">
              <h3 className="text-base font-semibold">工具调用过程</h3>

              {agentChatMutation.data.tool_calls.length === 0 ? (
                <div className="text-sm text-slate-900">暂无工具调用。</div>
              ) : (
                <div className="space-y-3">
                  {agentChatMutation.data.tool_calls.map((toolCall, index) => (
                    <div
                      key={`${toolCall.tool_name}-${index}`}
                      className="border border-slate-600 rounded p-3 space-y-2"
                    >
                      <div className="text-sm font-medium">
                        {index + 1}. {toolCall.tool_name}
                      </div>

                      <div className="text-xs text-slate-900 whitespace-pre-wrap">
                        参数：
                        {JSON.stringify(toolCall.arguments, null, 2)}
                      </div>

                      <div className="text-xs text-slate-900">
                        状态：{toolCall.success ? "成功" : "失败"}
                      </div>

                      <div className="text-sm whitespace-pre-wrap">
                        {toolCall.observation}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-600 bg-white p-3 space-y-2">
              <h3 className="text-base font-semibold">Agent Sources</h3>

              {agentChatMutation.data.sources.length === 0 ? (
                <div className="text-sm text-slate-900">暂无来源资料。</div>
              ) : (
                <div className="space-y-3">
                  {agentChatMutation.data.sources.map((source, index) => (
                    <div
                      key={source.chunk_id}
                      className="border border-slate-600 rounded p-3 space-y-2"
                    >
                      <div className="text-sm font-medium">
                        [{index + 1}] {source.original_filename}
                      </div>

                      <div className="text-xs text-slate-900">
                        chunk_index：{source.chunk_index} ｜ content_length：
                        {source.content_length} ｜ match_count：
                        {source.match_count} ｜ similarity：
                        {source.similarity === null || source.similarity === undefined
                          ? "-"
                          : source.similarity.toFixed(4)}
                      </div>

                      <div className="text-sm whitespace-pre-wrap">
                        {source.content}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-600 bg-white p-3 space-y-2">
              <h3 className="text-base font-semibold">Agent Trace</h3>

              {agentChatMutation.data.trace.length === 0 ? (
                <div className="text-sm text-slate-900">暂无 trace。</div>
              ) : (
                <ol className="list-decimal list-inside text-sm space-y-1">
                  {agentChatMutation.data.trace.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        ) : null}
      </div>

      <CollapsibleSection
        title="Agent 历史记录"
        description="查看 Agent Chat 的历史问题、回答、工具调用链、sources 和 trace。"
        isOpen={expandedSections.agentHistory}
        onToggle={() => toggleSection("agentHistory")}
      >
        <div className="flex justify-end">

          <button
            className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={() =>
              queryClient.invalidateQueries({
                queryKey: ["agent-runs", knowledgeBaseId],
              })
            }
          >
            刷新历史
          </button>
        </div>

        <div className="flex gap-2">
          <input
            className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="搜索 Agent 历史，例如：FastAPI / embedding / RAG"
            value={agentRunKeyword}
            onChange={(event) => setAgentRunKeyword(event.target.value)}
          />

          <button
            className="border rounded px-3 py-2 text-sm"
            onClick={() =>
              queryClient.invalidateQueries({
                queryKey: ["agent-runs", knowledgeBaseId, agentRunKeyword],
              })
            }
          >
            搜索
          </button>

          <button
            className="border rounded px-3 py-2 text-sm"
            onClick={() => setAgentRunKeyword("")}
          >
            清空
          </button>
        </div>

        {agentRunsQuery.isLoading ? (
          <div className="text-sm text-slate-900">正在加载 Agent 历史记录...</div>
        ) : null}

        {agentRunsQuery.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            Agent 历史加载失败：
            {JSON.stringify(agentRunsQuery.error, null, 2)}
          </div>
        ) : null}

        {deleteAgentRunMutation.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            删除 Agent 历史失败：
            {JSON.stringify(deleteAgentRunMutation.error, null, 2)}
          </div>
        ) : null}

        {agentRunsQuery.data ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-900">
              共 {agentRunsQuery.data.count} 条 Agent 历史记录。
            </div>

            {agentRunsQuery.data.data.length === 0 ? (
              <div className="text-sm text-slate-900">
                暂无 Agent 历史记录。可以先在 Agent Chat 测试区提问。
              </div>
            ) : (
              agentRunsQuery.data.data.map((run) => {
                const expanded = expandedAgentRunIds.includes(run.id)

                return (
                  <div
                    key={run.id}
                    className="border border-slate-600 rounded p-3 space-y-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="text-sm font-semibold">
                          {run.question}
                        </div>

                        <div className="text-xs text-slate-900">
                          top_k={run.top_k} ｜ max_steps={run.max_steps} ｜ S=
                          {run.semantic_weight} ｜ K={run.keyword_weight} ｜ 耗时：
                          {run.latency_ms === null || run.latency_ms === undefined
                            ? "-"
                            : `${run.latency_ms} ms`}
                        </div>

                        <div className="text-xs text-slate-900">
                          创建时间：
                          {run.created_at
                            ? new Date(run.created_at).toLocaleString()
                            : "-"}
                        </div>

                        {run.error_message ? (
                          <div className="text-xs text-rose-600">
                            错误：{run.error_message}
                          </div>
                        ) : null}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          className="rounded-md border border-slate-600 bg-white px-2 py-1 text-xs font-medium text-slate-600 transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                          onClick={() => handleToggleAgentRun(run.id)}
                        >
                          {expanded ? "收起" : "展开"}
                        </button>

                        <button
                          className="border border-rose-200 text-rose-600 rounded px-2 py-1 text-xs"
                          onClick={() => handleDeleteAgentRun(run.id)}
                          disabled={deleteAgentRunMutation.isPending}
                        >
                          删除
                        </button>
                      </div>
                    </div>

                    <div className="text-sm whitespace-pre-wrap border-t pt-3">
                      {run.answer.length > 300 && !expanded
                        ? `${run.answer.slice(0, 300)}...`
                        : run.answer}
                    </div>

                    {expanded ? (
                      <div className="space-y-3 border-t pt-3">
                        <div className="space-y-2">
                          <h3 className="text-sm font-semibold">工具调用过程</h3>

                          {run.tool_calls.length === 0 ? (
                            <div className="text-sm text-slate-900">
                              暂无工具调用。
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {run.tool_calls.map((toolCall, index) => (
                                <div
                                  key={`${run.id}-${toolCall.tool_name}-${index}`}
                                  className="border border-slate-600 rounded p-3 space-y-2"
                                >
                                  <div className="text-sm font-medium">
                                    {index + 1}. {toolCall.tool_name}
                                  </div>

                                  <div className="text-xs text-slate-900 whitespace-pre-wrap">
                                    参数：
                                    {JSON.stringify(toolCall.arguments, null, 2)}
                                  </div>

                                  <div className="text-xs text-slate-900">
                                    状态：{toolCall.success ? "成功" : "失败"}
                                  </div>

                                  <div className="text-sm whitespace-pre-wrap">
                                    {toolCall.observation}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          <h3 className="text-sm font-semibold">Sources</h3>

                          {run.sources.length === 0 ? (
                            <div className="text-sm text-slate-900">
                              暂无来源资料。
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {run.sources.map((source, index) => (
                                <div
                                  key={`${run.id}-${source.chunk_id}`}
                                  className="border border-slate-600 rounded p-3 space-y-2"
                                >
                                  <div className="text-sm font-medium">
                                    [{index + 1}] {source.original_filename}
                                  </div>

                                  <div className="text-xs text-slate-900">
                                    chunk_index：{source.chunk_index} ｜ length：
                                    {source.content_length} ｜ match_count：
                                    {source.match_count} ｜ similarity：
                                    {source.similarity === null ||
                                    source.similarity === undefined
                                      ? "-"
                                      : source.similarity.toFixed(4)}
                                  </div>

                                  <div className="text-sm whitespace-pre-wrap">
                                    {source.content}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          <h3 className="text-sm font-semibold">Trace</h3>

                          {run.trace.length === 0 ? (
                            <div className="text-sm text-slate-900">暂无 trace。</div>
                          ) : (
                            <ol className="list-decimal list-inside text-sm space-y-1">
                              {run.trace.map((item, index) => (
                                <li key={`${run.id}-${item}-${index}`}>{item}</li>
                              ))}
                            </ol>
                          )}
                        </div>
                      </div>
                    ) : null}
                  </div>
                )
              })
            )}
          </div>
        ) : null}
      </CollapsibleSection>

      <div className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">RAG vs Agent 对比测试</h2>
          <p className="text-sm text-slate-900">
            输入同一个问题，同时调用普通 RAG 和 Agent，比较回答、来源、工具调用和耗时。
          </p>
        </div>

        <div className="space-y-2">
          <textarea
            className="min-h-[110px] w-full rounded-xl border border-slate-600 bg-white px-3 py-3 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="请输入对比问题，例如：请详细总结一下这个知识库主要讲了什么"
            value={compareQuestion}
            onChange={(event) => setCompareQuestion(event.target.value)}
          />

          <div className="flex flex-wrap items-center gap-2">
            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={handleCompareRagAgent}
              disabled={compareRagAgentMutation.isPending}
            >
              {compareRagAgentMutation.isPending
                ? "对比运行中..."
                : "同时运行 RAG 和 Agent"}
            </button>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                setCompareQuestion("请详细总结一下这个知识库主要讲了什么")
              }
            >
              示例：总结知识库
            </button>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                setCompareQuestion("FastAPI 的接口参数是怎么校验的？")
              }
            >
              示例：具体问题
            </button>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                setCompareQuestion("总结一下最近上传的文档主要讲了什么")
              }
            >
              示例：总结文档
            </button>
          </div>
        </div>

        {compareRagAgentMutation.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            对比运行失败：
            {JSON.stringify(compareRagAgentMutation.error, null, 2)}
          </div>
        ) : null}

        {compareRagAgentMutation.data ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="rounded-xl border border-slate-600 bg-white p-3 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold">普通 RAG</h3>

                <div className="text-xs text-slate-900">
                  耗时：
                  {compareRagAgentMutation.data.ragResult.latency_ms === null ||
                  compareRagAgentMutation.data.ragResult.latency_ms === undefined
                    ? "-"
                    : `${compareRagAgentMutation.data.ragResult.latency_ms} ms`}
                </div>
              </div>

              <div className="text-sm whitespace-pre-wrap border rounded p-3">
                {compareRagAgentMutation.data.ragResult.answer}
              </div>

              <div className="text-xs text-slate-900">
                Sources 数量：
                {compareRagAgentMutation.data.ragResult.sources.length}
              </div>

              <details className="rounded-xl border border-slate-600 bg-white p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  查看 RAG Sources
                </summary>

                <div className="space-y-3 mt-3">
                  {compareRagAgentMutation.data.ragResult.sources.length === 0 ? (
                    <div className="text-sm text-slate-900">暂无来源资料。</div>
                  ) : (
                    compareRagAgentMutation.data.ragResult.sources.map(
                      (source, index) => (
                        <div
                          key={source.chunk_id}
                          className="border border-slate-600 rounded p-3 space-y-2"
                        >
                          <div className="text-sm font-medium">
                            [{index + 1}] {source.original_filename}
                          </div>

                          <div className="text-xs text-slate-900">
                            chunk_index：{source.chunk_index} ｜ match_count：
                            {source.match_count} ｜ similarity：
                            {source.similarity === null ||
                            source.similarity === undefined
                              ? "-"
                              : source.similarity.toFixed(4)}
                          </div>

                          <div className="text-sm whitespace-pre-wrap">
                            {source.content}
                          </div>
                        </div>
                      ),
                    )
                  )}
                </div>
              </details>

              <details className="rounded-xl border border-slate-600 bg-white p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  查看 RAG Trace
                </summary>

                <ol className="list-decimal list-inside text-sm space-y-1 mt-3">
                  {compareRagAgentMutation.data.ragResult.trace.map(
                    (item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ),
                  )}
                </ol>
              </details>
            </div>

            <div className="rounded-xl border border-slate-600 bg-white p-3 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold">Agent</h3>

                <div className="text-xs text-slate-900">
                  耗时：
                  {compareRagAgentMutation.data.agentResult.latency_ms === null ||
                  compareRagAgentMutation.data.agentResult.latency_ms === undefined
                    ? "-"
                    : `${compareRagAgentMutation.data.agentResult.latency_ms} ms`}
                </div>
              </div>

              <div className="text-sm whitespace-pre-wrap border rounded p-3">
                {compareRagAgentMutation.data.agentResult.answer}
              </div>

              <div className="text-xs text-slate-900">
                Sources 数量：
                {compareRagAgentMutation.data.agentResult.sources.length} ｜ 工具调用数量：
                {compareRagAgentMutation.data.agentResult.tool_calls.length}
              </div>

              <details className="rounded-xl border border-slate-600 bg-white p-3" open>
                <summary className="cursor-pointer text-sm font-medium">
                  查看 Agent 工具调用
                </summary>

                <div className="space-y-3 mt-3">
                  {compareRagAgentMutation.data.agentResult.tool_calls.length ===
                  0 ? (
                    <div className="text-sm text-slate-900">暂无工具调用。</div>
                  ) : (
                    compareRagAgentMutation.data.agentResult.tool_calls.map(
                      (toolCall, index) => (
                        <div
                          key={`${toolCall.tool_name}-${index}`}
                          className="border border-slate-600 rounded p-3 space-y-2"
                        >
                          <div className="text-sm font-medium">
                            {index + 1}. {toolCall.tool_name}
                          </div>

                          <div className="text-xs text-slate-900 whitespace-pre-wrap">
                            参数：
                            {JSON.stringify(toolCall.arguments, null, 2)}
                          </div>

                          <div className="text-xs text-slate-900">
                            状态：{toolCall.success ? "成功" : "失败"}
                          </div>

                          <div className="text-sm whitespace-pre-wrap">
                            {toolCall.observation}
                          </div>
                        </div>
                      ),
                    )
                  )}
                </div>
              </details>

              <details className="rounded-xl border border-slate-600 bg-white p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  查看 Agent Sources
                </summary>

                <div className="space-y-3 mt-3">
                  {compareRagAgentMutation.data.agentResult.sources.length === 0 ? (
                    <div className="text-sm text-slate-900">暂无来源资料。</div>
                  ) : (
                    compareRagAgentMutation.data.agentResult.sources.map(
                      (source, index) => (
                        <div
                          key={source.chunk_id}
                          className="border border-slate-600 rounded p-3 space-y-2"
                        >
                          <div className="text-sm font-medium">
                            [{index + 1}] {source.original_filename}
                          </div>

                          <div className="text-xs text-slate-900">
                            chunk_index：{source.chunk_index} ｜ match_count：
                            {source.match_count} ｜ similarity：
                            {source.similarity === null ||
                            source.similarity === undefined
                              ? "-"
                              : source.similarity.toFixed(4)}
                          </div>

                          <div className="text-sm whitespace-pre-wrap">
                            {source.content}
                          </div>
                        </div>
                      ),
                    )
                  )}
                </div>
              </details>

              <details className="rounded-xl border border-slate-600 bg-white p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  查看 Agent Trace
                </summary>

                <ol className="list-decimal list-inside text-sm space-y-1 mt-3">
                  {compareRagAgentMutation.data.agentResult.trace.map(
                    (item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ),
                  )}
                </ol>
              </details>
            </div>
          </div>
        ) : null}
      </div>

          </div>
        ) : null}

        {activeWorkspaceTab === "evaluation" ? (
          <div className="space-y-6">
      <div className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">RAG vs Agent 批量对比评测</h2>
          <p className="text-sm text-slate-900">
            使用当前知识库下的评测样例，同时运行普通 RAG 和 Agent，比较耗时、来源数量和工具调用情况。
          </p>
        </div>

        <button
          className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
          onClick={() => runRagAgentCompareEvalMutation.mutate()}
          disabled={runRagAgentCompareEvalMutation.isPending}
        >
          {runRagAgentCompareEvalMutation.isPending
            ? "批量对比运行中..."
            : "运行 RAG vs Agent 批量对比"}
        </button>

        {runRagAgentCompareEvalMutation.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            批量对比失败：
            {JSON.stringify(runRagAgentCompareEvalMutation.error, null, 2)}
          </div>
        ) : null}

        {runRagAgentCompareEvalMutation.data ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-xl border border-slate-600 bg-white p-3">
                <div className="text-xs text-slate-900">样例数</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.total_cases}
                </div>
              </div>

              <div className="rounded-xl border border-slate-600 bg-white p-3">
                <div className="text-xs text-slate-900">失败数</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.failed}
                </div>
              </div>

              <div className="rounded-xl border border-slate-600 bg-white p-3">
                <div className="text-xs text-slate-900">RAG 平均耗时</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.average_rag_latency_ms
                    ? `${runRagAgentCompareEvalMutation.data.summary.average_rag_latency_ms.toFixed(0)} ms`
                    : "-"}
                </div>
              </div>

              <div className="rounded-xl border border-slate-600 bg-white p-3">
                <div className="text-xs text-slate-900">Agent 平均耗时</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.average_agent_latency_ms
                    ? `${runRagAgentCompareEvalMutation.data.summary.average_agent_latency_ms.toFixed(0)} ms`
                    : "-"}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-xl border border-slate-600 bg-white p-3">
                <div className="text-xs text-slate-900">Agent 平均工具数</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.average_agent_tool_call_count
                    ? runRagAgentCompareEvalMutation.data.summary.average_agent_tool_call_count.toFixed(2)
                    : "-"}
                </div>
              </div>

              <div className="rounded-xl border border-slate-600 bg-white p-3">
                <div className="text-xs text-slate-900">工具失败总数</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.total_agent_failed_tool_count}
                </div>
              </div>

              <div className="rounded-xl border border-slate-600 bg-white p-3">
                <div className="text-xs text-slate-900">summarize_document</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.summarize_document_count}
                </div>
              </div>

              <div className="rounded-xl border border-slate-600 bg-white p-3">
                <div className="text-xs text-slate-900">read_document_chunks</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.read_document_chunks_count}
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {runRagAgentCompareEvalMutation.data.data.map((item, index) => (
                <details
                  key={item.eval_case_id}
                  className="rounded-xl border border-slate-600 bg-white p-3"
                >
                  <summary className="cursor-pointer text-sm font-medium">
                    {index + 1}. {item.question}
                    {" ｜ "}
                    RAG {item.rag_latency_ms ?? "-"} ms
                    {" ｜ "}
                    Agent {item.agent_latency_ms ?? "-"} ms
                    {" ｜ "}
                    {item.is_failed ? "有失败" : "正常"}
                  </summary>

                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-3">
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold">普通 RAG</h4>

                      {item.rag_error_message ? (
                        <div className="text-sm text-rose-600">
                          {item.rag_error_message}
                        </div>
                      ) : null}

                      <div className="text-xs text-slate-900">
                        Sources：{item.rag_sources_count}
                      </div>

                      <div className="text-sm whitespace-pre-wrap border rounded p-3">
                        {item.rag_answer || "暂无回答"}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold">Agent</h4>

                      {item.agent_error_message ? (
                        <div className="text-sm text-rose-600">
                          {item.agent_error_message}
                        </div>
                      ) : null}

                      <div className="text-xs text-slate-900">
                        Sources：{item.agent_sources_count} ｜ 工具调用：
                        {item.agent_tool_call_count} ｜ 工具失败：
                        {item.agent_failed_tool_count}
                      </div>

                      <div className="text-sm whitespace-pre-wrap border rounded p-3">
                        {item.agent_answer || "暂无回答"}
                      </div>

                      <details className="rounded-xl border border-slate-600 bg-white p-3">
                        <summary className="cursor-pointer text-sm">
                          查看工具调用
                        </summary>

                        <div className="space-y-3 mt-3">
                          {item.agent_tool_calls.map((toolCall, toolIndex) => (
                            <div
                              key={`${toolCall.tool_name}-${toolIndex}`}
                              className="rounded-xl border border-slate-600 bg-white p-3 space-y-2"
                            >
                              <div className="text-sm font-medium">
                                {toolIndex + 1}. {toolCall.tool_name}
                              </div>

                              <div className="text-xs text-slate-900">
                                状态：{toolCall.success ? "成功" : "失败"}
                              </div>

                              <div className="text-xs whitespace-pre-wrap">
                                参数：{JSON.stringify(toolCall.arguments, null, 2)}
                              </div>

                              <div className="text-sm whitespace-pre-wrap">
                                {toolCall.observation}
                              </div>
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  </div>
                </details>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <RagAgentCompareHistorySection
        isOpen={expandedSections.compareHistory}
        onToggle={() => toggleSection("compareHistory")}
        batchesData={ragAgentCompareBatchesQuery.data}
        isLoading={ragAgentCompareBatchesQuery.isLoading}
        isError={ragAgentCompareBatchesQuery.isError}
        error={ragAgentCompareBatchesQuery.error}
        selectedCompareBatchId={selectedCompareBatchId}
        onSelectBatch={(batchId) => {
          setSelectedCompareBatchId(batchId)
          setFailureBatchIdFilter(batchId)
        }}
        onExportMarkdown={(batchId) =>
          exportRagAgentCompareReportMutation.mutate(batchId)
        }
        onExportDocx={(batchId) =>
          exportRagAgentCompareDocxReportMutation.mutate(batchId)
        }
        onExportPdf={(batchId) =>
          exportRagAgentComparePdfReportMutation.mutate(batchId)
        }
        onDeleteBatch={(batchId) =>
          deleteRagAgentCompareBatchMutation.mutate(batchId)
        }
        isExportMarkdownPending={exportRagAgentCompareReportMutation.isPending}
        isExportDocxPending={exportRagAgentCompareDocxReportMutation.isPending}
        isExportPdfPending={exportRagAgentComparePdfReportMutation.isPending}
        isDeletePending={deleteRagAgentCompareBatchMutation.isPending}
        exportMarkdownError={exportRagAgentCompareReportMutation.error}
        exportDocxError={exportRagAgentCompareDocxReportMutation.error}
        exportPdfError={exportRagAgentComparePdfReportMutation.error}
        isExportMarkdownError={exportRagAgentCompareReportMutation.isError}
        isExportDocxError={exportRagAgentCompareDocxReportMutation.isError}
        isExportPdfError={exportRagAgentComparePdfReportMutation.isError}
      />

      <RagAgentCompareDetailSection
        isOpen={expandedSections.compareHistory}
        selectedCompareBatchId={selectedCompareBatchId}
        batchDetailData={ragAgentCompareBatchDetailQuery.data}
        isLoading={ragAgentCompareBatchDetailQuery.isLoading}
        isError={ragAgentCompareBatchDetailQuery.isError}
        error={ragAgentCompareBatchDetailQuery.error}
        onClose={() => setSelectedCompareBatchId(null)}
      />

      <RagAgentFailureAnalysisSection
        isOpen={expandedSections.compareHistory}
        batchDetailData={ragAgentCompareBatchDetailQuery.data}
      />

      <div className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">当前 Agent 默认配置</h2>
          <p className="text-sm text-slate-900">
            当前 Agent Chat、RAG vs Agent 单条对比和批量对比会优先使用这组参数。该配置会保存到后端，刷新页面后仍然生效。
          </p>
        </div>

        {agentSettingsQuery.isLoading ? (
          <div className="text-sm text-slate-900">正在加载后端 Agent 配置...</div>
        ) : null}

        {agentSettingsQuery.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            加载 Agent 配置失败：
            {JSON.stringify(agentSettingsQuery.error, null, 2)}
          </div>
        ) : null}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border border-slate-600 bg-white p-3">
            <div className="text-xs text-slate-900">top_k</div>
            <div className="text-xl font-semibold">{appliedAgentConfig.topK}</div>
          </div>

          <div className="rounded-xl border border-slate-600 bg-white p-3">
            <div className="text-xs text-slate-900">max_steps</div>
            <div className="text-xl font-semibold">
              {appliedAgentConfig.maxSteps}
            </div>
          </div>

          <div className="rounded-xl border border-slate-600 bg-white p-3">
            <div className="text-xs text-slate-900">semantic_weight</div>
            <div className="text-xl font-semibold">
              {appliedAgentConfig.semanticWeight}
            </div>
          </div>

          <div className="rounded-xl border border-slate-600 bg-white p-3">
            <div className="text-xs text-slate-900">keyword_weight</div>
            <div className="text-xl font-semibold">
              {appliedAgentConfig.keywordWeight}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={handleResetAgentConfig}
            disabled={updateAgentSettingsMutation.isPending}
          >
            恢复默认配置
          </button>
        </div>

        {updateAgentSettingsMutation.isPending ? (
          <div className="text-sm text-slate-900">正在保存 Agent 配置...</div>
        ) : null}

        {updateAgentSettingsMutation.isError ? (
          <div className="text-sm text-rose-600 whitespace-pre-wrap">
            保存 Agent 配置失败：
            {JSON.stringify(updateAgentSettingsMutation.error, null, 2)}
          </div>
        ) : null}
      </div>


      <AgentParamTuningSection
        isOpen={expandedSections.agentParamTuning}
        onToggle={() => toggleSection("agentParamTuning")}
        config={agentParamConfig}
        onConfigChange={setAgentParamConfig}
        onRunTuning={() => runAgentParamTuningMutation.mutate()}
        isTuningPending={runAgentParamTuningMutation.isPending}
        isTuningError={runAgentParamTuningMutation.isError}
        tuningError={runAgentParamTuningMutation.error}
        tuningData={runAgentParamTuningMutation.data}
        recommendation={agentParamRecommendation}
        onApplyRecommendation={handleApplyRecommendedAgentConfig}
        isApplyRecommendationPending={updateAgentSettingsMutation.isPending}
        isApplyRecommendationError={updateAgentSettingsMutation.isError}
        applyRecommendationError={updateAgentSettingsMutation.error}
      />

      <div className="rounded-2xl border border-slate-600 bg-white p-5 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">RAG 评测面板</h2>
          <p className="text-sm text-slate-900">
            这里可以创建固定测试问题，运行 RAG
            评测，并查看关键词命中、来源命中、得分和耗时。
          </p>
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div>
            <h3 className="text-base font-semibold">检索参数调优</h3>
            <p className="text-sm text-slate-900">
              调整 top_k、语义权重和关键词权重后，可以重新运行评测，观察平均分、失败率和命中率变化。
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="space-y-1">
              <div className="text-sm text-slate-900">top_k</div>
              <input
                type="number"
                min={1}
                max={20}
                className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                value={ragTopK}
                onChange={(event) => setRagTopK(Number(event.target.value))}
              />
            </label>

            <label className="space-y-1">
              <div className="text-sm text-slate-900">语义检索权重</div>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                value={ragSemanticWeight}
                onChange={(event) =>
                  setRagSemanticWeight(Number(event.target.value))
                }
              />
            </label>

            <label className="space-y-1">
              <div className="text-sm text-slate-900">关键词检索权重</div>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                value={ragKeywordWeight}
                onChange={(event) =>
                  setRagKeywordWeight(Number(event.target.value))
                }
              />
            </label>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() => {
                setRagTopK(5)
                setRagSemanticWeight(0.75)
                setRagKeywordWeight(0.25)
              }}
            >
              默认参数 0.75 / 0.25
            </button>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() => {
                setRagTopK(5)
                setRagSemanticWeight(0.9)
                setRagKeywordWeight(0.1)
              }}
            >
              偏语义 0.9 / 0.1
            </button>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() => {
                setRagTopK(5)
                setRagSemanticWeight(0.6)
                setRagKeywordWeight(0.4)
              }}
            >
              平衡偏关键词 0.6 / 0.4
            </button>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() => {
                setRagTopK(8)
                setRagSemanticWeight(0.75)
                setRagKeywordWeight(0.25)
              }}
            >
              提高 top_k 到 8
            </button>
          </div>

          <div className="rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-xs text-sky-700">
            当前参数：top_k = {ragTopK}，semantic_weight = {ragSemanticWeight}，
            keyword_weight = {ragKeywordWeight}
          </div>

          <div className="border-t pt-3 space-y-3">
              <h4 className="text-sm font-semibold">批量评测实验信息</h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input
                  className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                  placeholder="实验名称，可选，例如：默认参数组第一次测试"
                  value={evalBatchName}
                  onChange={(event) => setEvalBatchName(event.target.value)}
                />

                <input
                  className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                  placeholder="实验备注，可选，例如：测试偏语义权重下的来源命中率"
                  value={evalBatchNote}
                  onChange={(event) => setEvalBatchNote(event.target.value)}
                />
              </div>

              <div className="text-xs text-slate-900">
                点击“运行全部评测”后，会自动生成一条实验批次记录。
              </div>
            </div>
            <div className="border-t pt-3 space-y-3">
              <h4 className="text-sm font-semibold">参数预设</h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input
                  className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                  placeholder="预设名称，例如：默认参数组 / 偏语义组 / 高召回组"
                  value={presetName}
                  onChange={(event) => setPresetName(event.target.value)}
                />

                <input
                  className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                  placeholder="备注，可选，例如：用于测试来源命中率"
                  value={presetNote}
                  onChange={(event) => setPresetNote(event.target.value)}
                />
              </div>

              <button
                className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                onClick={handleCreateRagRetrievalPreset}
                disabled={createRagRetrievalPresetMutation.isPending}
              >
                {createRagRetrievalPresetMutation.isPending
                  ? "保存中..."
                  : "保存当前参数为预设"}
              </button>

              {createRagRetrievalPresetMutation.isError ? (
                <div className="text-sm text-rose-600 whitespace-pre-wrap">
                  保存参数预设失败：
                  {JSON.stringify(createRagRetrievalPresetMutation.error, null, 2)}
                </div>
              ) : null}

              {deleteRagRetrievalPresetMutation.isError ? (
                <div className="text-sm text-rose-600 whitespace-pre-wrap">
                  删除参数预设失败：
                  {JSON.stringify(deleteRagRetrievalPresetMutation.error, null, 2)}
                </div>
              ) : null}

              {ragRetrievalPresetsQuery.isLoading ? (
                <div className="text-sm text-slate-900">正在加载参数预设...</div>
              ) : null}

              {ragRetrievalPresetsQuery.isError ? (
                <div className="text-sm text-rose-600 whitespace-pre-wrap">
                  参数预设加载失败：
                  {JSON.stringify(ragRetrievalPresetsQuery.error, null, 2)}
                </div>
              ) : null}

              {ragRetrievalPresetsQuery.data ? (
                <div className="space-y-2">
                  {ragRetrievalPresetsQuery.data.data.length === 0 ? (
                    <div className="text-sm text-slate-900">
                      暂无参数预设。你可以先调整参数后保存。
                    </div>
                  ) : (
                    ragRetrievalPresetsQuery.data.data.map((preset) => (
                      <div
                        key={preset.id}
                        className="border border-slate-600 rounded p-3 bg-slate-50 text-slate-900 space-y-2"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium">{preset.name}</div>
                            <div className="text-xs text-slate-900">
                              top_k={preset.top_k} ｜ S={preset.semantic_weight} ｜ K=
                              {preset.keyword_weight}
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              className="rounded-md border border-slate-600 bg-white px-2 py-1 text-xs font-medium text-slate-600 transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                              onClick={() => handleApplyRagRetrievalPreset(preset)}
                            >
                              应用
                            </button>

                            <button
                              className="border border-rose-200 text-rose-600 rounded px-2 py-1 text-xs"
                              onClick={() => handleDeleteRagRetrievalPreset(preset.id)}
                              disabled={deleteRagRetrievalPresetMutation.isPending}
                            >
                              删除
                            </button>
                          </div>
                        </div>

                        {preset.note ? (
                          <div className="text-xs text-slate-900">
                            备注：{preset.note}
                          </div>
                        ) : null}

                        {preset.created_at ? (
                          <div className="text-xs text-slate-900">
                            创建时间：{new Date(preset.created_at).toLocaleString()}
                          </div>
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
              ) : null}
            </div>
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">评测统计概览</h3>
              <p className="text-sm text-slate-900">
                统计最近的 RAG 评测运行结果，用于观察整体检索与回答效果。
              </p>
            </div>

            <div className="flex gap-2">
              <button
                className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                onClick={() =>
                  queryClient.invalidateQueries({
                    queryKey: ["rag-eval-summary", knowledgeBaseId],
                  })
                }
              >
                刷新统计
              </button>

              <button
                className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                onClick={handleRunAllRagEvalCases}
                disabled={runAllRagEvalCasesMutation.isPending}
              >
                {runAllRagEvalCasesMutation.isPending
                  ? "批量运行中..."
                  : "运行全部评测"}
              </button>
            </div>
          </div>

          {ragEvalSummaryQuery.isLoading ? (
            <div className="text-sm text-slate-900">正在加载评测统计...</div>
          ) : null}

          {ragEvalSummaryQuery.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              评测统计加载失败：
              {JSON.stringify(ragEvalSummaryQuery.error, null, 2)}
            </div>
          ) : null}

          {runAllRagEvalCasesMutation.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              批量运行评测失败：
              {JSON.stringify(runAllRagEvalCasesMutation.error, null, 2)}
            </div>
          ) : null}

          {runAllRagEvalCasesMutation.data ? (
            <div className="text-sm text-slate-900">
              批量运行结果：共 {runAllRagEvalCasesMutation.data.total_cases}
              条样例，成功运行 {runAllRagEvalCasesMutation.data.ran}
              条，失败 {runAllRagEvalCasesMutation.data.failed} 条。
            </div>
          ) : null}

          {ragEvalSummaryQuery.data ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="border rounded p-3 bg-slate-50 text-slate-900">
                <div className="text-xs text-slate-900">总评测次数</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.total_runs}
                </div>
              </div>

              <div className="border rounded p-3 bg-slate-50 text-slate-900">
                <div className="text-xs text-slate-900">平均分</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.average_score === null
                    ? "-"
                    : ragEvalSummaryQuery.data.average_score.toFixed(2)}
                </div>
              </div>

              <div className="border rounded p-3 bg-slate-50 text-slate-900">
                <div className="text-xs text-slate-900">关键词命中率</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.keyword_hit_rate === null
                    ? "-"
                    : `${(ragEvalSummaryQuery.data.keyword_hit_rate * 100).toFixed(
                        1,
                      )}%`}
                </div>
              </div>

              <div className="border rounded p-3 bg-slate-50 text-slate-900">
                <div className="text-xs text-slate-900">来源命中率</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.source_hit_rate === null
                    ? "-"
                    : `${(ragEvalSummaryQuery.data.source_hit_rate * 100).toFixed(
                        1,
                      )}%`}
                </div>
              </div>

              <div className="border rounded p-3 bg-slate-50 text-slate-900">
                <div className="text-xs text-slate-900">平均耗时</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.average_latency_ms === null
                    ? "-"
                    : `${ragEvalSummaryQuery.data.average_latency_ms.toFixed(0)} ms`}
                </div>
              </div>

              <div className="border rounded p-3 bg-slate-50 text-slate-900">
                <div className="text-xs text-slate-900">最高分</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.max_score === null
                    ? "-"
                    : ragEvalSummaryQuery.data.max_score.toFixed(2)}
                </div>
              </div>

              <div className="border rounded p-3 bg-slate-50 text-slate-900">
                <div className="text-xs text-slate-900">最低分</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.min_score === null
                    ? "-"
                    : ragEvalSummaryQuery.data.min_score.toFixed(2)}
                </div>
              </div>

              <div className="border rounded p-3 bg-slate-50 text-slate-900">
                <div className="text-xs text-slate-900">最新评测时间</div>
                <div className="text-sm font-medium">
                  {ragEvalSummaryQuery.data.latest_run_at
                    ? new Date(
                        ragEvalSummaryQuery.data.latest_run_at,
                      ).toLocaleString()
                    : "-"}
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="font-medium">Code RAG / Code Agent 分任务类型统计</h3>
              <p className="text-sm text-slate-900">
                按评测样例类型统计普通 RAG 与 Code Agent 的命中率、耗时和工具调用差异。
              </p>
            </div>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["code-eval-type-compare-summary", knowledgeBaseId],
                })
              }
            >
              刷新统计
            </button>
          </div>

          <button
            className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={() => {
              const confirmed = window.confirm(
                "确定要批量运行 RAG vs Agent 对比吗？这会同时调用普通 RAG 和 Agent，耗时会比普通评测更长。",
              )

              if (!confirmed) {
                return
              }

              runRagAgentCompareEvalMutation.mutate()
            }}
            disabled={runRagAgentCompareEvalMutation.isPending}
          >
            {runRagAgentCompareEvalMutation.isPending
              ? "RAG vs Agent 对比运行中..."
              : "批量运行 RAG vs Agent 对比"}
          </button>

          {runRagAgentCompareEvalMutation.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              RAG vs Agent 对比失败：
              {JSON.stringify(runRagAgentCompareEvalMutation.error, null, 2)}
            </div>
          ) : null}

          {runRagAgentCompareEvalMutation.data ? (
            <div className="text-sm text-emerald-700">
              RAG vs Agent 对比完成，共运行{" "}
              {(runRagAgentCompareEvalMutation.data as any).count ?? "-"} 条样例。
            </div>
          ) : null}

          {codeEvalTypeCompareSummaryQuery.isLoading ? (
            <div className="text-sm text-slate-900">正在加载统计结果...</div>
          ) : null}

          {codeEvalTypeCompareSummaryQuery.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              加载分任务类型统计失败：
              {JSON.stringify(codeEvalTypeCompareSummaryQuery.error, null, 2)}
            </div>
          ) : null}

          {codeEvalTypeCompareSummaryQuery.data ? (
            codeEvalTypeCompareSummaryQuery.data.data.length === 0 ? (
              <div className="text-sm text-slate-900">
                暂无可统计的 Code Eval 对比结果。请先生成代码评测集，并运行 RAG vs Agent 对比。
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm border">
                  <thead className="bg-gray-500">
                    <tr>
                      <th className="border px-3 py-2 text-left">任务类型</th>
                      <th className="border px-3 py-2 text-right">样例数</th>
                      <th className="border px-3 py-2 text-right">已对比</th>
                      <th className="border px-3 py-2 text-right">RAG文件命中</th>
                      <th className="border px-3 py-2 text-right">Agent文件命中</th>
                      <th className="border px-3 py-2 text-right">RAG关键词命中</th>
                      <th className="border px-3 py-2 text-right">Agent关键词命中</th>
                      <th className="border px-3 py-2 text-right">RAG耗时</th>
                      <th className="border px-3 py-2 text-right">Agent耗时</th>
                      <th className="border px-3 py-2 text-right">Agent平均工具数</th>
                      <th className="border px-3 py-2 text-left">工具分布</th>
                    </tr>
                  </thead>

                  <tbody>
                    {codeEvalTypeCompareSummaryQuery.data.data.map((item) => (
                      <tr key={item.case_type}>
                        <td className="border px-3 py-2">
                          {item.case_type_label}
                          <div className="text-xs text-slate-900">
                            {item.case_type}
                          </div>
                        </td>

                        <td className="border px-3 py-2 text-right">
                          {item.total_cases}
                        </td>

                        <td className="border px-3 py-2 text-right">
                          {item.compared_cases}
                        </td>

                        <td className="border px-3 py-2 text-right">
                          {formatPercent(item.rag_source_hit_rate)}
                        </td>

                        <td className="border px-3 py-2 text-right">
                          {formatPercent(item.agent_source_hit_rate)}
                        </td>

                        <td className="border px-3 py-2 text-right">
                          {formatPercent(item.rag_keyword_hit_rate)}
                        </td>

                        <td className="border px-3 py-2 text-right">
                          {formatPercent(item.agent_keyword_hit_rate)}
                        </td>

                        <td className="border px-3 py-2 text-right">
                          {formatLatency(item.rag_avg_latency_ms)}
                        </td>

                        <td className="border px-3 py-2 text-right">
                          {formatLatency(item.agent_avg_latency_ms)}
                        </td>

                        <td className="border px-3 py-2 text-right">
                          {item.agent_avg_tool_calls === null ||
                          item.agent_avg_tool_calls === undefined
                            ? "-"
                            : item.agent_avg_tool_calls.toFixed(2)}
                        </td>

                        <td className="border px-3 py-2">
                          {formatToolUsage(item.agent_tool_usage_json)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="font-medium">RAG vs Agent 失败案例分析</h3>
              <p className="text-sm text-slate-900">
                自动归因 RAG vs Agent 对比中的异常样例，包括来源未命中、关键词未命中、工具失败、无工具调用和 Agent 过慢等情况。
              </p>
            </div>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-agent-compare-failure-analysis", knowledgeBaseId],
                })
              }
            >
              刷新失败分析
            </button>
          </div>

          <div className="text-xs text-slate-900">
            当前筛选：
            任务类型 = {failureCaseTypeFilter || "全部"}；
            对比批次 = {failureBatchIdFilter || "全部"}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="text-sm space-y-1">
              <span className="block text-slate-600">按任务类型筛选</span>
              <select
                className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                value={failureCaseTypeFilter}
                onChange={(event) => setFailureCaseTypeFilter(event.target.value)}
              >
                <option className="bg-white text-slate-900" value="">
                  全部类型
                </option>
                <option className="bg-white text-slate-900" value="file_overview">
                  文件概览 file_overview
                </option>
                <option className="bg-white text-slate-900" value="symbol_definition">
                  符号定义 symbol_definition
                </option>
                <option className="bg-white text-slate-900" value="symbol_reference">
                  引用定位 symbol_reference
                </option>
                <option className="bg-white text-slate-900" value="code_logic">
                  代码逻辑 code_logic
                </option>
                <option className="bg-white text-slate-900" value="bug_location">
                  Bug 定位 bug_location
                </option>
                <option className="bg-white text-slate-900" value="unknown">
                  未分类 unknown
                </option>
              </select>
            </label>

            <label className="text-sm space-y-1">
              <span className="block text-slate-600">按对比批次筛选</span>
              <select
                className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                value={failureBatchIdFilter}
                onChange={(event) => setFailureBatchIdFilter(event.target.value)}
              >
                <option className="bg-white text-slate-900" value="">
                  全部批次
                </option>

                {ragAgentCompareBatchesQuery.data?.data.map((batch) => (
                  <option
                    key={batch.id}
                    value={batch.id}
                    className="bg-white text-slate-900"
                  >
                    {batch.name}｜{batch.ran}/{batch.total_cases}｜
                    {batch.created_at
                      ? new Date(batch.created_at).toLocaleString()
                      : "-"}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex items-end gap-2">
              <button
                className="border rounded px-3 py-2 text-sm"
                onClick={() =>
                  queryClient.invalidateQueries({
                    queryKey: [
                      "rag-agent-compare-failure-analysis",
                      knowledgeBaseId,
                      failureBatchIdFilter,
                      failureCaseTypeFilter,
                    ],
                  })
                }
              >
                应用筛选
              </button>

              <button
                className="border rounded px-3 py-2 text-sm"
                onClick={() => {
                  setFailureCaseTypeFilter("")
                  setFailureBatchIdFilter("")
                }}
              >
                清空筛选
              </button>
            </div>
          </div>

          {ragAgentCompareFailureAnalysisQuery.isLoading ? (
            <div className="text-sm text-slate-900">正在加载失败案例分析...</div>
          ) : null}

          {ragAgentCompareFailureAnalysisQuery.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              加载失败案例分析失败：
              {JSON.stringify(ragAgentCompareFailureAnalysisQuery.error, null, 2)}
            </div>
          ) : null}

          {ragAgentCompareFailureAnalysisQuery.data ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">分析样例数</div>
                  <div className="text-xl font-semibold">
                    {ragAgentCompareFailureAnalysisQuery.data.total_items}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">异常样例数</div>
                  <div className="text-xl font-semibold">
                    {ragAgentCompareFailureAnalysisQuery.data.failed_items}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">异常率</div>
                  <div className="text-xl font-semibold">
                    {ragAgentCompareFailureAnalysisQuery.data.total_items === 0
                      ? "-"
                      : `${(
                          (ragAgentCompareFailureAnalysisQuery.data.failed_items /
                            ragAgentCompareFailureAnalysisQuery.data.total_items) *
                          100
                        ).toFixed(1)}%`}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">原因类型数</div>
                  <div className="text-xl font-semibold">
                    {ragAgentCompareFailureAnalysisQuery.data.reason_stats.length}
                  </div>
                </div>
              </div>

              {ragAgentCompareFailureAnalysisQuery.data.reason_stats.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm border">
                    <thead className="bg-gray-500">
                      <tr>
                        <th className="border px-3 py-2 text-left">失败原因</th>
                        <th className="border px-3 py-2 text-right">次数</th>
                      </tr>
                    </thead>

                    <tbody>
                      {ragAgentCompareFailureAnalysisQuery.data.reason_stats.map((item) => (
                        <tr key={item.reason}>
                          <td className="border px-3 py-2">
                            {item.reason_label}
                            <div className="text-xs text-slate-900">
                              {item.reason}
                            </div>
                          </td>
                          <td className="border px-3 py-2 text-right">
                            {item.count}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-slate-900">
                  暂无明显失败原因。请先运行 RAG vs Agent 对比。
                </div>
              )}

              <div className="space-y-3">
                {ragAgentCompareFailureAnalysisQuery.data.data.map((item) => (
                  <div
                    key={item.id}
                    className="border rounded p-3 space-y-2 bg-slate-50 text-slate-900"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">
                          {item.question}
                        </div>

                        <div className="text-xs text-slate-900 mt-1">
                          类型：{item.case_type_label} ｜ batch_id：{item.batch_id}
                        </div>
                      </div>

                      <div className="text-xs text-rose-600">
                        {item.failure_reason_labels.join("、")}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                      <div>
                        RAG 来源命中：
                        {item.rag_source_hit ? "是" : "否"}
                      </div>
                      <div>
                        Agent 来源命中：
                        {item.agent_source_hit ? "是" : "否"}
                      </div>
                      <div>
                        RAG 关键词：
                        {formatPercent(item.rag_keyword_hit_rate)}
                      </div>
                      <div>
                        Agent 关键词：
                        {formatPercent(item.agent_keyword_hit_rate)}
                      </div>
                      <div>
                        RAG 耗时：
                        {formatLatency(item.rag_latency_ms)}
                      </div>
                      <div>
                        Agent 耗时：
                        {formatLatency(item.agent_latency_ms)}
                      </div>
                      <div>
                        Agent 工具数：
                        {item.agent_tool_call_count}
                      </div>
                      <div>
                        Agent 失败工具数：
                        {item.agent_failed_tool_count}
                      </div>
                    </div>

                    {item.agent_tool_names.length > 0 ? (
                      <div className="text-xs text-slate-900">
                        Agent 工具链：{item.agent_tool_names.join(" → ")}
                      </div>
                    ) : (
                      <div className="text-xs text-amber-600">
                        Agent 没有工具调用
                      </div>
                    )}

                    {item.rag_error_message ? (
                      <div className="text-xs text-rose-600">
                        RAG 错误：{item.rag_error_message}
                      </div>
                    ) : null}

                    {item.agent_error_message ? (
                      <div className="text-xs text-rose-600">
                        Agent 错误：{item.agent_error_message}
                      </div>
                    ) : null}

                    <details className="text-xs">
                      <summary className="cursor-pointer text-slate-900">
                        查看 RAG / Agent 回答
                      </summary>

                      <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="border rounded p-2">
                          <div className="font-medium mb-1">RAG 回答</div>
                          <pre className="whitespace-pre-wrap text-xs">
                            {item.rag_answer || "无"}
                          </pre>
                        </div>

                        <div className="border rounded p-2">
                          <div className="font-medium mb-1">Agent 回答</div>
                          <pre className="whitespace-pre-wrap text-xs">
                            {item.agent_answer || "无"}
                          </pre>
                        </div>
                      </div>
                    </details>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="font-medium">Code Agent 优化建议</h3>
              <p className="text-sm text-slate-900">
                根据分任务类型统计和失败案例分析，自动生成下一轮 Agent 策略与参数优化建议。
              </p>
            </div>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() => {
                queryClient.invalidateQueries({
                  queryKey: ["code-eval-type-compare-summary", knowledgeBaseId],
                })

                queryClient.invalidateQueries({
                  queryKey: [
                    "rag-agent-compare-failure-analysis",
                    knowledgeBaseId,
                    failureBatchIdFilter,
                    failureCaseTypeFilter,
                  ],
                })
              }}
            >
              刷新建议
            </button>
          </div>

          {codeEvalTypeCompareSummaryQuery.isLoading ||
          ragAgentCompareFailureAnalysisQuery.isLoading ? (
            <div className="text-sm text-slate-900">
              正在根据统计结果生成优化建议...
            </div>
          ) : null}

          {codeEvalTypeCompareSummaryQuery.isError ||
          ragAgentCompareFailureAnalysisQuery.isError ? (
            <div className="text-sm text-rose-600">
              当前统计数据加载失败，暂时无法生成可靠优化建议。
            </div>
          ) : null}

          <div className="space-y-3">
            {codeAgentOptimizationAdvice.map((advice, index) => (
              <div
                key={`${advice.title}-${index}`}
                className={`border rounded p-3 space-y-2 ${getAdviceLevelClassName(
                  advice.level,
                )}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">
                    {index + 1}. {advice.title}
                  </div>

                  <span className="text-xs border rounded px-2 py-0.5">
                    {advice.level === "high"
                      ? "高优先级"
                      : advice.level === "medium"
                        ? "中优先级"
                        : "观察项"}
                  </span>
                </div>

                <div className="text-sm">
                  <span className="font-medium">判断依据：</span>
                  {advice.reason}
                </div>

                <div className="text-sm">
                  <span className="font-medium">优化建议：</span>
                  {advice.suggestion}
                </div>
              </div>
            ))}
          </div>

          <div className="border-t pt-3 text-sm text-slate-900">
            建议的下一轮实验参数：
            <span className="font-medium text-slate-600">
              {" "}
              top_k=5，max_steps=6，semantic_weight=0.65，keyword_weight=0.35
            </span>
            。如果 Agent 耗时过高，则保持 max_steps=5，优先优化工具选择规则。
          </div>
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="font-medium">优化前后对比表</h3>
              <p className="text-sm text-slate-900">
                选择两个 RAG vs Agent 批次，对比优化前后在失败率、耗时、工具调用和 sources 获取上的变化。
              </p>
            </div>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-agent-compare-batches", knowledgeBaseId],
                })
              }
            >
              刷新批次
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="text-sm space-y-1">
              <span className="block text-slate-600">优化前批次</span>
              <select
                className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                value={baselineCompareBatchId}
                onChange={(event) => setBaselineCompareBatchId(event.target.value)}
              >
                <option className="bg-white text-slate-900" value="">
                  请选择优化前批次
                </option>

                {compareBatchRows.map((batch) => (
                  <option
                    key={batch.id}
                    value={batch.id}
                    className="bg-white text-slate-900"
                  >
                    {batch.name}｜{batch.ran}/{batch.total_cases}｜
                    {batch.created_at
                      ? new Date(batch.created_at).toLocaleString()
                      : "-"}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm space-y-1">
              <span className="block text-slate-600">优化后批次</span>
              <select
                className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                value={optimizedCompareBatchId}
                onChange={(event) => setOptimizedCompareBatchId(event.target.value)}
              >
                <option className="bg-white text-slate-900" value="">
                  请选择优化后批次
                </option>

                {compareBatchRows.map((batch) => (
                  <option
                    key={batch.id}
                    value={batch.id}
                    className="bg-white text-slate-900"
                  >
                    {batch.name}｜{batch.ran}/{batch.total_cases}｜
                    {batch.created_at
                      ? new Date(batch.created_at).toLocaleString()
                      : "-"}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {ragAgentCompareBatchesQuery.isLoading ? (
            <div className="text-sm text-slate-900">正在加载对比批次...</div>
          ) : null}

          {ragAgentCompareBatchesQuery.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              加载对比批次失败：
              {JSON.stringify(ragAgentCompareBatchesQuery.error, null, 2)}
            </div>
          ) : null}

          {compareBatchRows.length === 0 ? (
            <div className="text-sm text-slate-900">
              暂无 RAG vs Agent 对比批次。请先运行至少两次批量对比。
            </div>
          ) : null}

          {!baselineCompareBatch || !optimizedCompareBatch ? (
            <div className="text-sm text-slate-900">
              请选择“优化前批次”和“优化后批次”，然后查看对比结果。
            </div>
          ) : null}

          {baselineCompareBatch && optimizedCompareBatch ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="border rounded p-3 bg-slate-50 text-slate-900 space-y-1">
                  <div className="text-xs text-slate-900">优化前</div>
                  <div className="font-medium">{baselineCompareBatch.name}</div>
                  <div className="text-xs text-slate-900">
                    创建时间：
                    {baselineCompareBatch.created_at
                      ? new Date(baselineCompareBatch.created_at).toLocaleString()
                      : "-"}
                  </div>
                  <div className="text-xs text-slate-900">
                    参数：top_k={baselineCompareBatch.top_k} ｜ max_steps=
                    {baselineCompareBatch.max_steps} ｜ S=
                    {baselineCompareBatch.semantic_weight} ｜ K=
                    {baselineCompareBatch.keyword_weight}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900 space-y-1">
                  <div className="text-xs text-slate-900">优化后</div>
                  <div className="font-medium">{optimizedCompareBatch.name}</div>
                  <div className="text-xs text-slate-900">
                    创建时间：
                    {optimizedCompareBatch.created_at
                      ? new Date(optimizedCompareBatch.created_at).toLocaleString()
                      : "-"}
                  </div>
                  <div className="text-xs text-slate-900">
                    参数：top_k={optimizedCompareBatch.top_k} ｜ max_steps=
                    {optimizedCompareBatch.max_steps} ｜ S=
                    {optimizedCompareBatch.semantic_weight} ｜ K=
                    {optimizedCompareBatch.keyword_weight}
                  </div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full text-sm border">
                  <thead className="bg-gray-500">
                    <tr>
                      <th className="border px-3 py-2 text-left">指标</th>
                      <th className="border px-3 py-2 text-right">优化前</th>
                      <th className="border px-3 py-2 text-right">优化后</th>
                      <th className="border px-3 py-2 text-right">变化</th>
                      <th className="border px-3 py-2 text-left">判断</th>
                      <th className="border px-3 py-2 text-left">说明</th>
                    </tr>
                  </thead>

                  <tbody>
                    {optimizationCompareRows.map((row) => (
                      <tr key={row.metric}>
                        <td className="border px-3 py-2 font-medium">
                          {row.metric}
                        </td>
                        <td className="border px-3 py-2 text-right">
                          {row.beforeText}
                        </td>
                        <td className="border px-3 py-2 text-right">
                          {row.afterText}
                        </td>
                        <td className="border px-3 py-2 text-right">
                          {row.changeText}
                        </td>
                        <td
                          className={`border px-3 py-2 ${getResultClassName(
                            row.result,
                          )}`}
                        >
                          {getResultLabel(row.result)}
                        </td>
                        <td className="border px-3 py-2 text-slate-600">
                          {row.explanation}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="border rounded p-3 bg-slate-50 text-slate-900 space-y-2">
                <div className="font-medium">自动结论</div>

                <div className="text-sm text-slate-600">
                  {optimizationCompareRows.filter((row) => row.result === "better")
                    .length >
                  optimizationCompareRows.filter((row) => row.result === "worse")
                    .length ? (
                    <>
                      本轮优化整体呈现正向效果。改善项多于变差项，可以继续保留当前 Agent
                      工具选择策略，并进一步观察分任务类型统计中 symbol_reference 和 code_logic
                      是否也同步提升。
                    </>
                  ) : optimizationCompareRows.filter((row) => row.result === "worse")
                      .length >
                    optimizationCompareRows.filter((row) => row.result === "better")
                      .length ? (
                    <>
                      本轮优化存在副作用。建议重点查看失败案例分析，判断是工具调用过多导致耗时上升，
                      还是检索权重变化导致 sources 或关键词命中下降。
                    </>
                  ) : (
                    <>
                      本轮优化效果不明显。可以扩大评测样例数量，或者针对 symbol_reference、
                      code_logic、bug_location 单独设计更难的代码任务，再进行下一轮对比。
                    </>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="font-medium">Code RAG / Code Agent 实验报告</h3>
              <p className="text-sm text-slate-900">
                根据当前选择的优化前后批次、分任务类型统计、失败案例分析和优化建议，生成 Markdown 实验报告。
              </p>
            </div>

            <div className="flex gap-2">
              <button
                className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                onClick={handleGenerateCodeAgentExperimentReport}
              >
                生成报告预览
              </button>

              <button
                className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                onClick={handleDownloadCodeAgentExperimentReport}
                disabled={!experimentReportMarkdown.trim()}
              >
                下载 Markdown 报告
              </button>
              <button
                className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                onClick={() => {
                  if (!baselineCompareBatchId || !optimizedCompareBatchId) {
                    alert("请先选择优化前批次和优化后批次")
                    return
                  }

                  exportBackendCodeAgentReportMutation.mutate()
                }}
                disabled={
                  exportBackendCodeAgentReportMutation.isPending ||
                  !baselineCompareBatchId ||
                  !optimizedCompareBatchId
                }
              >
                {exportBackendCodeAgentReportMutation.isPending
                  ? "后端报告生成中..."
                  : "后端导出 Markdown 报告"}
              </button>
            </div>
          </div>

          {!baselineCompareBatch || !optimizedCompareBatch ? (
            <div className="text-sm text-yellow-500">
              请先在“优化前后对比表”中选择优化前批次和优化后批次，再生成实验报告。
            </div>
          ) : null}

          {experimentReportMarkdown ? (
            <div className="space-y-2">
              <div className="text-sm text-slate-900">
                报告已生成，可复制预览内容，也可以点击“下载 Markdown 报告”。
              </div>

              <pre className="border rounded p-3 bg-slate-50 text-slate-900 text-xs whitespace-pre-wrap overflow-x-auto max-h-[600px]">
                {experimentReportMarkdown}
              </pre>
            </div>
          ) : (
            <div className="text-sm text-slate-900">
              暂无报告预览。请选择批次后点击“生成报告预览”。
            </div>
          )}
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">参数版本对比</h3>
              <p className="text-sm text-slate-900">
                按 top_k、语义权重和关键词权重分组，对比不同参数组合下的平均分、失败率、命中率和耗时。
              </p>
            </div>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-param-groups", knowledgeBaseId],
                })
              }
            >
              刷新对比
            </button>
          </div>

          {ragEvalParamGroupsQuery.isLoading ? (
            <div className="text-sm text-slate-900">正在加载参数版本对比...</div>
          ) : null}

          {ragEvalParamGroupsQuery.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              参数版本对比加载失败：
              {JSON.stringify(ragEvalParamGroupsQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalParamGroupsQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-slate-900">
                共 {ragEvalParamGroupsQuery.data.count} 组参数组合。
              </div>

              {ragEvalParamGroupsQuery.data.data.length === 0 ? (
                <div className="text-sm text-slate-900">
                  暂无参数对比数据。可以先运行几次不同参数组合的评测。
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-slate-600 text-slate-900">
                        <th className="text-left py-2 px-2">参数组合</th>
                        <th className="text-left py-2 px-2">运行次数</th>
                        <th className="text-left py-2 px-2">平均分</th>
                        <th className="text-left py-2 px-2">失败率</th>
                        <th className="text-left py-2 px-2">关键词命中率</th>
                        <th className="text-left py-2 px-2">来源命中率</th>
                        <th className="text-left py-2 px-2">平均耗时</th>
                        <th className="text-left py-2 px-2">最新运行</th>
                      </tr>
                    </thead>

                    <tbody>
                      {ragEvalParamGroupsQuery.data.data.map((group) => (
                        <tr
                          key={`${group.top_k}-${group.semantic_weight}-${group.keyword_weight}`}
                          className="border-b border-slate-600 text-slate-900"
                        >
                          <td className="py-2 px-2">
                            <div className="space-y-1">
                              {group.preset_names.length > 0 ? (
                                <div className="font-medium text-slate-900">
                                  {group.preset_names.join("、")}
                                </div>
                              ) : (
                                <div className="font-medium text-slate-900">未命名参数组</div>
                              )}

                              <div className="text-xs text-slate-900">
                                top_k={group.top_k} ｜ S={group.semantic_weight} ｜ K=
                                {group.keyword_weight}
                              </div>
                            </div>
                          </td>

                          <td className="py-2 px-2">{group.total_runs}</td>

                          <td className="py-2 px-2">
                            {group.average_score === null
                              ? "-"
                              : group.average_score.toFixed(2)}
                          </td>

                          <td className="py-2 px-2">
                            {group.failure_rate === null
                              ? "-"
                              : `${(group.failure_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {group.keyword_hit_rate === null
                              ? "-"
                              : `${(group.keyword_hit_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {group.source_hit_rate === null
                              ? "-"
                              : `${(group.source_hit_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {group.average_latency_ms === null
                              ? "-"
                              : `${group.average_latency_ms.toFixed(0)} ms`}
                          </td>

                          <td className="py-2 px-2">
                            {group.latest_run_at
                              ? new Date(group.latest_run_at).toLocaleString()
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">实验批次记录</h3>
              <p className="text-sm text-slate-900">
                每次运行全部评测都会生成一条实验批次记录，用于对比不同参数组合下的整体效果。
              </p>
            </div>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-batches", knowledgeBaseId],
                })
              }
            >
              刷新批次
            </button>
          </div>

          {ragEvalBatchesQuery.isLoading ? (
            <div className="text-sm text-slate-900">正在加载实验批次...</div>
          ) : null}

          {ragEvalBatchesQuery.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              实验批次加载失败：
              {JSON.stringify(ragEvalBatchesQuery.error, null, 2)}
            </div>
          ) : null}

          {deleteRagEvalBatchMutation.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              删除实验批次失败：
              {JSON.stringify(deleteRagEvalBatchMutation.error, null, 2)}
            </div>
          ) : null}

          {ragEvalBatchesQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-slate-900">
                共 {ragEvalBatchesQuery.data.count} 条实验批次记录。
              </div>

              {ragEvalBatchesQuery.data.data.length === 0 ? (
                <div className="text-sm text-slate-900">
                  暂无实验批次。可以先点击“运行全部评测”生成一条记录。
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-slate-600 text-slate-900">
                        <th className="text-left py-2 px-2">实验名称</th>
                        <th className="text-left py-2 px-2">参数</th>
                        <th className="text-left py-2 px-2">样例数</th>
                        <th className="text-left py-2 px-2">成功 / 失败</th>
                        <th className="text-left py-2 px-2">平均分</th>
                        <th className="text-left py-2 px-2">关键词命中率</th>
                        <th className="text-left py-2 px-2">来源命中率</th>
                        <th className="text-left py-2 px-2">平均耗时</th>
                        <th className="text-left py-2 px-2">创建时间</th>
                        <th className="text-left py-2 px-2">操作</th>
                      </tr>
                    </thead>

                    <tbody>
                      {ragEvalBatchesQuery.data.data.map((batch) => (
                        <tr
                          key={batch.id}
                          className="border-b border-slate-600 text-slate-900"
                        >
                          <td className="py-2 px-2">
                            <div className="space-y-1">
                              <div className="font-medium">{batch.name}</div>

                              {batch.note ? (
                                <div className="text-xs text-slate-900">
                                  {batch.note}
                                </div>
                              ) : null}
                            </div>
                          </td>

                          <td className="py-2 px-2">
                            top_k={batch.top_k} ｜ S={batch.semantic_weight} ｜ K=
                            {batch.keyword_weight}
                          </td>

                          <td className="py-2 px-2">{batch.total_cases}</td>

                          <td className="py-2 px-2">
                            {batch.ran} / {batch.failed}
                          </td>

                          <td className="py-2 px-2">
                            {batch.average_score === null
                              ? "-"
                              : batch.average_score.toFixed(2)}
                          </td>

                          <td className="py-2 px-2">
                            {batch.keyword_hit_rate === null
                              ? "-"
                              : `${(batch.keyword_hit_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {batch.source_hit_rate === null
                              ? "-"
                              : `${(batch.source_hit_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {batch.average_latency_ms === null
                              ? "-"
                              : `${batch.average_latency_ms.toFixed(0)} ms`}
                          </td>

                          <td className="py-2 px-2">
                            {batch.created_at
                              ? new Date(batch.created_at).toLocaleString()
                              : "-"}
                          </td>

                          <td className="py-2 px-2">
                            <button
                              className="border border-rose-200 text-rose-600 rounded px-2 py-1 text-xs"
                              onClick={() => handleDeleteRagEvalBatch(batch.id)}
                              disabled={deleteRagEvalBatchMutation.isPending}
                            >
                              删除
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">失败样例分析</h3>
              <p className="text-sm text-slate-900">
                这里统计最近评测中的失败样例，帮助定位是关键词、来源还是运行错误导致的问题。
              </p>
            </div>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
                })
              }
            >
              刷新分析
            </button>
          </div>

          {ragEvalFailureAnalysisQuery.isLoading ? (
            <div className="text-sm text-slate-900">正在加载失败分析...</div>
          ) : null}

          {ragEvalFailureAnalysisQuery.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              失败分析加载失败：
              {JSON.stringify(ragEvalFailureAnalysisQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalFailureAnalysisQuery.data ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">失败次数</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.failed_runs}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">失败率</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.failure_rate === null
                      ? "-"
                      : `${(
                          ragEvalFailureAnalysisQuery.data.failure_rate * 100
                        ).toFixed(1)}%`}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">关键词未命中</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.keyword_miss_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">来源未命中</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.source_miss_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">运行错误</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.error_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">低分样例</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.low_score_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">零分样例</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.zero_score_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-slate-50 text-slate-900">
                  <div className="text-xs text-slate-900">失败平均耗时</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data
                      .average_failed_latency_ms === null
                      ? "-"
                      : `${ragEvalFailureAnalysisQuery.data.average_failed_latency_ms.toFixed(
                          0,
                        )} ms`}
                  </div>
                </div>
              </div>

              <details>
                <summary className="cursor-pointer text-sm text-slate-600">
                  查看最近失败样例（
                  {ragEvalFailureAnalysisQuery.data.recent_failed_runs.length}）
                </summary>

                <div className="space-y-2 pt-2">
                  {ragEvalFailureAnalysisQuery.data.recent_failed_runs.length ===
                  0 ? (
                    <div className="text-sm text-slate-900">暂无失败样例。</div>
                  ) : (
                    ragEvalFailureAnalysisQuery.data.recent_failed_runs.map(
                      (run) => (
                        <div
                          key={run.id}
                          className="border border-slate-600 rounded p-3 bg-white text-slate-900 space-y-2"
                        >
                          <div className="text-sm font-medium">
                            问题：{run.question}
                          </div>

                          <div className="text-xs text-slate-900">
                            Score：{run.score ?? "-"} ｜ 失败原因：
                            {run.failure_reasons.length > 0
                              ? run.failure_reasons.join("、")
                              : "无"}
                          </div>

                          <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                            {run.answer}
                          </pre>
                        </div>
                      ),
                    )
                  )}
                </div>
              </details>
            </div>
          ) : null}
        </div>

        <div className="border rounded p-3 space-y-3 bg-gray-900">
          <div>
            <h3 className="font-medium">一键生成代码评测集</h3>
            <p className="text-sm text-slate-900">
              根据当前知识库中的代码文件，自动生成代码仓库问答评测用例，例如文件作用、函数定义、类/组件引用位置等问题。
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="text-sm space-y-1">
              <span className="block text-slate-600">最多扫描代码文件数 max_files</span>
              <input
                className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                type="number"
                min={1}
                max={100}
                value={codeEvalMaxFiles}
                onChange={(event) =>
                  setCodeEvalMaxFiles(Number(event.target.value))
                }
              />
            </label>

            <label className="text-sm space-y-1">
              <span className="block text-slate-600">最多生成 symbol 问题数 max_symbols</span>
              <input
                className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                type="number"
                min={1}
                max={200}
                value={codeEvalMaxSymbols}
                onChange={(event) =>
                  setCodeEvalMaxSymbols(Number(event.target.value))
                }
              />
            </label>
          </div>

          <button
            className="border rounded px-4 py-2 text-sm"
            onClick={() => seedCodeEvalCasesMutation.mutate()}
            disabled={seedCodeEvalCasesMutation.isPending}
          >
            {seedCodeEvalCasesMutation.isPending
              ? "正在生成代码评测集..."
              : "一键生成代码评测集"}
          </button>

          {seedCodeEvalCasesMutation.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              生成代码评测集失败：
              {JSON.stringify(seedCodeEvalCasesMutation.error, null, 2)}
            </div>
          ) : null}

          {seedCodeEvalCasesMutation.data ? (
            <div className="text-sm text-emerald-700">
              代码评测集生成完成，共生成{" "}
              {seedCodeEvalCasesMutation.data.count} 条评测用例。
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <h3 className="text-base font-semibold">创建评测样例</h3>

          <input
            className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="评测问题，例如：用户登录状态应该怎么保存？"
            value={evalQuestion}
            onChange={(event) => setEvalQuestion(event.target.value)}
          />

          <input
            className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="预期关键词，用逗号分隔，例如：token, Authorization, JWT"
            value={evalKeywords}
            onChange={(event) => setEvalKeywords(event.target.value)}
          />

          <input
            className="w-full rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="预期来源文件名，可选，例如：auth.md"
            value={evalSourceFilename}
            onChange={(event) => setEvalSourceFilename(event.target.value)}
          />

          <textarea
            className="border rounded px-3 py-2 w-full min-h-20"
            placeholder="备注，可选"
            value={evalNote}
            onChange={(event) => setEvalNote(event.target.value)}
          />

          <button
            className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
            onClick={handleCreateRagEvalCase}
            disabled={createRagEvalCaseMutation.isPending}
          >
            {createRagEvalCaseMutation.isPending ? "创建中..." : "创建评测样例"}
          </button>

          {createRagEvalCaseMutation.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              创建评测样例失败：
              {JSON.stringify(createRagEvalCaseMutation.error, null, 2)}
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-600 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">评测样例列表</h3>

            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-cases", knowledgeBaseId],
                })
              }
            >
              刷新样例
            </button>
          </div>

          {ragEvalCasesQuery.isLoading ? (
            <div className="text-sm text-slate-900">正在加载评测样例...</div>
          ) : null}

          {ragEvalCasesQuery.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              评测样例加载失败：
              {JSON.stringify(ragEvalCasesQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalCasesQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-slate-900">
                共 {ragEvalCasesQuery.data.count} 条评测样例。
              </div>

              {ragEvalCasesQuery.data.data.length === 0 ? (
                <div className="text-sm text-slate-900">
                  暂无评测样例。可以先在上方创建一个测试问题。
                </div>
              ) : (
                <div className="space-y-3">
                  {ragEvalCasesQuery.data.data.map((evalCase) => {
                    const caseType = getCodeEvalCaseType(evalCase.note)
                    const caseTypeLabel = getCodeEvalCaseTypeLabel(caseType)
                    const caseTypeClassName = getCodeEvalCaseTypeClassName(caseType)

                    return (
                      <div key={evalCase.id} className="rounded-xl border border-slate-600 bg-white p-3 space-y-2">
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="font-medium">
                              {evalCase.question}
                            </div>

                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <span
                                className={`inline-flex items-center rounded-full border px-2 py-0.5 ${caseTypeClassName}`}
                              >
                                类型：{caseTypeLabel}
                              </span>

                              {evalCase.expected_source_filename ? (
                                <span className="text-slate-900">
                                  预期来源：{evalCase.expected_source_filename}
                                </span>
                              ) : null}
                            </div>
                          </div>

                          <button
                            className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                            onClick={() => handleRunRagEvalCase(evalCase.id)}
                            disabled={runningEvalCaseIds.has(evalCase.id)}
                          >
                            {runningEvalCaseIds.has(evalCase.id)
                              ? "运行中..."
                              : "运行评测"}
                          </button>
                        </div>

                        {evalCase.expected_keywords_json ? (
                          <div className="text-xs text-slate-900 break-all">
                            预期关键词：{evalCase.expected_keywords_json}
                          </div>
                        ) : null}

                        {evalCase.note ? (
                          <div className="text-xs text-slate-900">
                            note：{evalCase.note}
                          </div>
                        ) : null}

                        {evalCase.created_at ? (
                          <div className="text-xs text-slate-900">
                            创建时间：{new Date(evalCase.created_at).toLocaleString()}
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          ) : null}

          {runRagEvalCaseMutation.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              运行评测失败：
              {JSON.stringify(runRagEvalCaseMutation.error, null, 2)}
            </div>
          ) : null}

          {deleteRagEvalCaseMutation.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              删除评测样例失败：
              {JSON.stringify(deleteRagEvalCaseMutation.error, null, 2)}
            </div>
          ) : null}
        </div>

        <CollapsibleSection
          title="评测运行结果"
          description="查看 RAG Eval 的运行结果、失败样例、评分和参数记录。"
          isOpen={expandedSections.evalRuns}
          onToggle={() => toggleSection("evalRuns")}
        >
          <div className="flex justify-end">
            <button
              className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-runs", knowledgeBaseId],
                })
              }
            >
              刷新结果
            </button>
          </div>

          <div className="flex flex-col md:flex-row gap-3">
            <input
              className="flex-1 rounded-lg border border-slate-600 bg-white px-3 py-2 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
              placeholder="搜索评测结果，例如：登录、token、FastAPI"
              value={evalRunKeyword}
              onChange={(event) => setEvalRunKeyword(event.target.value)}
            />

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={evalFailedOnly}
                onChange={(event) => setEvalFailedOnly(event.target.checked)}
              />
              只看失败样例
            </label>

            <select
              className="rounded-lg border border-slate-600 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              value={evalFailureType}
              onChange={(event) =>
                setEvalFailureType(
                  event.target.value as
                    | "all"
                    | "keyword"
                    | "source"
                    | "error"
                    | "zero",
                )
              }
            >
              <option value="all">全部类型</option>
              <option value="keyword">关键词未命中</option>
              <option value="source">来源未命中</option>
              <option value="error">运行错误</option>
              <option value="zero">零分样例</option>
            </select>

            <button
              className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
              onClick={() => {
                setEvalRunKeyword("")
                setEvalFailedOnly(false)
                setEvalFailureType("all")
              }}
            >
              清空筛选
            </button>
          </div>

          {ragEvalRunsQuery.isLoading ? (
            <div className="text-sm text-slate-900">正在加载评测结果...</div>
          ) : null}

          {ragEvalRunsQuery.isError ? (
            <div className="text-sm text-rose-600 whitespace-pre-wrap">
              评测结果加载失败：
              {JSON.stringify(ragEvalRunsQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalRunsQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-slate-900">
                共 {ragEvalRunsQuery.data.count} 条评测运行结果。
              </div>

              {ragEvalRunsQuery.data.data.length === 0 ? (
                <div className="text-sm text-slate-900">
                  暂无评测结果。可以先点击某条样例的“运行评测”。
                </div>
              ) : (
                ragEvalRunsQuery.data.data.map((run) => (
                  <div
                    key={run.id}
                    className="border border-slate-600 rounded p-4 bg-slate-50 text-slate-900 space-y-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">问题：{run.question}</div>

                      <div className="text-xs text-slate-900">
                        Score：{run.score ?? "-"} ｜ 关键词命中：
                        {run.keyword_hit === null
                          ? "-"
                          : run.keyword_hit
                            ? "是"
                            : "否"}{" "}
                        ｜ 来源命中：
                        {run.source_hit === null
                          ? "-"
                          : run.source_hit
                            ? "是"
                            : "否"}{" "}
                        ｜ 耗时：{run.latency_ms ?? "-"} ms
                      </div>
                    </div>

                    <div className="text-xs text-slate-900">
                      预期关键词：
                      {run.expected_keywords.length > 0
                        ? run.expected_keywords.join("、")
                        : "无"}{" "}
                      ｜ 预期来源：
                      {run.expected_source_filename || "无"} ｜ 检索方式：
                      {run.retrieval_type} ｜ top_k：{run.top_k} ｜ 语义权重：
                      {run.semantic_weight} ｜ 关键词权重：{run.keyword_weight}
                    </div>

                    {run.is_failed ? (
                      <div className="text-xs text-rose-600">
                        失败原因：
                        {run.failure_reasons.length > 0
                          ? run.failure_reasons.join("、")
                          : "未知原因"}
                      </div>
                    ) : (
                      <div className="text-xs text-emerald-600">
                        当前评测未发现失败项
                      </div>
                    )}

                    <div className="space-y-1">
                      <div className="text-sm font-medium text-slate-700">回答</div>
                      <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                        {run.answer}
                      </pre>
                    </div>

                    <details>
                      <summary className="cursor-pointer text-sm text-slate-600">
                        查看引用来源（{run.sources.length}）
                      </summary>

                      <div className="space-y-2 pt-2">
                        {run.sources.length === 0 ? (
                          <div className="text-sm text-slate-900">
                            当前评测结果没有引用来源。
                          </div>
                        ) : (
                          run.sources.map((source) => (
                            <div
                              key={source.chunk_id}
                              className="border border-slate-600 rounded p-3 bg-white text-slate-900 space-y-2"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-sm font-medium">
                                  来源文件：{source.original_filename} ｜ Chunk{" "}
                                  {source.chunk_index}
                                </div>

                                <div className="text-xs text-slate-900">
                                  相似度：{source.similarity?.toFixed(4)} ｜
                                  关键词命中：{source.match_count} ｜ 长度：
                                  {source.content_length}
                                </div>
                              </div>

                              <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                                {source.content}
                              </pre>
                            </div>
                          ))
                        )}
                      </div>
                    </details>

                    <details>
                      <summary className="cursor-pointer text-sm text-slate-600">
                        查看执行过程 Trace
                      </summary>

                      <div className="pt-2 text-sm text-slate-900">
                        {run.trace.length > 0 ? run.trace.join(" → ") : "暂无 trace"}
                      </div>
                    </details>

                    {run.created_at ? (
                      <div className="text-xs text-slate-900">
                        创建时间：{new Date(run.created_at).toLocaleString()}
                      </div>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          ) : null}
        </CollapsibleSection>
      </div>


          </div>
        ) : null}

        {activeWorkspaceTab === "overview" ? (
      <CollapsibleSection
        title="文档列表"
        description="查看当前知识库中的文档。点击展开后显示文档详情、解析状态和切分结果入口。"
        isOpen={expandedSections.documents}
        onToggle={() => toggleSection("documents")}
      >

        {documents.data.length === 0 ? (
          <div className="text-slate-900">该知识库下暂无文档</div>
        ) : (
          <div className="space-y-3">
            {documents.data.map((document) => {
              const isExpanded = expandedDocumentId === document.id

              return (
                <div key={document.id} className="rounded-xl border border-slate-600 bg-white p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">
                        {document.original_filename}
                      </div>

                      <div className="text-sm text-slate-900">
                        类型：{document.content_type || "未知"} ｜ 大小：
                        {formatFileSize(document.file_size)} ｜ 状态：
                        {document.status}
                      </div>

                      {document.error_message ? (
                        <div className="text-sm text-rose-600">
                          解析信息：{document.error_message}
                        </div>
                      ) : null}

                      <div className="text-xs text-slate-900">
                        文档 ID：{document.id}
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button
                        className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                        onClick={() => handleToggleChunks(document.id)}
                      >
                        {isExpanded ? "收起切分结果" : "查看切分结果"}
                      </button>

                      <button
                        className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                        onClick={() =>
                          handleDownload(document.id, document.original_filename)
                        }
                      >
                        下载
                      </button>

                      <button
                        className="rounded-lg border border-slate-600 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
                        onClick={() => {
                          if (confirm("确定删除这个文档吗？")) {
                            deleteDocumentMutation.mutate(document.id)
                          }
                        }}
                        disabled={deleteDocumentMutation.isPending}
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  {isExpanded ? (
                    <div className="border-t pt-4 space-y-3">
                      <div className="font-medium">切分结果</div>

                      {isChunksPending ? (
                        <div className="text-sm text-slate-900">
                          正在加载切分结果...
                        </div>
                      ) : null}

                      {isChunksError ? (
                        <div className="text-sm text-rose-600">
                          切分结果加载失败
                        </div>
                      ) : null}

                      {!isChunksPending &&
                      !isChunksError &&
                      chunks?.data.length === 0 ? (
                        <div className="text-sm text-slate-900">
                          暂无切分结果。可能是文件未解析成功、内容为空，或 PDF 为扫描版图片。
                        </div>
                      ) : null}

                      {!isChunksPending &&
                      !isChunksError &&
                      chunks?.data.map((chunk) => (
                        <div
                          key={chunk.id}
                          className="border border-slate-600 rounded p-3 bg-slate-50 text-slate-900 space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <div className="text-sm font-medium text-slate-900">
                              Chunk {chunk.chunk_index}
                            </div>

                            <div className="text-xs text-slate-900">
                              长度：{chunk.content_length}
                            </div>
                          </div>

                          <pre className="text-sm whitespace-pre-wrap break-words font-sans text-slate-900">
                            {chunk.content}
                          </pre>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </CollapsibleSection>
        ) : null}
      </div>
    </div>
  )
}