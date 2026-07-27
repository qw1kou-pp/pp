import {
  KnowledgeBasesService,
} from "@/client"
import {
  queryOptions,
} from "@tanstack/react-query"

export const knowledgeBaseDetailKeys = {
  all:
    ["knowledge-base-detail"] as const,

  detail: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseDetailKeys.all,
    knowledgeBaseId,
  ] as const,
}

export function knowledgeBaseDetailQueryOptions(
  knowledgeBaseId: string,
) {
  return queryOptions({
    queryKey:
      knowledgeBaseDetailKeys.detail(
        knowledgeBaseId,
      ),

    queryFn: () =>
      KnowledgeBasesService.readKnowledgeBase({
        id: knowledgeBaseId,
      }),
  })
}
