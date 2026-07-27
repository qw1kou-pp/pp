import {
  Download,
  ScrollText,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import type {
  RepositoryAnalysisTaskPublic,
} from "@/client"
import { Button } from "@/components/ui/button"

export function RepositoryAnalysisReportTab({
  task,
}: {
  task: RepositoryAnalysisTaskPublic
}) {
  const report =
    task.report_markdown?.trim()

  if (!report) {
    return (
      <div className="flex min-h-64 flex-col items-center justify-center rounded-lg border border-dashed px-6 text-center">
        <ScrollText className="size-8 text-muted-foreground" />

        <h3 className="mt-4 font-medium">
          暂无分析报告
        </h3>

        <p className="mt-2 max-w-md text-sm text-muted-foreground">
          {task.status === "completed"
            ? "任务已经完成，但没有返回 Markdown 报告。"
            : "仓库分析完成后，这里将显示完整报告。"}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            downloadMarkdown(
              task.repository_full_name,
              report,
            )
          }}
        >
          <Download />
          下载 Markdown
        </Button>
      </div>

      <article className="prose max-w-none rounded-lg border p-6 dark:prose-invert">
        <ReactMarkdown
          remarkPlugins={[
            remarkGfm,
          ]}
        >
          {report}
        </ReactMarkdown>
      </article>
    </div>
  )
}

function downloadMarkdown(
  repositoryFullName: string,
  content: string,
) {
  const safeName =
    repositoryFullName
      .replace(
        /[^a-zA-Z0-9._-]+/g,
        "-",
      )
      .replace(
        /^-+|-+$/g,
        "",
      ) ||
    "repository-analysis"

  const blob = new Blob(
    [content],
    {
      type: "text/markdown;charset=utf-8",
    },
  )

  const url =
    URL.createObjectURL(blob)

  const anchor =
    document.createElement(
      "a",
    )

  anchor.href = url
  anchor.download =
    `${safeName}-analysis.md`

  document.body.appendChild(
    anchor,
  )

  anchor.click()
  anchor.remove()

  URL.revokeObjectURL(url)
}