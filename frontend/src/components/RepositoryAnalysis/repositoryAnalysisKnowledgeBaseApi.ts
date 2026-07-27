import {
  OpenAPI,
  type KnowledgeBasePublic,
  type RepositoryAnalysisTaskPublic,
} from "@/client"
import {
  request as apiRequest,
} from "@/client/core/request"

export type RepositoryAnalysisKnowledgeBaseRequest = {
  knowledge_base_id?: string
  knowledge_base_name?: string
  knowledge_base_description?: string
}

export type RepositoryAnalysisKnowledgeBaseBindingPublic = {
  task: RepositoryAnalysisTaskPublic
  knowledge_base: KnowledgeBasePublic
  created_new_knowledge_base: boolean
}

export function bindRepositoryAnalysisKnowledgeBase(
  taskId: string,
  body: RepositoryAnalysisKnowledgeBaseRequest,
) {
  const normalizedTaskId =
    taskId.trim()

  if (!normalizedTaskId) {
    throw new Error(
      "Repository analysis task ID is required",
    )
  }

  return apiRequest<
    RepositoryAnalysisKnowledgeBaseBindingPublic
  >(
    OpenAPI,
    {
      method: "POST",

      url:
        "/api/v1/repository-analyses/{task_id}/knowledge-base",

      path: {
        task_id: normalizedTaskId,
      },

      body,

      mediaType: "application/json",

      errors: {
        403: "Not enough permissions",
        404: (
          "Repository analysis or "
          + "knowledge base not found"
        ),
        409: (
          "Repository analysis is not ready "
          + "or is already bound"
        ),
        422: "Invalid knowledge base request",
      },
    },
  )
}

export type RepositoryAnalysisKnowledgeImportPublic = {
  task_id: string
  knowledge_base_id: string

  repository_full_name: string
  commit_sha: string

  document_count: number
  chunk_count: number
  imported_bytes: number

  skipped_unsupported_file_count: number
  skipped_large_file_count: number
  skipped_unreadable_file_count: number

  import_truncated: boolean
  already_imported: boolean
}

export function importRepositoryAnalysisKnowledgeBase(
  taskId: string,
) {
  const normalizedTaskId =
    taskId.trim()

  if (!normalizedTaskId) {
    throw new Error(
      "Repository analysis task ID is required",
    )
  }

  return apiRequest<
    RepositoryAnalysisKnowledgeImportPublic
  >(
    OpenAPI,
    {
      method: "POST",

      url:
        "/api/v1/repository-analyses/{task_id}/knowledge-base/import",

      path: {
        task_id: normalizedTaskId,
      },

      errors: {
        404: (
          "Repository analysis or "
          + "knowledge base not found"
        ),
        409: (
          "Repository analysis is not ready "
          + "or is not bound"
        ),
        413: (
          "Repository code import is too large"
        ),
        422: (
          "No supported repository code files"
        ),
        502: (
          "Repository snapshot could not "
          + "be prepared"
        ),
      },
    },
  )
}

export type RepositoryAnalysisEmbeddingStatusPublic = {
  task_id: string
  knowledge_base_id: string

  embedding_model: string

  total_count: number
  pending_count: number
  embedded_count: number
  failed_count: number

  progress_percent: number

  index_status:
    | "not_imported"
    | "pending"
    | "completed"
    | "completed_with_errors"
    | "failed"

  ready_for_search: boolean

  sample_error_message?: string | null
}

export type RepositoryAnalysisEmbeddingBatchPublic =
  RepositoryAnalysisEmbeddingStatusPublic & {
    processed_count: number
    embedded_in_batch: number
    failed_in_batch: number
  }

export function readRepositoryAnalysisEmbeddingStatus(
  taskId: string,
) {
  const normalizedTaskId =
    taskId.trim()

  if (!normalizedTaskId) {
    throw new Error(
      "Repository analysis task ID is required",
    )
  }

  return apiRequest<
    RepositoryAnalysisEmbeddingStatusPublic
  >(
    OpenAPI,
    {
      method: "GET",

      url:
        "/api/v1/repository-analyses/{task_id}/knowledge-base/embedding-status",

      path: {
        task_id: normalizedTaskId,
      },

      errors: {
        404: (
          "Repository analysis or "
          + "knowledge base not found"
        ),
        409: (
          "Repository analysis is not ready"
        ),
      },
    },
  )
}

export function backfillRepositoryAnalysisEmbeddings(
  taskId: string,
  body: {
    limit: number
    retry_failed: boolean
  },
) {
  const normalizedTaskId =
    taskId.trim()

  if (!normalizedTaskId) {
    throw new Error(
      "Repository analysis task ID is required",
    )
  }

  return apiRequest<
    RepositoryAnalysisEmbeddingBatchPublic
  >(
    OpenAPI,
    {
      method: "POST",

      url:
        "/api/v1/repository-analyses/{task_id}/knowledge-base/embeddings/backfill",

      path: {
        task_id: normalizedTaskId,
      },

      body,

      mediaType: "application/json",

      errors: {
        404: (
          "Repository analysis or "
          + "knowledge base not found"
        ),
        409: (
          "Repository analysis is not ready"
        ),
      },
    },
  )
}