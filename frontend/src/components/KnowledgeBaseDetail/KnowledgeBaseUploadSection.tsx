import {
  formatFileSize,
} from "./knowledgeBaseFormatters"
import type {
  KnowledgeBaseOverviewController,
} from "./useKnowledgeBaseOverview"

type Props = {
  overview:
    KnowledgeBaseOverviewController
}

const DOCUMENT_ACCEPT = [
  ".pdf",
  ".txt",
  ".md",
  ".docx",
  ".py",
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".java",
  ".go",
  ".c",
  ".cpp",
  ".h",
  ".hpp",
  ".cs",
  ".rs",
  ".vue",
  ".html",
  ".css",
  ".scss",
  ".json",
  ".yaml",
  ".yml",
  ".toml",
  ".zip",
  ".rar",
  "application/zip",
  "application/x-zip-compressed",
  "application/x-rar-compressed",
  "application/vnd.rar",
].join(",")

const REPOSITORY_ARCHIVE_ACCEPT = [
  ".zip",
  ".rar",
  "application/zip",
  "application/x-rar-compressed",
  "application/vnd.rar",
].join(",")

export function KnowledgeBaseUploadSection({
  overview,
}: Props) {
  return (
    <section className="space-y-4 rounded-2xl border border-slate-600 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          上传与导入
        </h2>

        <p className="text-sm text-slate-600">
          支持上传普通文档、代码文件，
          也可以导入完整代码仓库压缩包。
        </p>
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={overview.fileInputRef}
            type="file"
            accept={DOCUMENT_ACCEPT}
            onChange={(event) => {
              overview.setSelectedFile(
                event.target.files?.[0]
                || null,
              )
            }}
          />

          <button
            type="button"
            className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={
              overview
                .handleUploadDocument
            }
            disabled={
              overview
                .uploadDocumentMutation
                .isPending
            }
          >
            {overview
              .uploadDocumentMutation
              .isPending
              ? "上传中..."
              : "上传"}
          </button>
        </div>

        {overview.selectedFile ? (
          <p className="text-sm text-slate-600">
            当前选择：
            {overview.selectedFile.name}
            ，大小：
            {formatFileSize(
              overview.selectedFile.size,
            )}
          </p>
        ) : null}

        {overview
          .uploadDocumentMutation
          .isError ? (
          <p className="whitespace-pre-wrap text-sm text-rose-600">
            上传失败：
            {formatMutationError(
              overview
                .uploadDocumentMutation
                .error,
            )}
          </p>
        ) : null}
      </div>

      <div className="space-y-3 border-t pt-4">
        <div>
          <h3 className="font-medium text-slate-900">
            导入代码仓库
          </h3>

          <p className="text-sm leading-6 text-slate-600">
            上传项目 ZIP 或 RAR。后端会忽略
            node_modules、.git、dist、build 等目录，
            并解析其中支持的代码文件。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={
              overview
                .repositoryZipInputRef
            }
            type="file"
            accept={
              REPOSITORY_ARCHIVE_ACCEPT
            }
            onChange={(event) => {
              overview
                .setSelectedRepositoryZip(
                  event.target.files?.[0]
                  || null,
                )
            }}
          />

          <button
            type="button"
            className="rounded-lg border border-slate-600 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={
              overview
                .handleUploadRepositoryZip
            }
            disabled={
              overview
                .uploadCodeRepositoryZipMutation
                .isPending
            }
          >
            {overview
              .uploadCodeRepositoryZipMutation
              .isPending
              ? "解析仓库中..."
              : "上传代码仓库"}
          </button>
        </div>

        {overview
          .selectedRepositoryZip ? (
          <p className="text-sm text-slate-600">
            当前选择：
            {
              overview
                .selectedRepositoryZip
                .name
            }
            ，大小：
            {formatFileSize(
              overview
                .selectedRepositoryZip
                .size,
            )}
          </p>
        ) : null}

        {overview
          .uploadCodeRepositoryZipMutation
          .isError ? (
          <p className="whitespace-pre-wrap text-sm text-rose-600">
            上传代码仓库失败：
            {formatMutationError(
              overview
                .uploadCodeRepositoryZipMutation
                .error,
            )}
          </p>
        ) : null}

        {overview
          .uploadCodeRepositoryZipMutation
          .data ? (
          <p className="text-sm text-emerald-700">
            代码仓库解析完成，共导入
            {" "}
            {
              overview
                .uploadCodeRepositoryZipMutation
                .data
                .count
            }
            {" "}
            个代码文件。
          </p>
        ) : null}
      </div>
    </section>
  )
}

function formatMutationError(
  error: unknown,
): string {
  if (error instanceof Error) {
    return error.message
  }

  try {
    return JSON.stringify(
      error,
      null,
      2,
    )
  } catch {
    return String(error)
  }
}
