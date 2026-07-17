import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  useEffect,
  useState,
} from "react"

import {
  CodeSkillService,
  type GitHubReviewPublicationResultPublic,
} from "@/client"

import {
  GITHUB_REVIEW_EVENTS,
  formatPublicationDateTime,
  getGitHubReviewEventDescription,
  getGitHubReviewEventLabel,
  getPublicationLink,
  getPublicationStatusClassName,
  getPublicationStatusLabel,
  normalizeGitHubReviewEvent,
  readPublicationApiError,
  type GitHubReviewEvent,
} from "./githubReviewPublicationUtils"

type GitHubReviewPublishPanelProps = {
  knowledgeBaseId: string

  reviewRunId:
    string | null

  reviewRunTitle?:
    string | null

  onPublished?: (
    result:
      GitHubReviewPublicationResultPublic,
  ) => void
}

export const githubPublicationPreviewQueryKey = (
  knowledgeBaseId: string,
  reviewRunId: string,
) => [
  "github-review-publication-preview",
  knowledgeBaseId,
  reviewRunId,
] as const

export const codeReviewPublicationsQueryKey = (
  knowledgeBaseId: string,
  reviewRunId: string,
) => [
  "code-review-publications",
  knowledgeBaseId,
  reviewRunId,
] as const

export function GitHubReviewPublishPanel({
  knowledgeBaseId,
  reviewRunId,
  reviewRunTitle,
  onPublished,
}: GitHubReviewPublishPanelProps) {
  const queryClient =
    useQueryClient()

  const [
    isDialogOpen,
    setIsDialogOpen,
  ] = useState(false)

  const [
    selectedEvent,
    setSelectedEvent,
  ] = useState<
    GitHubReviewEvent
  >("COMMENT")

  const [
    forceRepublish,
    setForceRepublish,
  ] = useState(false)

  const [
    publishedResult,
    setPublishedResult,
  ] = useState<
    GitHubReviewPublicationResultPublic
    | null
  >(null)

  const safeReviewRunId =
    reviewRunId || ""

  const previewQuery =
    useQuery({
      queryKey:
        githubPublicationPreviewQueryKey(
          knowledgeBaseId,
          safeReviewRunId,
        ),

      queryFn: () =>
        CodeSkillService
          .previewGithubCodeReviewPublication({
            knowledgeBaseId,

            reviewRunId:
              safeReviewRunId,
          }),

      enabled:
        Boolean(
          reviewRunId
          && isDialogOpen,
        ),

      retry: false,
    })

  const publicationsQuery =
    useQuery({
      queryKey:
        codeReviewPublicationsQueryKey(
          knowledgeBaseId,
          safeReviewRunId,
        ),

      queryFn: () =>
        CodeSkillService
          .readCodeReviewPublications({
            knowledgeBaseId,

            reviewRunId:
              safeReviewRunId,
          }),

      enabled:
        Boolean(
          reviewRunId,
        ),

      retry: false,
    })

  useEffect(
    () => {
      if (
        !previewQuery.data
      ) {
        return
      }

      setSelectedEvent(
        normalizeGitHubReviewEvent(
          previewQuery
            .data
            .default_event,
        ),
      )
    },
    [
      previewQuery.data,
    ],
  )

  useEffect(
    () => {
      setIsDialogOpen(false)
      setForceRepublish(false)
      setPublishedResult(null)
    },
    [
      reviewRunId,
    ],
  )

  const publishMutation =
    useMutation({
      mutationFn: ({
        event,
        force,
      }: {
        event:
          GitHubReviewEvent

        force:
          boolean
      }) =>
        CodeSkillService
          .publishGithubCodeReview({
            knowledgeBaseId,

            reviewRunId:
              safeReviewRunId,

            requestBody: {
              event,

              force_republish:
                force,
            },
          }),

      onSuccess: async (
        result,
      ) => {
        setPublishedResult(
          result,
        )

        setForceRepublish(
          false,
        )

        await Promise.all([
          queryClient
            .invalidateQueries({
              queryKey:
                githubPublicationPreviewQueryKey(
                  knowledgeBaseId,
                  safeReviewRunId,
                ),
            }),

          queryClient
            .invalidateQueries({
              queryKey:
                codeReviewPublicationsQueryKey(
                  knowledgeBaseId,
                  safeReviewRunId,
                ),
            }),
        ])

        onPublished?.(
          result,
        )

        const githubUrl =
          result
            .publication
            .external_review_url
          || result
            .pull_request_url

        if (githubUrl) {
          window.open(
            githubUrl,
            "_blank",
            "noopener,noreferrer",
          )
        }
      },
    })

  const previewError =
    previewQuery.isError
      ? readPublicationApiError(
          previewQuery.error,
        )
      : null

  const publicationHistoryError =
    publicationsQuery.isError
      ? readPublicationApiError(
          publicationsQuery.error,
        )
      : null

  const publishError =
    publishMutation.isError
      ? readPublicationApiError(
          publishMutation.error,
        )
      : null

  const preview =
    previewQuery.data

  const alreadyPublished =
    preview?.already_published
    === true

  const requiresForceConfirmation =
    alreadyPublished
    && !forceRepublish

  const handleOpenDialog = () => {
    if (!reviewRunId) {
      return
    }

    setPublishedResult(null)
    setForceRepublish(false)
    publishMutation.reset()

    setIsDialogOpen(true)
  }

  const handleCloseDialog = () => {
    if (
      publishMutation.isPending
    ) {
      return
    }

    setIsDialogOpen(false)
    publishMutation.reset()
  }

  const handlePublish = () => {
    if (
      !reviewRunId
      || !preview
      || requiresForceConfirmation
    ) {
      return
    }

    publishMutation.mutate({
      event:
        selectedEvent,

      force:
        forceRepublish,
    })
  }

  return (
    <section className="space-y-4 rounded-2xl border border-violet-200 bg-violet-50/40 p-4 md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-violet-600">
            GitHub App Publishing
          </div>

          <h3 className="mt-1 text-base font-semibold text-slate-900">
            发布正式 GitHub Review
          </h3>

          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
            系统将使用已保存的仓库、PR 编号、
            Head SHA 和报告正文发布，页面不能覆盖这些可信字段。
          </p>
        </div>

        <button
          type="button"
          className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={
            !reviewRunId
          }
          onClick={
            handleOpenDialog
          }
        >
          预览并发布
        </button>
      </div>

      {!reviewRunId ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
          请先生成一份完整 Review，或者从历史记录中打开一份 Review。
        </div>
      ) : (
        <div className="rounded-xl border border-violet-100 bg-white px-4 py-3">
          <div className="text-xs text-slate-500">
            当前发布对象
          </div>

          <div className="mt-1 text-sm font-medium text-slate-800">
            {reviewRunTitle
              || "RepoGuard Review"}
          </div>

          <div className="mt-1 break-all font-mono text-xs text-slate-400">
            Review Run：
            {reviewRunId}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h4 className="text-sm font-semibold text-slate-800">
              发布历史
            </h4>

            <p className="mt-1 text-xs text-slate-500">
              展示当前 Review Run 的全部发布尝试。
            </p>
          </div>

          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:border-violet-300 hover:text-violet-700 disabled:opacity-50"
            disabled={
              !reviewRunId
              || publicationsQuery
                .isFetching
            }
            onClick={() => {
              void publicationsQuery
                .refetch()
            }}
          >
            {publicationsQuery
              .isFetching
              ? "刷新中..."
              : "刷新历史"}
          </button>
        </div>

        {publicationsQuery
          .isLoading ? (
          <div className="mt-4 text-sm text-slate-500">
            正在加载发布历史...
          </div>
        ) : null}

        {publicationHistoryError ? (
          <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            {publicationHistoryError
              .message}
          </div>
        ) : null}

        {publicationsQuery.data ? (
          <div className="mt-4 space-y-3">
            {publicationsQuery
              .data
              .data
              .length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
                这份 Review 尚未发布到 GitHub。
              </div>
            ) : (
              publicationsQuery
                .data
                .data
                .map(
                  (
                    publication,
                  ) => {
                    const link =
                      getPublicationLink(
                        publication,
                      )

                    return (
                      <article
                        key={
                          publication.id
                        }
                        className="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-slate-800">
                              第{" "}
                              {
                                publication
                                  .attempt_number
                              }{" "}
                              次发布
                            </div>

                            <div className="mt-1 text-xs text-slate-500">
                              {formatPublicationDateTime(
                                publication
                                  .created_at,
                              )}
                            </div>
                          </div>

                          <span
                            className={
                              "rounded-full border px-2.5 py-1 text-xs font-medium "
                              + getPublicationStatusClassName(
                                publication
                                  .status,
                              )
                            }
                          >
                            {getPublicationStatusLabel(
                              publication
                                .status,
                            )}
                          </span>
                        </div>

                        <dl className="mt-3 grid grid-cols-1 gap-2 text-xs md:grid-cols-2">
                          <div>
                            <dt className="text-slate-400">
                              Event
                            </dt>

                            <dd className="mt-0.5 font-medium text-slate-700">
                              {
                                publication
                                  .requested_event
                              }
                            </dd>
                          </div>

                          <div>
                            <dt className="text-slate-400">
                              Head SHA
                            </dt>

                            <dd className="mt-0.5 break-all font-mono text-slate-700">
                              {
                                publication
                                  .target_head_sha
                              }
                            </dd>
                          </div>

                          <div>
                            <dt className="text-slate-400">
                              GitHub 状态
                            </dt>

                            <dd className="mt-0.5 text-slate-700">
                              {
                                publication
                                  .external_review_state
                                || "-"
                              }
                            </dd>
                          </div>

                          <div>
                            <dt className="text-slate-400">
                              发布账号
                            </dt>

                            <dd className="mt-0.5 text-slate-700">
                              {
                                publication
                                  .external_actor
                                || "-"
                              }
                            </dd>
                          </div>
                        </dl>

                        {publication
                          .error_message ? (
                          <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs leading-5 text-rose-700">
                            <div className="font-medium">
                              {
                                publication
                                  .error_code
                              }
                            </div>

                            <div className="mt-1">
                              {
                                publication
                                  .error_message
                              }
                            </div>
                          </div>
                        ) : null}

                        {link ? (
                          <a
                            className="mt-3 inline-flex text-xs font-medium text-violet-700 hover:underline"
                            href={link}
                            target="_blank"
                            rel="noreferrer"
                          >
                            在 GitHub 中打开
                          </a>
                        ) : null}
                      </article>
                    )
                  },
                )
            )}
          </div>
        ) : null}
      </div>

      {isDialogOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="发布 GitHub Review"
        >
          <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">
                  确认发布 GitHub Review
                </h3>

                <p className="mt-1 text-sm text-slate-500">
                  发布前请确认目标、提交 SHA、Review 状态和正文。
                </p>
              </div>

              <button
                type="button"
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                disabled={
                  publishMutation
                    .isPending
                }
                onClick={
                  handleCloseDialog
                }
              >
                关闭
              </button>
            </div>

            <div className="space-y-5 p-5">
              {previewQuery
                .isLoading ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-500">
                  正在生成发布预览...
                </div>
              ) : null}

              {previewError ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
                  <div className="text-sm font-medium text-rose-800">
                    {
                      previewError
                        .code
                    }
                  </div>

                  <div className="mt-1 text-sm leading-6 text-rose-700">
                    {
                      previewError
                        .message
                    }
                  </div>
                </div>
              ) : null}

              {preview ? (
                <>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <PreviewValue
                      label="目标仓库"
                      value={
                        preview
                          .target_repository
                      }
                    />

                    <PreviewValue
                      label="Pull Request"
                      value={`#${preview.target_change_number}`}
                    />

                    <PreviewValue
                      label="正文字符数"
                      value={
                        preview
                          .body_character_count
                          .toLocaleString()
                      }
                    />
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="text-xs font-medium text-slate-500">
                      已审查 Head SHA
                    </div>

                    <div className="mt-2 break-all font-mono text-xs text-slate-800">
                      {
                        preview
                          .reviewed_head_sha
                      }
                    </div>
                  </div>

                  <fieldset className="space-y-3">
                    <legend className="text-sm font-semibold text-slate-800">
                      GitHub Review 状态
                    </legend>

                    {GITHUB_REVIEW_EVENTS
                      .map(
                        (
                          event,
                        ) => (
                          <label
                            key={event}
                            className={
                              "block cursor-pointer rounded-xl border p-4 transition "
                              + (
                                selectedEvent
                                === event
                                  ? "border-violet-400 bg-violet-50"
                                  : "border-slate-200 bg-white hover:border-violet-200"
                              )
                            }
                          >
                            <div className="flex items-start gap-3">
                              <input
                                type="radio"
                                name="github-review-event"
                                className="mt-1"
                                value={event}
                                checked={
                                  selectedEvent
                                  === event
                                }
                                onChange={() => {
                                  setSelectedEvent(
                                    event,
                                  )
                                }}
                              />

                              <div>
                                <div className="text-sm font-medium text-slate-800">
                                  {getGitHubReviewEventLabel(
                                    event,
                                  )}
                                </div>

                                <div className="mt-1 text-xs leading-5 text-slate-500">
                                  {getGitHubReviewEventDescription(
                                    event,
                                  )}
                                </div>

                                {preview
                                  .default_event
                                  === event ? (
                                  <span className="mt-2 inline-flex rounded-full border border-violet-200 bg-violet-100 px-2 py-0.5 text-[11px] font-medium text-violet-700">
                                    系统推荐
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          </label>
                        ),
                      )}
                  </fieldset>

                  {alreadyPublished ? (
                    <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
                      <div className="text-sm font-medium text-amber-900">
                        这份 Review 已成功发布过{" "}
                        {
                          preview
                            .successful_publication_count
                        }{" "}
                        次
                      </div>

                      <p className="mt-1 text-xs leading-5 text-amber-700">
                        默认禁止重复发布。只有明确勾选后，后端才允许再次创建 GitHub Review。
                      </p>

                      <label className="mt-3 flex cursor-pointer items-start gap-2 text-sm text-amber-900">
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={
                            forceRepublish
                          }
                          onChange={(
                            event,
                          ) => {
                            setForceRepublish(
                              event
                                .target
                                .checked,
                            )
                          }}
                        />

                        <span>
                          我确认要强制再次发布
                        </span>
                      </label>
                    </div>
                  ) : null}

                  <details className="rounded-xl border border-slate-200 bg-slate-950">
                    <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-slate-100">
                      查看将要发送的 Markdown 正文
                    </summary>

                    <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap break-words border-t border-slate-800 p-4 font-mono text-xs leading-5 text-slate-200">
                      {
                        preview
                          .body_markdown
                      }
                    </pre>
                  </details>

                  {publishError ? (
                    <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
                      <div className="text-sm font-medium text-rose-800">
                        {
                          publishError
                            .code
                        }
                      </div>

                      <div className="mt-1 text-sm leading-6 text-rose-700">
                        {
                          publishError
                            .message
                        }
                      </div>

                      {publishError.code
                        === "GITHUB_PR_HEAD_CHANGED" ? (
                        <div className="mt-3 space-y-1 break-all font-mono text-xs text-rose-700">
                          <div>
                            Reviewed：
                            {String(
                              publishError
                                .context
                                .reviewed_head_sha
                              || "-",
                            )}
                          </div>

                          <div>
                            Current：
                            {String(
                              publishError
                                .context
                                .current_head_sha
                              || "-",
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {publishedResult ? (
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                      <div className="text-sm font-medium text-emerald-800">
                        GitHub Review 发布成功
                      </div>

                      <a
                        className="mt-2 inline-flex text-sm font-medium text-emerald-700 hover:underline"
                        href={
                          publishedResult
                            .publication
                            .external_review_url
                          || publishedResult
                            .pull_request_url
                        }
                        target="_blank"
                        rel="noreferrer"
                      >
                        打开 GitHub Review
                      </a>
                    </div>
                  ) : null}
                </>
              ) : null}
            </div>

            <div className="flex flex-wrap justify-end gap-3 border-t border-slate-200 px-5 py-4">
              <button
                type="button"
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                disabled={
                  publishMutation
                    .isPending
                }
                onClick={
                  handleCloseDialog
                }
              >
                取消
              </button>

              <button
                type="button"
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={
                  !preview
                  || publishMutation
                    .isPending
                  || requiresForceConfirmation
                }
                onClick={
                  handlePublish
                }
              >
                {publishMutation
                  .isPending
                  ? "正在发布..."
                  : `确认发布 ${selectedEvent}`}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}

function PreviewValue({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="text-xs font-medium text-slate-500">
        {label}
      </div>

      <div className="mt-1 break-all text-sm font-semibold text-slate-800">
        {value}
      </div>
    </div>
  )
}