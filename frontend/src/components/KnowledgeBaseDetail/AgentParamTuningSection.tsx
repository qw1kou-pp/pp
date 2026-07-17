import { CollapsibleSection } from "./CollapsibleSection"
import { readField } from "./compareUtils"

export type AgentParamConfig = {
  topK: number
  maxSteps: number
  limit: number
  semanticWeight: number
  keywordWeight: number
}

export type AgentParamPreset = AgentParamConfig & {
  name: string
}

export const AGENT_PARAM_PRESETS: AgentParamPreset[] = [
  {
    name: "保守配置：少检索 + 少步骤",
    topK: 3,
    maxSteps: 3,
    limit: 10,
    semanticWeight: 0.75,
    keywordWeight: 0.25,
  },
  {
    name: "默认配置：平衡",
    topK: 5,
    maxSteps: 5,
    limit: 10,
    semanticWeight: 0.75,
    keywordWeight: 0.25,
  },
  {
    name: "高召回配置：更多 sources",
    topK: 10,
    maxSteps: 5,
    limit: 10,
    semanticWeight: 0.75,
    keywordWeight: 0.25,
  },
  {
    name: "多步 Agent 配置：更多工具步骤",
    topK: 5,
    maxSteps: 8,
    limit: 10,
    semanticWeight: 0.75,
    keywordWeight: 0.25,
  },
  {
    name: "更偏语义检索",
    topK: 5,
    maxSteps: 5,
    limit: 10,
    semanticWeight: 0.9,
    keywordWeight: 0.1,
  },
  {
    name: "语义 + 关键词更均衡",
    topK: 5,
    maxSteps: 5,
    limit: 10,
    semanticWeight: 0.6,
    keywordWeight: 0.4,
  },
]

type AgentParamTuningSectionProps = {
  isOpen: boolean
  onToggle: () => void

  config: AgentParamConfig
  onConfigChange: (config: AgentParamConfig) => void

  onRunTuning: () => void
  isTuningPending: boolean
  isTuningError: boolean
  tuningError: unknown
  tuningData: any

  recommendation: any
  onApplyRecommendation: () => void
  isApplyRecommendationPending: boolean
  isApplyRecommendationError?: boolean
  applyRecommendationError?: unknown
}

const formatNumber = (value: number | null | undefined, suffix = "") => {
  if (value === null || value === undefined) {
    return "-"
  }

  if (Number.isInteger(value)) {
    return `${value}${suffix}`
  }

  return `${value.toFixed(2)}${suffix}`
}

const readRecommendedConfig = (recommendation: any): Partial<AgentParamConfig> => {
  if (!recommendation) {
    return {}
  }

  const config =
    recommendation.recommendedConfig ??
    recommendation.recommended_config ??
    recommendation.config ??
    recommendation

  return {
    topK: readField<number | undefined>(config, "top_k", "topK", undefined),
    maxSteps: readField<number | undefined>(
      config,
      "max_steps",
      "maxSteps",
      undefined,
    ),
    limit: readField<number | undefined>(config, "limit", "limit", undefined),
    semanticWeight: readField<number | undefined>(
      config,
      "semantic_weight",
      "semanticWeight",
      undefined,
    ),
    keywordWeight: readField<number | undefined>(
      config,
      "keyword_weight",
      "keywordWeight",
      undefined,
    ),
  }
}

