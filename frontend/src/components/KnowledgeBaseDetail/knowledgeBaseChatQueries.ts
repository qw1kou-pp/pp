import {
  DocumentsService,
} from "@/client"
import {
  queryOptions,
} from "@tanstack/react-query"

export const knowledgeBaseChatKeys = {
  all: [
    "knowledge-base-chat",
  ] as const,

  ragRuns: (
    knowledgeBaseId: string,
    keyword: string,
  ) => [
    ...knowledgeBaseChatKeys.all,
    "rag-runs",
    knowledgeBaseId,
    keyword,
  ] as const,

  agentRuns: (
    knowledgeBaseId: string,
    keyword: string,
  ) => [
    ...knowledgeBaseChatKeys.all,
    "agent-runs",
    knowledgeBaseId,
    keyword,
  ] as const,

  agentSettings: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseChatKeys.all,
    "agent-settings",
    knowledgeBaseId,
  ] as const,
}

export function ragRunsQueryOptions({
  knowledgeBaseId,
  keyword,
}: {
  knowledgeBaseId: string
  keyword: string
}) {
  const normalizedKeyword =
    keyword.trim()

  return queryOptions({
    queryKey:
      knowledgeBaseChatKeys.ragRuns(
        knowledgeBaseId,
        normalizedKeyword,
      ),

    queryFn: () =>
      DocumentsService.readKnowledgeBaseRagRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword:
          normalizedKeyword
          || undefined,
      }),
  })
}

export function agentRunsQueryOptions({
  knowledgeBaseId,
  keyword,
}: {
  knowledgeBaseId: string
  keyword: string
}) {
  const normalizedKeyword =
    keyword.trim()

  return queryOptions({
    queryKey:
      knowledgeBaseChatKeys.agentRuns(
        knowledgeBaseId,
        normalizedKeyword,
      ),

    queryFn: () =>
      DocumentsService.readAgentRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword:
          normalizedKeyword
          || undefined,
      }),
  })
}

export function agentSettingsQueryOptions(
  knowledgeBaseId: string,
) {
  return queryOptions({
    queryKey:
      knowledgeBaseChatKeys.agentSettings(
        knowledgeBaseId,
      ),

    queryFn: () =>
      DocumentsService.readKnowledgeBaseAgentSettings({
        knowledgeBaseId,
      }),
  })
}
