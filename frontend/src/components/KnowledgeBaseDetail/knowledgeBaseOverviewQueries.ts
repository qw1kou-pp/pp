import { DocumentsService } from "@/client"
import { queryOptions } from "@tanstack/react-query"

export const knowledgeBaseOverviewKeys = {
  all: ["knowledge-base-overview"] as const,

  documents: (knowledgeBaseId: string) =>
    [
      ...knowledgeBaseOverviewKeys.all,
      "documents",
      knowledgeBaseId,
    ] as const,

  chunks: (documentId: string) =>
    [
      ...knowledgeBaseOverviewKeys.all,
      "document-chunks",
      documentId,
    ] as const,
}

export function knowledgeBaseDocumentsQueryOptions(
  knowledgeBaseId: string,
) {
  return queryOptions({
    queryKey:
      knowledgeBaseOverviewKeys.documents(
        knowledgeBaseId,
      ),

    queryFn: () =>
      DocumentsService.readDocumentsByKnowledgeBase({
        knowledgeBaseId,
        skip: 0,
        limit: 100,
      }),
  })
}

export function documentChunksQueryOptions(
  documentId: string,
) {
  return queryOptions({
    queryKey:
      knowledgeBaseOverviewKeys.chunks(
        documentId,
      ),

    queryFn: () =>
      DocumentsService.readDocumentChunks({
        documentId,
        skip: 0,
        limit: 100,
      }),
  })
}
