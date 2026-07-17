import {
  useMutation,
} from "@tanstack/react-query"
import {
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

type CodeReviewSourceImportPanelProps = {
  knowledgeBaseId: string

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
  resolvedSource,
  disabled = false,
  onResolved,
  onClear,
}: CodeReviewSourceImportPanelProps) {
  const [
    sourceUrl,
    setSourceUrl,
  ] = useState("")

  const resolveMutation =
    useMutation({
      mutationFn: () =>
        CodeSkillService
          .resolveCodeReviewSource({
            knowledgeBaseId,

            requestBody: {
              source_url:
                sourceUrl.trim(),
            },
          }),

      onSuccess: (source) => {
        setSourceUrl(
          source.source_url,
        )

        onResolved(source)
      },
    })

  const handleSubmit = (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()

    if (
      !sourceUrl.trim() ||
      disabled ||
      resolveMutation.isPending
    ) {
      return
    }

    resolveMutation.reset()
    resolveMutation.mutate()
  }

  const handleClear = () => {
    setSourceUrl("")
    resolveMutation.reset()
    onClear()
  }

  const canSubmit =
    Boolean(sourceUrl.trim()) &&
    !disabled &&
    !resolveMutation.isPending

  return (
    <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div>
        <h3 className="font-medium text-slate-900">
          从 Pull Request / Merge
          Request 导入
        </h3>

        <p className="mt-1 text-sm leading-6 text-slate-500">
          支持公开 GitHub PR 和
          GitLab MR。导入成功后会自动填充
          Git Diff，不会保存访问令牌。
        </p>
      </div>

      <form
        className="mt-4 flex flex-col gap-3 sm:flex-row"
        onSubmit={handleSubmit}
      >
        <input
          type="url"
          value={sourceUrl}
          onChange={(event) => {
            setSourceUrl(
              event.target.value,
            )

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
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100"
        />

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

      {resolveMutation.isError ? (
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