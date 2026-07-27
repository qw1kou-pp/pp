import {
  DocumentsService,
  type KnowledgeBasePublic,
  type RagAgentCompareBatchPublic,
  type RagRetrievalPresetPublic,
} from "@/client"
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  useEffect,
  useMemo,
  useState,
} from "react"

import {
  AGENT_PARAM_PRESETS,
  type AgentParamConfig,
} from "./AgentParamTuningSection"
import {
  buildCodeAgentExperimentReportMarkdown,
} from "./codeAgentExperimentReport"
import {
  buildAgentParamRecommendation,
  buildCodeAgentOptimizationAdvice,
  buildOptimizationCompareRows,
} from "./codeAgentOptimization"
import {
  downloadBase64File,
  downloadTextFile,
} from "./compareUtils"
import type {
  AppliedAgentConfig,
} from "./knowledgeBaseDetailTypes"
import {
  knowledgeBaseEvaluationKeys,
  ragEvalCasesQueryOptions,
  ragEvalRunsQueryOptions,
} from "./knowledgeBaseEvaluationQueries"
import {
  DEFAULT_AGENT_CONFIG,
  DEFAULT_AGENT_TUNING_CONFIG,
  DEFAULT_RETRIEVAL_SETTINGS,
  normalizeRetrievalSettings,
  type EvaluationFailureFilter,
  type RetrievalSettings,
} from "./knowledgeBaseEvaluationTypes"

export type UseKnowledgeBaseEvaluationOptions = {
  knowledgeBaseId: string
  knowledgeBase: KnowledgeBasePublic
}

