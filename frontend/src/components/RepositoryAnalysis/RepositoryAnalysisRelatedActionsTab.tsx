import {
  useQuery,
} from "@tanstack/react-query"
import {
  useNavigate,
} from "@tanstack/react-router"
import {
  ArrowRight,
  BookOpen,
  GitPullRequest,
  MessageSquare,
} from "lucide-react"
import {
  useEffect,
  useState,
} from "react"

import {
  KnowledgeBasesService,
  type RepositoryAnalysisTaskPublic,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import {
  repositoryReviewSource,
} from "../repositoryReviewHandoff"
import {
  RepositoryAnalysisKnowledgeBaseCard,
} from "./RepositoryAnalysisKnowledgeBaseCard"
import {
  buildRepositoryChatQuestion,
  repositoryChatSource,
} from "./repositoryChatHandoff"

type RepositoryAnalysisRelatedActionsTabProps = {
  task:
    RepositoryAnalysisTaskPublic
}

export function RepositoryAnalysisRelatedActionsTab({
  task,
}: RepositoryAnalysisRelatedActionsTabProps) {
  const navigate =
    useNavigate()

  const [
    selectedKnowledgeBaseId,
    setSelectedKnowledgeBaseId,
  ] = useState(
    task.knowledge_base_id ?? "",
  )

  const knowledgeBasesQuery =
    useQuery({
      queryKey: [
        "knowledge-bases",
        "repository-review-targets",
      ],

      queryFn: () =>
        KnowledgeBasesService
          .readKnowledgeBases({
            skip: 0,
            limit: 100,
          }),

      enabled:
        !task.knowledge_base_id,

      staleTime: 30_000,
    })

  const knowledgeBases =
    knowledgeBasesQuery
      .data?.data ?? []

  useEffect(() => {
    const boundKnowledgeBaseId =
      task.knowledge_base_id?.trim()

    if (boundKnowledgeBaseId) {
      setSelectedKnowledgeBaseId(
        boundKnowledgeBaseId,
      )

      return
    }

    if (
      !selectedKnowledgeBaseId &&
      knowledgeBases.length === 1
    ) {
      setSelectedKnowledgeBaseId(
        knowledgeBases[0].id,
      )
    }
  }, [
    task.knowledge_base_id,
    knowledgeBases,
    selectedKnowledgeBaseId,
  ])

  const targetKnowledgeBaseId =
    task.knowledge_base_id?.trim() ||
    selectedKnowledgeBaseId.trim()

  const repositoryInformationReady =
    Boolean(
      task.repository_owner?.trim() &&
        task.repository_name?.trim() &&
        task.canonical_url?.trim(),
    )

  const taskCompleted =
    task.status === "completed"


  const repositoryChatReady =
  taskCompleted &&
  task.analysis_mode === "deep" &&
  Boolean(
    task.knowledge_base_id?.trim(),
  ) &&
  Boolean(
    task.resolved_commit_sha?.trim(),
  )

  const canStartReview =
    taskCompleted &&
    repositoryInformationReady &&
    Boolean(
      targetKnowledgeBaseId,
    )

  const handleStartReview = () => {
    if (
      !canStartReview ||
      !task.repository_owner ||
      !task.repository_name
    ) {
      return
    }

    void navigate({
      to:
        "/knowledge-bases/$knowledgeBaseId",

      params: {
        knowledgeBaseId:
          targetKnowledgeBaseId,
      },

      search: {
        tab: "review",

        source:
          repositoryReviewSource,

        repositoryOwner:
          task.repository_owner,

        repositoryName:
          task.repository_name,

        repositoryUrl:
          task.canonical_url,

        resolvedCommitSha:
          task.resolved_commit_sha ||
          undefined,

        repositoryAnalysisTaskId:
          task.id,
      },
    })
  }

  const handleStartRepositoryChat =
  () => {
    const knowledgeBaseId =
      task.knowledge_base_id?.trim()

    const commitSha =
      task.resolved_commit_sha?.trim()

    if (
      !repositoryChatReady
      || !knowledgeBaseId
      || !commitSha
    ) {
      return
    }

    void navigate({
      to:
        "/knowledge-bases/$knowledgeBaseId",

      params: {
        knowledgeBaseId,
      },

      search: {
        tab: "chat",

        source:
          repositoryChatSource,

        repositoryFullName:
          task.repository_full_name,

        repositoryUrl:
          task.canonical_url,

        resolvedCommitSha:
          commitSha,

        repositoryAnalysisTaskId:
          task.id,

        question:
          buildRepositoryChatQuestion(
            task,
          ),
      },
    })
  }

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-blue-200 bg-blue-50/50 p-5">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-blue-100 p-2 text-blue-700">
            <GitPullRequest className="size-5" />
          </div>

          <div className="min-w-0 flex-1">
            <h3 className="font-medium text-slate-900">
              审查该仓库的 Pull Request
            </h3>

            <p className="mt-1 text-sm leading-6 text-slate-600">
              自动带入仓库 owner、仓库名称和分析
              Commit。进入代码审查后，只需要填写
              Pull Request 编号。
            </p>

            <dl className="mt-4 grid gap-3 rounded-lg border border-blue-100 bg-white p-4 text-sm sm:grid-cols-2">
              <RepositoryMetadata
                label="仓库"
                value={
                  task.repository_full_name
                }
              />

              <RepositoryMetadata
                label="分析 Commit"
                value={
                  task.resolved_commit_sha
                    ?.slice(0, 12) ||
                  "—"
                }
              />
            </dl>

            {!taskCompleted && (
              <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                仓库分析完成后才能发起
                Pull Request 审查。
              </div>
            )}

            {taskCompleted &&
              !repositoryInformationReady && (
                <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  当前任务缺少仓库 owner
                  或仓库名称，无法生成
                  Pull Request 地址。
                </div>
              )}

            {task.knowledge_base_id ? (
              <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                将使用该任务已经绑定的知识库：
                <span className="ml-1 font-mono">
                  {task.knowledge_base_id}
                </span>
              </div>
            ) : (
              <div className="mt-4 space-y-2">
                <label
                  htmlFor="review-knowledge-base"
                  className="text-sm font-medium text-slate-800"
                >
                  选择用于代码审查的知识库
                </label>

                <Select
                  value={
                    selectedKnowledgeBaseId ||
                    undefined
                  }
                  onValueChange={
                    setSelectedKnowledgeBaseId
                  }
                  disabled={
                    knowledgeBasesQuery
                      .isPending
                  }
                >
                  <SelectTrigger
                    id="review-knowledge-base"
                    className="w-full bg-white"
                  >
                    <SelectValue
                      placeholder={
                        knowledgeBasesQuery
                          .isPending
                          ? "正在加载知识库"
                          : "请选择知识库"
                      }
                    />
                  </SelectTrigger>

                  <SelectContent>
                    {knowledgeBases.map(
                      (knowledgeBase) => (
                        <SelectItem
                          key={
                            knowledgeBase.id
                          }
                          value={
                            knowledgeBase.id
                          }
                        >
                          {knowledgeBase.name}
                        </SelectItem>
                      ),
                    )}
                  </SelectContent>
                </Select>

                <p className="text-xs leading-5 text-slate-500">
                  请选择已经包含该仓库代码的知识库。
                  变更审查需要通过知识库定位符号、
                  影响范围和测试文件。
                </p>

                {knowledgeBasesQuery
                  .isError && (
                  <p className="text-sm text-red-600">
                    知识库列表加载失败。
                  </p>
                )}

                {!knowledgeBasesQuery
                  .isPending &&
                  !knowledgeBasesQuery
                    .isError &&
                  knowledgeBases.length ===
                    0 && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        void navigate({
                          to:
                            "/knowledge-bases",
                        })
                      }}
                    >
                      前往创建知识库
                    </Button>
                  )}
              </div>
            )}

            <Button
              type="button"
              className="mt-5"
              disabled={
                !canStartReview
              }
              onClick={
                handleStartReview
              }
            >
              <GitPullRequest />
              发起 Pull Request 审查
              <ArrowRight />
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <RepositoryAnalysisKnowledgeBaseCard
          task={task}
        />

        <section className="rounded-xl border border-violet-200 bg-violet-50/50 p-5">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-violet-100 p-2 text-violet-700">
              <MessageSquare className="size-5" />
            </div>

            <div className="min-w-0 flex-1">
              <h3 className="font-medium text-slate-900">
                基于仓库开始问答
              </h3>

              <p className="mt-1 text-sm leading-6 text-slate-600">
                问答范围将限定为当前仓库分析任务
                导入的固定 Commit，不会检索同一知识库
                中其他仓库或普通文档。
              </p>

              <dl className="mt-4 grid gap-3 rounded-lg border border-violet-100 bg-white p-4 text-sm sm:grid-cols-2">
                <RepositoryMetadata
                  label="仓库"
                  value={
                    task.repository_full_name
                  }
                />

                <RepositoryMetadata
                  label="固定 Commit"
                  value={
                    task.resolved_commit_sha
                      ?.slice(0, 12) ||
                    "—"
                  }
                />
              </dl>

              {!repositoryChatReady && (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                  需要先完成知识库绑定、代码导入和
                  向量索引，才能开始仓库问答。
                </div>
              )}

              <Button
                type="button"
                className="mt-4"
                disabled={
                  !repositoryChatReady
                }
                onClick={
                  handleStartRepositoryChat
                }
              >
                <MessageSquare />
                进入仓库问答
                <ArrowRight />
              </Button>
            </div>
          </div>
        </section>
      </section>
    </div>
  )
}

function RepositoryMetadata({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-slate-500">
        {label}
      </dt>

      <dd className="mt-1 break-all font-medium text-slate-800">
        {value}
      </dd>
    </div>
  )
}

