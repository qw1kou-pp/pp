import {
  CodeReviewWorkbench,
} from "@/components/CodeReviewWorkbench"
import {
  KnowledgeBaseChatTab,
} from "@/components/KnowledgeBaseDetail/KnowledgeBaseChatTab"
import {
  KnowledgeBaseDetailPageState,
} from "@/components/KnowledgeBaseDetail/KnowledgeBaseDetailPageState"
import {
  KnowledgeBaseEvaluationTab,
} from "@/components/KnowledgeBaseDetail/KnowledgeBaseEvaluationTab"
import {
  KnowledgeBaseOverviewTab,
} from "@/components/KnowledgeBaseDetail/KnowledgeBaseOverviewTab"
import {
  KnowledgeBaseWorkspaceHeader,
} from "@/components/KnowledgeBaseDetail/KnowledgeBaseWorkspaceHeader"
import {
  KnowledgeBaseWorkspaceTabs,
} from "@/components/KnowledgeBaseDetail/KnowledgeBaseWorkspaceTabs"
import {
  knowledgeBaseDetailQueryOptions,
} from "@/components/KnowledgeBaseDetail/knowledgeBaseDetailQueries"
import {
  parseKnowledgeBaseDetailSearch,
  type KnowledgeBaseDetailSearch,
  type WorkspaceTab,
} from "@/components/KnowledgeBaseDetail/knowledgeBaseDetailTypes"
import {
  knowledgeBaseDocumentsQueryOptions,
} from "@/components/KnowledgeBaseDetail/knowledgeBaseOverviewQueries"
import {
  useKnowledgeBaseDetailHandoff,
} from "@/components/KnowledgeBaseDetail/useKnowledgeBaseDetailHandoff"
import {
  useQuery,
} from "@tanstack/react-query"
import {
  createFileRoute,
} from "@tanstack/react-router"
import {
  useCallback,
} from "react"

export const Route = createFileRoute(
  "/_layout/knowledge-bases/$knowledgeBaseId",
)({
  validateSearch: (
    search: Record<string, unknown>,
  ) =>
    parseKnowledgeBaseDetailSearch(
      search,
    ),

  component:
    KnowledgeBaseDetailPage,
})

function KnowledgeBaseDetailPage() {
  const {
    knowledgeBaseId,
  } = Route.useParams()

  const search =
    Route.useSearch()

  const navigate =
    Route.useNavigate()

  const ensureWorkspaceTab =
    useCallback(
      (
        tab: WorkspaceTab,
      ) => {
        void navigate({
          search: (
            previousSearch: KnowledgeBaseDetailSearch,
          ) => ({
            ...previousSearch,
            tab,
          }),

          replace: true,
        })
      },
      [
        navigate,
      ],
    )

  const {
    activeWorkspaceTab,
    repositoryReviewPrefill,
    repositoryChatPrefill,
  } = useKnowledgeBaseDetailHandoff({
    search,
    onEnsureTab:
      ensureWorkspaceTab,
  })

  const knowledgeBaseQuery =
    useQuery(
      knowledgeBaseDetailQueryOptions(
        knowledgeBaseId,
      ),
    )

  // 与 Overview 标签共用同一 Query Key。
  // 上传或删除文档后，Header 的文档总数会一起刷新。
  const documentsQuery =
    useQuery(
      knowledgeBaseDocumentsQueryOptions(
        knowledgeBaseId,
      ),
    )

  const handleWorkspaceTabChange =
    useCallback(
      (
        tab: WorkspaceTab,
      ) => {
        void navigate({
          search: (
            previousSearch: KnowledgeBaseDetailSearch,
          ) => ({
            ...previousSearch,
            tab,
          }),
        })
      },
      [
        navigate,
      ],
    )

  if (
    knowledgeBaseQuery.isPending
    || documentsQuery.isPending
  ) {
    return (
      <KnowledgeBaseDetailPageState
        title="正在加载知识库详情..."
        description="正在读取知识库信息和文档统计。"
      />
    )
  }

  if (
    knowledgeBaseQuery.isError
  ) {
    return (
      <KnowledgeBaseDetailPageState
        title="知识库加载失败"
        description="请确认知识库仍然存在，并检查后端服务和登录状态。"
        tone="error"
      />
    )
  }

  if (
    documentsQuery.isError
  ) {
    return (
      <KnowledgeBaseDetailPageState
        title="文档统计加载失败"
        description="知识库已读取，但文档列表接口暂时不可用。"
        tone="error"
      />
    )
  }

  const knowledgeBase =
    knowledgeBaseQuery.data

  const documents =
    documentsQuery.data

  if (
    !knowledgeBase
    || !documents
  ) {
    return (
      <KnowledgeBaseDetailPageState
        title="暂无知识库数据"
        description="接口没有返回可展示的知识库详情。"
      />
    )
  }

  return (
    <main className="min-h-screen bg-slate-50/70">
      <div className="mx-auto max-w-[1440px] space-y-6 px-4 py-6 md:px-6 lg:px-8">
        <KnowledgeBaseWorkspaceHeader
          knowledgeBase={
            knowledgeBase
          }
          documentCount={
            documents.count
          }
        />

        <KnowledgeBaseWorkspaceTabs
          activeTab={
            activeWorkspaceTab
          }
          onTabChange={
            handleWorkspaceTabChange
          }
        />

        {activeWorkspaceTab
          === "overview" ? (
          <KnowledgeBaseOverviewTab
            knowledgeBaseId={
              knowledgeBaseId
            }
          />
        ) : null}

        {activeWorkspaceTab
          === "review" ? (
          <CodeReviewWorkbench
            knowledgeBaseId={
              knowledgeBaseId
            }
            repositoryPrefill={
              repositoryReviewPrefill
            }
          />
        ) : null}

        {activeWorkspaceTab
          === "chat" ? (
          <KnowledgeBaseChatTab
            knowledgeBaseId={
              knowledgeBaseId
            }
            repositoryChatPrefill={
              repositoryChatPrefill
            }
          />
        ) : null}

        {activeWorkspaceTab
          === "evaluation" ? (
          <KnowledgeBaseEvaluationTab
            knowledgeBaseId={
              knowledgeBaseId
            }
            knowledgeBase={
              knowledgeBase
            }
          />
        ) : null}
      </div>
    </main>
  )
}
