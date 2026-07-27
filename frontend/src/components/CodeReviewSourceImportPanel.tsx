import {
  useMutation,
} from "@tanstack/react-query"
import {
  useEffect,
  useState,
  type FormEvent,
} from "react"

import {
  CodeSkillService,
  type CodeReviewSourceResolvedPublic,
} from "@/client"

import {
  formatCodeReviewSourceLabel,
  formatDiffSize,
  formatSourceDateTime,
} from "./codeReviewSourceUtils"

import {
  buildGitHubPullRequestUrl,
  formatRepositoryReviewName,
  type CodeReviewRepositoryPrefill,
} from "./repositoryReviewHandoff"

type CodeReviewSourceImportPanelProps = {
  knowledgeBaseId: string

  repositoryPrefill?:
  CodeReviewRepositoryPrefill
  | null

  resolvedSource:
    CodeReviewSourceResolvedPublic
    | null

  disabled?: boolean

  onResolved: (
    source:
      CodeReviewSourceResolvedPublic,
  ) => void

  onClear: () => void
}

const formatSourceApiError = (
  error: unknown,
): string => {
  if (
    !error ||
    typeof error !== "object"
  ) {
    return String(
      error || "未知错误",
    )
  }

  const candidate =
    error as {
      message?: string

      body?: {
        detail?: unknown
      }
    }

  const detail =
    candidate.body?.detail

  if (
    typeof detail === "string"
  ) {
    return detail
  }

  if (detail !== undefined) {
    return JSON.stringify(
      detail,
      null,
      2,
    )
  }

  return (
    candidate.message ||
    "获取 PR/MR 失败"
  )
}

const getProviderClassName = (
  provider:
    CodeReviewSourceResolvedPublic[
      "provider"
    ],
): string => {
  if (provider === "gitlab") {
    return (
      "border-orange-200 " +
      "bg-orange-50 " +
      "text-orange-700"
    )
  }

  return (
    "border-slate-300 " +
    "bg-slate-100 " +
    "text-slate-700"
  )
}

