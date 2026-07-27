import {
  getSummaryValue,
  readArrayField,
  readField,
  readNumberField,
} from "./compareUtils"
import {
  formatLatency,
  formatPercent,
  formatSignedLatency,
  formatSignedNumber,
  formatSignedPercentPoint,
} from "./knowledgeBaseFormatters"

const KNOWN_CODE_EVAL_CASE_TYPES = new Set([
  "file_overview",
  "symbol_definition",
  "symbol_reference",
  "code_logic",
  "bug_location",
  "unknown",
])

export const getCodeEvalCaseType = (note?: string | null) => {
  const normalizedNote = note?.trim()

  if (!normalizedNote) {
    return "unknown"
  }

  if (normalizedNote.startsWith("code:")) {
    const candidate = normalizedNote.slice("code:".length).trim()
    return KNOWN_CODE_EVAL_CASE_TYPES.has(candidate) ? candidate : "unknown"
  }

  if (
    normalizedNote.includes("代码文件列表") ||
    normalizedNote.includes("代码文件作用")
  ) {
    return "file_overview"
  }

  if (normalizedNote.includes("定义与作用")) {
    return "symbol_definition"
  }

  if (normalizedNote.includes("引用定位")) {
    return "symbol_reference"
  }

  return "unknown"
}

export const getCodeEvalCaseTypeLabel = (caseType: string) => {
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

export const getCodeEvalCaseTypeClassName = (caseType: string) => {
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

export type CodeAgentOptimizationAdvice = {
  level: "high" | "medium" | "low"
  title: string
  reason: string
  suggestion: string
}

export const getAdviceLevelClassName = (level: CodeAgentOptimizationAdvice["level"]) => {
  const classMap: Record<CodeAgentOptimizationAdvice["level"], string> = {
    high: "border-rose-200 bg-rose-50 text-rose-800",
    medium: "border-amber-200 bg-amber-50 text-amber-800",
    low: "border-sky-200 bg-sky-50 text-sky-800",
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

export const buildCodeAgentOptimizationAdvice = ({
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

export type OptimizationCompareResult = "better" | "worse" | "neutral"

export type OptimizationCompareRow = {
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


export const getResultClassName = (result: OptimizationCompareResult) => {
  const classMap: Record<OptimizationCompareResult, string> = {
    better: "text-emerald-600",
    worse: "text-rose-600",
    neutral: "text-slate-900",
  }

  return classMap[result]
}

export const getResultLabel = (result: OptimizationCompareResult) => {
  const labelMap: Record<OptimizationCompareResult, string> = {
    better: "改善",
    worse: "变差",
    neutral: "基本不变",
  }

  return labelMap[result]
}

export const buildOptimizationCompareRows = (
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

  const beforeAttempted = beforeRan + beforeFailed
  const afterAttempted = afterRan + afterFailed

  const beforeFailureRate =
    beforeAttempted > 0 ? beforeFailed / beforeAttempted : null

  const afterFailureRate =
    afterAttempted > 0 ? afterFailed / afterAttempted : null

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
      changeText: formatSignedLatency(change),
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
    result: "neutral",
    explanation:
      "调用次数增加表示 Agent 更频繁地读取上下文，但不一定代表效果改善，需要结合来源命中率、失败率和耗时一起判断。",
  })

  return rows
}

export const buildAgentParamRecommendation = (tuningResults: any[]) => {
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

    const totalCases = getSummaryValue<number>(
      summary,
      "total_cases",
      "totalCases",
      preset.limit ?? 0,
    )

    const failureRate =
      totalCases > 0 ? failed / totalCases : failed > 0 ? 1 : 0

    const failurePenalty = failureRate * 1000
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
      totalCases,
      failureRate,
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