export const AgentParamTuningSection = ({
  isOpen,
  onToggle,
  config,
  onConfigChange,
  onRunTuning,
  isTuningPending,
  isTuningError,
  tuningError,
  tuningData,
  recommendation,
  onApplyRecommendation,
  isApplyRecommendationPending,
  isApplyRecommendationError = false,
  applyRecommendationError,
}: AgentParamTuningSectionProps) => {
  const tuningResults = Array.isArray(tuningData) ? tuningData : []
  const tuningSummary = readField<any>(tuningData, "summary", "summary", null)

  const recommendedConfig = readRecommendedConfig(recommendation)

  const updateConfig = (partial: Partial<AgentParamConfig>) => {
    onConfigChange({
      ...config,
      ...partial,
    })
  }

  return (
    <CollapsibleSection
      title="Agent 参数优化实验"
      description="对比不同 top_k、max_steps、semantic_weight 和 keyword_weight 配置，辅助选择更合适的 Agent 默认参数。"
      isOpen={isOpen}
      onToggle={onToggle}
    >
      <div className="space-y-4">
        <div className="border rounded p-3 space-y-3">
          <div>
            <h3 className="text-base font-semibold">当前参数</h3>
            <p className="text-sm text-gray-500">
              这里的参数会用于下一次 Agent 参数优化实验。
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <label className="text-sm space-y-1">
              <span className="text-gray-500">top_k</span>
              <input
                className="border rounded px-2 py-1 w-full"
                type="number"
                min={1}
                max={20}
                value={config.topK}
                onChange={(event) =>
                  updateConfig({
                    topK: Number(event.target.value),
                  })
                }
              />
            </label>

            <label className="text-sm space-y-1">
              <span className="text-gray-500">max_steps</span>
              <input
                className="border rounded px-2 py-1 w-full"
                type="number"
                min={1}
                max={10}
                value={config.maxSteps}
                onChange={(event) =>
                  updateConfig({
                    maxSteps: Number(event.target.value),
                  })
                }
              />
            </label>

            <label className="text-sm space-y-1">
              <span className="text-gray-500">limit</span>
              <input
                className="border rounded px-2 py-1 w-full"
                type="number"
                min={1}
                max={50}
                value={config.limit}
                onChange={(event) =>
                  updateConfig({
                    limit: Number(event.target.value),
                  })
                }
              />
            </label>

            <label className="text-sm space-y-1">
              <span className="text-gray-500">semantic_weight</span>
              <input
                className="border rounded px-2 py-1 w-full"
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={config.semanticWeight}
                onChange={(event) =>
                  updateConfig({
                    semanticWeight: Number(event.target.value),
                  })
                }
              />
            </label>

            <label className="text-sm space-y-1">
              <span className="text-gray-500">keyword_weight</span>
              <input
                className="border rounded px-2 py-1 w-full"
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={config.keywordWeight}
                onChange={(event) =>
                  updateConfig({
                    keywordWeight: Number(event.target.value),
                  })
                }
              />
            </label>
          </div>

          <div className="flex flex-wrap gap-2">
            {AGENT_PARAM_PRESETS.map((preset) => (
              <button
                key={preset.name}
                type="button"
                className="border rounded px-3 py-1 text-sm"
                onClick={() =>
                  onConfigChange({
                    topK: preset.topK,
                    maxSteps: preset.maxSteps,
                    limit: preset.limit,
                    semanticWeight: preset.semanticWeight,
                    keywordWeight: preset.keywordWeight,
                  })
                }
              >
                {preset.name}
              </button>
            ))}
          </div>

          <div>
            <button
              type="button"
              className="border rounded px-3 py-1 text-sm"
              onClick={onRunTuning}
              disabled={isTuningPending}
            >
              {isTuningPending ? "正在运行参数优化..." : "运行参数优化实验"}
            </button>
          </div>
        </div>

        {isTuningError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            参数优化实验失败：
            {JSON.stringify(tuningError, null, 2)}
          </div>
        ) : null}

        {tuningSummary ? (
          <div className="border rounded p-3 space-y-3">
            <h3 className="text-base font-semibold">参数优化汇总</h3>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="border rounded p-2">
                <div className="text-xs text-gray-400">总样例数</div>
                <div className="text-base font-semibold">
                  {readField<number>(tuningSummary, "total_cases", "totalCases", 0)}
                </div>
              </div>

              <div className="border rounded p-2">
                <div className="text-xs text-gray-400">运行数</div>
                <div className="text-base font-semibold">
                  {readField<number>(tuningSummary, "ran", "ran", 0)}
                </div>
              </div>

              <div className="border rounded p-2">
                <div className="text-xs text-gray-400">失败数</div>
                <div className="text-base font-semibold">
                  {readField<number>(tuningSummary, "failed", "failed", 0)}
                </div>
              </div>

              <div className="border rounded p-2">
                <div className="text-xs text-gray-400">工具失败总数</div>
                <div className="text-base font-semibold">
                  {readField<number>(
                    tuningSummary,
                    "total_agent_failed_tool_count",
                    "totalAgentFailedToolCount",
                    0,
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {recommendation ? (
          <div className="border rounded p-3 space-y-3">
            <div>
              <h3 className="text-base font-semibold">推荐配置</h3>
              <p className="text-sm text-gray-500">
                根据当前参数优化结果，自动推荐更适合作为 Agent 默认参数的配置。
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              <div className="border rounded p-2">
                <div className="text-xs text-gray-400">top_k</div>
                <div className="text-base font-semibold">
                  {recommendedConfig.topK ?? "-"}
                </div>
              </div>

              <div className="border rounded p-2">
                <div className="text-xs text-gray-400">max_steps</div>
                <div className="text-base font-semibold">
                  {recommendedConfig.maxSteps ?? "-"}
                </div>
              </div>

              <div className="border rounded p-2">
                <div className="text-xs text-gray-400">limit</div>
                <div className="text-base font-semibold">
                  {recommendedConfig.limit ?? "-"}
                </div>
              </div>

              <div className="border rounded p-2">
                <div className="text-xs text-gray-400">semantic_weight</div>
                <div className="text-base font-semibold">
                  {recommendedConfig.semanticWeight ?? "-"}
                </div>
              </div>

              <div className="border rounded p-2">
                <div className="text-xs text-gray-400">keyword_weight</div>
                <div className="text-base font-semibold">
                  {recommendedConfig.keywordWeight ?? "-"}
                </div>
              </div>
            </div>

            <div className="text-sm text-gray-700 whitespace-pre-wrap">
              {readField<string>(
                recommendation,
                "reason",
                "reason",
                "当前推荐结果没有提供额外说明。",
              )}
            </div>

            <button
              type="button"
              className="border rounded px-3 py-1 text-sm"
              onClick={onApplyRecommendation}
              disabled={isApplyRecommendationPending}
            >
              {isApplyRecommendationPending
                ? "正在应用推荐参数..."
                : "一键应用推荐参数"}
            </button>

            {isApplyRecommendationError ? (
              <div className="text-sm text-red-500 whitespace-pre-wrap">
                应用推荐参数失败：
                {JSON.stringify(applyRecommendationError, null, 2)}
              </div>
            ) : null}
          </div>
        ) : null}

        {tuningResults.length > 0 ? (
          <div className="border rounded p-3 space-y-3">
            <h3 className="text-base font-semibold">参数优化明细</h3>

            <div className="space-y-3">
              {tuningResults.map((item, index) => {
                const question = readField<string>(
                  item,
                  "question",
                  "question",
                  "",
                )

                const ragLatency = readField<number | null>(
                  item,
                  "rag_latency_ms",
                  "ragLatencyMs",
                  null,
                )

                const agentLatency = readField<number | null>(
                  item,
                  "agent_latency_ms",
                  "agentLatencyMs",
                  null,
                )

                const agentToolCallCount = readField<number>(
                  item,
                  "agent_tool_call_count",
                  "agentToolCallCount",
                  0,
                )

                const agentFailedToolCount = readField<number>(
                  item,
                  "agent_failed_tool_count",
                  "agentFailedToolCount",
                  0,
                )

                const isFailed = readField<boolean>(
                  item,
                  "is_failed",
                  "isFailed",
                  false,
                )

                return (
                  <details
                    key={readField<string>(item, "id", "id", `${index}`)}
                    className="border rounded p-3"
                  >
                    <summary className="cursor-pointer text-sm font-medium">
                      {index + 1}. {question || "未命名问题"}
                      {" ｜ "}
                      RAG：{formatNumber(ragLatency, " ms")}
                      {" ｜ "}
                      Agent：{formatNumber(agentLatency, " ms")}
                      {" ｜ "}
                      工具：{agentToolCallCount}
                      {" ｜ "}
                      工具失败：{agentFailedToolCount}
                      {" ｜ "}
                      {isFailed ? "有失败" : "正常"}
                    </summary>

                    <div className="text-sm whitespace-pre-wrap mt-3">
                      {JSON.stringify(item, null, 2)}
                    </div>
                  </details>
                )
              })}
            </div>
          </div>
        ) : null}
      </div>
    </CollapsibleSection>
  )
}