export function useKnowledgeBaseEvaluation({
  knowledgeBaseId,
  knowledgeBase,
}: UseKnowledgeBaseEvaluationOptions) {
  const queryClient = useQueryClient()

  const [retrievalSettings, setRetrievalSettings] =
    useState<RetrievalSettings>(
      DEFAULT_RETRIEVAL_SETTINGS,
    )

  const [agentParamConfig, setAgentParamConfig] =
    useState<AgentParamConfig>(
      DEFAULT_AGENT_TUNING_CONFIG,
    )

  const [appliedAgentConfig, setAppliedAgentConfig] =
    useState<AppliedAgentConfig>(
      DEFAULT_AGENT_CONFIG,
    )

  const [evalQuestion, setEvalQuestion] =
    useState("")
  const [evalKeywords, setEvalKeywords] =
    useState("")
  const [evalSourceFilename, setEvalSourceFilename] =
    useState("")
  const [evalNote, setEvalNote] =
    useState("")

  const [codeEvalMaxFiles, setCodeEvalMaxFiles] =
    useState(20)
  const [codeEvalMaxSymbols, setCodeEvalMaxSymbols] =
    useState(40)

  const [runningEvalCaseIds, setRunningEvalCaseIds] =
    useState<Set<string>>(
      () => new Set(),
    )
  const [evalCaseRunErrors, setEvalCaseRunErrors] =
    useState<Record<string, unknown>>({})

  const [evalBatchName, setEvalBatchName] =
    useState("")
  const [evalBatchNote, setEvalBatchNote] =
    useState("")

  const [presetName, setPresetName] =
    useState("")
  const [presetNote, setPresetNote] =
    useState("")

  const [evalRunKeyword, setEvalRunKeyword] =
    useState("")
  const [evalFailedOnly, setEvalFailedOnly] =
    useState(false)
  const [evalFailureType, setEvalFailureType] =
    useState<EvaluationFailureFilter>("all")

  const [selectedCompareBatchId, setSelectedCompareBatchId] =
    useState<string | null>(null)
  const [compareHistoryOpen, setCompareHistoryOpen] =
    useState(false)
  const [evalRunsOpen, setEvalRunsOpen] =
    useState(false)
  const [agentParamTuningOpen, setAgentParamTuningOpen] =
    useState(false)

  const [failureCaseTypeFilter, setFailureCaseTypeFilter] =
    useState("")
  const [failureBatchIdFilter, setFailureBatchIdFilter] =
    useState("")

  const [baselineCompareBatchId, setBaselineCompareBatchId] =
    useState("")
  const [optimizedCompareBatchId, setOptimizedCompareBatchId] =
    useState("")
  const [experimentReportMarkdown, setExperimentReportMarkdown] =
    useState("")

  const normalizedRetrievalSettings = useMemo(
    () => normalizeRetrievalSettings(
      retrievalSettings,
    ),
    [retrievalSettings],
  )

  const ragEvalCasesQuery = useQuery(
    ragEvalCasesQueryOptions(
      knowledgeBaseId,
    ),
  )

  const ragEvalRunsQuery = useQuery({
    ...ragEvalRunsQueryOptions({
      knowledgeBaseId,
      keyword: evalRunKeyword,
      failedOnly: evalFailedOnly,
      failureFilter: evalFailureType,
    }),
    enabled: evalRunsOpen,
  })

  const ragEvalSummaryQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.summary(
        knowledgeBaseId,
      ),
    queryFn: () =>
      DocumentsService.readRagEvalSummary({
        knowledgeBaseId,
        limit: 200,
      }),
  })

  const ragEvalFailureAnalysisQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.failureAnalysis(
        knowledgeBaseId,
      ),
    queryFn: () =>
      DocumentsService.readRagEvalFailureAnalysis({
        knowledgeBaseId,
        limit: 200,
        recentLimit: 10,
      }),
  })

  const ragEvalParamGroupsQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.paramGroups(
        knowledgeBaseId,
      ),
    queryFn: () =>
      DocumentsService.readRagEvalParamGroups({
        knowledgeBaseId,
        limit: 500,
      }),
  })

  const ragRetrievalPresetsQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.presets(
        knowledgeBaseId,
      ),
    queryFn: () =>
      DocumentsService.readRagRetrievalPresets({
        knowledgeBaseId,
        skip: 0,
        limit: 50,
      }),
  })

  const ragEvalBatchesQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.batches(
        knowledgeBaseId,
      ),
    queryFn: () =>
      DocumentsService.readRagEvalBatches({
        knowledgeBaseId,
        skip: 0,
        limit: 50,
      }),
  })

  const ragAgentCompareBatchesQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.compareBatches(
        knowledgeBaseId,
      ),
    queryFn: () =>
      DocumentsService.readRagAgentCompareBatches({
        knowledgeBaseId,
        skip: 0,
        limit: 50,
      }),
  })

  const ragAgentCompareBatchDetailQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.compareBatch(
        selectedCompareBatchId,
      ),
    queryFn: () => {
      if (!selectedCompareBatchId) {
        throw new Error(
          "Compare batch id is required",
        )
      }

      return DocumentsService.readRagAgentCompareBatch({
        batchId: selectedCompareBatchId,
      })
    },
    enabled:
      compareHistoryOpen
      && Boolean(selectedCompareBatchId),
  })

  const agentSettingsQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.agentSettings(
        knowledgeBaseId,
      ),
    queryFn: () =>
      DocumentsService.readKnowledgeBaseAgentSettings({
        knowledgeBaseId,
      }),
  })

  const codeEvalTypeCompareSummaryQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.codeTypeSummary(
        knowledgeBaseId,
      ),
    queryFn: () =>
      DocumentsService.getCodeEvalTypeCompareSummary({
        knowledgeBaseId,
      }),
  })

  const ragAgentCompareFailureAnalysisQuery = useQuery({
    queryKey:
      knowledgeBaseEvaluationKeys.compareFailureAnalysis({
        knowledgeBaseId,
        batchId: failureBatchIdFilter,
        caseType: failureCaseTypeFilter,
      }),
    queryFn: () =>
      DocumentsService.readRagAgentCompareFailureAnalysis({
        knowledgeBaseId,
        batchId:
          failureBatchIdFilter
          || undefined,
        caseType:
          failureCaseTypeFilter
          || undefined,
        limit: 50,
      }),
  })

  useEffect(() => {
    const settings =
      agentSettingsQuery.data

    if (!settings) {
      return
    }

    setAppliedAgentConfig({
      topK: settings.top_k,
      maxSteps: settings.max_steps,
      semanticWeight:
        settings.semantic_weight,
      keywordWeight:
        settings.keyword_weight,
    })
  }, [agentSettingsQuery.data])

  const compareBatchRows =
    ragAgentCompareBatchesQuery.data?.data
    ?? []

  const baselineCompareBatch =
    compareBatchRows.find(
      (batch) =>
        batch.id
        === baselineCompareBatchId,
    )

  const optimizedCompareBatch =
    compareBatchRows.find(
      (batch) =>
        batch.id
        === optimizedCompareBatchId,
    )

  const optimizationCompareRows =
    buildOptimizationCompareRows(
      baselineCompareBatch,
      optimizedCompareBatch,
    )

  const codeAgentOptimizationAdvice =
    buildCodeAgentOptimizationAdvice({
      typeSummaryData:
        codeEvalTypeCompareSummaryQuery.data,
      failureAnalysisData:
        ragAgentCompareFailureAnalysisQuery.data,
    })

  const createRagEvalCaseMutation = useMutation({
    mutationFn: () =>
      DocumentsService.createRagEvalCase({
        knowledgeBaseId,
        requestBody: {
          question: evalQuestion.trim(),
          expected_keywords:
            evalKeywords
              .split(/[,，\n]/)
              .map((item) => item.trim())
              .filter(Boolean),
          expected_source_filename:
            evalSourceFilename.trim()
            || null,
          note:
            evalNote.trim()
            || null,
        },
      }),
    onSuccess: async () => {
      setEvalQuestion("")
      setEvalKeywords("")
      setEvalSourceFilename("")
      setEvalNote("")
      await invalidateCases()
    },
  })

  const runRagEvalCaseMutation = useMutation({
    mutationFn: (evalCaseId: string) =>
      DocumentsService.runRagEvalCase({
        evalCaseId,
        requestBody: {
          top_k:
            normalizedRetrievalSettings.topK,
          semantic_weight:
            normalizedRetrievalSettings.semanticWeight,
          keyword_weight:
            normalizedRetrievalSettings.keywordWeight,
        },
      }),
    onSuccess: async () => {
      await invalidateEvaluationResults()
    },
  })

  const deleteRagEvalCaseMutation = useMutation({
    mutationFn: (evalCaseId: string) =>
      DocumentsService.deleteRagEvalCase({
        evalCaseId,
      }),
    onSuccess: async () => {
      await Promise.all([
        invalidateCases(),
        invalidateEvaluationResults(),
      ])
    },
  })

  const runAllRagEvalCasesMutation = useMutation({
    mutationFn: () =>
      DocumentsService.runAllRagEvalCases({
        knowledgeBaseId,
        requestBody: {
          top_k:
            normalizedRetrievalSettings.topK,
          limit: 100,
          semantic_weight:
            normalizedRetrievalSettings.semanticWeight,
          keyword_weight:
            normalizedRetrievalSettings.keywordWeight,
          batch_name:
            evalBatchName.trim()
            || null,
          batch_note:
            evalBatchNote.trim()
            || null,
        },
      }),
    onSuccess: async () => {
      setEvalBatchName("")
      setEvalBatchNote("")
      await invalidateEvaluationResults()
    },
  })

  const seedCodeEvalCasesMutation = useMutation({
    mutationFn: () =>
      DocumentsService.seedCodeEvalCases({
        knowledgeBaseId,
        maxFiles: Math.min(
          Math.max(
            Number(codeEvalMaxFiles) || 1,
            1,
          ),
          200,
        ),
        maxSymbols: Math.min(
          Math.max(
            Number(codeEvalMaxSymbols) || 1,
            1,
          ),
          500,
        ),
      }),
    onSuccess: async () => {
      await Promise.all([
        invalidateCases(),
        invalidateEvaluationResults(),
      ])
    },
  })

  const createRagRetrievalPresetMutation = useMutation({
    mutationFn: () =>
      DocumentsService.createRagRetrievalPreset({
        knowledgeBaseId,
        requestBody: {
          name: presetName.trim(),
          top_k:
            normalizedRetrievalSettings.topK,
          semantic_weight:
            normalizedRetrievalSettings.semanticWeight,
          keyword_weight:
            normalizedRetrievalSettings.keywordWeight,
          note:
            presetNote.trim()
            || null,
        },
      }),
    onSuccess: async () => {
      setPresetName("")
      setPresetNote("")
      await queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.presets(
            knowledgeBaseId,
          ),
      })
    },
  })

  const deleteRagRetrievalPresetMutation = useMutation({
    mutationFn: (presetId: string) =>
      DocumentsService.deleteRagRetrievalPreset({
        presetId,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.presets(
            knowledgeBaseId,
          ),
      })
    },
  })

  const deleteRagEvalBatchMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.deleteRagEvalBatch({
        batchId,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey:
            knowledgeBaseEvaluationKeys.batches(
              knowledgeBaseId,
            ),
        }),
        invalidateEvaluationResults(),
      ])
    },
  })

  const runRagAgentCompareEvalMutation = useMutation({
    mutationFn: () =>
      DocumentsService.runRagAgentCompareEval({
        knowledgeBaseId,
        requestBody: {
          name:
            `RAG vs Agent Compare ${new Date().toLocaleString()}`,
          top_k: appliedAgentConfig.topK,
          max_steps:
            appliedAgentConfig.maxSteps,
          limit: 10,
          semantic_weight:
            appliedAgentConfig.semanticWeight,
          keyword_weight:
            appliedAgentConfig.keywordWeight,
        },
      }),
    onSuccess: async (data) => {
      const compareBatchId =
        data.compare_batch_id

      if (compareBatchId) {
        setSelectedCompareBatchId(
          compareBatchId,
        )
        setFailureBatchIdFilter(
          compareBatchId,
        )
        setOptimizedCompareBatchId(
          compareBatchId,
        )
      }

      await invalidateCompareResults()
    },
  })

  const runAgentParamTuningMutation = useMutation({
    mutationFn: async () => {
      const results = []

      for (
        const preset
        of AGENT_PARAM_PRESETS
      ) {
        const result =
          await DocumentsService.runRagAgentCompareEval({
            knowledgeBaseId,
            requestBody: {
              name:
                `参数优化 - ${preset.name} - ${new Date().toLocaleString()}`,
              top_k: preset.topK,
              max_steps: preset.maxSteps,
              limit: preset.limit,
              semantic_weight:
                preset.semanticWeight,
              keyword_weight:
                preset.keywordWeight,
            },
          })

        results.push({
          preset,
          result,
        })
      }

      return results
    },
    onSuccess: async () => {
      await invalidateCompareResults()
    },
  })

  const agentParamRecommendation =
    runAgentParamTuningMutation.data
      ? buildAgentParamRecommendation(
        runAgentParamTuningMutation.data,
      )
      : null

  const deleteRagAgentCompareBatchMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.deleteRagAgentCompareBatch({
        batchId,
      }),
    onSuccess: async (_, batchId) => {
      if (
        selectedCompareBatchId
        === batchId
      ) {
        setSelectedCompareBatchId(null)
      }

      if (
        baselineCompareBatchId
        === batchId
      ) {
        setBaselineCompareBatchId("")
      }

      if (
        optimizedCompareBatchId
        === batchId
      ) {
        setOptimizedCompareBatchId("")
      }

      await invalidateCompareResults()
    },
  })

  const updateAgentSettingsMutation = useMutation({
    mutationFn: ({
      config,
    }: {
      config: AppliedAgentConfig
      name?: string
    }) =>
      DocumentsService.updateKnowledgeBaseAgentSettings({
        knowledgeBaseId,
        requestBody: {
          top_k: config.topK,
          max_steps: config.maxSteps,
          semantic_weight:
            config.semanticWeight,
          keyword_weight:
            config.keywordWeight,
        },
      }),
    onSuccess: async (data) => {
      setAppliedAgentConfig({
        topK: data.top_k,
        maxSteps: data.max_steps,
        semanticWeight:
          data.semantic_weight,
        keywordWeight:
          data.keyword_weight,
      })

      await queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.agentSettings(
            knowledgeBaseId,
          ),
      })
    },
  })

  const exportRagAgentCompareReportMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.readRagAgentCompareBatchReport({
        batchId,
      }),
    onSuccess: (data) => {
      downloadTextFile({
        filename: data.filename,
        content: data.content,
      })
    },
  })

  const exportRagAgentCompareDocxReportMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.readRagAgentCompareBatchDocxReport({
        batchId,
      }),
    onSuccess: (data) => {
      downloadBase64File({
        filename: data.filename,
        mimeType: data.mime_type,
        contentBase64:
          data.content_base64,
      })
    },
  })

  const exportRagAgentComparePdfReportMutation = useMutation({
    mutationFn: (batchId: string) =>
      DocumentsService.readRagAgentCompareBatchPdfReport({
        batchId,
      }),
    onSuccess: (data) => {
      downloadBase64File({
        filename: data.filename,
        mimeType: data.mime_type,
        contentBase64:
          data.content_base64,
      })
    },
  })

  const exportBackendCodeAgentReportMutation = useMutation({
    mutationFn: () => {
      if (
        !baselineCompareBatchId
        || !optimizedCompareBatchId
      ) {
        throw new Error(
          "请选择优化前后批次",
        )
      }

      return DocumentsService.readCodeAgentExperimentReport({
        knowledgeBaseId,
        baselineBatchId:
          baselineCompareBatchId,
        optimizedBatchId:
          optimizedCompareBatchId,
        failureLimit: 8,
      })
    },
    onSuccess: (data) => {
      downloadTextFile({
        filename: data.filename,
        content: data.content,
      })
    },
  })

  async function invalidateCases() {
    await queryClient.invalidateQueries({
      queryKey:
        knowledgeBaseEvaluationKeys.cases(
          knowledgeBaseId,
        ),
    })
  }

  async function invalidateEvaluationResults() {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.summary(
            knowledgeBaseId,
          ),
      }),
      queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.failureAnalysis(
            knowledgeBaseId,
          ),
      }),
      queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.paramGroups(
            knowledgeBaseId,
          ),
      }),
      queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.batches(
            knowledgeBaseId,
          ),
      }),
      queryClient.invalidateQueries({
        queryKey: [
          ...knowledgeBaseEvaluationKeys.root(
            knowledgeBaseId,
          ),
          "runs",
        ],
      }),
    ])
  }

  async function invalidateCompareResults() {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.compareBatches(
            knowledgeBaseId,
          ),
      }),
      queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.codeTypeSummary(
            knowledgeBaseId,
          ),
      }),
      queryClient.invalidateQueries({
        queryKey: [
          ...knowledgeBaseEvaluationKeys.root(
            knowledgeBaseId,
          ),
          "compare-failure-analysis",
        ],
      }),
    ])
  }

  async function handleRunRagEvalCase(
    evalCaseId: string,
  ) {
    setRunningEvalCaseIds((previous) => {
      const next = new Set(previous)
      next.add(evalCaseId)
      return next
    })

    setEvalCaseRunErrors((previous) => {
      const next = { ...previous }
      delete next[evalCaseId]
      return next
    })

    try {
      await runRagEvalCaseMutation.mutateAsync(
        evalCaseId,
      )
    } catch (error) {
      setEvalCaseRunErrors((previous) => ({
        ...previous,
        [evalCaseId]: error,
      }))
    } finally {
      setRunningEvalCaseIds((previous) => {
        const next = new Set(previous)
        next.delete(evalCaseId)
        return next
      })
    }
  }

  function handleCreateRagEvalCase() {
    if (!evalQuestion.trim()) {
      window.alert("请输入评测问题")
      return
    }

    createRagEvalCaseMutation.mutate()
  }

  function handleRunAllRagEvalCases() {
    if (
      !window.confirm(
        "确定要运行当前知识库下的全部评测样例吗？这可能需要等待一段时间。",
      )
    ) {
      return
    }

    runAllRagEvalCasesMutation.mutate()
  }

  function handleDeleteRagEvalCase(
    evalCaseId: string,
  ) {
    if (
      !window.confirm(
        "确定要删除这条评测样例吗？",
      )
    ) {
      return
    }

    deleteRagEvalCaseMutation.mutate(
      evalCaseId,
    )
  }

  function handleDeleteRagEvalBatch(
    batchId: string,
  ) {
    if (
      !window.confirm(
        "确定要删除这条实验批次记录吗？对应评测结果不会删除，只会解除和该批次的关联。",
      )
    ) {
      return
    }

    deleteRagEvalBatchMutation.mutate(
      batchId,
    )
  }

  function handleCreateRagRetrievalPreset() {
    if (!presetName.trim()) {
      window.alert(
        "请输入参数预设名称",
      )
      return
    }

    createRagRetrievalPresetMutation.mutate()
  }

  function handleApplyRagRetrievalPreset(
    preset: RagRetrievalPresetPublic,
  ) {
    setRetrievalSettings({
      topK: preset.top_k,
      semanticWeight:
        preset.semantic_weight,
      keywordWeight:
        preset.keyword_weight,
    })
  }

  function handleDeleteRagRetrievalPreset(
    presetId: string,
  ) {
    if (
      !window.confirm(
        "确定要删除这个参数预设吗？",
      )
    ) {
      return
    }

    deleteRagRetrievalPresetMutation.mutate(
      presetId,
    )
  }

  function handleApplyRecommendedAgentConfig() {
    if (!agentParamRecommendation) {
      window.alert(
        "暂无可应用的推荐配置，请先运行 Agent 参数优化实验",
      )
      return
    }

    const bestPreset =
      agentParamRecommendation.best.preset

    const nextTuningConfig:
      AgentParamConfig = {
        topK: bestPreset.topK,
        maxSteps: bestPreset.maxSteps,
        limit: bestPreset.limit,
        semanticWeight:
          bestPreset.semanticWeight,
        keywordWeight:
          bestPreset.keywordWeight,
      }

    const nextAppliedConfig:
      AppliedAgentConfig = {
        topK: bestPreset.topK,
        maxSteps: bestPreset.maxSteps,
        semanticWeight:
          bestPreset.semanticWeight,
        keywordWeight:
          bestPreset.keywordWeight,
      }

    setAgentParamConfig(
      nextTuningConfig,
    )

    updateAgentSettingsMutation.mutate({
      name: bestPreset.name,
      config: nextAppliedConfig,
    })
  }

  function handleResetAgentConfig() {
    updateAgentSettingsMutation.mutate({
      name: "默认配置",
      config: DEFAULT_AGENT_CONFIG,
    })
  }

  function handleGenerateExperimentReport() {
    if (
      !baselineCompareBatch
      || !optimizedCompareBatch
    ) {
      window.alert(
        "请先选择优化前批次和优化后批次",
      )
      return
    }

    const markdown =
      buildCodeAgentExperimentReportMarkdown({
        knowledgeBase,
        baselineCompareBatch,
        optimizedCompareBatch,
        optimizationCompareRows,
        typeSummaryData:
          codeEvalTypeCompareSummaryQuery.data,
        failureAnalysisData:
          ragAgentCompareFailureAnalysisQuery.data,
        adviceList:
          codeAgentOptimizationAdvice,
      })

    setExperimentReportMarkdown(
      markdown,
    )
  }

  function handleDownloadExperimentReport() {
    if (!experimentReportMarkdown.trim()) {
      window.alert(
        "请先生成实验报告预览",
      )
      return
    }

    const safeKnowledgeBaseName =
      String(
        knowledgeBase.name
        || "knowledge-base",
      )
        .replace(/[\\/:*?"<>|]/g, "_")
        .slice(0, 50)

    downloadTextFile({
      filename:
        `code-rag-agent-report-${safeKnowledgeBaseName}-${new Date().toISOString().slice(0, 10)}.md`,
      content:
        experimentReportMarkdown,
    })
  }

  function selectCompareBatch(
    batchId: string,
  ) {
    setSelectedCompareBatchId(batchId)
    setFailureBatchIdFilter(batchId)
  }

  function getCompareBatch(
    batchId: string,
  ): RagAgentCompareBatchPublic | undefined {
    return compareBatchRows.find(
      (batch) => batch.id === batchId,
    )
  }

  return {
    knowledgeBaseId,
    knowledgeBase,

    retrievalSettings,
    setRetrievalSettings,
    normalizedRetrievalSettings,

    agentParamConfig,
    setAgentParamConfig,
    appliedAgentConfig,

    evalQuestion,
    setEvalQuestion,
    evalKeywords,
    setEvalKeywords,
    evalSourceFilename,
    setEvalSourceFilename,
    evalNote,
    setEvalNote,

    codeEvalMaxFiles,
    setCodeEvalMaxFiles,
    codeEvalMaxSymbols,
    setCodeEvalMaxSymbols,

    runningEvalCaseIds,
    evalCaseRunErrors,

    evalBatchName,
    setEvalBatchName,
    evalBatchNote,
    setEvalBatchNote,

    presetName,
    setPresetName,
    presetNote,
    setPresetNote,

    evalRunKeyword,
    setEvalRunKeyword,
    evalFailedOnly,
    setEvalFailedOnly,
    evalFailureType,
    setEvalFailureType,

    selectedCompareBatchId,
    setSelectedCompareBatchId,
    compareHistoryOpen,
    setCompareHistoryOpen,
    evalRunsOpen,
    setEvalRunsOpen,
    agentParamTuningOpen,
    setAgentParamTuningOpen,

    failureCaseTypeFilter,
    setFailureCaseTypeFilter,
    failureBatchIdFilter,
    setFailureBatchIdFilter,

    baselineCompareBatchId,
    setBaselineCompareBatchId,
    optimizedCompareBatchId,
    setOptimizedCompareBatchId,
    experimentReportMarkdown,

    compareBatchRows,
    baselineCompareBatch,
    optimizedCompareBatch,
    optimizationCompareRows,
    codeAgentOptimizationAdvice,
    agentParamRecommendation,

    ragEvalCasesQuery,
    ragEvalRunsQuery,
    ragEvalSummaryQuery,
    ragEvalFailureAnalysisQuery,
    ragEvalParamGroupsQuery,
    ragRetrievalPresetsQuery,
    ragEvalBatchesQuery,
    ragAgentCompareBatchesQuery,
    ragAgentCompareBatchDetailQuery,
    agentSettingsQuery,
    codeEvalTypeCompareSummaryQuery,
    ragAgentCompareFailureAnalysisQuery,

    createRagEvalCaseMutation,
    runRagEvalCaseMutation,
    deleteRagEvalCaseMutation,
    runAllRagEvalCasesMutation,
    seedCodeEvalCasesMutation,
    createRagRetrievalPresetMutation,
    deleteRagRetrievalPresetMutation,
    deleteRagEvalBatchMutation,
    runRagAgentCompareEvalMutation,
    runAgentParamTuningMutation,
    deleteRagAgentCompareBatchMutation,
    updateAgentSettingsMutation,
    exportRagAgentCompareReportMutation,
    exportRagAgentCompareDocxReportMutation,
    exportRagAgentComparePdfReportMutation,
    exportBackendCodeAgentReportMutation,

    handleCreateRagEvalCase,
    handleRunRagEvalCase,
    handleRunAllRagEvalCases,
    handleDeleteRagEvalCase,
    handleDeleteRagEvalBatch,
    handleCreateRagRetrievalPreset,
    handleApplyRagRetrievalPreset,
    handleDeleteRagRetrievalPreset,
    handleApplyRecommendedAgentConfig,
    handleResetAgentConfig,
    handleGenerateExperimentReport,
    handleDownloadExperimentReport,
    selectCompareBatch,
    getCompareBatch,

    refreshSummary: () =>
      queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.summary(
            knowledgeBaseId,
          ),
      }),
    refreshCodeTypeSummary: () =>
      queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.codeTypeSummary(
            knowledgeBaseId,
          ),
      }),
    refreshCompareFailureAnalysis: () =>
      queryClient.invalidateQueries({
        queryKey:
          knowledgeBaseEvaluationKeys.compareFailureAnalysis({
            knowledgeBaseId,
            batchId:
              failureBatchIdFilter,
            caseType:
              failureCaseTypeFilter,
          }),
      }),
  }
}

export type KnowledgeBaseEvaluationController =
  ReturnType<
    typeof useKnowledgeBaseEvaluation
  >
