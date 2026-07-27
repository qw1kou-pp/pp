import {
  readArrayField,
  readField,
  readNumberField,
} from "./compareUtils"
import {
  getResultLabel,
  type CodeAgentOptimizationAdvice,
  type OptimizationCompareRow,
} from "./codeAgentOptimization"
import {
  formatLatency,
  formatNullableNumber,
  formatPercent,
  formatReportDateTime,
  safeMarkdownText,
} from "./knowledgeBaseFormatters"

const buildBatchSummaryMarkdown = (batch: any, label: string) => {
  if (!batch) {
    return `### ${label}\n\n未选择批次。\n`
  }

  const failed = readNumberField(batch, "failed", "failed", 0)
  const ran = readNumberField(batch, "ran", "ran", 0)
  const attempted = ran + failed
  const failureRate = attempted > 0 ? failed / attempted : null

  return [
    `### ${label}`,
    "",
    `- 批次名称：${readField<string>(batch, "name", "name", "-")}`,
    `- 批次 ID：${readField<string>(batch, "id", "id", "-")}`,
    `- 创建时间：${formatReportDateTime(
      readField<string | null>(batch, "created_at", "createdAt", null),
    )}`,
    `- 样例数量：${readNumberField(batch, "total_cases", "totalCases", 0)}`,
    `- 总尝试数：${attempted}`,
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

export const buildCodeAgentExperimentReportMarkdown = ({
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


