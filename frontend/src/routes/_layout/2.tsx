import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { useRef, useState, useEffect } from "react"
import type React from "react"
import { DocumentsService, KnowledgeBasesService } from "@/client"
import { CollapsibleSection } from "../../components/KnowledgeBaseDetail/CollapsibleSection"
import {
  downloadBase64File,
  downloadTextFile,
  getSummaryValue,
  getToolName,
  getToolSuccess,
  readArrayField,
  readField,
  readNumberField,
} from "../../components/KnowledgeBaseDetail/compareUtils"
import { RagAgentCompareDetailSection } from "../../components/KnowledgeBaseDetail/RagAgentCompareDetailSection"
import { RagAgentFailureAnalysisSection } from "../../components/KnowledgeBaseDetail/RagAgentFailureAnalysisSection"
import { RagAgentCompareHistorySection } from "../../components/KnowledgeBaseDetail/RagAgentCompareHistorySection"
import {
  AGENT_PARAM_PRESETS,
  AgentParamTuningSection,
  type AgentParamConfig,
} from "../../components/KnowledgeBaseDetail/AgentParamTuningSection"

type AppliedAgentConfig = {
  topK: number
  maxSteps: number
  semanticWeight: number
  keywordWeight: number
}

export const Route = createFileRoute("/_layout/2")({
  component: KnowledgeBaseDetailPage,
})

const buildAgentParamRecommendation = (tuningResults: any[]) => {
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

    const failurePenalty = failed * 100
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

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }

  return `${(size / 1024 / 1024).toFixed(1)} MB`
}


type CollapsibleSectionProps = {
  title: string
  description?: string
  isOpen: boolean
  onToggle: () => void
  children: React.ReactNode
}

