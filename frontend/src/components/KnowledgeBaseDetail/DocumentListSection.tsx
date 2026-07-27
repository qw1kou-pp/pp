import {
  CollapsibleSection,
} from "./CollapsibleSection"
import {
  formatFileSize,
} from "./knowledgeBaseFormatters"
import type {
  KnowledgeBaseOverviewController,
} from "./useKnowledgeBaseOverview"

type Props = {
  overview:
    KnowledgeBaseOverviewController

  isOpen: boolean
  onToggle: () => void
}

export function DocumentListSection({
  overview,
  isOpen,
  onToggle,
}: Props) {
  const {
    documentsQuery,
  } = overview

  return (
    <CollapsibleSection
      title="文档列表"
      description="查看当前知识库中的文档、解析状态和切分结果。"
      isOpen={isOpen}
      onToggle={onToggle}
    >
      {documentsQuery.isPending ? (
        <p className="text-sm text-slate-600">
          正在加载文档列表...
        </p>
      ) : null}

      {documentsQuery.isError ? (
        <p className="whitespace-pre-wrap text-sm text-rose-600">
          文档列表加载失败：
          {formatError(
            documentsQuery.error,
          )}
        </p>
      ) : null}

      {documentsQuery.data ? (
        documentsQuery.data.data.length
        === 0 ? (
          <p className="text-sm text-slate-600">
            该知识库下暂无文档。
          </p>
        ) : (
          <div className="space-y-3">
            {documentsQuery.data.data.map(
              (document) => (
                <DocumentCard
                  key={document.id}
                  document={document}
                  overview={overview}
                />
              ),
            )}
          </div>
        )
      ) : null}
    </CollapsibleSection>
  )
}

type DocumentCardProps = {
  document: NonNullable<
    KnowledgeBaseOverviewController[
      "documentsQuery"
    ]["data"]
  >["data"][number]

  overview:
    KnowledgeBaseOverviewController
}

function DocumentCard({
  document,
  overview,
}: DocumentCardProps) {
  const isExpanded =
    overview.expandedDocumentId
    === document.id

  const isDeleting =
    overview.deleteDocumentMutation
      .isPending

  return (
    <article className="space-y-4 rounded-xl border border-slate-300 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <h3 className="break-all font-medium text-slate-900">
            {document.original_filename}
          </h3>

          <p className="text-sm text-slate-600">
            类型：
            {document.content_type
              || "未知"}
            {" ｜ "}
            大小：
            {formatFileSize(
              document.file_size,
            )}
            {" ｜ "}
            状态：
            {document.status}
          </p>

          {document.error_message ? (
            <p className="whitespace-pre-wrap text-sm text-rose-600">
              解析信息：
              {document.error_message}
            </p>
          ) : null}

          <p className="break-all font-mono text-xs text-slate-500">
            文档 ID：{document.id}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700"
            onClick={() => {
              overview
                .handleToggleDocument(
                  document.id,
                )
            }}
          >
            {isExpanded
              ? "收起切分结果"
              : "查看切分结果"}
          </button>

          <button
            type="button"
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:text-sky-700"
            onClick={() => {
              void overview
                .handleDownloadDocument(
                  document.id,
                  document.original_filename,
                )
            }}
          >
            下载
          </button>

          <button
            type="button"
            className="rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-sm font-medium text-rose-600 shadow-sm transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => {
              overview
                .handleDeleteDocument(
                  document.id,
                )
            }}
            disabled={isDeleting}
          >
            删除
          </button>
        </div>
      </div>

      {isExpanded ? (
        <DocumentChunks
          overview={overview}
        />
      ) : null}
    </article>
  )
}

function DocumentChunks({
  overview,
}: {
  overview:
    KnowledgeBaseOverviewController
}) {
  const {
    chunksQuery,
  } = overview

  return (
    <div className="space-y-3 border-t pt-4">
      <h4 className="font-medium text-slate-900">
        切分结果
      </h4>

      {chunksQuery.isPending ? (
        <p className="text-sm text-slate-600">
          正在加载切分结果...
        </p>
      ) : null}

      {chunksQuery.isError ? (
        <p className="whitespace-pre-wrap text-sm text-rose-600">
          切分结果加载失败：
          {formatError(
            chunksQuery.error,
          )}
        </p>
      ) : null}

      {chunksQuery.data ? (
        chunksQuery.data.data.length
        === 0 ? (
          <p className="text-sm leading-6 text-slate-600">
            暂无切分结果。可能是文件未解析成功、
            内容为空，或 PDF 是扫描版图片。
          </p>
        ) : (
          <div className="space-y-3">
            {chunksQuery.data.data.map(
              (chunk) => (
                <article
                  key={chunk.id}
                  className="space-y-2 rounded-lg border border-slate-300 bg-slate-50 p-3 text-slate-900"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h5 className="text-sm font-medium">
                      Chunk {
                        chunk.chunk_index
                      }
                    </h5>

                    <span className="text-xs text-slate-500">
                      长度：
                      {
                        chunk
                          .content_length
                      }
                    </span>
                  </div>

                  <pre className="whitespace-pre-wrap break-words font-sans text-sm text-slate-900">
                    {chunk.content}
                  </pre>
                </article>
              ),
            )}
          </div>
        )
      ) : null}
    </div>
  )
}

function formatError(
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
