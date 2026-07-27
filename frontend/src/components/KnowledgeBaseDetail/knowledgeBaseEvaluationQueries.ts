import {
  DocumentsService,
} from "@/client"

import type {
  EvaluationFailureFilter,
} from "./knowledgeBaseEvaluationTypes"

export const knowledgeBaseEvaluationKeys = {
  root: (
    knowledgeBaseId: string,
  ) => [
    "knowledge-base-evaluation",
    knowledgeBaseId,
  ] as const,

  cases: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "cases",
  ] as const,

  runs: ({
    knowledgeBaseId,
    keyword,
    failedOnly,
    failureFilter,
  }: {
    knowledgeBaseId: string
    keyword: string
    failedOnly: boolean
    failureFilter:
      EvaluationFailureFilter
  }) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "runs",
    keyword,
    failedOnly,
    failureFilter,
  ] as const,

  summary: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "summary",
  ] as const,

  failureAnalysis: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "failure-analysis",
  ] as const,

  paramGroups: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "param-groups",
  ] as const,

  presets: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "presets",
  ] as const,

  batches: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "batches",
  ] as const,

  compareBatches: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "compare-batches",
  ] as const,

  compareBatch: (
    batchId: string | null,
  ) => [
    "rag-agent-compare-batch",
    batchId,
  ] as const,

  agentSettings: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "agent-settings",
  ] as const,

  codeTypeSummary: (
    knowledgeBaseId: string,
  ) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "code-type-summary",
  ] as const,

  compareFailureAnalysis: ({
    knowledgeBaseId,
    batchId,
    caseType,
  }: {
    knowledgeBaseId: string
    batchId: string
    caseType: string
  }) => [
    ...knowledgeBaseEvaluationKeys.root(
      knowledgeBaseId,
    ),
    "compare-failure-analysis",
    batchId,
    caseType,
  ] as const,
}

export function ragEvalCasesQueryOptions(
  knowledgeBaseId: string,
) {
  return {
    queryKey:
      knowledgeBaseEvaluationKeys.cases(
        knowledgeBaseId,
      ),
    queryFn: () =>
      DocumentsService.readRagEvalCases({
        knowledgeBaseId,
        skip: 0,
        limit: 100,
      }),
  }
}

export function ragEvalRunsQueryOptions({
  knowledgeBaseId,
  keyword,
  failedOnly,
  failureFilter,
}: {
  knowledgeBaseId: string
  keyword: string
  failedOnly: boolean
  failureFilter:
    EvaluationFailureFilter
}) {
  return {
    queryKey:
      knowledgeBaseEvaluationKeys.runs({
        knowledgeBaseId,
        keyword,
        failedOnly,
        failureFilter,
      }),
    queryFn: () =>
      DocumentsService.readRagEvalRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 50,
        keyword:
          keyword.trim()
          || undefined,
        failedOnly:
          failedOnly || undefined,
        keywordHit:
          failureFilter === "keyword"
            ? false
            : undefined,
        sourceHit:
          failureFilter === "source"
            ? false
            : undefined,
        errorOnly:
          failureFilter === "error"
            ? true
            : undefined,
        maxScore:
          failureFilter === "zero"
            ? 0
            : undefined,
      }),
  }
}
