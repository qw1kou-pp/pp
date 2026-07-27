import {
  DocumentsService,
  type RagChatRequest,
} from "@/client"
import type {
  RepositoryChatPrefill,
} from "@/components/RepositoryAnalysis/repositoryChatHandoff"
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"

import type {
  AppliedAgentConfig,
} from "./knowledgeBaseDetailTypes"
import {
  agentSettingsQueryOptions,
  knowledgeBaseChatKeys,
} from "./knowledgeBaseChatQueries"
import {
  DEFAULT_AGENT_CONFIG,
  DEFAULT_RETRIEVAL_SETTINGS,
  normalizeAgentConfig,
  normalizeRetrievalSettings,
  type RetrievalSettings,
} from "./knowledgeBaseChatTypes"

export type UseKnowledgeBaseChatOptions = {
  knowledgeBaseId: string
  repositoryChatPrefill?:
    RepositoryChatPrefill | null
  retrievalSettings?:
    Partial<RetrievalSettings>
  agentConfig?:
    Partial<AppliedAgentConfig>
}

export function useKnowledgeBaseChat({
  knowledgeBaseId,
  repositoryChatPrefill = null,
  retrievalSettings,
  agentConfig,
}: UseKnowledgeBaseChatOptions) {
  const queryClient =
    useQueryClient()

  const [
    searchQuery,
    setSearchQuery,
  ] = useState("")

  const [
    semanticQuery,
    setSemanticQuery,
  ] = useState("")

  const [
    chatQuestion,
    setChatQuestion,
  ] = useState(
    repositoryChatPrefill?.question
    ?? "",
  )

  const [
    ragRunKeyword,
    setRagRunKeyword,
  ] = useState("")

  const [
    agentQuestion,
    setAgentQuestion,
  ] = useState("")

  const [
    agentRunKeyword,
    setAgentRunKeyword,
  ] = useState("")

  const [
    compareQuestion,
    setCompareQuestion,
  ] = useState("")

  const [
    ragHistoryOpen,
    setRagHistoryOpen,
  ] = useState(false)

  const [
    agentHistoryOpen,
    setAgentHistoryOpen,
  ] = useState(false)

  const [
    expandedAgentRunIds,
    setExpandedAgentRunIds,
  ] = useState<string[]>([])

  const appliedRepositoryChatRef =
    useRef<string | null>(null)

  useEffect(() => {
    if (!repositoryChatPrefill) {
      appliedRepositoryChatRef.current =
        null
      return
    }

    const handoffKey = [
      repositoryChatPrefill
        .repositoryAnalysisTaskId,
      repositoryChatPrefill
        .question
        ?? "",
    ].join(":")

    if (
      appliedRepositoryChatRef.current
      === handoffKey
    ) {
      return
    }

    if (
      repositoryChatPrefill.question
    ) {
      setChatQuestion(
        repositoryChatPrefill.question,
      )
    }

    appliedRepositoryChatRef.current =
      handoffKey
  }, [
    repositoryChatPrefill,
  ])

  const normalizedRetrievalSettings =
    useMemo(
      () =>
        normalizeRetrievalSettings(
          retrievalSettings
          ?? DEFAULT_RETRIEVAL_SETTINGS,
        ),
      [
        retrievalSettings,
      ],
    )

  const agentSettingsQuery =
  useQuery({
    ...agentSettingsQueryOptions(
      knowledgeBaseId,
    ),

    enabled:
      !agentConfig,
  })

  const effectiveAgentConfig =
    useMemo(() => {
      if (agentConfig) {
        return normalizeAgentConfig(
          agentConfig,
        )
      }

      if (agentSettingsQuery.data) {
        return normalizeAgentConfig({
          topK:
            agentSettingsQuery.data.top_k,
          maxSteps:
            agentSettingsQuery.data.max_steps,
          semanticWeight:
            agentSettingsQuery.data.semantic_weight,
          keywordWeight:
            agentSettingsQuery.data.keyword_weight,
        })
      }

      return DEFAULT_AGENT_CONFIG
    }, [
      agentConfig,
      agentSettingsQuery.data,
    ])

  const repositoryAnalysisTaskId =
    repositoryChatPrefill
      ?.repositoryAnalysisTaskId

  const isRepositoryScoped =
    Boolean(
      repositoryAnalysisTaskId,
    )

  const ragRunsQuery =
    useQuery({
      queryKey: [
        "rag-runs",
        knowledgeBaseId,
        repositoryAnalysisTaskId
          ?? "knowledge-base",
        ragRunKeyword,
      ],

      queryFn: () =>
        DocumentsService
          .readKnowledgeBaseRagRuns({
            knowledgeBaseId,
            skip: 0,
            limit: 20,

            keyword:
              ragRunKeyword
                .trim()
              || undefined,

            repositoryAnalysisTaskId,
          }),

      enabled:
        ragHistoryOpen,
    })

  const agentRunsQuery =
    useQuery({
      queryKey: [
        "agent-runs",
        knowledgeBaseId,
        repositoryAnalysisTaskId
          ?? "knowledge-base",
        agentRunKeyword,
      ],

      queryFn: () =>
        DocumentsService
          .readAgentRuns({
            knowledgeBaseId,
            skip: 0,
            limit: 20,

            keyword:
              agentRunKeyword
                .trim()
              || undefined,

            repositoryAnalysisTaskId,
          }),

      enabled:
        agentHistoryOpen,
    })

  const searchKnowledgeBaseMutation =
    useMutation({
      mutationFn: (
        query: string,
      ) =>
        DocumentsService.searchKnowledgeBaseChunks({
          knowledgeBaseId,
          requestBody: {
            query,
            limit: 10,
          },
        }),
    })

  const semanticSearchKnowledgeBaseMutation =
    useMutation({
      mutationFn: (
        query: string,
      ) =>
        DocumentsService.semanticSearchKnowledgeBaseChunks({
          knowledgeBaseId,
          requestBody: {
            query,
            top_k:
              normalizedRetrievalSettings.topK,
          },
        }),
    })

//   const repositoryAnalysisTaskId =
//     repositoryChatPrefill
//       ?.repositoryAnalysisTaskId
//
//   const isRepositoryScoped =
//     Boolean(
//       repositoryAnalysisTaskId,
//     )

  const backfillEmbeddingsMutation =
    useMutation({
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

  const chatKnowledgeBaseMutation =
    useMutation({
      mutationFn: (
        question: string,
      ) => {
        const settings =
          normalizedRetrievalSettings

        return (
          DocumentsService
            .chatWithKnowledgeBase({
              knowledgeBaseId,

              requestBody: {
                question,

                top_k:
                  settings.topK,

                semantic_weight:
                  settings
                    .semanticWeight,

                keyword_weight:
                  settings
                    .keywordWeight,

                repository_analysis_task_id:
                  repositoryAnalysisTaskId,
              } as any,
            })
        )
      },

      onSuccess: async () => {
        await invalidateRagRuns()
      },
    })

  const agentChatMutation =
    useMutation({
      mutationFn: (
        question: string,
      ) =>
        DocumentsService
          .agentChatWithKnowledgeBase({
            knowledgeBaseId,

            requestBody: {
              question,

              top_k:
                appliedAgentConfig
                  .topK,

              max_steps:
                appliedAgentConfig
                  .maxSteps,

              semantic_weight:
                appliedAgentConfig
                  .semanticWeight,

              keyword_weight:
                appliedAgentConfig
                  .keywordWeight,

              repository_analysis_task_id:
                repositoryAnalysisTaskId,
            } as any,
          }),

      onSuccess: async () => {
        await invalidateAgentRuns()
      },
    })
  const compareRagAgentMutation =
    useMutation({
      mutationFn: async (
        question: string,
      ) => {
        const [
          ragResult,
          agentResult,
        ] = await Promise.all([
          DocumentsService
            .chatWithKnowledgeBase({
              knowledgeBaseId,

              requestBody: {
                question,

                top_k:
                  appliedAgentConfig
                    .topK,

                semantic_weight:
                  appliedAgentConfig
                    .semanticWeight,

                keyword_weight:
                  appliedAgentConfig
                    .keywordWeight,

                repository_analysis_task_id:
                  repositoryAnalysisTaskId,
              } as any,
            }),

          DocumentsService
            .agentChatWithKnowledgeBase({
              knowledgeBaseId,

              requestBody: {
                question,

                top_k:
                  appliedAgentConfig
                    .topK,

                max_steps:
                  appliedAgentConfig
                    .maxSteps,

                semantic_weight:
                  appliedAgentConfig
                    .semanticWeight,

                keyword_weight:
                  appliedAgentConfig
                    .keywordWeight,

                repository_analysis_task_id:
                  repositoryAnalysisTaskId,
              } as any,
            }),
        ])

        return {
          ragResult,
          agentResult,
        }
      },

      onSuccess: async () => {
        await Promise.all([
          invalidateRagRuns(),
          invalidateAgentRuns(),
        ])
      },
    })

  const deleteRagRunMutation =
    useMutation({
      mutationFn: (
        ragRunId: string,
      ) =>
        DocumentsService.deleteRagRun({
          ragRunId,
        }),

      onSuccess: async () => {
        await invalidateRagRuns()
      },
    })

  const deleteAgentRunMutation =
    useMutation({
      mutationFn: (
        agentRunId: string,
      ) =>
        DocumentsService.deleteAgentRun({
          agentRunId,
        }),

      onSuccess: async () => {
        await invalidateAgentRuns()
      },
    })

  function invalidateRagRuns() {
    return queryClient
      .invalidateQueries({
        queryKey: [
          ...knowledgeBaseChatKeys.all,
          "rag-runs",
          knowledgeBaseId,

          repositoryAnalysisTaskId
          ?? "knowledge-base",
        ],
      })
  }

  function invalidateAgentRuns() {
    return queryClient
      .invalidateQueries({
        queryKey: [
          ...knowledgeBaseChatKeys.all,
          "agent-runs",
          knowledgeBaseId,

          repositoryAnalysisTaskId
          ?? "knowledge-base",
        ],
      })
  }

  const handleSearch = () => {
    const query =
      searchQuery.trim()

    if (!query) {
      window.alert(
        "请输入要检索的内容",
      )
      return
    }

    searchKnowledgeBaseMutation.mutate(
      query,
    )
  }

  const handleSemanticSearch = () => {
    const query =
      semanticQuery.trim()

    if (!query) {
      window.alert(
        "请输入要语义检索的内容",
      )
      return
    }

    semanticSearchKnowledgeBaseMutation.mutate(
      query,
    )
  }

  const handleChat = () => {
    const question =
      chatQuestion.trim()

    if (!question) {
      window.alert(
        "请输入要提问的内容",
      )
      return
    }

    chatKnowledgeBaseMutation.mutate(
      question,
    )
  }

  const handleAgentChat = () => {
    const question =
      agentQuestion.trim()

    if (!question) {
      window.alert(
        "请输入 Agent 问题",
      )
      return
    }

    agentChatMutation.mutate(
      question,
    )
  }

  const handleCompareRagAgent = () => {
    const question =
      compareQuestion.trim()

    if (!question) {
      window.alert(
        "请输入对比问题",
      )
      return
    }

    compareRagAgentMutation.mutate(
      question,
    )
  }

  const handleDeleteRagRun = (
    ragRunId: string,
  ) => {
    const confirmed =
      window.confirm(
        "确定要删除这条 RAG 问答历史吗？",
      )

    if (!confirmed) {
      return
    }

    deleteRagRunMutation.mutate(
      ragRunId,
    )
  }

  const handleDeleteAgentRun = (
    agentRunId: string,
  ) => {
    const confirmed =
      window.confirm(
        "确定要删除这条 Agent 历史记录吗？",
      )

    if (!confirmed) {
      return
    }

    deleteAgentRunMutation.mutate(
      agentRunId,
    )
  }

  const handleToggleAgentRun = (
    agentRunId: string,
  ) => {
    setExpandedAgentRunIds(
      (currentIds) =>
        currentIds.includes(
          agentRunId,
        )
          ? currentIds.filter(
            (id) =>
              id !== agentRunId,
          )
          : [
            ...currentIds,
            agentRunId,
          ],
    )
  }

  return {
    searchQuery,
    setSearchQuery,
    semanticQuery,
    setSemanticQuery,
    chatQuestion,
    setChatQuestion,
    ragRunKeyword,
    setRagRunKeyword,
    agentQuestion,
    setAgentQuestion,
    agentRunKeyword,
    setAgentRunKeyword,
    compareQuestion,
    setCompareQuestion,

    ragHistoryOpen,
    setRagHistoryOpen,
    agentHistoryOpen,
    setAgentHistoryOpen,
    expandedAgentRunIds,

    normalizedRetrievalSettings,
    effectiveAgentConfig,
    agentSettingsQuery,

    ragRunsQuery,
    agentRunsQuery,

    searchKnowledgeBaseMutation,
    semanticSearchKnowledgeBaseMutation,
    backfillEmbeddingsMutation,
    chatKnowledgeBaseMutation,
    agentChatMutation,
    compareRagAgentMutation,
    deleteRagRunMutation,
    deleteAgentRunMutation,

    handleSearch,
    handleSemanticSearch,
    handleChat,
    handleAgentChat,
    handleCompareRagAgent,
    handleDeleteRagRun,
    handleDeleteAgentRun,
    handleToggleAgentRun,

    refreshRagRuns:
      invalidateRagRuns,
    refreshAgentRuns:
      invalidateAgentRuns,

    repositoryAnalysisTaskId,
    isRepositoryScoped,
  }
}