export function CodeReviewSourceImportPanel({
  knowledgeBaseId,
  repositoryPrefill = null,
  resolvedSource,
  disabled = false,
  onResolved,
  onClear,
}: CodeReviewSourceImportPanelProps) {
  const [
    sourceUrl,
    setSourceUrl,
  ] = useState("")

  const [
    pullRequestNumber,
    setPullRequestNumber,
  ] = useState("")

  const [
    useRepositoryPrefill,
    setUseRepositoryPrefill,
  ] = useState(
    Boolean(repositoryPrefill),
  )

  const [
    inputError,
    setInputError,
  ] = useState<string | null>(
    null,
  )

  const repositoryPrefillKey =
    repositoryPrefill
      ? [
          repositoryPrefill
            .repositoryOwner,
          repositoryPrefill
            .repositoryName,
          repositoryPrefill
            .repositoryUrl,
          repositoryPrefill
            .resolvedCommitSha ?? "",
        ].join("|")
      : ""

  const resolveMutation =
    useMutation({
      mutationFn: (
        nextSourceUrl: string,
      ) =>
        CodeSkillService
          .resolveCodeReviewSource({
            knowledgeBaseId,

            requestBody: {
              source_url:
                nextSourceUrl,
            },
          }),

      onSuccess: (source) => {
        setSourceUrl(
          source.source_url,
        )

        onResolved(source)
      },
    })

  const resetResolveMutation =
    resolveMutation.reset

  useEffect(() => {
    setUseRepositoryPrefill(
      repositoryPrefillKey.length >
        0,
    )

    setPullRequestNumber("")
    setSourceUrl("")
    setInputError(null)

    resetResolveMutation()
  }, [
    repositoryPrefillKey,
    resetResolveMutation,
  ])


  const handleSubmit = (
    event:
      FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()

    if (
      disabled ||
      resolveMutation.isPending
    ) {
      return
    }

    setInputError(null)

    let nextSourceUrl =
      sourceUrl.trim()

    if (
      useRepositoryPrefill &&
      repositoryPrefill
    ) {
      try {
        nextSourceUrl =
          buildGitHubPullRequestUrl(
            repositoryPrefill,
            pullRequestNumber,
          )
      } catch (error) {
        setInputError(
          error instanceof Error
            ? error.message
            : "请输入有效的 PR 编号",
        )

        return
      }
    }

    if (!nextSourceUrl) {
      setInputError(
        "请输入 Pull Request 或 Merge Request 地址",
      )

      return
    }

    resolveMutation.reset()

    resolveMutation.mutate(
      nextSourceUrl,
    )
  }

  const handleClear = () => {
    setSourceUrl("")
    setPullRequestNumber("")
    setInputError(null)

    resolveMutation.reset()
    onClear()
  }

  const handleUseDifferentRepository =
    () => {
      handleClear()

      setUseRepositoryPrefill(
        false,
      )
    }

  const handleRestoreRepositoryPrefill =
    () => {
      handleClear()

      setUseRepositoryPrefill(
        true,
      )
    }

  const repositoryPullRequestReady =
    /^[1-9]\d*$/.test(
      pullRequestNumber.trim(),
    )

  const canSubmit =
    (
      useRepositoryPrefill &&
      repositoryPrefill
        ? repositoryPullRequestReady
        : Boolean(
            sourceUrl.trim(),
          )
    ) &&
    !disabled &&
    !resolveMutation.isPending

  return (
    <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div>
        <h3 className="font-medium text-slate-900">
          {useRepositoryPrefill &&
          repositoryPrefill
            ? "审查该仓库的 Pull Request"
            : "从 Pull Request / Merge Request 导入"}
        </h3>

        <p className="mt-1 text-sm leading-6 text-slate-500">
          {useRepositoryPrefill &&
          repositoryPrefill
            ? "仓库信息已经从仓库分析任务自动带入，只需要填写 Pull Request 编号。"
            : "支持公开 GitHub PR 和 GitLab MR。导入成功后会自动填充 Git Diff，不会保存访问令牌。"}
        </p>
      </div>

      {useRepositoryPrefill &&
      repositoryPrefill ? (
        <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-medium text-blue-600">
                来自仓库分析
              </div>

              <div className="mt-1 break-all font-medium text-slate-900">
                {formatRepositoryReviewName(
                  repositoryPrefill,
                )}
              </div>

              <a
                href={
                  repositoryPrefill
                    .repositoryUrl
                }
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex break-all text-sm text-blue-600 hover:underline"
              >
                {
                  repositoryPrefill
                    .repositoryUrl
                }
              </a>

              {repositoryPrefill
                .resolvedCommitSha ? (
                <div className="mt-2 font-mono text-xs text-slate-500">
                  分析 Commit：
                  {repositoryPrefill
                    .resolvedCommitSha
                    .slice(0, 12)}
                </div>
              ) : null}
            </div>

            <button
              type="button"
              disabled={disabled}
              onClick={
                handleUseDifferentRepository
              }
              className="rounded-lg border border-blue-200 bg-white px-3 py-1.5 text-sm text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              更换仓库
            </button>
          </div>
        </div>
      ) : null}

      <form
        className="mt-4 flex flex-col gap-3 sm:flex-row"
        onSubmit={handleSubmit}
      >
        {useRepositoryPrefill &&
        repositoryPrefill ? (
          <div className="flex min-w-0 flex-1 items-center overflow-hidden rounded-lg border border-slate-300 bg-white focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100">
            <span className="border-r border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
              PR #
            </span>

            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              aria-label="Pull Request 编号"
              value={
                pullRequestNumber
              }
              onChange={(event) => {
                setPullRequestNumber(
                  event.target.value.replace(
                    /\D/g,
                    "",
                  ),
                )

                setInputError(null)

                if (
                  resolveMutation.isError
                ) {
                  resolveMutation.reset()
                }
              }}
              placeholder="例如：123"
              disabled={
                disabled ||
                resolveMutation.isPending
              }
              className="min-w-0 flex-1 px-3 py-2 text-sm text-slate-900 outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
            />
          </div>
        ) : (
          <input
            type="url"
            value={sourceUrl}
            onChange={(event) => {
              setSourceUrl(
                event.target.value,
              )

              setInputError(null)

              if (
                resolveMutation.isError
              ) {
                resolveMutation.reset()
              }
            }}
            placeholder={
              "https://github.com/" +
              "owner/repo/pull/123"
            }
            disabled={
              disabled ||
              resolveMutation.isPending
            }
            className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus-within:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100"
          />
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {resolveMutation.isPending
            ? "正在获取变更…"
            : "获取变更"}
        </button>
      </form>

      {repositoryPrefill &&
      !useRepositoryPrefill &&
      !resolvedSource ? (
        <button
          type="button"
          className="mt-3 text-sm font-medium text-blue-600 hover:underline"
          onClick={
            handleRestoreRepositoryPrefill
          }
        >
          恢复使用仓库分析中的仓库
        </button>
      ) : null}

      {inputError ? (
        <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {inputError}
        </div>
      ) : resolveMutation.isError ? (
        <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {formatSourceApiError(
            resolveMutation.error,
          )}
        </div>
      ) : null}

      {resolvedSource ? (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={[
                    "rounded-full border",
                    "px-2.5 py-1",
                    "text-xs font-medium",
                    getProviderClassName(
                      resolvedSource
                        .provider,
                    ),
                  ].join(" ")}
                >
                  {formatCodeReviewSourceLabel(
                    resolvedSource,
                  )}
                </span>

                <span className="text-xs text-emerald-700">
                  已导入
                </span>
              </div>

              <div className="mt-3 font-medium text-slate-900">
                {resolvedSource.title}
              </div>

              <div className="mt-1 break-all text-sm text-slate-600">
                {
                  resolvedSource
                    .repository
                }
              </div>
            </div>

            <button
              type="button"
              onClick={handleClear}
              disabled={disabled}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              清除来源
            </button>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">
                分支
              </div>

              <div className="mt-1 break-all text-slate-800">
                {
                  resolvedSource
                    .head_ref
                }
                {" → "}
                {
                  resolvedSource
                    .base_ref
                }
              </div>
            </div>

            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">
                作者
              </div>

              <div className="mt-1 text-slate-800">
                {
                  resolvedSource
                    .author ||
                  "未知"
                }
              </div>
            </div>

            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">
                Diff 大小
              </div>

              <div className="mt-1 text-slate-800">
                {formatDiffSize(
                  resolvedSource
                    .diff_text,
                )}
              </div>
            </div>

            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">
                获取时间
              </div>

              <div className="mt-1 text-slate-800">
                {formatSourceDateTime(
                  resolvedSource
                    .fetched_at,
                )}
              </div>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-500">
            <div className="break-all">
              Base：
              {resolvedSource.base_sha.slice(
                0,
                12,
              )}
            </div>

            <div className="break-all">
              Head：
              {resolvedSource.head_sha.slice(
                0,
                12,
              )}
            </div>

            <div className="break-all">
              Diff：
              {resolvedSource.diff_hash.slice(
                0,
                12,
              )}
            </div>
          </div>

          <a
            href={
              resolvedSource
                .source_url
            }
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex text-sm font-medium text-blue-600 hover:underline"
          >
            打开原始 PR/MR
          </a>
        </div>
      ) : null}
    </section>
  )
}