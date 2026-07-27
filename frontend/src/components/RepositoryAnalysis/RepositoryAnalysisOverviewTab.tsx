import type {
  RepositoryAnalysisTaskPublic,
} from "@/client"

import {
  RepositoryAnalysisJsonView,
} from "./RepositoryAnalysisJsonView"

export function RepositoryAnalysisOverviewTab({
  task,
}: {
  task: RepositoryAnalysisTaskPublic
}) {
  return (
    <RepositoryAnalysisJsonView
      value={task.result_json}
      emptyTitle="暂无仓库概览"
      emptyDescription={
        task.status === "completed"
          ? "任务已经完成，但没有返回结构化概览。"
          : "仓库分析完成后，这里将展示项目结构、技术栈和模块信息。"
      }
    />
  )
}