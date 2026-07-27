import type {
  RepositoryChatPrefill,
} from "@/components/RepositoryAnalysis/repositoryChatHandoff"

import {
  AgentChatSection,
} from "./AgentChatSection"
import {
  AgentHistorySection,
} from "./AgentHistorySection"
import {
  KeywordSearchSection,
} from "./KeywordSearchSection"
import {
  RagAgentSingleCompareSection,
} from "./RagAgentSingleCompareSection"
import {
  RagChatSection,
} from "./RagChatSection"
import {
  RagHistorySection,
} from "./RagHistorySection"
import {
  RepositoryScopedChatBanner,
} from "./RepositoryScopedChatBanner"
import {
  SemanticSearchSection,
} from "./SemanticSearchSection"
import type {
  RetrievalSettings,
} from "./knowledgeBaseChatTypes"
import type {
  AppliedAgentConfig,
} from "./knowledgeBaseDetailTypes"
import {
  useKnowledgeBaseChat,
} from "./useKnowledgeBaseChat"

type KnowledgeBaseChatTabProps = {
  knowledgeBaseId: string

  repositoryChatPrefill?:
    RepositoryChatPrefill | null

  retrievalSettings?:
    Partial<RetrievalSettings>

  agentConfig?:
    Partial<AppliedAgentConfig>
}

