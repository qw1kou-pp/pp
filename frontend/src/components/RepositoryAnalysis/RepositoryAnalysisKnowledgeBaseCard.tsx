import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  useNavigate,
} from "@tanstack/react-router"
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
} from "lucide-react"
import {
  useEffect,
  useMemo,
  useState,
} from "react"

import {
  KnowledgeBasesService,
  type RepositoryAnalysisTaskPublic,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  LoadingButton,
} from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"

import {
  bindRepositoryAnalysisKnowledgeBase,
  importRepositoryAnalysisKnowledgeBase,
} from "./repositoryAnalysisKnowledgeBaseApi"
import {
  repositoryAnalysisKeys,
  syncRepositoryAnalysisTaskToLists,
} from "./repositoryAnalysisQueries"
import {
  formatRepositoryAnalysisError,
} from "./repositoryAnalysisUi"
import {
  RepositoryAnalysisEmbeddingPanel,
} from "./RepositoryAnalysisEmbeddingPanel"

type Props = {
  task: RepositoryAnalysisTaskPublic
}

type KnowledgeBaseMode =
  | "existing"
  | "new"

export function RepositoryAnalysisKnowledgeBaseCard({
  task,
}: Props) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const {
    showSuccessToast,
    showErrorToast,
  } = useCustomToast()

  const [
    dialogOpen,
    setDialogOpen,
  ] = useState(false)

  const [
    mode,
    setMode,
  ] = useState<KnowledgeBaseMode>(
    "existing",
  )

  const [
    selectedKnowledgeBaseId,
    setSelectedKnowledgeBaseId,
  ] = useState("")

  const [
    knowledgeBaseName,
    setKnowledgeBaseName,
  ] = useState("")

  const [
    knowledgeBaseDescription,
    setKnowledgeBaseDescription,
  ] = useState("")

  const defaultKnowledgeBaseName =
    useMemo(
      () =>
        buildDefaultKnowledgeBaseName(
          task,
        ),
      [task],
    )

  const defaultDescription =
    useMemo(
      () =>
        buildDefaultDescription(
          task,
        ),
      [task],
    )

  const knowledgeBasesQuery =
    useQuery({
      queryKey: [
        "knowledge-bases",
        "repository-analysis-binding",
      ],

      queryFn: () =>
        KnowledgeBasesService
          .readKnowledgeBases({
            skip: 0,
            limit: 100,
          }),

      enabled:
        dialogOpen &&
        task.status === "completed" &&
        !task.knowledge_base_id,

      staleTime: 30_000,
    })

  const knowledgeBases =
    knowledgeBasesQuery
      .data?.data ?? []

  useEffect(() => {
    setMode("existing")
    setSelectedKnowledgeBaseId("")
    setKnowledgeBaseName(
      defaultKnowledgeBaseName,
    )
    setKnowledgeBaseDescription(
      defaultDescription,
    )
  }, [
    task.id,
    defaultKnowledgeBaseName,
    defaultDescription,
  ])

  useEffect(() => {
    if (
      !dialogOpen ||
      knowledgeBasesQuery.isPending
    ) {
      return
    }

    if (knowledgeBases.length === 0) {
      setMode("new")
      return
    }

    if (!selectedKnowledgeBaseId) {
      setSelectedKnowledgeBaseId(
        knowledgeBases[0].id,
      )
    }
  }, [
    dialogOpen,
    knowledgeBases,
    knowledgeBasesQuery.isPending,
    selectedKnowledgeBaseId,
  ])

    const importMutation =
    useMutation({
      mutationFn: (
        repositoryAnalysisTaskId: string,
      ) =>
        importRepositoryAnalysisKnowledgeBase(
          repositoryAnalysisTaskId,
        ),

      onSuccess: (result) => {
        showSuccessToast(
          result.already_imported
            ? (
              `固定 Commit 已经导入：`
              + `${result.document_count} 个文件，`
              + `${result.chunk_count} 个代码块`
            )
            : (
              `固定 Commit 导入完成：`
              + `${result.document_count} 个文件，`
              + `${result.chunk_count} 个代码块`
            ),
        )

        void queryClient.invalidateQueries({
          queryKey: [
            "knowledge-base-documents",
            result.knowledge_base_id,
          ],
        })
      },

      onError: (error) => {
        showErrorToast(
          "知识库已经绑定，但固定 Commit 导入失败："
          + formatRepositoryAnalysisError(
            error,
          ),
        )
      },
    })


  const bindingMutation =
    useMutation({
      mutationFn: () => {
        if (mode === "existing") {
          const knowledgeBaseId =
            selectedKnowledgeBaseId.trim()

          if (!knowledgeBaseId) {
            throw new Error(
              "请选择一个已有知识库",
            )
          }

          return (
            bindRepositoryAnalysisKnowledgeBase(
              task.id,
              {
                knowledge_base_id:
                  knowledgeBaseId,
              },
            )
          )
        }

        const name =
          knowledgeBaseName.trim()

        if (!name) {
          throw new Error(
            "请输入知识库名称",
          )
        }

        return (
          bindRepositoryAnalysisKnowledgeBase(
            task.id,
            {
              knowledge_base_name: name,

              knowledge_base_description:
                knowledgeBaseDescription
                  .trim() ||
                undefined,
            },
          )
        )
      },

      onSuccess: (result) => {
        queryClient.setQueryData(
          repositoryAnalysisKeys.detail(
            result.task.id,
          ),
          result.task,
        )

        syncRepositoryAnalysisTaskToLists(
          queryClient,
          result.task,
        )

        void queryClient.invalidateQueries({
          queryKey:
            repositoryAnalysisKeys.lists(),
        })

        void queryClient.invalidateQueries({
          queryKey: [
            "knowledge-bases",
          ],
        })

        setDialogOpen(false)

        showSuccessToast(
          result.created_new_knowledge_base
            ? "知识库创建并绑定成功，开始导入固定 Commit"
            : "知识库绑定成功，开始导入固定 Commit",
        )

        importMutation.mutate(
          result.task.id,
        )
      },

      onError: (error) => {
        showErrorToast(
          formatRepositoryAnalysisError(
            error,
          ),
        )
      },
    })

  const boundKnowledgeBaseId =
    task.knowledge_base_id?.trim() || ""

  const taskReady =
    task.status === "completed"

  if (boundKnowledgeBaseId) {
    return (
      <section className="space-y-4 rounded-xl border border-emerald-200 bg-emerald-50/50 p-5">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-emerald-100 p-2 text-emerald-700">
            <CheckCircle2 className="size-5" />
          </div>

          <div className="min-w-0 flex-1">
            <h3 className="font-medium text-slate-900">
              已绑定代码知识库
            </h3>

            <p className="mt-1 text-sm leading-6 text-slate-600">
              当前仓库分析任务已经保存，
              并与下面的知识库建立关联。
            </p>

            <p className="mt-3 break-all rounded-lg border bg-white p-3 font-mono text-sm">
              {boundKnowledgeBaseId}
            </p>

            <div className="mt-4 rounded-lg border bg-white p-4">
              <h4 className="text-sm font-medium text-slate-900">
                固定 Commit 代码导入
              </h4>

              <p className="mt-1 break-all text-xs text-slate-500">
                Commit：
                {task.resolved_commit_sha || "-"}
              </p>

              {(
                importMutation.data &&
                importMutation.variables
                  === task.id
              ) && (
                <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <p>
                    文件数：
                    {importMutation.data.document_count}
                  </p>

                  <p>
                    代码块：
                    {importMutation.data.chunk_count}
                  </p>

                  <p>
                    导入大小：
                    {formatImportBytes(
                      importMutation.data.imported_bytes,
                    )}
                  </p>

                  <p>
                    导入状态：
                    {importMutation.data.already_imported
                      ? "此前已经导入"
                      : "本次导入完成"}
                  </p>
                </div>
              )}

              <LoadingButton
                type="button"
                className="mt-3"
                loading={
                  importMutation.isPending
                }
                disabled={
                  !task.resolved_commit_sha
                }
                onClick={() => {
                  importMutation.mutate(
                    task.id,
                  )
                }}
              >
                导入固定 Commit
              </LoadingButton>
            </div>

            <RepositoryAnalysisEmbeddingPanel
              task={task}
            />

            <Button
              type="button"
              className="mt-4"
              onClick={() => {
                void navigate({
                  to:
                    "/knowledge-bases/$knowledgeBaseId",

                  params: {
                    knowledgeBaseId:
                      boundKnowledgeBaseId,
                  },

                  search: {
                    tab: "overview",
                  },
                })
              }}
            >
              进入知识库
              <ArrowRight />
            </Button>
          </div>
        </div>
      </section>
    )
  }

  return (
    <>
      <section className="rounded-xl border border-violet-200 bg-violet-50/50 p-5">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-violet-100 p-2 text-violet-700">
            <BookOpen className="size-5" />
          </div>

          <div className="min-w-0 flex-1">
            <h3 className="font-medium text-slate-900">
              绑定代码知识库
            </h3>

            <p className="mt-1 text-sm leading-6 text-slate-600">
              选择已有知识库，或者现场创建新知识库。
              下一步会把当前固定 Commit 的代码导入该知识库。
            </p>

            {!taskReady && (
              <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                仓库分析完成后才能绑定知识库。
              </p>
            )}

            <Button
              type="button"
              className="mt-4"
              disabled={!taskReady}
              onClick={() => {
                setDialogOpen(true)
              }}
            >
              <BookOpen />
              选择或创建知识库
            </Button>
          </div>
        </div>
      </section>

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (bindingMutation.isPending) {
            return
          }

          setDialogOpen(open)
        }}
      >
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>
              选择代码知识库
            </DialogTitle>

            <DialogDescription>
              可以使用已有知识库，
              也可以为当前仓库创建新的知识库。
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1">
            <Button
              type="button"
              variant={
                mode === "existing"
                  ? "default"
                  : "ghost"
              }
              disabled={
                knowledgeBases.length === 0
              }
              onClick={() => {
                setMode("existing")
              }}
            >
              选择已有知识库
            </Button>

            <Button
              type="button"
              variant={
                mode === "new"
                  ? "default"
                  : "ghost"
              }
              onClick={() => {
                setMode("new")
              }}
            >
              创建新知识库
            </Button>
          </div>

          {mode === "existing" ? (
            <div className="space-y-2">
              <Label htmlFor="repository-analysis-knowledge-base">
                目标知识库
              </Label>

              <Select
                value={
                  selectedKnowledgeBaseId ||
                  undefined
                }
                onValueChange={
                  setSelectedKnowledgeBaseId
                }
                disabled={
                  knowledgeBasesQuery.isPending
                }
              >
                <SelectTrigger
                  id="repository-analysis-knowledge-base"
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
                        key={knowledgeBase.id}
                        value={knowledgeBase.id}
                      >
                        {knowledgeBase.name}
                      </SelectItem>
                    ),
                  )}
                </SelectContent>
              </Select>

              {knowledgeBasesQuery.isError && (
                <p className="text-sm text-red-600">
                  知识库列表加载失败。
                </p>
              )}

              {!knowledgeBasesQuery.isPending &&
                !knowledgeBasesQuery.isError &&
                knowledgeBases.length === 0 && (
                  <p className="text-sm text-amber-700">
                    当前没有知识库，
                    请切换到“创建新知识库”。
                  </p>
                )}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="repository-analysis-knowledge-base-name">
                  知识库名称
                </Label>

                <Input
                  id="repository-analysis-knowledge-base-name"
                  value={knowledgeBaseName}
                  maxLength={255}
                  onChange={(event) => {
                    setKnowledgeBaseName(
                      event.target.value,
                    )
                  }}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="repository-analysis-knowledge-base-description">
                  描述（可选）
                </Label>

                <Input
                  id="repository-analysis-knowledge-base-description"
                  value={
                    knowledgeBaseDescription
                  }
                  maxLength={255}
                  onChange={(event) => {
                    setKnowledgeBaseDescription(
                      event.target.value,
                    )
                  }}
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={
                bindingMutation.isPending
              }
              onClick={() => {
                setDialogOpen(false)
              }}
            >
              取消
            </Button>

            <LoadingButton
              type="button"
              loading={
                bindingMutation.isPending
              }
              disabled={
                mode === "existing"
                  ? !selectedKnowledgeBaseId
                  : !knowledgeBaseName.trim()
              }
              onClick={() => {
                bindingMutation.mutate()
              }}
            >
              确认绑定
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function buildDefaultKnowledgeBaseName(
  task: RepositoryAnalysisTaskPublic,
): string {
  const commit =
    task.resolved_commit_sha
      ?.slice(0, 12) ||
    "unknown"

  return (
    `${task.repository_full_name} @ ${commit}`
  ).slice(0, 255)
}

function buildDefaultDescription(
  task: RepositoryAnalysisTaskPublic,
): string {
  const commit =
    task.resolved_commit_sha ||
    "unknown"

  return (
    `由仓库分析任务 ${task.id} 创建；`
    + `来源 ${task.canonical_url}；`
    + `固定 Commit ${commit}`
  ).slice(0, 255)
}
function formatImportBytes(
  bytes: number,
): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }

  if (bytes < 1024 * 1024) {
    return (
      `${(bytes / 1024).toFixed(1)} KB`
    )
  }

  if (bytes < 1024 * 1024 * 1024) {
    return (
      `${(
        bytes /
        (1024 * 1024)
      ).toFixed(1)} MB`
    )
  }

  return (
    `${(
      bytes /
      (1024 * 1024 * 1024)
    ).toFixed(2)} GB`
  )
}