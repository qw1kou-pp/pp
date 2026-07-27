import type {
  AgentChatResponse,
  AgentRunPublic,
  KnowledgeBaseSearchResults,
  KnowledgeBaseSemanticSearchResults,
  RagChatResponse,
  RagRunPublic,
} from "@/client"

import type {
  AppliedAgentConfig,
} from "./knowledgeBaseDetailTypes"

export type RetrievalSettings = {
  topK: number
  semanticWeight: number
  keywordWeight: number
}

export type KnowledgeBaseChatState = {
  searchQuery: string
  semanticQuery: string
  chatQuestion: string
  ragRunKeyword: string
  agentQuestion: string
  agentRunKeyword: string
  compareQuestion: string
}

export type KnowledgeBaseSearchViewModel = {
  data?: KnowledgeBaseSearchResults
  isPending: boolean
  isError: boolean
  error: unknown
}

export type KnowledgeBaseSemanticSearchViewModel = {
  data?: KnowledgeBaseSemanticSearchResults
  isPending: boolean
  isError: boolean
  error: unknown
}

export type RagChatViewModel = {
  data?: RagChatResponse
  isPending: boolean
  isError: boolean
  error: unknown
}

export type AgentChatViewModel = {
  data?: AgentChatResponse
  isPending: boolean
  isError: boolean
  error: unknown
}

export type RagAgentSingleCompareResult = {
  ragResult: RagChatResponse
  agentResult: AgentChatResponse
}

export type RagRunListViewModel = {
  data?: {
    data: RagRunPublic[]
    count: number
  }
  isLoading: boolean
  isError: boolean
  error: unknown
}

export type AgentRunListViewModel = {
  data?: {
    data: AgentRunPublic[]
    count: number
  }
  isLoading: boolean
  isError: boolean
  error: unknown
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

export function normalizeRetrievalSettings(
  value?: Partial<RetrievalSettings>,
): RetrievalSettings {
  const topK = clampNumber(
    value?.topK,
    1,
    20,
    DEFAULT_RETRIEVAL_SETTINGS.topK,
  )

  let semanticWeight = clampNumber(
    value?.semanticWeight,
    0,
    1,
    DEFAULT_RETRIEVAL_SETTINGS.semanticWeight,
  )

  let keywordWeight = clampNumber(
    value?.keywordWeight,
    0,
    1,
    DEFAULT_RETRIEVAL_SETTINGS.keywordWeight,
  )

  if (
    semanticWeight + keywordWeight
    <= 0
  ) {
    semanticWeight =
      DEFAULT_RETRIEVAL_SETTINGS.semanticWeight

    keywordWeight =
      DEFAULT_RETRIEVAL_SETTINGS.keywordWeight
  }

  return {
    topK,
    semanticWeight,
    keywordWeight,
  }
}

export function normalizeAgentConfig(
  value?: Partial<AppliedAgentConfig>,
): AppliedAgentConfig {
  return {
    topK: clampNumber(
      value?.topK,
      1,
      20,
      DEFAULT_AGENT_CONFIG.topK,
    ),

    maxSteps: clampNumber(
      value?.maxSteps,
      1,
      20,
      DEFAULT_AGENT_CONFIG.maxSteps,
    ),

    semanticWeight: clampNumber(
      value?.semanticWeight,
      0,
      1,
      DEFAULT_AGENT_CONFIG.semanticWeight,
    ),

    keywordWeight: clampNumber(
      value?.keywordWeight,
      0,
      1,
      DEFAULT_AGENT_CONFIG.keywordWeight,
    ),
  }
}

export function formatKnowledgeBaseChatError(
  error: unknown,
): string {
  if (error instanceof Error) {
    return error.message
  }

  if (
    typeof error === "object"
    && error !== null
  ) {
    const candidate = error as {
      message?: unknown
      body?: unknown
    }

    if (
      typeof candidate.message
      === "string"
      && candidate.message.trim()
    ) {
      return candidate.message
    }

    try {
      return JSON.stringify(
        candidate.body ?? error,
        null,
        2,
      )
    } catch {
      return "请求失败，请检查后端日志。"
    }
  }

  return String(error)
}

function clampNumber(
  value: number | undefined,
  min: number,
  max: number,
  fallback: number,
): number {
  if (
    value === undefined
    || !Number.isFinite(value)
  ) {
    return fallback
  }

  return Math.min(
    Math.max(value, min),
    max,
  )
}
