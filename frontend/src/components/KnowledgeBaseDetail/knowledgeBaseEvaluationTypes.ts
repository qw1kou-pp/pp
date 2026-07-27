import type {
  AgentParamConfig,
} from "./AgentParamTuningSection"
import type {
  AppliedAgentConfig,
} from "./knowledgeBaseDetailTypes"

export type EvaluationFailureFilter =
  | "all"
  | "keyword"
  | "source"
  | "error"
  | "zero"

export type RetrievalSettings = {
  topK: number
  semanticWeight: number
  keywordWeight: number
}

export const DEFAULT_RETRIEVAL_SETTINGS:
  RetrievalSettings = {
    topK: 5,
    semanticWeight: 0.75,
    keywordWeight: 0.25,
  }

export const DEFAULT_AGENT_CONFIG:
  AppliedAgentConfig = {
    topK: 5,
    maxSteps: 5,
    semanticWeight: 0.75,
    keywordWeight: 0.25,
  }

export const DEFAULT_AGENT_TUNING_CONFIG:
  AgentParamConfig = {
    topK: 5,
    maxSteps: 5,
    limit: 10,
    semanticWeight: 0.75,
    keywordWeight: 0.25,
  }

export function normalizeRetrievalSettings({
  topK,
  semanticWeight,
  keywordWeight,
}: RetrievalSettings): RetrievalSettings {
  const normalizedTopK = Math.min(
    Math.max(Number(topK) || 5, 1),
    20,
  )

  const normalizedSemanticWeight = Math.min(
    Math.max(Number(semanticWeight) || 0, 0),
    1,
  )

  const normalizedKeywordWeight = Math.min(
    Math.max(Number(keywordWeight) || 0, 0),
    1,
  )

  if (
    normalizedSemanticWeight
      + normalizedKeywordWeight
    <= 0
  ) {
    return {
      topK: normalizedTopK,
      semanticWeight: 0.75,
      keywordWeight: 0.25,
    }
  }

  return {
    topK: normalizedTopK,
    semanticWeight:
      normalizedSemanticWeight,
    keywordWeight:
      normalizedKeywordWeight,
  }
}