export function KnowledgeBaseChatTab({
  knowledgeBaseId,
  repositoryChatPrefill = null,
  retrievalSettings,
  agentConfig,
}: KnowledgeBaseChatTabProps) {
  const chat = useKnowledgeBaseChat({
    knowledgeBaseId,
    repositoryChatPrefill,
    retrievalSettings,
    agentConfig,
  })

  /*
   * 不要只判断 repositoryChatPrefill 是否存在。
   *
   * 真正表示仓库范围的是：
   * repositoryAnalysisTaskId
   */
  const isRepositoryScoped =
    Boolean(
      repositoryChatPrefill
        ?.repositoryAnalysisTaskId,
    )

  return (
    <div className="space-y-6">
      {isRepositoryScoped
      && repositoryChatPrefill ? (
        <RepositoryScopedChatBanner
          prefill={
            repositoryChatPrefill
          }
        />
      ) : null}

      {isRepositoryScoped ? (
        <section className="rounded-xl border border-violet-200 bg-violet-50 px-4 py-3 text-sm leading-6 text-violet-800">
          当前处于仓库范围模式。
          普通 RAG 和 Code Agent
          都只会读取当前仓库分析任务
          导入的固定 Commit 代码，
          不会混入当前知识库中的其他
          仓库或普通文档。
          关键词检索、独立语义检索和
          历史记录暂时隐藏。
        </section>
      ) : (
        <>
          <KeywordSearchSection
            query={
              chat.searchQuery
            }
            onQueryChange={
              chat.setSearchQuery
            }
            onSearch={
              chat.handleSearch
            }
            data={
              chat
                .searchKnowledgeBaseMutation
                .data
            }
            isPending={
              chat
                .searchKnowledgeBaseMutation
                .isPending
            }
            isError={
              chat
                .searchKnowledgeBaseMutation
                .isError
            }
            error={
              chat
                .searchKnowledgeBaseMutation
                .error
            }
          />

          <SemanticSearchSection
            query={
              chat.semanticQuery
            }
            onQueryChange={
              chat.setSemanticQuery
            }
            onSearch={
              chat.handleSemanticSearch
            }
            onBackfillEmbeddings={() => {
              chat
                .backfillEmbeddingsMutation
                .mutate()
            }}
            data={
              chat
                .semanticSearchKnowledgeBaseMutation
                .data
            }
            isPending={
              chat
                .semanticSearchKnowledgeBaseMutation
                .isPending
            }
            isError={
              chat
                .semanticSearchKnowledgeBaseMutation
                .isError
            }
            error={
              chat
                .semanticSearchKnowledgeBaseMutation
                .error
            }
            backfillData={
              chat
                .backfillEmbeddingsMutation
                .data
            }
            isBackfillPending={
              chat
                .backfillEmbeddingsMutation
                .isPending
            }
            isBackfillError={
              chat
                .backfillEmbeddingsMutation
                .isError
            }
            backfillError={
              chat
                .backfillEmbeddingsMutation
                .error
            }
          />
        </>
      )}

      {/* 普通 RAG 在两种模式下都显示 */}
      <RagChatSection
        question={
          chat.chatQuestion
        }
        onQuestionChange={
          chat.setChatQuestion
        }
        onSubmit={
          chat.handleChat
        }
        data={
          chat
            .chatKnowledgeBaseMutation
            .data
        }
        isPending={
          chat
            .chatKnowledgeBaseMutation
            .isPending
        }
        isError={
          chat
            .chatKnowledgeBaseMutation
            .isError
        }
        error={
          chat
            .chatKnowledgeBaseMutation
            .error
        }
        repositoryScoped={
          isRepositoryScoped
        }
      />

      <RagHistorySection
        isOpen={
          chat.ragHistoryOpen
        }
        onToggle={() => {
          chat.setRagHistoryOpen(
            (current) =>
              !current,
          )
        }}
        keyword={
          chat.ragRunKeyword
        }
        onKeywordChange={
          chat.setRagRunKeyword
        }
        onRefresh={() => {
          void chat.refreshRagRuns()
        }}
        data={
          chat.ragRunsQuery.data
        }
        isLoading={
          chat.ragRunsQuery.isLoading
        }
        isError={
          chat.ragRunsQuery.isError
          }
        error={
          chat.ragRunsQuery.error
        }
        onDelete={
          chat.handleDeleteRagRun
        }
        isDeletePending={
          chat
            .deleteRagRunMutation
            .isPending
        }
        isDeleteError={
          chat
            .deleteRagRunMutation
            .isError
        }
        deleteError={
          chat
            .deleteRagRunMutation
            .error
        }
        repositoryScoped={
          isRepositoryScoped
        }
      />

      <AgentChatSection
        question={
          chat.agentQuestion
        }
        onQuestionChange={
          chat.setAgentQuestion
        }
        onSubmit={
          chat.handleAgentChat
        }
        data={
          chat.agentChatMutation.data
        }
        isPending={
          chat
            .agentChatMutation
            .isPending
        }
        isError={
          chat
            .agentChatMutation
            .isError
        }
        error={
          chat
            .agentChatMutation
            .error
        }
        repositoryScoped={
          isRepositoryScoped
        }
        repositoryFullName={
          repositoryChatPrefill
            ?.repositoryFullName
        }
        resolvedCommitSha={
          repositoryChatPrefill
            ?.resolvedCommitSha
        }
      />

      <AgentHistorySection
        isOpen={
          chat.agentHistoryOpen
        }
        onToggle={() => {
          chat.setAgentHistoryOpen(
            (current) =>
              !current,
          )
        }}
        keyword={
          chat.agentRunKeyword
        }
        onKeywordChange={
          chat.setAgentRunKeyword
        }
        onRefresh={() => {
          void chat.refreshAgentRuns()
        }}
        data={
          chat.agentRunsQuery.data
        }
        isLoading={
          chat
            .agentRunsQuery
            .isLoading
        }
        isError={
          chat
            .agentRunsQuery
            .isError
        }
        error={
          chat
            .agentRunsQuery
            .error
        }
        expandedRunIds={
          chat.expandedAgentRunIds
        }
        onToggleRun={
          chat.handleToggleAgentRun
        }
        onDelete={
          chat.handleDeleteAgentRun
        }
        isDeletePending={
          chat
            .deleteAgentRunMutation
            .isPending
        }
        isDeleteError={
          chat
            .deleteAgentRunMutation
            .isError
        }
        deleteError={
          chat
            .deleteAgentRunMutation
            .error
        }
        repositoryScoped={
          isRepositoryScoped
        }
      />

      {/* 单题对比在仓库模式下重新开放 */}
      <RagAgentSingleCompareSection
        question={
          chat.compareQuestion
        }
        onQuestionChange={
          chat.setCompareQuestion
        }
        onSubmit={
          chat.handleCompareRagAgent
        }
        data={
          chat
            .compareRagAgentMutation
            .data
        }
        isPending={
          chat
            .compareRagAgentMutation
            .isPending
        }
        isError={
          chat
            .compareRagAgentMutation
            .isError
        }
        error={
          chat
            .compareRagAgentMutation
            .error
        }
        repositoryScoped={
          isRepositoryScoped
        }
        repositoryFullName={
          repositoryChatPrefill
            ?.repositoryFullName
        }
        resolvedCommitSha={
          repositoryChatPrefill
            ?.resolvedCommitSha
        }
      />
    </div>
  )
}