function KnowledgeBaseDetailPage() {
  const { knowledgeBaseId } = Route.useParams()
  const queryClient = useQueryClient()

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [expandedDocumentId, setExpandedDocumentId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [chatQuestion, setChatQuestion] = useState("")
  const [semanticQuery, setSemanticQuery] = useState("")
  const [ragRunKeyword, setRagRunKeyword] = useState("")
  const [evalQuestion, setEvalQuestion] = useState("")
  const [evalKeywords, setEvalKeywords] = useState("")
  const [evalSourceFilename, setEvalSourceFilename] = useState("")
  const [evalNote, setEvalNote] = useState("")
  const [ragTopK, setRagTopK] = useState(5)
  const [ragSemanticWeight, setRagSemanticWeight] = useState(0.75)
  const [ragKeywordWeight, setRagKeywordWeight] = useState(0.25)
  const [evalBatchName, setEvalBatchName] = useState("")
  const [evalBatchNote, setEvalBatchNote] = useState("")
  const [agentQuestion, setAgentQuestion] = useState("")
  const [compareQuestion, setCompareQuestion] = useState("")
  const [selectedCompareBatchId, setSelectedCompareBatchId] = useState<
    string | null
  >(null)
  const [agentParamConfig, setAgentParamConfig] = useState<AgentParamConfig>({
    topK: 5,
    maxSteps: 5,
    limit: 10,
    semanticWeight: 0.75,
    keywordWeight: 0.25,
  })
  const [appliedAgentConfig, setAppliedAgentConfig] =
    useState<AppliedAgentConfig>({
      topK: 5,
      maxSteps: 5,
      semanticWeight: 0.75,
      keywordWeight: 0.25,
    })
  const [agentRunKeyword, setAgentRunKeyword] = useState("")
  const [expandedAgentRunIds, setExpandedAgentRunIds] = useState<string[]>([])
  const [presetName, setPresetName] = useState("")
  const [presetNote, setPresetNote] = useState("")
  const [evalRunKeyword, setEvalRunKeyword] = useState("")
  const [evalFailedOnly, setEvalFailedOnly] = useState(false)
  const [evalFailureType, setEvalFailureType] = useState<
    "all" | "keyword" | "source" | "error" | "zero"
  >("all")
  type ExpandableSectionKey =
  | "documents"
  | "ragHistory"
  | "agentHistory"
  | "compareHistory"
  | "evalRuns"

  const [expandedSections, setExpandedSections] = useState<
    Record<ExpandableSectionKey, boolean>
  >({
    documents: false,
    ragHistory: false,
    agentHistory: false,
    compareHistory: false,
    evalRuns: false,
    agentParamTuning: false,
  })

  const toggleSection = (sectionKey: ExpandableSectionKey) => {
    setExpandedSections((previous) => ({
      ...previous,
      [sectionKey]: !previous[sectionKey],
    }))
  }

  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const {
    data: knowledgeBase,
    isPending: isKnowledgeBasePending,
    isError: isKnowledgeBaseError,
  } = useQuery({
    queryKey: ["knowledge-base", knowledgeBaseId],
    queryFn: () =>
      KnowledgeBasesService.readKnowledgeBase({
        id: knowledgeBaseId,
      }),
  })

  const {
    data: documents,
    isPending: isDocumentsPending,
    isError: isDocumentsError,
  } = useQuery({
    queryKey: ["documents", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readDocumentsByKnowledgeBase({
        knowledgeBaseId,
        skip: 0,
        limit: 100,
      }),
  })

  const {
    data: chunks,
    isPending: isChunksPending,
    isError: isChunksError,
  } = useQuery({
    queryKey: ["document-chunks", expandedDocumentId],
    enabled: expandedDocumentId !== null,
    queryFn: () => {
      if (!expandedDocumentId) {
        throw new Error("Document id is required")
      }

      return DocumentsService.readDocumentChunks({
        documentId: expandedDocumentId,
        skip: 0,
        limit: 100,
      })
    },
  })

  const ragRunsQuery = useQuery({
    queryKey: ["rag-runs", knowledgeBaseId, ragRunKeyword],
    queryFn: () =>
      DocumentsService.readKnowledgeBaseRagRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword: ragRunKeyword.trim() || undefined,
      }),
    enabled: expandedSections.ragHistory,
  })

  const ragEvalCasesQuery = useQuery({
    queryKey: ["rag-eval-cases", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalCases({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
      }),
  })

  const ragEvalRunsQuery = useQuery({
    queryKey: [
      "rag-eval-runs",
      knowledgeBaseId,
      evalRunKeyword,
      evalFailedOnly,
      evalFailureType,
    ],
    queryFn: () =>
      DocumentsService.readRagEvalRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword: evalRunKeyword.trim() || undefined,
        failedOnly: evalFailedOnly || undefined,
        keywordHit: evalFailureType === "keyword" ? false : undefined,
        sourceHit: evalFailureType === "source" ? false : undefined,
        errorOnly: evalFailureType === "error" ? true : undefined,
        maxScore: evalFailureType === "zero" ? 0 : undefined,
      }),
    enabled: expandedSections.evalRuns,
  })

  const ragEvalSummaryQuery = useQuery({
    queryKey: ["rag-eval-summary", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalSummary({
        knowledgeBaseId,
        limit: 200,
      }),
  })

  const ragEvalParamGroupsQuery = useQuery({
    queryKey: ["rag-eval-param-groups", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalParamGroups({
        knowledgeBaseId,
        limit: 500,
      }),
  })


  const ragRetrievalPresetsQuery = useQuery({
    queryKey: ["rag-retrieval-presets", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagRetrievalPresets({
        knowledgeBaseId,
        skip: 0,
        limit: 50,
      }),
  })

  const ragEvalFailureAnalysisQuery = useQuery({
    queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalFailureAnalysis({
        knowledgeBaseId,
        limit: 200,
        recentLimit: 10,
      }),
  })


  const ragEvalBatchesQuery = useQuery({
    queryKey: ["rag-eval-batches", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalBatches({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
      }),
  })

  const agentRunsQuery = useQuery({
    queryKey: ["agent-runs", knowledgeBaseId, agentRunKeyword],
    queryFn: () =>
      DocumentsService.readAgentRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword: agentRunKeyword.trim() || undefined,
      }),
    enabled: expandedSections.agentHistory,
  })

  const ragAgentCompareBatchesQuery = useQuery({
    queryKey: ["rag-agent-compare-batches", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagAgentCompareBatches({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
      }),
    enabled: expandedSections.compareHistory,
  })

  const ragAgentCompareBatchDetailQuery = useQuery({
    queryKey: ["rag-agent-compare-batch", selectedCompareBatchId],
    queryFn: () =>
      DocumentsService.readRagAgentCompareBatch({
        batchId: selectedCompareBatchId as string,
      }),
    enabled: expandedSections.compareHistory && Boolean(selectedCompareBatchId),
  })

  const agentSettingsQuery = useQuery({
    queryKey: ["knowledge-base-agent-settings", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readKnowledgeBaseAgentSettings({
        knowledgeBaseId,
      }),
  })

  useEffect(() => {
    if (!agentSettingsQuery.data) {
      return
    }

    const settings = agentSettingsQuery.data as any

    setAppliedAgentConfig({
      topK: readField<number>(settings, "top_k", "topK", 5),
      maxSteps: readField<number>(settings, "max_steps", "maxSteps", 5),
      semanticWeight: readField<number>(
        settings,
        "semantic_weight",
        "semanticWeight",
        0.75,
      ),
      keywordWeight: readField<number>(
        settings,
        "keyword_weight",
        "keywordWeight",
        0.25,
      ),
    })
  }, [agentSettingsQuery.data])

  const uploadDocumentMutation = useMutation({
    mutationFn: (file: File) =>
      DocumentsService.uploadDocument({
        knowledgeBaseId,
        formData: {
          file,
        },
      }),
    onSuccess: () => {
      setSelectedFile(null)

      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }

      queryClient.invalidateQueries({
        queryKey: ["documents", knowledgeBaseId],
      })
    },
  })

  const deleteDocumentMutation = useMutation({
    mutationFn: (documentId: string) =>
      DocumentsService.deleteDocument({
        documentId,
      }),
    onSuccess: () => {
      setExpandedDocumentId(null)

      queryClient.invalidateQueries({
        queryKey: ["documents", knowledgeBaseId],
      })
    },
  })

  const searchKnowledgeBaseMutation = useMutation({
    mutationFn: (query: string) =>
      DocumentsService.searchKnowledgeBaseChunks({
        knowledgeBaseId,
        requestBody: {
          query,
          limit: 10,
        },
      }),
  })

  const semanticSearchKnowledgeBaseMutation = useMutation({
    mutationFn: (query: string) =>
      DocumentsService.semanticSearchKnowledgeBaseChunks({
        knowledgeBaseId,
        requestBody: {
          query,
          top_k: 5,
        },
      }),
  })

  const backfillEmbeddingsMutation = useMutation({
    mutationFn: () =>
      DocumentsService.backfillKnowledgeBaseEmbeddings({
        knowledgeBaseId,
        requestBody: {
          limit: 20,
          retry_failed: true,
          force: false,
        },
      }),
  })

  const chatKnowledgeBaseMutation = useMutation({
    mutationFn: (question: string) => {
      const settings = getRetrievalSettings()

      return DocumentsService.chatWithKnowledgeBase({
        knowledgeBaseId,
        requestBody: {
          question,
          top_k: settings.topK,
          semantic_weight: settings.semanticWeight,
          keyword_weight: settings.keywordWeight,
        },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-runs", knowledgeBaseId],
      })
    },
  })


  const compareRagAgentMutation = useMutation({
    mutationFn: async (question: string) => {
      const settings = getRetrievalSettings()

      const [ragResult, agentResult] = await Promise.all([
        DocumentsService.chatWithKnowledgeBase({
          knowledgeBaseId,
          requestBody: {
            question,
            top_k: appliedAgentConfig.topK,
            semantic_weight: appliedAgentConfig.semanticWeight,
            keyword_weight: appliedAgentConfig.keywordWeight,
          } as any,
        }),

        DocumentsService.agentChatWithKnowledgeBase({
          knowledgeBaseId,
          requestBody: {
            question,
            top_k: appliedAgentConfig.topK,
            max_steps: appliedAgentConfig.maxSteps,
            semantic_weight: appliedAgentConfig.semanticWeight,
            keyword_weight: appliedAgentConfig.keywordWeight,
          } as any,
        }),
      ])

      return {
        ragResult,
        agentResult,
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-runs", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["agent-runs", knowledgeBaseId],
      })
    },
  })

  const deleteRagRunMutation = useMutation({
    mutationFn: (ragRunId: string) =>
      DocumentsService.deleteRagRun({
        ragRunId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-runs", knowledgeBaseId],
      })
    },
  })

  const createRagEvalCaseMutation = useMutation({
    mutationFn: () =>
      DocumentsService.createRagEvalCase({
        knowledgeBaseId,
        requestBody: {
          question: evalQuestion.trim(),
          expected_keywords: evalKeywords
            .split(/[,，\n]/)
            .map((item) => item.trim())
            .filter(Boolean),
          expected_source_filename: evalSourceFilename.trim() || null,
          note: evalNote.trim() || null,
        },
      }),
    onSuccess: () => {
      setEvalQuestion("")
      setEvalKeywords("")
      setEvalSourceFilename("")
      setEvalNote("")

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-cases", knowledgeBaseId],
      })
    },
  })

  const runRagEvalCaseMutation = useMutation({
    mutationFn: (evalCaseId: string) => {
      const settings = getRetrievalSettings()

      return DocumentsService.runRagEvalCase({
        evalCaseId,
        requestBody: {
          top_k: settings.topK,
          semantic_weight: settings.semanticWeight,
          keyword_weight: settings.keywordWeight,
        },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-runs", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-summary", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-param-groups", knowledgeBaseId],
      })
    },
  })

  const deleteRagEvalCaseMutation = useMutation({
    mutationFn: (evalCaseId: string) =>
      DocumentsService.deleteRagEvalCase({
        evalCaseId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-cases", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-runs", knowledgeBaseId],
      })
    },
  })

 const runAllRagEvalCasesMutation = useMutation({
   mutationFn: () => {
     const settings = getRetrievalSettings()

     return DocumentsService.runAllRagEvalCases({
       knowledgeBaseId,
       requestBody: {
         top_k: settings.topK,
         limit: 100,
         semantic_weight: settings.semanticWeight,
         keyword_weight: settings.keywordWeight,
         batch_name: evalBatchName.trim() || null,
         batch_note: evalBatchNote.trim() || null,
       },
     })
   },
   onSuccess: () => {
     setEvalBatchName("")
     setEvalBatchNote("")

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-runs", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-summary", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-param-groups", knowledgeBaseId],
     })

     queryClient.invalidateQueries({
       queryKey: ["rag-eval-batches", knowledgeBaseId],
     })
   },
 })

  const createRagRetrievalPresetMutation = useMutation({
    mutationFn: () => {
      const settings = getRetrievalSettings()

      return DocumentsService.createRagRetrievalPreset({
        knowledgeBaseId,
        requestBody: {
          name: presetName.trim(),
          top_k: settings.topK,
          semantic_weight: settings.semanticWeight,
          keyword_weight: settings.keywordWeight,
          note: presetNote.trim() || null,
        },
      })
    },
    onSuccess: () => {
      setPresetName("")
      setPresetNote("")

      queryClient.invalidateQueries({
        queryKey: ["rag-retrieval-presets", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-param-groups", knowledgeBaseId],
      })
    },
  })

  const deleteRagRetrievalPresetMutation = useMutation({
    mutationFn: (presetId: string) =>
      DocumentsService.deleteRagRetrievalPreset({
        presetId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-retrieval-presets", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-param-groups", knowledgeBaseId],
      })
    },
  })

  const getRetrievalSettings = () => {
    const topK = Math.min(Math.max(Number(ragTopK) || 5, 1), 20)
    const semanticWeight = Math.min(
      Math.max(Number(ragSemanticWeight) || 0, 0),
      1,
    )
    const keywordWeight = Math.min(
      Math.max(Number(ragKeywordWeight) || 0, 0),
      1,
    )

    if (semanticWeight + keywordWeight <= 0) {
      return {
        topK,
        semanticWeight: 0.75,
        keywordWeight: 0.25,
      }
    }

    return {
      topK,
      semanticWeight,
      keywordWeight,
    }
  }


  const deleteRagEvalBatchMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.deleteRagEvalBatch({
        batchId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-batches", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-runs", knowledgeBaseId],
      })
    },
  })

  const agentChatMutation = useMutation({
    mutationFn: (question: string) => {
      const settings = getRetrievalSettings()

      return DocumentsService.agentChatWithKnowledgeBase({
        knowledgeBaseId,
        requestBody: {
          question,
          top_k: appliedAgentConfig.topK,
          max_steps: appliedAgentConfig.maxSteps,
          semantic_weight: appliedAgentConfig.semanticWeight,
          keyword_weight: appliedAgentConfig.keywordWeight,
        } as any,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["agent-runs", knowledgeBaseId],
      })
    },
  })

  const deleteAgentRunMutation = useMutation({
    mutationFn: (agentRunId: string) =>
      DocumentsService.deleteAgentRun({
        agentRunId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["agent-runs", knowledgeBaseId],
      })
    },
  })


  const runRagAgentCompareEvalMutation = useMutation({
    mutationFn: () =>
      DocumentsService.runRagAgentCompareEval({
        knowledgeBaseId,
        requestBody: {
          name: `RAG vs Agent Compare ${new Date().toLocaleString()}`,
          top_k: appliedAgentConfig.topK,
          max_steps: appliedAgentConfig.maxSteps,
          limit: 10,
          semantic_weight: appliedAgentConfig.semanticWeight,
          keyword_weight: appliedAgentConfig.keywordWeight,
        } as any,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: ["rag-agent-compare-batches", knowledgeBaseId],
      })

      if (data.compare_batch_id) {
        setSelectedCompareBatchId(data.compare_batch_id)
      }
    },
  })


  const runAgentParamTuningMutation = useMutation({
    mutationFn: async () => {
      const results = []

      for (const preset of AGENT_PARAM_PRESETS) {
        const result = await DocumentsService.runRagAgentCompareEval({
          knowledgeBaseId,
          requestBody: {
            name: `参数优化 - ${preset.name} - ${new Date().toLocaleString()}`,
            top_k: preset.topK,
            max_steps: preset.maxSteps,
            limit: preset.limit,
            semantic_weight: preset.semanticWeight,
            keyword_weight: preset.keywordWeight,
          } as any,
        })

        results.push({
          preset,
          result,
        })
      }

      return results
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-agent-compare-batches", knowledgeBaseId],
      })
    },
  })

  const agentParamRecommendation = runAgentParamTuningMutation.data
    ? buildAgentParamRecommendation(runAgentParamTuningMutation.data)
    : null

  const deleteRagAgentCompareBatchMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.deleteRagAgentCompareBatch({
        batchId,
      }),
    onSuccess: () => {
      setSelectedCompareBatchId(null)

      queryClient.invalidateQueries({
        queryKey: ["rag-agent-compare-batches", knowledgeBaseId],
      })
    },
  })

  const updateAgentSettingsMutation = useMutation({
    mutationFn: ({
      config,
      name,
    }: {
      config: AppliedAgentConfig
      name?: string
    }) =>
      DocumentsService.updateKnowledgeBaseAgentSettings({
        knowledgeBaseId,
        requestBody: {
          top_k: config.topK,
          max_steps: config.maxSteps,
          semantic_weight: config.semanticWeight,
          keyword_weight: config.keywordWeight,
        } as any,
      }),
    onSuccess: (data, variables) => {
      const settings = data as any

      const nextConfig = {
        topK: readField<number>(settings, "top_k", "topK", variables.config.topK),
        maxSteps: readField<number>(
          settings,
          "max_steps",
          "maxSteps",
          variables.config.maxSteps,
        ),
        semanticWeight: readField<number>(
          settings,
          "semantic_weight",
          "semanticWeight",
          variables.config.semanticWeight,
        ),
        keywordWeight: readField<number>(
          settings,
          "keyword_weight",
          "keywordWeight",
          variables.config.keywordWeight,
        ),
      }

      setAppliedAgentConfig(nextConfig)

      queryClient.invalidateQueries({
        queryKey: ["knowledge-base-agent-settings", knowledgeBaseId],
      })

      alert(
        `已保存并应用 Agent 配置：${variables.name ?? `自定义配置`}\n` +
          `top_k=${nextConfig.topK}, max_steps=${nextConfig.maxSteps}, ` +
          `semantic_weight=${nextConfig.semanticWeight}, keyword_weight=${nextConfig.keywordWeight}`,
      )
    },
  })


  const exportRagAgentCompareReportMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.readRagAgentCompareBatchReport({
        batchId,
      }),
    onSuccess: (data) => {
      const report = data as any

      const filename = readField<string>(
        report,
        "filename",
        "filename",
        "rag_agent_compare_report.md",
      )

      const content = readField<string>(
        report,
        "content",
        "content",
        "",
      )

      downloadTextFile({
        filename,
        content,
      })
    },
  })

  const exportRagAgentCompareDocxReportMutation = useMutation({
  mutationFn: (batchId: string) =>
    DocumentsService.readRagAgentCompareBatchDocxReport({
      batchId,
    }),
  onSuccess: (data) => {
    const report = data as any

    const filename = readField<string>(
      report,
      "filename",
      "filename",
      "rag_agent_compare_report.docx",
    )

    const mimeType = readField<string>(
      report,
      "mime_type",
      "mimeType",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    const contentBase64 = readField<string>(
      report,
      "content_base64",
      "contentBase64",
      "",
    )

    downloadBase64File({
      filename,
      mimeType,
      contentBase64,
    })
  },
})

  const exportRagAgentComparePdfReportMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.readRagAgentCompareBatchPdfReport({
        batchId,
      }),
    onSuccess: (data) => {
      const report = data as any

      const filename = readField<string>(
        report,
        "filename",
        "filename",
        "rag_agent_compare_report.pdf",
      )

      const mimeType = readField<string>(
        report,
        "mime_type",
        "mimeType",
        "application/pdf",
      )

      const contentBase64 = readField<string>(
        report,
        "content_base64",
        "contentBase64",
        "",
      )

      downloadBase64File({
        filename,
        mimeType,
        contentBase64,
      })
    },
  })

  const handleUpload = () => {
    if (!selectedFile) {
      alert("请先选择文件")
      return
    }

    uploadDocumentMutation.mutate(selectedFile)
  }

  const handleToggleChunks = (documentId: string) => {
    if (expandedDocumentId === documentId) {
      setExpandedDocumentId(null)
      return
    }

    setExpandedDocumentId(documentId)
  }

  const handleSearch = () => {
    const query = searchQuery.trim()

    if (!query) {
      alert("请输入要检索的内容")
      return
    }

    searchKnowledgeBaseMutation.mutate(query)
  }

  const handleDeleteRagRun = (ragRunId: string) => {
    const confirmed = window.confirm("确定要删除这条 RAG 问答历史吗？")

    if (!confirmed) {
      return
    }

    deleteRagRunMutation.mutate(ragRunId)
  }

  const handleSemanticSearch = () => {
    const query = semanticQuery.trim()

    if (!query) {
      alert("请输入要语义检索的内容")
      return
    }

    semanticSearchKnowledgeBaseMutation.mutate(query)
  }

  const handleBackfillEmbeddings = () => {
    backfillEmbeddingsMutation.mutate()
  }

  const handleChat = () => {
    const question = chatQuestion.trim()

    if (!question) {
      alert("请输入要提问的内容")
      return
    }

    chatKnowledgeBaseMutation.mutate(question)
  }

  const handleAgentChat = () => {
    const question = agentQuestion.trim()

    if (!question) {
      alert("请输入 Agent 问题")
      return
    }

    agentChatMutation.mutate(question)
  }

  const handleToggleAgentRun = (agentRunId: string) => {
    setExpandedAgentRunIds((currentIds) => {
      if (currentIds.includes(agentRunId)) {
        return currentIds.filter((id) => id !== agentRunId)
      }

      return [...currentIds, agentRunId]
    })
  }

  const handleDeleteAgentRun = (agentRunId: string) => {
    const confirmed = window.confirm("确定要删除这条 Agent 历史记录吗？")

    if (!confirmed) {
      return
    }

    deleteAgentRunMutation.mutate(agentRunId)
  }

  const handleCreateRagEvalCase = () => {
    if (!evalQuestion.trim()) {
      alert("请输入评测问题")
      return
    }

    createRagEvalCaseMutation.mutate()
  }

  const handleRunRagEvalCase = (evalCaseId: string) => {
    runRagEvalCaseMutation.mutate(evalCaseId)
  }

  const handleRunAllRagEvalCases = () => {
    const confirmed = window.confirm(
      "确定要运行当前知识库下的全部评测样例吗？这可能需要等待一段时间。"
    )

    if (!confirmed) {
      return
    }

    runAllRagEvalCasesMutation.mutate()
  }


  const handleDeleteRagEvalBatch = (batchId: string) => {
    const confirmed = window.confirm(
      "确定要删除这条实验批次记录吗？对应评测结果不会删除，只会解除和该批次的关联。"
    )

    if (!confirmed) {
      return
    }

    deleteRagEvalBatchMutation.mutate(batchId)
  }

  const handleCreateRagRetrievalPreset = () => {
    if (!presetName.trim()) {
      alert("请输入参数预设名称")
      return
    }

    createRagRetrievalPresetMutation.mutate()
  }

  const handleApplyRagRetrievalPreset = (preset: {
    top_k: number
    semantic_weight: number
    keyword_weight: number
  }) => {
    setRagTopK(preset.top_k)
    setRagSemanticWeight(preset.semantic_weight)
    setRagKeywordWeight(preset.keyword_weight)
  }

  const handleDeleteRagRetrievalPreset = (presetId: string) => {
    const confirmed = window.confirm("确定要删除这个参数预设吗？")

    if (!confirmed) {
      return
    }

    deleteRagRetrievalPresetMutation.mutate(presetId)
  }


  const handleDeleteRagEvalCase = (evalCaseId: string) => {
    const confirmed = window.confirm("确定要删除这条评测样例吗？")

    if (!confirmed) {
      return
    }

    deleteRagEvalCaseMutation.mutate(evalCaseId)
  }


  const handleCompareRagAgent = () => {
    const question = compareQuestion.trim()

    if (!question) {
      alert("请输入对比问题")
      return
    }

    compareRagAgentMutation.mutate(question)
  }

  const handleApplyRecommendedAgentConfig = () => {
    if (!agentParamRecommendation) {
      alert("暂无可应用的推荐配置，请先运行 Agent 参数优化实验")
      return
    }

    const bestPreset = agentParamRecommendation.best.preset

    const nextConfig = {
      topK: bestPreset.topK,
      maxSteps: bestPreset.maxSteps,
      limit: bestPreset.limit,
      semanticWeight: bestPreset.semanticWeight,
      keywordWeight: bestPreset.keywordWeight,
    }
    setAgentParamConfig(nextConfig)

    updateAgentSettingsMutation.mutate({
    name: bestPreset.name,
    config: {
      top_k: nextConfig.topK,
      max_steps: nextConfig.maxSteps,
      semantic_weight: nextConfig.semanticWeight,
      keyword_weight: nextConfig.keywordWeight,
    },
  } as any)
}

  const handleResetAgentConfig = () => {
    updateAgentSettingsMutation.mutate({
      name: "默认配置",
      config: {
        topK: 5,
        maxSteps: 5,
        semanticWeight: 0.75,
        keywordWeight: 0.25,
      },
    })
  }

  const handleDownload = async (documentId: string, filename: string) => {
    const token = localStorage.getItem("access_token")

    if (!token) {
      alert("请先登录")
      return
    }

    const response = await fetch(
      `${import.meta.env.VITE_API_URL}/api/v1/documents/${documentId}/download`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    if (!response.ok) {
      alert("下载失败")
      return
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)

    const link = window.document.createElement("a")
    link.href = url
    link.download = filename
    link.click()

    window.URL.revokeObjectURL(url)
  }

  if (isKnowledgeBasePending || isDocumentsPending) {
    return <div className="p-6">正在加载知识库详情...</div>
  }

  if (isKnowledgeBaseError) {
    return <div className="p-6">知识库加载失败</div>
  }

  if (isDocumentsError) {
    return <div className="p-6">文档列表加载失败</div>
  }

  if (!knowledgeBase || !documents) {
    return <div className="p-6">暂无数据</div>
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <Link to="/knowledge-bases" className="text-sm underline">
          返回知识库列表
        </Link>
      </div>

      <div className="border rounded-lg p-4 space-y-2">
        <h1 className="text-2xl font-bold">{knowledgeBase.name}</h1>

        <p className="text-sm text-gray-500">
          {knowledgeBase.description || "暂无描述"}
        </p>

        <p className="text-xs text-gray-400">知识库 ID：{knowledgeBase.id}</p>
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">上传文档</h2>
          <p className="text-sm text-gray-500">
            支持上传 txt、md、pdf、docx 文件。文字版 PDF 和 docx 会自动解析并切分。
          </p>
        </div>

        <div className="flex gap-3 items-center">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,.docx"
            onChange={(event) => {
              const file = event.target.files?.[0] || null
              setSelectedFile(file)
            }}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleUpload}
            disabled={uploadDocumentMutation.isPending}
          >
            {uploadDocumentMutation.isPending ? "上传中..." : "上传"}
          </button>
        </div>

        {selectedFile ? (
          <div className="text-sm text-gray-500">
            当前选择：{selectedFile.name}，大小：
            {formatFileSize(selectedFile.size)}
          </div>
        ) : null}

        {uploadDocumentMutation.isError ? (
          <div className="text-sm text-red-500">
            上传失败，请检查文件类型、文件大小或登录状态。
          </div>
        ) : null}
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">知识库检索测试</h2>
          <p className="text-sm text-gray-500">
            这里先用关键词检索 DocumentChunk，后面可以替换成向量检索。
          </p>
        </div>

        <div className="flex gap-3">
          <input
            className="border rounded px-3 py-2 flex-1"
            placeholder="请输入关键词，例如：FastAPI 路由"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleSearch()
              }
            }}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleSearch}
            disabled={searchKnowledgeBaseMutation.isPending}
          >
            {searchKnowledgeBaseMutation.isPending ? "检索中..." : "检索"}
          </button>
        </div>

        {searchKnowledgeBaseMutation.isError ? (
          <div className="text-sm text-red-500">检索失败，请检查后端接口。</div>
        ) : null}

        {searchKnowledgeBaseMutation.data ? (
          <div className="space-y-3">
            <div className="text-sm text-gray-500">
              共找到 {searchKnowledgeBaseMutation.data.count} 条结果，当前展示{" "}
              {searchKnowledgeBaseMutation.data.data.length} 条。
            </div>

            {searchKnowledgeBaseMutation.data.data.length === 0 ? (
              <div className="text-sm text-gray-500">暂无匹配结果</div>
            ) : (
              searchKnowledgeBaseMutation.data.data.map((result) => (
                <div
                  key={result.chunk_id}
                  className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">
                      来源文件：{result.original_filename} ｜ Chunk{" "}
                      {result.chunk_index}
                    </div>

                    <div className="text-xs text-gray-400">
                      命中次数：{result.match_count} ｜ 长度：
                      {result.content_length}
                    </div>
                  </div>

                  <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                    {result.content}
                  </pre>
                </div>
              ))
            )}
          </div>
        ) : null}
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">语义检索测试</h2>
          <p className="text-sm text-gray-500">
            这里会把你的问题转成 embedding，然后和 DocumentChunk 的 embedding
            计算相似度，返回语义最接近的 chunk。
          </p>
        </div>

        <div className="flex gap-3">
          <input
            className="border rounded px-3 py-2 flex-1"
            placeholder="请输入问题，例如：用户登录状态应该怎么保存？"
            value={semanticQuery}
            onChange={(event) => setSemanticQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleSemanticSearch()
              }
            }}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleSemanticSearch}
            disabled={semanticSearchKnowledgeBaseMutation.isPending}
          >
            {semanticSearchKnowledgeBaseMutation.isPending
              ? "检索中..."
              : "语义检索"}
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button
            className="border rounded px-4 py-2"
            onClick={handleBackfillEmbeddings}
            disabled={backfillEmbeddingsMutation.isPending}
          >
            {backfillEmbeddingsMutation.isPending
              ? "回填中..."
              : "回填旧数据 Embedding"}
          </button>

          <span className="text-xs text-gray-500">
            如果旧文档没有 embedding，可以先点击这里回填。
          </span>
        </div>

        {backfillEmbeddingsMutation.isError ? (
          <div className="text-sm text-red-500">
            Embedding 回填失败，请检查后端日志或 API Key。
          </div>
        ) : null}

        {backfillEmbeddingsMutation.data ? (
          <div className="text-sm text-gray-500">
            回填结果：本次处理 {backfillEmbeddingsMutation.data.processed} 个，
            成功 {backfillEmbeddingsMutation.data.embedded} 个，失败{" "}
            {backfillEmbeddingsMutation.data.failed} 个，剩余{" "}
            {backfillEmbeddingsMutation.data.remaining} 个。模型：
            {backfillEmbeddingsMutation.data.model}
          </div>
        ) : null}

        {semanticSearchKnowledgeBaseMutation.isError ? (
          <div className="text-sm text-red-500">
            语义检索失败，请检查后端 semantic-search 接口或 embedding 配置。
          </div>
        ) : null}

        {semanticSearchKnowledgeBaseMutation.data ? (
          <div className="space-y-3">
            <div className="text-sm text-gray-500">
              共找到 {semanticSearchKnowledgeBaseMutation.data.count}
              条语义检索结果。
            </div>

            {semanticSearchKnowledgeBaseMutation.data.data.length === 0 ? (
              <div className="text-sm text-gray-500">
                暂无语义检索结果。可能是当前知识库还没有生成 embedding。
              </div>
            ) : (
              semanticSearchKnowledgeBaseMutation.data.data.map((result) => (
                <div
                  key={result.chunk_id}
                  className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium">
                      来源文件：{result.original_filename} ｜ Chunk{" "}
                      {result.chunk_index}
                    </div>

                    <div className="text-xs text-gray-400">
                      相似度：{result.similarity.toFixed(4)} ｜ 长度：
                      {result.content_length}
                    </div>
                  </div>

                  <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                    {result.content}
                  </pre>
                </div>
              ))
            )}
          </div>
        ) : null}
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">RAG 问答测试</h2>
          <p className="text-sm text-gray-500">
            这里会先从当前知识库检索相关 chunk，再基于检索结果生成回答。
            当前版本是 RAG Chat v0，先返回资料型回答，后续可以接入大模型。
          </p>
        </div>

        <div className="flex gap-3">
          <input
            className="border rounded px-3 py-2 flex-1"
            placeholder="请输入问题，例如：这份文档主要讲了什么？"
            value={chatQuestion}
            onChange={(event) => setChatQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleChat()
              }
            }}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleChat}
            disabled={chatKnowledgeBaseMutation.isPending}
          >
            {chatKnowledgeBaseMutation.isPending ? "回答中..." : "提问"}
          </button>
        </div>

        {chatKnowledgeBaseMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            问答失败：{JSON.stringify(chatKnowledgeBaseMutation.error, null, 2)}
          </div>
        ) : null}

        {chatKnowledgeBaseMutation.data ? (
          <div className="space-y-4">
            <div className="border border-gray-700 rounded p-4 bg-neutral-900 text-gray-100 space-y-3">
              <div className="font-medium">回答</div>

              <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                {chatKnowledgeBaseMutation.data.answer}
              </pre>
            </div>

            <div className="border rounded p-4 space-y-3">
              <div className="font-medium">引用来源</div>

              {chatKnowledgeBaseMutation.data.sources.length === 0 ? (
                <div className="text-sm text-gray-500">
                  暂无引用来源。说明当前知识库没有检索到相关 chunk。
                </div>
              ) : (
                chatKnowledgeBaseMutation.data.sources.map((source) => (
                  <div
                    key={source.chunk_id}
                    className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium">
                        来源文件：{source.original_filename} ｜ Chunk{" "}
                        {source.chunk_index}
                      </div>

                      <div className="text-xs text-gray-400">
                        {source.retrieval_type === "hybrid" ? (
                          <>
                            检索方式：混合检索 ｜ 相似度：
                            {source.similarity?.toFixed(4)} ｜ 关键词命中：
                            {source.match_count} ｜ 长度：{source.content_length}
                          </>
                        ) : source.retrieval_type === "semantic" ? (
                          <>
                            检索方式：语义检索 ｜ 相似度：
                            {source.similarity?.toFixed(4)} ｜ 长度：{source.content_length}
                          </>
                        ) : (
                          <>
                            检索方式：关键词检索 ｜ 命中次数：{source.match_count} ｜ 长度：
                            {source.content_length}
                          </>
                        )}
                      </div>
                    </div>

                    <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                      {source.content}
                    </pre>
                  </div>
                ))
              )}
            </div>

            <div className="border rounded p-4 space-y-2">
              <div className="font-medium">执行过程 Trace</div>

              <div className="text-sm text-gray-500">
                {chatKnowledgeBaseMutation.data.trace.join(" → ")}
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <CollapsibleSection
        title="RAG 问答历史"
        description="查看普通 RAG Chat 的历史问题、回答、sources 和 trace。"
        isOpen={expandedSections.ragHistory}
        onToggle={() => toggleSection("ragHistory")}
      >
        <div className="flex justify-end">

          <button
            className="border rounded px-3 py-1 text-sm"
            onClick={() =>
              queryClient.invalidateQueries({
                queryKey: ["rag-runs", knowledgeBaseId],
              })
            }
          >
            刷新历史
          </button>
        </div>

        <div className="flex gap-3">
          <input
            className="border rounded px-3 py-2 flex-1"
            placeholder="搜索历史记录，例如：FastAPI、JWT、登录、hybrid"
            value={ragRunKeyword}
            onChange={(event) => setRagRunKeyword(event.target.value)}
          />

          {ragRunKeyword.trim() ? (
            <button
              className="border rounded px-4 py-2"
              onClick={() => setRagRunKeyword("")}
            >
              清空
            </button>
          ) : null}
        </div>

        {deleteRagRunMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            删除失败：
            {JSON.stringify(deleteRagRunMutation.error, null, 2)}
          </div>
        ) : null}

        {ragRunsQuery.isLoading ? (
          <div className="text-sm text-gray-500">正在加载问答历史...</div>
        ) : null}

        {ragRunsQuery.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            问答历史加载失败：
            {JSON.stringify(ragRunsQuery.error, null, 2)}
          </div>
        ) : null}

        {ragRunsQuery.data ? (
          <div className="space-y-3">
            <div className="text-sm text-gray-500">
              共 {ragRunsQuery.data.count} 条记录，当前展示{" "}
              {ragRunsQuery.data.data.length} 条。
            </div>

            {ragRunsQuery.data.data.length === 0 ? (
              <div className="text-sm text-gray-500">
                暂无问答历史。你可以先在上面的 RAG 问答测试里提一个问题。
              </div>
            ) : (
              ragRunsQuery.data.data.map((run) => (
                <div
                  key={run.id}
                  className="border border-gray-700 rounded p-4 bg-neutral-900 text-gray-100 space-y-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium">问题：{run.question}</div>

                    <div className="flex items-center gap-3">
                      <div className="text-xs text-gray-400">
                        检索方式：{run.retrieval_type} ｜ 耗时：
                        {run.latency_ms ?? "-"} ms
                      </div>

                      <button
                        className="border border-red-500 text-red-400 rounded px-2 py-1 text-xs"
                        onClick={() => handleDeleteRagRun(run.id)}
                        disabled={deleteRagRunMutation.isPending}
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="text-sm font-medium text-gray-200">回答</div>
                    <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                      {run.answer}
                    </pre>
                  </div>

                  <details className="space-y-2">
                    <summary className="cursor-pointer text-sm text-gray-300">
                      查看引用来源（{run.sources.length}）
                    </summary>

                    <div className="space-y-2 pt-2">
                      {run.sources.length === 0 ? (
                        <div className="text-sm text-gray-500">
                          当前记录没有引用来源。
                        </div>
                      ) : (
                        run.sources.map((source) => (
                          <div
                            key={source.chunk_id}
                            className="border border-gray-700 rounded p-3 bg-black text-gray-100 space-y-2"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="text-sm font-medium">
                                来源文件：{source.original_filename} ｜ Chunk{" "}
                                {source.chunk_index}
                              </div>

                              <div className="text-xs text-gray-400">
                                {source.retrieval_type === "hybrid" ? (
                                  <>
                                    混合检索 ｜ 相似度：
                                    {source.similarity?.toFixed(4)} ｜ 关键词命中：
                                    {source.match_count} ｜ 长度：
                                    {source.content_length}
                                  </>
                                ) : source.retrieval_type === "semantic" ? (
                                  <>
                                    语义检索 ｜ 相似度：
                                    {source.similarity?.toFixed(4)} ｜ 长度：
                                    {source.content_length}
                                  </>
                                ) : (
                                  <>
                                    关键词检索 ｜ 命中次数：{source.match_count} ｜
                                    长度：{source.content_length}
                                  </>
                                )}
                              </div>
                            </div>

                            <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                              {source.content}
                            </pre>
                          </div>
                        ))
                      )}
                    </div>
                  </details>

                  <details>
                    <summary className="cursor-pointer text-sm text-gray-300">
                      查看执行过程 Trace
                    </summary>

                    <div className="pt-2 text-sm text-gray-400">
                      {run.trace.length > 0 ? run.trace.join(" → ") : "暂无 trace"}
                    </div>
                  </details>

                  {run.created_at ? (
                    <div className="text-xs text-gray-500">
                      创建时间：{new Date(run.created_at).toLocaleString()}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        ) : null}
      </CollapsibleSection>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Agent Chat 测试区</h2>
          <p className="text-sm text-gray-500">
            Agent 会根据问题调用工具，例如查看文档列表、检索知识库，再生成最终回答。
          </p>
        </div>

        <div className="space-y-2">
          <textarea
            className="border rounded px-3 py-2 w-full min-h-[90px]"
            placeholder="请输入 Agent 问题，例如：这个知识库有哪些文档？或者：请总结这个知识库主要讲了什么"
            value={agentQuestion}
            onChange={(event) => setAgentQuestion(event.target.value)}
          />

          <div className="flex items-center gap-2">
            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={handleAgentChat}
              disabled={agentChatMutation.isPending}
            >
              {agentChatMutation.isPending ? "Agent 思考中..." : "发送给 Agent"}
            </button>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() => setAgentQuestion("这个知识库有哪些文档？")}
            >
              示例：查看文档
            </button>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() => setAgentQuestion("请总结一下这个知识库主要讲了什么")}
            >
              示例：总结知识库
            </button>
          </div>
        </div>

        {agentChatMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            Agent 调用失败：
            {JSON.stringify(agentChatMutation.error, null, 2)}
          </div>
        ) : null}

        {agentChatMutation.data ? (
          <div className="space-y-4">
            <div className="border rounded p-3 space-y-2">
              <h3 className="text-base font-semibold">Agent 最终回答</h3>
              <div className="text-sm whitespace-pre-wrap">
                {agentChatMutation.data.answer}
              </div>
            </div>

            <div className="border rounded p-3 space-y-2">
              <h3 className="text-base font-semibold">工具调用过程</h3>

              {agentChatMutation.data.tool_calls.length === 0 ? (
                <div className="text-sm text-gray-500">暂无工具调用。</div>
              ) : (
                <div className="space-y-3">
                  {agentChatMutation.data.tool_calls.map((toolCall, index) => (
                    <div
                      key={`${toolCall.tool_name}-${index}`}
                      className="border border-gray-700 rounded p-3 space-y-2"
                    >
                      <div className="text-sm font-medium">
                        {index + 1}. {toolCall.tool_name}
                      </div>

                      <div className="text-xs text-gray-400 whitespace-pre-wrap">
                        参数：
                        {JSON.stringify(toolCall.arguments, null, 2)}
                      </div>

                      <div className="text-xs text-gray-400">
                        状态：{toolCall.success ? "成功" : "失败"}
                      </div>

                      <div className="text-sm whitespace-pre-wrap">
                        {toolCall.observation}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="border rounded p-3 space-y-2">
              <h3 className="text-base font-semibold">Agent Sources</h3>

              {agentChatMutation.data.sources.length === 0 ? (
                <div className="text-sm text-gray-500">暂无来源资料。</div>
              ) : (
                <div className="space-y-3">
                  {agentChatMutation.data.sources.map((source, index) => (
                    <div
                      key={source.chunk_id}
                      className="border border-gray-700 rounded p-3 space-y-2"
                    >
                      <div className="text-sm font-medium">
                        [{index + 1}] {source.original_filename}
                      </div>

                      <div className="text-xs text-gray-400">
                        chunk_index：{source.chunk_index} ｜ content_length：
                        {source.content_length} ｜ match_count：
                        {source.match_count} ｜ similarity：
                        {source.similarity === null || source.similarity === undefined
                          ? "-"
                          : source.similarity.toFixed(4)}
                      </div>

                      <div className="text-sm whitespace-pre-wrap">
                        {source.content}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="border rounded p-3 space-y-2">
              <h3 className="text-base font-semibold">Agent Trace</h3>

              {agentChatMutation.data.trace.length === 0 ? (
                <div className="text-sm text-gray-500">暂无 trace。</div>
              ) : (
                <ol className="list-decimal list-inside text-sm space-y-1">
                  {agentChatMutation.data.trace.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        ) : null}
      </div>

      <CollapsibleSection
        title="Agent 历史记录"
        description="查看 Agent Chat 的历史问题、回答、工具调用链、sources 和 trace。"
        isOpen={expandedSections.agentHistory}
        onToggle={() => toggleSection("agentHistory")}
      >
        <div className="flex justify-end">

          <button
            className="border rounded px-3 py-1 text-sm"
            onClick={() =>
              queryClient.invalidateQueries({
                queryKey: ["agent-runs", knowledgeBaseId],
              })
            }
          >
            刷新历史
          </button>
        </div>

        <div className="flex gap-2">
          <input
            className="border rounded px-3 py-2 w-full"
            placeholder="搜索 Agent 历史，例如：FastAPI / embedding / RAG"
            value={agentRunKeyword}
            onChange={(event) => setAgentRunKeyword(event.target.value)}
          />

          <button
            className="border rounded px-3 py-2 text-sm"
            onClick={() =>
              queryClient.invalidateQueries({
                queryKey: ["agent-runs", knowledgeBaseId, agentRunKeyword],
              })
            }
          >
            搜索
          </button>

          <button
            className="border rounded px-3 py-2 text-sm"
            onClick={() => setAgentRunKeyword("")}
          >
            清空
          </button>
        </div>

        {agentRunsQuery.isLoading ? (
          <div className="text-sm text-gray-500">正在加载 Agent 历史记录...</div>
        ) : null}

        {agentRunsQuery.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            Agent 历史加载失败：
            {JSON.stringify(agentRunsQuery.error, null, 2)}
          </div>
        ) : null}

        {deleteAgentRunMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            删除 Agent 历史失败：
            {JSON.stringify(deleteAgentRunMutation.error, null, 2)}
          </div>
        ) : null}

        {agentRunsQuery.data ? (
          <div className="space-y-3">
            <div className="text-sm text-gray-500">
              共 {agentRunsQuery.data.count} 条 Agent 历史记录。
            </div>

            {agentRunsQuery.data.data.length === 0 ? (
              <div className="text-sm text-gray-500">
                暂无 Agent 历史记录。可以先在 Agent Chat 测试区提问。
              </div>
            ) : (
              agentRunsQuery.data.data.map((run) => {
                const expanded = expandedAgentRunIds.includes(run.id)

                return (
                  <div
                    key={run.id}
                    className="border border-gray-700 rounded p-3 space-y-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="text-sm font-semibold">
                          {run.question}
                        </div>

                        <div className="text-xs text-gray-400">
                          top_k={run.top_k} ｜ max_steps={run.max_steps} ｜ S=
                          {run.semantic_weight} ｜ K={run.keyword_weight} ｜ 耗时：
                          {run.latency_ms === null || run.latency_ms === undefined
                            ? "-"
                            : `${run.latency_ms} ms`}
                        </div>

                        <div className="text-xs text-gray-500">
                          创建时间：
                          {run.created_at
                            ? new Date(run.created_at).toLocaleString()
                            : "-"}
                        </div>

                        {run.error_message ? (
                          <div className="text-xs text-red-500">
                            错误：{run.error_message}
                          </div>
                        ) : null}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          className="border rounded px-2 py-1 text-xs"
                          onClick={() => handleToggleAgentRun(run.id)}
                        >
                          {expanded ? "收起" : "展开"}
                        </button>

                        <button
                          className="border border-red-500 text-red-400 rounded px-2 py-1 text-xs"
                          onClick={() => handleDeleteAgentRun(run.id)}
                          disabled={deleteAgentRunMutation.isPending}
                        >
                          删除
                        </button>
                      </div>
                    </div>

                    <div className="text-sm whitespace-pre-wrap border-t pt-3">
                      {run.answer.length > 300 && !expanded
                        ? `${run.answer.slice(0, 300)}...`
                        : run.answer}
                    </div>

                    {expanded ? (
                      <div className="space-y-3 border-t pt-3">
                        <div className="space-y-2">
                          <h3 className="text-sm font-semibold">工具调用过程</h3>

                          {run.tool_calls.length === 0 ? (
                            <div className="text-sm text-gray-500">
                              暂无工具调用。
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {run.tool_calls.map((toolCall, index) => (
                                <div
                                  key={`${run.id}-${toolCall.tool_name}-${index}`}
                                  className="border border-gray-700 rounded p-3 space-y-2"
                                >
                                  <div className="text-sm font-medium">
                                    {index + 1}. {toolCall.tool_name}
                                  </div>

                                  <div className="text-xs text-gray-400 whitespace-pre-wrap">
                                    参数：
                                    {JSON.stringify(toolCall.arguments, null, 2)}
                                  </div>

                                  <div className="text-xs text-gray-400">
                                    状态：{toolCall.success ? "成功" : "失败"}
                                  </div>

                                  <div className="text-sm whitespace-pre-wrap">
                                    {toolCall.observation}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          <h3 className="text-sm font-semibold">Sources</h3>

                          {run.sources.length === 0 ? (
                            <div className="text-sm text-gray-500">
                              暂无来源资料。
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {run.sources.map((source, index) => (
                                <div
                                  key={`${run.id}-${source.chunk_id}`}
                                  className="border border-gray-700 rounded p-3 space-y-2"
                                >
                                  <div className="text-sm font-medium">
                                    [{index + 1}] {source.original_filename}
                                  </div>

                                  <div className="text-xs text-gray-400">
                                    chunk_index：{source.chunk_index} ｜ length：
                                    {source.content_length} ｜ match_count：
                                    {source.match_count} ｜ similarity：
                                    {source.similarity === null ||
                                    source.similarity === undefined
                                      ? "-"
                                      : source.similarity.toFixed(4)}
                                  </div>

                                  <div className="text-sm whitespace-pre-wrap">
                                    {source.content}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          <h3 className="text-sm font-semibold">Trace</h3>

                          {run.trace.length === 0 ? (
                            <div className="text-sm text-gray-500">暂无 trace。</div>
                          ) : (
                            <ol className="list-decimal list-inside text-sm space-y-1">
                              {run.trace.map((item, index) => (
                                <li key={`${run.id}-${item}-${index}`}>{item}</li>
                              ))}
                            </ol>
                          )}
                        </div>
                      </div>
                    ) : null}
                  </div>
                )
              })
            )}
          </div>
        ) : null}
      </CollapsibleSection>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">RAG vs Agent 对比测试</h2>
          <p className="text-sm text-gray-500">
            输入同一个问题，同时调用普通 RAG 和 Agent，比较回答、来源、工具调用和耗时。
          </p>
        </div>

        <div className="space-y-2">
          <textarea
            className="border rounded px-3 py-2 w-full min-h-[90px]"
            placeholder="请输入对比问题，例如：请详细总结一下这个知识库主要讲了什么"
            value={compareQuestion}
            onChange={(event) => setCompareQuestion(event.target.value)}
          />

          <div className="flex flex-wrap items-center gap-2">
            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={handleCompareRagAgent}
              disabled={compareRagAgentMutation.isPending}
            >
              {compareRagAgentMutation.isPending
                ? "对比运行中..."
                : "同时运行 RAG 和 Agent"}
            </button>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                setCompareQuestion("请详细总结一下这个知识库主要讲了什么")
              }
            >
              示例：总结知识库
            </button>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                setCompareQuestion("FastAPI 的接口参数是怎么校验的？")
              }
            >
              示例：具体问题
            </button>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                setCompareQuestion("总结一下最近上传的文档主要讲了什么")
              }
            >
              示例：总结文档
            </button>
          </div>
        </div>

        {compareRagAgentMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            对比运行失败：
            {JSON.stringify(compareRagAgentMutation.error, null, 2)}
          </div>
        ) : null}

        {compareRagAgentMutation.data ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="border rounded p-3 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold">普通 RAG</h3>

                <div className="text-xs text-gray-500">
                  耗时：
                  {compareRagAgentMutation.data.ragResult.latency_ms === null ||
                  compareRagAgentMutation.data.ragResult.latency_ms === undefined
                    ? "-"
                    : `${compareRagAgentMutation.data.ragResult.latency_ms} ms`}
                </div>
              </div>

              <div className="text-sm whitespace-pre-wrap border rounded p-3">
                {compareRagAgentMutation.data.ragResult.answer}
              </div>

              <div className="text-xs text-gray-500">
                Sources 数量：
                {compareRagAgentMutation.data.ragResult.sources.length}
              </div>

              <details className="border rounded p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  查看 RAG Sources
                </summary>

                <div className="space-y-3 mt-3">
                  {compareRagAgentMutation.data.ragResult.sources.length === 0 ? (
                    <div className="text-sm text-gray-500">暂无来源资料。</div>
                  ) : (
                    compareRagAgentMutation.data.ragResult.sources.map(
                      (source, index) => (
                        <div
                          key={source.chunk_id}
                          className="border border-gray-700 rounded p-3 space-y-2"
                        >
                          <div className="text-sm font-medium">
                            [{index + 1}] {source.original_filename}
                          </div>

                          <div className="text-xs text-gray-400">
                            chunk_index：{source.chunk_index} ｜ match_count：
                            {source.match_count} ｜ similarity：
                            {source.similarity === null ||
                            source.similarity === undefined
                              ? "-"
                              : source.similarity.toFixed(4)}
                          </div>

                          <div className="text-sm whitespace-pre-wrap">
                            {source.content}
                          </div>
                        </div>
                      ),
                    )
                  )}
                </div>
              </details>

              <details className="border rounded p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  查看 RAG Trace
                </summary>

                <ol className="list-decimal list-inside text-sm space-y-1 mt-3">
                  {compareRagAgentMutation.data.ragResult.trace.map(
                    (item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ),
                  )}
                </ol>
              </details>
            </div>

            <div className="border rounded p-3 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold">Agent</h3>

                <div className="text-xs text-gray-500">
                  耗时：
                  {compareRagAgentMutation.data.agentResult.latency_ms === null ||
                  compareRagAgentMutation.data.agentResult.latency_ms === undefined
                    ? "-"
                    : `${compareRagAgentMutation.data.agentResult.latency_ms} ms`}
                </div>
              </div>

              <div className="text-sm whitespace-pre-wrap border rounded p-3">
                {compareRagAgentMutation.data.agentResult.answer}
              </div>

              <div className="text-xs text-gray-500">
                Sources 数量：
                {compareRagAgentMutation.data.agentResult.sources.length} ｜ 工具调用数量：
                {compareRagAgentMutation.data.agentResult.tool_calls.length}
              </div>

              <details className="border rounded p-3" open>
                <summary className="cursor-pointer text-sm font-medium">
                  查看 Agent 工具调用
                </summary>

                <div className="space-y-3 mt-3">
                  {compareRagAgentMutation.data.agentResult.tool_calls.length ===
                  0 ? (
                    <div className="text-sm text-gray-500">暂无工具调用。</div>
                  ) : (
                    compareRagAgentMutation.data.agentResult.tool_calls.map(
                      (toolCall, index) => (
                        <div
                          key={`${toolCall.tool_name}-${index}`}
                          className="border border-gray-700 rounded p-3 space-y-2"
                        >
                          <div className="text-sm font-medium">
                            {index + 1}. {toolCall.tool_name}
                          </div>

                          <div className="text-xs text-gray-400 whitespace-pre-wrap">
                            参数：
                            {JSON.stringify(toolCall.arguments, null, 2)}
                          </div>

                          <div className="text-xs text-gray-400">
                            状态：{toolCall.success ? "成功" : "失败"}
                          </div>

                          <div className="text-sm whitespace-pre-wrap">
                            {toolCall.observation}
                          </div>
                        </div>
                      ),
                    )
                  )}
                </div>
              </details>

              <details className="border rounded p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  查看 Agent Sources
                </summary>

                <div className="space-y-3 mt-3">
                  {compareRagAgentMutation.data.agentResult.sources.length === 0 ? (
                    <div className="text-sm text-gray-500">暂无来源资料。</div>
                  ) : (
                    compareRagAgentMutation.data.agentResult.sources.map(
                      (source, index) => (
                        <div
                          key={source.chunk_id}
                          className="border border-gray-700 rounded p-3 space-y-2"
                        >
                          <div className="text-sm font-medium">
                            [{index + 1}] {source.original_filename}
                          </div>

                          <div className="text-xs text-gray-400">
                            chunk_index：{source.chunk_index} ｜ match_count：
                            {source.match_count} ｜ similarity：
                            {source.similarity === null ||
                            source.similarity === undefined
                              ? "-"
                              : source.similarity.toFixed(4)}
                          </div>

                          <div className="text-sm whitespace-pre-wrap">
                            {source.content}
                          </div>
                        </div>
                      ),
                    )
                  )}
                </div>
              </details>

              <details className="border rounded p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  查看 Agent Trace
                </summary>

                <ol className="list-decimal list-inside text-sm space-y-1 mt-3">
                  {compareRagAgentMutation.data.agentResult.trace.map(
                    (item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ),
                  )}
                </ol>
              </details>
            </div>
          </div>
        ) : null}
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">RAG vs Agent 批量对比评测</h2>
          <p className="text-sm text-gray-500">
            使用当前知识库下的评测样例，同时运行普通 RAG 和 Agent，比较耗时、来源数量和工具调用情况。
          </p>
        </div>

        <button
          className="border rounded px-3 py-1 text-sm"
          onClick={() => runRagAgentCompareEvalMutation.mutate()}
          disabled={runRagAgentCompareEvalMutation.isPending}
        >
          {runRagAgentCompareEvalMutation.isPending
            ? "批量对比运行中..."
            : "运行 RAG vs Agent 批量对比"}
        </button>

        {runRagAgentCompareEvalMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            批量对比失败：
            {JSON.stringify(runRagAgentCompareEvalMutation.error, null, 2)}
          </div>
        ) : null}

        {runRagAgentCompareEvalMutation.data ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="border rounded p-3">
                <div className="text-xs text-gray-400">样例数</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.total_cases}
                </div>
              </div>

              <div className="border rounded p-3">
                <div className="text-xs text-gray-400">失败数</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.failed}
                </div>
              </div>

              <div className="border rounded p-3">
                <div className="text-xs text-gray-400">RAG 平均耗时</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.average_rag_latency_ms
                    ? `${runRagAgentCompareEvalMutation.data.summary.average_rag_latency_ms.toFixed(0)} ms`
                    : "-"}
                </div>
              </div>

              <div className="border rounded p-3">
                <div className="text-xs text-gray-400">Agent 平均耗时</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.average_agent_latency_ms
                    ? `${runRagAgentCompareEvalMutation.data.summary.average_agent_latency_ms.toFixed(0)} ms`
                    : "-"}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="border rounded p-3">
                <div className="text-xs text-gray-400">Agent 平均工具数</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.average_agent_tool_call_count
                    ? runRagAgentCompareEvalMutation.data.summary.average_agent_tool_call_count.toFixed(2)
                    : "-"}
                </div>
              </div>

              <div className="border rounded p-3">
                <div className="text-xs text-gray-400">工具失败总数</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.total_agent_failed_tool_count}
                </div>
              </div>

              <div className="border rounded p-3">
                <div className="text-xs text-gray-400">summarize_document</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.summarize_document_count}
                </div>
              </div>

              <div className="border rounded p-3">
                <div className="text-xs text-gray-400">read_document_chunks</div>
                <div className="text-xl font-semibold">
                  {runRagAgentCompareEvalMutation.data.summary.read_document_chunks_count}
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {runRagAgentCompareEvalMutation.data.data.map((item, index) => (
                <details
                  key={item.eval_case_id}
                  className="border rounded p-3"
                >
                  <summary className="cursor-pointer text-sm font-medium">
                    {index + 1}. {item.question}
                    {" ｜ "}
                    RAG {item.rag_latency_ms ?? "-"} ms
                    {" ｜ "}
                    Agent {item.agent_latency_ms ?? "-"} ms
                    {" ｜ "}
                    工具：{item.agent_tool_names.join(", ") || "-"}
                    {" ｜ "}
                    {item.is_failed ? "有失败" : "正常"}
                  </summary>

                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-3">
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold">普通 RAG</h4>

                      {item.rag_error_message ? (
                        <div className="text-sm text-red-500">
                          {item.rag_error_message}
                        </div>
                      ) : null}

                      <div className="text-xs text-gray-500">
                        Sources：{item.rag_sources_count}
                      </div>

                      <div className="text-sm whitespace-pre-wrap border rounded p-3">
                        {item.rag_answer || "暂无回答"}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold">Agent</h4>

                      {item.agent_error_message ? (
                        <div className="text-sm text-red-500">
                          {item.agent_error_message}
                        </div>
                      ) : null}

                      <div className="text-xs text-gray-500">
                        Sources：{item.agent_sources_count} ｜ 工具调用：
                        {item.agent_tool_call_count} ｜ 工具失败：
                        {item.agent_failed_tool_count}
                      </div>

                      <div className="text-sm whitespace-pre-wrap border rounded p-3">
                        {item.agent_answer || "暂无回答"}
                      </div>

                      <details className="border rounded p-3">
                        <summary className="cursor-pointer text-sm">
                          查看工具调用
                        </summary>

                        <div className="space-y-3 mt-3">
                          {item.agent_tool_calls.map((toolCall, toolIndex) => (
                            <div
                              key={`${toolCall.tool_name}-${toolIndex}`}
                              className="border rounded p-3 space-y-2"
                            >
                              <div className="text-sm font-medium">
                                {toolIndex + 1}. {toolCall.tool_name}
                              </div>

                              <div className="text-xs text-gray-500">
                                状态：{toolCall.success ? "成功" : "失败"}
                              </div>

                              <div className="text-xs whitespace-pre-wrap">
                                参数：{JSON.stringify(toolCall.arguments, null, 2)}
                              </div>

                              <div className="text-sm whitespace-pre-wrap">
                                {toolCall.observation}
                              </div>
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  </div>
                </details>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <RagAgentCompareHistorySection
        isOpen={expandedSections.compareHistory}
        onToggle={() => toggleSection("compareHistory")}
        batchesData={ragAgentCompareBatchesQuery.data}
        isLoading={ragAgentCompareBatchesQuery.isLoading}
        isError={ragAgentCompareBatchesQuery.isError}
        error={ragAgentCompareBatchesQuery.error}
        selectedCompareBatchId={selectedCompareBatchId}
        onSelectBatch={(batchId) => setSelectedCompareBatchId(batchId)}
        onExportMarkdown={(batchId) =>
          exportRagAgentCompareReportMutation.mutate(batchId)
        }
        onExportDocx={(batchId) =>
          exportRagAgentCompareDocxReportMutation.mutate(batchId)
        }
        onExportPdf={(batchId) =>
          exportRagAgentComparePdfReportMutation.mutate(batchId)
        }
        onDeleteBatch={(batchId) =>
          deleteRagAgentCompareBatchMutation.mutate(batchId)
        }
        isExportMarkdownPending={exportRagAgentCompareReportMutation.isPending}
        isExportDocxPending={exportRagAgentCompareDocxReportMutation.isPending}
        isExportPdfPending={exportRagAgentComparePdfReportMutation.isPending}
        isDeletePending={deleteRagAgentCompareBatchMutation.isPending}
        exportMarkdownError={exportRagAgentCompareReportMutation.error}
        exportDocxError={exportRagAgentCompareDocxReportMutation.error}
        exportPdfError={exportRagAgentComparePdfReportMutation.error}
        isExportMarkdownError={exportRagAgentCompareReportMutation.isError}
        isExportDocxError={exportRagAgentCompareDocxReportMutation.isError}
        isExportPdfError={exportRagAgentComparePdfReportMutation.isError}
      />

      <RagAgentCompareDetailSection
        isOpen={expandedSections.compareHistory}
        selectedCompareBatchId={selectedCompareBatchId}
        batchDetailData={ragAgentCompareBatchDetailQuery.data}
        isLoading={ragAgentCompareBatchDetailQuery.isLoading}
        isError={ragAgentCompareBatchDetailQuery.isError}
        error={ragAgentCompareBatchDetailQuery.error}
        onClose={() => setSelectedCompareBatchId(null)}
      />

      <RagAgentFailureAnalysisSection
        isOpen={expandedSections.compareHistory}
        batchDetailData={ragAgentCompareBatchDetailQuery.data}
      />

      <div className="border rounded-lg p-4 space-y-3">
        <div>
          <h2 className="text-lg font-semibold">当前 Agent 默认配置</h2>
          <p className="text-sm text-gray-500">
            当前 Agent Chat、RAG vs Agent 单条对比和批量对比会优先使用这组参数。该配置会保存到后端，刷新页面后仍然生效。
          </p>
        </div>

        {agentSettingsQuery.isLoading ? (
          <div className="text-sm text-gray-500">正在加载后端 Agent 配置...</div>
        ) : null}

        {agentSettingsQuery.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            加载 Agent 配置失败：
            {JSON.stringify(agentSettingsQuery.error, null, 2)}
          </div>
        ) : null}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="border rounded p-3">
            <div className="text-xs text-gray-400">top_k</div>
            <div className="text-xl font-semibold">{appliedAgentConfig.topK}</div>
          </div>

          <div className="border rounded p-3">
            <div className="text-xs text-gray-400">max_steps</div>
            <div className="text-xl font-semibold">
              {appliedAgentConfig.maxSteps}
            </div>
          </div>

          <div className="border rounded p-3">
            <div className="text-xs text-gray-400">semantic_weight</div>
            <div className="text-xl font-semibold">
              {appliedAgentConfig.semanticWeight}
            </div>
          </div>

          <div className="border rounded p-3">
            <div className="text-xs text-gray-400">keyword_weight</div>
            <div className="text-xl font-semibold">
              {appliedAgentConfig.keywordWeight}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            className="border rounded px-3 py-1 text-sm"
            onClick={handleResetAgentConfig}
            disabled={updateAgentSettingsMutation.isPending}
          >
            恢复默认配置
          </button>
        </div>

        {updateAgentSettingsMutation.isPending ? (
          <div className="text-sm text-gray-500">正在保存 Agent 配置...</div>
        ) : null}

        {updateAgentSettingsMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            保存 Agent 配置失败：
            {JSON.stringify(updateAgentSettingsMutation.error, null, 2)}
          </div>
        ) : null}
      </div>


      <AgentParamTuningSection
        isOpen={expandedSections.agentParamTuning}
        onToggle={() => toggleSection("agentParamTuning")}
        config={agentParamConfig}
        onConfigChange={setAgentParamConfig}
        onRunTuning={() => runAgentParamTuningMutation.mutate()}
        isTuningPending={runAgentParamTuningMutation.isPending}
        isTuningError={runAgentParamTuningMutation.isError}
        tuningError={runAgentParamTuningMutation.error}
        tuningData={runAgentParamTuningMutation.data}
        recommendation={agentParamRecommendation}
        onApplyRecommendation={handleApplyRecommendedAgentConfig}
        isApplyRecommendationPending={updateAgentSettingsMutation.isPending}
        isApplyRecommendationError={updateAgentSettingsMutation.isError}
        applyRecommendationError={updateAgentSettingsMutation.error}
      />

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">RAG 评测面板</h2>
          <p className="text-sm text-gray-500">
            这里可以创建固定测试问题，运行 RAG
            评测，并查看关键词命中、来源命中、得分和耗时。
          </p>
        </div>

        <div className="border rounded p-4 space-y-3">
          <div>
            <h3 className="text-base font-semibold">检索参数调优</h3>
            <p className="text-sm text-gray-500">
              调整 top_k、语义权重和关键词权重后，可以重新运行评测，观察平均分、失败率和命中率变化。
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="space-y-1">
              <div className="text-sm text-gray-500">top_k</div>
              <input
                type="number"
                min={1}
                max={20}
                className="border rounded px-3 py-2 w-full"
                value={ragTopK}
                onChange={(event) => setRagTopK(Number(event.target.value))}
              />
            </label>

            <label className="space-y-1">
              <div className="text-sm text-gray-500">语义检索权重</div>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                className="border rounded px-3 py-2 w-full"
                value={ragSemanticWeight}
                onChange={(event) =>
                  setRagSemanticWeight(Number(event.target.value))
                }
              />
            </label>

            <label className="space-y-1">
              <div className="text-sm text-gray-500">关键词检索权重</div>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                className="border rounded px-3 py-2 w-full"
                value={ragKeywordWeight}
                onChange={(event) =>
                  setRagKeywordWeight(Number(event.target.value))
                }
              />
            </label>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() => {
                setRagTopK(5)
                setRagSemanticWeight(0.75)
                setRagKeywordWeight(0.25)
              }}
            >
              默认参数 0.75 / 0.25
            </button>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() => {
                setRagTopK(5)
                setRagSemanticWeight(0.9)
                setRagKeywordWeight(0.1)
              }}
            >
              偏语义 0.9 / 0.1
            </button>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() => {
                setRagTopK(5)
                setRagSemanticWeight(0.6)
                setRagKeywordWeight(0.4)
              }}
            >
              平衡偏关键词 0.6 / 0.4
            </button>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() => {
                setRagTopK(8)
                setRagSemanticWeight(0.75)
                setRagKeywordWeight(0.25)
              }}
            >
              提高 top_k 到 8
            </button>
          </div>

          <div className="text-xs text-gray-500">
            当前参数：top_k = {ragTopK}，semantic_weight ={" "}
            <div className="border-t pt-3 space-y-3">
              <h4 className="text-sm font-semibold">批量评测实验信息</h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input
                  className="border rounded px-3 py-2 w-full"
                  placeholder="实验名称，可选，例如：默认参数组第一次测试"
                  value={evalBatchName}
                  onChange={(event) => setEvalBatchName(event.target.value)}
                />

                <input
                  className="border rounded px-3 py-2 w-full"
                  placeholder="实验备注，可选，例如：测试偏语义权重下的来源命中率"
                  value={evalBatchNote}
                  onChange={(event) => setEvalBatchNote(event.target.value)}
                />
              </div>

              <div className="text-xs text-gray-500">
                点击“运行全部评测”后，会自动生成一条实验批次记录。
              </div>
            </div>
            <div className="border-t pt-3 space-y-3">
              <h4 className="text-sm font-semibold">参数预设</h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input
                  className="border rounded px-3 py-2 w-full"
                  placeholder="预设名称，例如：默认参数组 / 偏语义组 / 高召回组"
                  value={presetName}
                  onChange={(event) => setPresetName(event.target.value)}
                />

                <input
                  className="border rounded px-3 py-2 w-full"
                  placeholder="备注，可选，例如：用于测试来源命中率"
                  value={presetNote}
                  onChange={(event) => setPresetNote(event.target.value)}
                />
              </div>

              <button
                className="border rounded px-3 py-1 text-sm"
                onClick={handleCreateRagRetrievalPreset}
                disabled={createRagRetrievalPresetMutation.isPending}
              >
                {createRagRetrievalPresetMutation.isPending
                  ? "保存中..."
                  : "保存当前参数为预设"}
              </button>

              {createRagRetrievalPresetMutation.isError ? (
                <div className="text-sm text-red-500 whitespace-pre-wrap">
                  保存参数预设失败：
                  {JSON.stringify(createRagRetrievalPresetMutation.error, null, 2)}
                </div>
              ) : null}

              {deleteRagRetrievalPresetMutation.isError ? (
                <div className="text-sm text-red-500 whitespace-pre-wrap">
                  删除参数预设失败：
                  {JSON.stringify(deleteRagRetrievalPresetMutation.error, null, 2)}
                </div>
              ) : null}

              {ragRetrievalPresetsQuery.isLoading ? (
                <div className="text-sm text-gray-500">正在加载参数预设...</div>
              ) : null}

              {ragRetrievalPresetsQuery.isError ? (
                <div className="text-sm text-red-500 whitespace-pre-wrap">
                  参数预设加载失败：
                  {JSON.stringify(ragRetrievalPresetsQuery.error, null, 2)}
                </div>
              ) : null}

              {ragRetrievalPresetsQuery.data ? (
                <div className="space-y-2">
                  {ragRetrievalPresetsQuery.data.data.length === 0 ? (
                    <div className="text-sm text-gray-500">
                      暂无参数预设。你可以先调整参数后保存。
                    </div>
                  ) : (
                    ragRetrievalPresetsQuery.data.data.map((preset) => (
                      <div
                        key={preset.id}
                        className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium">{preset.name}</div>
                            <div className="text-xs text-gray-400">
                              top_k={preset.top_k} ｜ S={preset.semantic_weight} ｜ K=
                              {preset.keyword_weight}
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              className="border rounded px-2 py-1 text-xs"
                              onClick={() => handleApplyRagRetrievalPreset(preset)}
                            >
                              应用
                            </button>

                            <button
                              className="border border-red-500 text-red-400 rounded px-2 py-1 text-xs"
                              onClick={() => handleDeleteRagRetrievalPreset(preset.id)}
                              disabled={deleteRagRetrievalPresetMutation.isPending}
                            >
                              删除
                            </button>
                          </div>
                        </div>

                        {preset.note ? (
                          <div className="text-xs text-gray-400">
                            备注：{preset.note}
                          </div>
                        ) : null}

                        {preset.created_at ? (
                          <div className="text-xs text-gray-500">
                            创建时间：{new Date(preset.created_at).toLocaleString()}
                          </div>
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
              ) : null}
            </div>
            {ragSemanticWeight}，keyword_weight = {ragKeywordWeight}
          </div>
        </div>

        <div className="border rounded p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">评测统计概览</h3>
              <p className="text-sm text-gray-500">
                统计最近的 RAG 评测运行结果，用于观察整体检索与回答效果。
              </p>
            </div>

            <div className="flex gap-2">
              <button
                className="border rounded px-3 py-1 text-sm"
                onClick={() =>
                  queryClient.invalidateQueries({
                    queryKey: ["rag-eval-summary", knowledgeBaseId],
                  })
                }
              >
                刷新统计
              </button>

              <button
                className="border rounded px-3 py-1 text-sm"
                onClick={handleRunAllRagEvalCases}
                disabled={runAllRagEvalCasesMutation.isPending}
              >
                {runAllRagEvalCasesMutation.isPending
                  ? "批量运行中..."
                  : "运行全部评测"}
              </button>
            </div>
          </div>

          {ragEvalSummaryQuery.isLoading ? (
            <div className="text-sm text-gray-500">正在加载评测统计...</div>
          ) : null}

          {ragEvalSummaryQuery.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              评测统计加载失败：
              {JSON.stringify(ragEvalSummaryQuery.error, null, 2)}
            </div>
          ) : null}

          {runAllRagEvalCasesMutation.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              批量运行评测失败：
              {JSON.stringify(runAllRagEvalCasesMutation.error, null, 2)}
            </div>
          ) : null}

          {runAllRagEvalCasesMutation.data ? (
            <div className="text-sm text-gray-500">
              批量运行结果：共 {runAllRagEvalCasesMutation.data.total_cases}
              条样例，成功运行 {runAllRagEvalCasesMutation.data.ran}
              条，失败 {runAllRagEvalCasesMutation.data.failed} 条。
            </div>
          ) : null}

          {ragEvalSummaryQuery.data ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                <div className="text-xs text-gray-400">总评测次数</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.total_runs}
                </div>
              </div>

              <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                <div className="text-xs text-gray-400">平均分</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.average_score === null
                    ? "-"
                    : ragEvalSummaryQuery.data.average_score.toFixed(2)}
                </div>
              </div>

              <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                <div className="text-xs text-gray-400">关键词命中率</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.keyword_hit_rate === null
                    ? "-"
                    : `${(ragEvalSummaryQuery.data.keyword_hit_rate * 100).toFixed(
                        1,
                      )}%`}
                </div>
              </div>

              <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                <div className="text-xs text-gray-400">来源命中率</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.source_hit_rate === null
                    ? "-"
                    : `${(ragEvalSummaryQuery.data.source_hit_rate * 100).toFixed(
                        1,
                      )}%`}
                </div>
              </div>

              <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                <div className="text-xs text-gray-400">平均耗时</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.average_latency_ms === null
                    ? "-"
                    : `${ragEvalSummaryQuery.data.average_latency_ms.toFixed(0)} ms`}
                </div>
              </div>

              <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                <div className="text-xs text-gray-400">最高分</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.max_score === null
                    ? "-"
                    : ragEvalSummaryQuery.data.max_score.toFixed(2)}
                </div>
              </div>

              <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                <div className="text-xs text-gray-400">最低分</div>
                <div className="text-xl font-semibold">
                  {ragEvalSummaryQuery.data.min_score === null
                    ? "-"
                    : ragEvalSummaryQuery.data.min_score.toFixed(2)}
                </div>
              </div>

              <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                <div className="text-xs text-gray-400">最新评测时间</div>
                <div className="text-sm font-medium">
                  {ragEvalSummaryQuery.data.latest_run_at
                    ? new Date(
                        ragEvalSummaryQuery.data.latest_run_at,
                      ).toLocaleString()
                    : "-"}
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="border rounded p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">参数版本对比</h3>
              <p className="text-sm text-gray-500">
                按 top_k、语义权重和关键词权重分组，对比不同参数组合下的平均分、失败率、命中率和耗时。
              </p>
            </div>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-param-groups", knowledgeBaseId],
                })
              }
            >
              刷新对比
            </button>
          </div>

          {ragEvalParamGroupsQuery.isLoading ? (
            <div className="text-sm text-gray-500">正在加载参数版本对比...</div>
          ) : null}

          {ragEvalParamGroupsQuery.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              参数版本对比加载失败：
              {JSON.stringify(ragEvalParamGroupsQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalParamGroupsQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-gray-500">
                共 {ragEvalParamGroupsQuery.data.count} 组参数组合。
              </div>

              {ragEvalParamGroupsQuery.data.data.length === 0 ? (
                <div className="text-sm text-gray-500">
                  暂无参数对比数据。可以先运行几次不同参数组合的评测。
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-gray-700 text-gray-400">
                        <th className="text-left py-2 px-2">参数组合</th>
                        <th className="text-left py-2 px-2">运行次数</th>
                        <th className="text-left py-2 px-2">平均分</th>
                        <th className="text-left py-2 px-2">失败率</th>
                        <th className="text-left py-2 px-2">关键词命中率</th>
                        <th className="text-left py-2 px-2">来源命中率</th>
                        <th className="text-left py-2 px-2">平均耗时</th>
                        <th className="text-left py-2 px-2">最新运行</th>
                      </tr>
                    </thead>

                    <tbody>
                      {ragEvalParamGroupsQuery.data.data.map((group) => (
                        <tr
                          key={`${group.top_k}-${group.semantic_weight}-${group.keyword_weight}`}
                          className="border-b border-gray-800 text-gray-100"
                        >
                          <td className="py-2 px-2">
                            <div className="space-y-1">
                              {group.preset_names.length > 0 ? (
                                <div className="font-medium text-gray-100">
                                  {group.preset_names.join("、")}
                                </div>
                              ) : (
                                <div className="font-medium text-gray-400">未命名参数组</div>
                              )}

                              <div className="text-xs text-gray-400">
                                top_k={group.top_k} ｜ S={group.semantic_weight} ｜ K=
                                {group.keyword_weight}
                              </div>
                            </div>
                          </td>

                          <td className="py-2 px-2">{group.total_runs}</td>

                          <td className="py-2 px-2">
                            {group.average_score === null
                              ? "-"
                              : group.average_score.toFixed(2)}
                          </td>

                          <td className="py-2 px-2">
                            {group.failure_rate === null
                              ? "-"
                              : `${(group.failure_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {group.keyword_hit_rate === null
                              ? "-"
                              : `${(group.keyword_hit_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {group.source_hit_rate === null
                              ? "-"
                              : `${(group.source_hit_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {group.average_latency_ms === null
                              ? "-"
                              : `${group.average_latency_ms.toFixed(0)} ms`}
                          </td>

                          <td className="py-2 px-2">
                            {group.latest_run_at
                              ? new Date(group.latest_run_at).toLocaleString()
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}
        </div>

        <div className="border rounded p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">实验批次记录</h3>
              <p className="text-sm text-gray-500">
                每次运行全部评测都会生成一条实验批次记录，用于对比不同参数组合下的整体效果。
              </p>
            </div>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-batches", knowledgeBaseId],
                })
              }
            >
              刷新批次
            </button>
          </div>

          {ragEvalBatchesQuery.isLoading ? (
            <div className="text-sm text-gray-500">正在加载实验批次...</div>
          ) : null}

          {ragEvalBatchesQuery.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              实验批次加载失败：
              {JSON.stringify(ragEvalBatchesQuery.error, null, 2)}
            </div>
          ) : null}

          {deleteRagEvalBatchMutation.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              删除实验批次失败：
              {JSON.stringify(deleteRagEvalBatchMutation.error, null, 2)}
            </div>
          ) : null}

          {ragEvalBatchesQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-gray-500">
                共 {ragEvalBatchesQuery.data.count} 条实验批次记录。
              </div>

              {ragEvalBatchesQuery.data.data.length === 0 ? (
                <div className="text-sm text-gray-500">
                  暂无实验批次。可以先点击“运行全部评测”生成一条记录。
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-gray-700 text-gray-400">
                        <th className="text-left py-2 px-2">实验名称</th>
                        <th className="text-left py-2 px-2">参数</th>
                        <th className="text-left py-2 px-2">样例数</th>
                        <th className="text-left py-2 px-2">成功 / 失败</th>
                        <th className="text-left py-2 px-2">平均分</th>
                        <th className="text-left py-2 px-2">关键词命中率</th>
                        <th className="text-left py-2 px-2">来源命中率</th>
                        <th className="text-left py-2 px-2">平均耗时</th>
                        <th className="text-left py-2 px-2">创建时间</th>
                        <th className="text-left py-2 px-2">操作</th>
                      </tr>
                    </thead>

                    <tbody>
                      {ragEvalBatchesQuery.data.data.map((batch) => (
                        <tr
                          key={batch.id}
                          className="border-b border-gray-800 text-gray-100"
                        >
                          <td className="py-2 px-2">
                            <div className="space-y-1">
                              <div className="font-medium">{batch.name}</div>

                              {batch.note ? (
                                <div className="text-xs text-gray-400">
                                  {batch.note}
                                </div>
                              ) : null}
                            </div>
                          </td>

                          <td className="py-2 px-2">
                            top_k={batch.top_k} ｜ S={batch.semantic_weight} ｜ K=
                            {batch.keyword_weight}
                          </td>

                          <td className="py-2 px-2">{batch.total_cases}</td>

                          <td className="py-2 px-2">
                            {batch.ran} / {batch.failed}
                          </td>

                          <td className="py-2 px-2">
                            {batch.average_score === null
                              ? "-"
                              : batch.average_score.toFixed(2)}
                          </td>

                          <td className="py-2 px-2">
                            {batch.keyword_hit_rate === null
                              ? "-"
                              : `${(batch.keyword_hit_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {batch.source_hit_rate === null
                              ? "-"
                              : `${(batch.source_hit_rate * 100).toFixed(1)}%`}
                          </td>

                          <td className="py-2 px-2">
                            {batch.average_latency_ms === null
                              ? "-"
                              : `${batch.average_latency_ms.toFixed(0)} ms`}
                          </td>

                          <td className="py-2 px-2">
                            {batch.created_at
                              ? new Date(batch.created_at).toLocaleString()
                              : "-"}
                          </td>

                          <td className="py-2 px-2">
                            <button
                              className="border border-red-500 text-red-400 rounded px-2 py-1 text-xs"
                              onClick={() => handleDeleteRagEvalBatch(batch.id)}
                              disabled={deleteRagEvalBatchMutation.isPending}
                            >
                              删除
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}
        </div>

        <div className="border rounded p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">失败样例分析</h3>
              <p className="text-sm text-gray-500">
                这里统计最近评测中的失败样例，帮助定位是关键词、来源还是运行错误导致的问题。
              </p>
            </div>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
                })
              }
            >
              刷新分析
            </button>
          </div>

          {ragEvalFailureAnalysisQuery.isLoading ? (
            <div className="text-sm text-gray-500">正在加载失败分析...</div>
          ) : null}

          {ragEvalFailureAnalysisQuery.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              失败分析加载失败：
              {JSON.stringify(ragEvalFailureAnalysisQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalFailureAnalysisQuery.data ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                  <div className="text-xs text-gray-400">失败次数</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.failed_runs}
                  </div>
                </div>

                <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                  <div className="text-xs text-gray-400">失败率</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.failure_rate === null
                      ? "-"
                      : `${(
                          ragEvalFailureAnalysisQuery.data.failure_rate * 100
                        ).toFixed(1)}%`}
                  </div>
                </div>

                <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                  <div className="text-xs text-gray-400">关键词未命中</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.keyword_miss_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                  <div className="text-xs text-gray-400">来源未命中</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.source_miss_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                  <div className="text-xs text-gray-400">运行错误</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.error_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                  <div className="text-xs text-gray-400">低分样例</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.low_score_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                  <div className="text-xs text-gray-400">零分样例</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.zero_score_count}
                  </div>
                </div>

                <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                  <div className="text-xs text-gray-400">失败平均耗时</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data
                      .average_failed_latency_ms === null
                      ? "-"
                      : `${ragEvalFailureAnalysisQuery.data.average_failed_latency_ms.toFixed(
                          0,
                        )} ms`}
                  </div>
                </div>
              </div>

              <details>
                <summary className="cursor-pointer text-sm text-gray-300">
                  查看最近失败样例（
                  {ragEvalFailureAnalysisQuery.data.recent_failed_runs.length}）
                </summary>

                <div className="space-y-2 pt-2">
                  {ragEvalFailureAnalysisQuery.data.recent_failed_runs.length ===
                  0 ? (
                    <div className="text-sm text-gray-500">暂无失败样例。</div>
                  ) : (
                    ragEvalFailureAnalysisQuery.data.recent_failed_runs.map(
                      (run) => (
                        <div
                          key={run.id}
                          className="border border-gray-700 rounded p-3 bg-black text-gray-100 space-y-2"
                        >
                          <div className="text-sm font-medium">
                            问题：{run.question}
                          </div>

                          <div className="text-xs text-gray-400">
                            Score：{run.score ?? "-"} ｜ 失败原因：
                            {run.failure_reasons.length > 0
                              ? run.failure_reasons.join("、")
                              : "无"}
                          </div>

                          <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                            {run.answer}
                          </pre>
                        </div>
                      ),
                    )
                  )}
                </div>
              </details>
            </div>
          ) : null}
        </div>

        <div className="border rounded p-4 space-y-3">
          <h3 className="text-base font-semibold">创建评测样例</h3>

          <input
            className="border rounded px-3 py-2 w-full"
            placeholder="评测问题，例如：用户登录状态应该怎么保存？"
            value={evalQuestion}
            onChange={(event) => setEvalQuestion(event.target.value)}
          />

          <input
            className="border rounded px-3 py-2 w-full"
            placeholder="预期关键词，用逗号分隔，例如：token, Authorization, JWT"
            value={evalKeywords}
            onChange={(event) => setEvalKeywords(event.target.value)}
          />

          <input
            className="border rounded px-3 py-2 w-full"
            placeholder="预期来源文件名，可选，例如：auth.md"
            value={evalSourceFilename}
            onChange={(event) => setEvalSourceFilename(event.target.value)}
          />

          <textarea
            className="border rounded px-3 py-2 w-full min-h-20"
            placeholder="备注，可选"
            value={evalNote}
            onChange={(event) => setEvalNote(event.target.value)}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleCreateRagEvalCase}
            disabled={createRagEvalCaseMutation.isPending}
          >
            {createRagEvalCaseMutation.isPending ? "创建中..." : "创建评测样例"}
          </button>

          {createRagEvalCaseMutation.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              创建评测样例失败：
              {JSON.stringify(createRagEvalCaseMutation.error, null, 2)}
            </div>
          ) : null}
        </div>

        <div className="border rounded p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">评测样例列表</h3>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-cases", knowledgeBaseId],
                })
              }
            >
              刷新样例
            </button>
          </div>

          {ragEvalCasesQuery.isLoading ? (
            <div className="text-sm text-gray-500">正在加载评测样例...</div>
          ) : null}

          {ragEvalCasesQuery.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              评测样例加载失败：
              {JSON.stringify(ragEvalCasesQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalCasesQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-gray-500">
                共 {ragEvalCasesQuery.data.count} 条评测样例。
              </div>

              {ragEvalCasesQuery.data.data.length === 0 ? (
                <div className="text-sm text-gray-500">
                  暂无评测样例。可以先在上方创建一个测试问题。
                </div>
              ) : (
                ragEvalCasesQuery.data.data.map((evalCase) => (
                  <div
                    key={evalCase.id}
                    className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">
                        问题：{evalCase.question}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          className="border rounded px-2 py-1 text-xs"
                          onClick={() => handleRunRagEvalCase(evalCase.id)}
                          disabled={runRagEvalCaseMutation.isPending}
                        >
                          {runRagEvalCaseMutation.isPending
                            ? "运行中..."
                            : "运行评测"}
                        </button>

                        <button
                          className="border border-red-500 text-red-400 rounded px-2 py-1 text-xs"
                          onClick={() => handleDeleteRagEvalCase(evalCase.id)}
                          disabled={deleteRagEvalCaseMutation.isPending}
                        >
                          删除
                        </button>
                      </div>
                    </div>

                    <div className="text-xs text-gray-400">
                      预期关键词：
                      {evalCase.expected_keywords.length > 0
                        ? evalCase.expected_keywords.join("、")
                        : "无"}{" "}
                      ｜ 预期来源：
                      {evalCase.expected_source_filename || "无"}
                    </div>

                    {evalCase.note ? (
                      <div className="text-xs text-gray-400">
                        备注：{evalCase.note}
                      </div>
                    ) : null}

                    {evalCase.created_at ? (
                      <div className="text-xs text-gray-500">
                        创建时间：{new Date(evalCase.created_at).toLocaleString()}
                      </div>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          ) : null}

          {runRagEvalCaseMutation.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              运行评测失败：
              {JSON.stringify(runRagEvalCaseMutation.error, null, 2)}
            </div>
          ) : null}

          {deleteRagEvalCaseMutation.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              删除评测样例失败：
              {JSON.stringify(deleteRagEvalCaseMutation.error, null, 2)}
            </div>
          ) : null}
        </div>

        <CollapsibleSection
          title="评测运行结果"
          description="查看 RAG Eval 的运行结果、失败样例、评分和参数记录。"
          isOpen={expandedSections.evalRuns}
          onToggle={() => toggleSection("evalRuns")}
        >
          <div className="flex justify-end">
            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-runs", knowledgeBaseId],
                })
              }
            >
              刷新结果
            </button>
          </div>

          <div className="flex flex-col md:flex-row gap-3">
            <input
              className="border rounded px-3 py-2 flex-1"
              placeholder="搜索评测结果，例如：登录、token、FastAPI"
              value={evalRunKeyword}
              onChange={(event) => setEvalRunKeyword(event.target.value)}
            />

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={evalFailedOnly}
                onChange={(event) => setEvalFailedOnly(event.target.checked)}
              />
              只看失败样例
            </label>

            <select
              className="border rounded px-3 py-2"
              value={evalFailureType}
              onChange={(event) =>
                setEvalFailureType(
                  event.target.value as
                    | "all"
                    | "keyword"
                    | "source"
                    | "error"
                    | "zero",
                )
              }
            >
              <option value="all">全部类型</option>
              <option value="keyword">关键词未命中</option>
              <option value="source">来源未命中</option>
              <option value="error">运行错误</option>
              <option value="zero">零分样例</option>
            </select>

            <button
              className="border rounded px-4 py-2"
              onClick={() => {
                setEvalRunKeyword("")
                setEvalFailedOnly(false)
                setEvalFailureType("all")
              }}
            >
              清空筛选
            </button>
          </div>

          {ragEvalRunsQuery.isLoading ? (
            <div className="text-sm text-gray-500">正在加载评测结果...</div>
          ) : null}

          {ragEvalRunsQuery.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              评测结果加载失败：
              {JSON.stringify(ragEvalRunsQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalRunsQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-gray-500">
                共 {ragEvalRunsQuery.data.count} 条评测运行结果。
              </div>

              {ragEvalRunsQuery.data.data.length === 0 ? (
                <div className="text-sm text-gray-500">
                  暂无评测结果。可以先点击某条样例的“运行评测”。
                </div>
              ) : (
                ragEvalRunsQuery.data.data.map((run) => (
                  <div
                    key={run.id}
                    className="border border-gray-700 rounded p-4 bg-neutral-900 text-gray-100 space-y-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">问题：{run.question}</div>

                      <div className="text-xs text-gray-400">
                        Score：{run.score ?? "-"} ｜ 关键词命中：
                        {run.keyword_hit === null
                          ? "-"
                          : run.keyword_hit
                            ? "是"
                            : "否"}{" "}
                        ｜ 来源命中：
                        {run.source_hit === null
                          ? "-"
                          : run.source_hit
                            ? "是"
                            : "否"}{" "}
                        ｜ 耗时：{run.latency_ms ?? "-"} ms
                      </div>
                    </div>

                    <div className="text-xs text-gray-400">
                      预期关键词：
                      {run.expected_keywords.length > 0
                        ? run.expected_keywords.join("、")
                        : "无"}{" "}
                      ｜ 预期来源：
                      {run.expected_source_filename || "无"} ｜ 检索方式：
                      {run.retrieval_type} ｜ top_k：{run.top_k} ｜ 语义权重：
                      {run.semantic_weight} ｜ 关键词权重：{run.keyword_weight}
                    </div>

                    {run.is_failed ? (
                      <div className="text-xs text-red-400">
                        失败原因：
                        {run.failure_reasons.length > 0
                          ? run.failure_reasons.join("、")
                          : "未知原因"}
                      </div>
                    ) : (
                      <div className="text-xs text-green-400">
                        当前评测未发现失败项
                      </div>
                    )}

                    <div className="space-y-1">
                      <div className="text-sm font-medium text-gray-200">回答</div>
                      <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                        {run.answer}
                      </pre>
                    </div>

                    <details>
                      <summary className="cursor-pointer text-sm text-gray-300">
                        查看引用来源（{run.sources.length}）
                      </summary>

                      <div className="space-y-2 pt-2">
                        {run.sources.length === 0 ? (
                          <div className="text-sm text-gray-500">
                            当前评测结果没有引用来源。
                          </div>
                        ) : (
                          run.sources.map((source) => (
                            <div
                              key={source.chunk_id}
                              className="border border-gray-700 rounded p-3 bg-black text-gray-100 space-y-2"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-sm font-medium">
                                  来源文件：{source.original_filename} ｜ Chunk{" "}
                                  {source.chunk_index}
                                </div>

                                <div className="text-xs text-gray-400">
                                  相似度：{source.similarity?.toFixed(4)} ｜
                                  关键词命中：{source.match_count} ｜ 长度：
                                  {source.content_length}
                                </div>
                              </div>

                              <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                                {source.content}
                              </pre>
                            </div>
                          ))
                        )}
                      </div>
                    </details>

                    <details>
                      <summary className="cursor-pointer text-sm text-gray-300">
                        查看执行过程 Trace
                      </summary>

                      <div className="pt-2 text-sm text-gray-400">
                        {run.trace.length > 0 ? run.trace.join(" → ") : "暂无 trace"}
                      </div>
                    </details>

                    {run.created_at ? (
                      <div className="text-xs text-gray-500">
                        创建时间：{new Date(run.created_at).toLocaleString()}
                      </div>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          ) : null}
        </CollapsibleSection>
      </div>


      <CollapsibleSection
        title="文档列表"
        description="查看当前知识库中的文档。点击展开后显示文档详情、解析状态和切分结果入口。"
        isOpen={expandedSections.documents}
        onToggle={() => toggleSection("documents")}
      >

        {documents.data.length === 0 ? (
          <div className="text-gray-500">该知识库下暂无文档</div>
        ) : (
          <div className="space-y-3">
            {documents.data.map((document) => {
              const isExpanded = expandedDocumentId === document.id

              return (
                <div key={document.id} className="border rounded p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">
                        {document.original_filename}
                      </div>

                      <div className="text-sm text-gray-500">
                        类型：{document.content_type || "未知"} ｜ 大小：
                        {formatFileSize(document.file_size)} ｜ 状态：
                        {document.status}
                      </div>

                      {document.error_message ? (
                        <div className="text-sm text-red-500">
                          解析信息：{document.error_message}
                        </div>
                      ) : null}

                      <div className="text-xs text-gray-400">
                        文档 ID：{document.id}
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button
                        className="border rounded px-3 py-1"
                        onClick={() => handleToggleChunks(document.id)}
                      >
                        {isExpanded ? "收起切分结果" : "查看切分结果"}
                      </button>

                      <button
                        className="border rounded px-3 py-1"
                        onClick={() =>
                          handleDownload(document.id, document.original_filename)
                        }
                      >
                        下载
                      </button>

                      <button
                        className="border rounded px-3 py-1"
                        onClick={() => {
                          if (confirm("确定删除这个文档吗？")) {
                            deleteDocumentMutation.mutate(document.id)
                          }
                        }}
                        disabled={deleteDocumentMutation.isPending}
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  {isExpanded ? (
                    <div className="border-t pt-4 space-y-3">
                      <div className="font-medium">切分结果</div>

                      {isChunksPending ? (
                        <div className="text-sm text-gray-500">
                          正在加载切分结果...
                        </div>
                      ) : null}

                      {isChunksError ? (
                        <div className="text-sm text-red-500">
                          切分结果加载失败
                        </div>
                      ) : null}

                      {!isChunksPending &&
                      !isChunksError &&
                      chunks?.data.length === 0 ? (
                        <div className="text-sm text-gray-500">
                          暂无切分结果。可能是文件未解析成功、内容为空，或 PDF 为扫描版图片。
                        </div>
                      ) : null}

                      {!isChunksPending &&
                      !isChunksError &&
                      chunks?.data.map((chunk) => (
                        <div
                          key={chunk.id}
                          className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <div className="text-sm font-medium text-gray-100">
                              Chunk {chunk.chunk_index}
                            </div>

                            <div className="text-xs text-gray-400">
                              长度：{chunk.content_length}
                            </div>
                          </div>

                          <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                            {chunk.content}
                          </pre>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </CollapsibleSection>
    </div>
  )
}