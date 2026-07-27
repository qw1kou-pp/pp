import { useCallback, useState } from "react"

import type { RepositoryAnalysisTaskPublic } from "@/client"

import { RepositoryAnalysisCreateForm } from "./RepositoryAnalysisCreateForm"
import {
  type RepositoryAnalysisDetailTab,
  RepositoryAnalysisTaskDetail,
} from "./RepositoryAnalysisTaskDetail"
import { RepositoryAnalysisTaskList } from "./RepositoryAnalysisTaskList"

const repositoryAnalysisSelectedTaskStorageKey =
  "repoguard.repository-analysis.selected-task-id"

export function RepositoryAnalysisWorkbench() {
  const [preferredTaskId, setPreferredTaskId] =
    useState<string | null>(() =>
      readStoredRepositoryAnalysisTaskId(),
    )

  const [selectedTaskId, setSelectedTaskId] =
    useState<string | null>(null)

  const [activeTab, setActiveTab] =
    useState<RepositoryAnalysisDetailTab>("progress")

  const handleSelectTask = useCallback((taskId: string) => {
    setPreferredTaskId(taskId)
    setSelectedTaskId(taskId)
    setActiveTab("progress")
    storeRepositoryAnalysisTaskId(taskId)
  }, [])

  const handleClearSelection = useCallback(() => {
    setPreferredTaskId(null)
    setSelectedTaskId(null)
    setActiveTab("progress")
    storeRepositoryAnalysisTaskId(null)
  }, [])

  const handleTaskCreated = useCallback(
    (task: RepositoryAnalysisTaskPublic) => {
      handleSelectTask(task.id)
    },
    [handleSelectTask],
  )

  return (
    <div className="space-y-6">
      <PageHeader />

      <RepositoryAnalysisCreateForm
        onCreated={handleTaskCreated}
      />

      <div className="grid gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]">
        <RepositoryAnalysisTaskList
          preferredTaskId={preferredTaskId}
          selectedTaskId={selectedTaskId}
          onSelectTask={handleSelectTask}
          onClearSelection={handleClearSelection}
        />

        <RepositoryAnalysisTaskDetail
          selectedTaskId={selectedTaskId}
          activeTab={activeTab}
          onActiveTabChange={setActiveTab}
        />
      </div>
    </div>
  )
}

function readStoredRepositoryAnalysisTaskId(): string | null {
  if (typeof window === "undefined") {
    return null
  }

  try {
    const taskId = window.localStorage
      .getItem(repositoryAnalysisSelectedTaskStorageKey)
      ?.trim()

    return taskId || null
  } catch {
    return null
  }
}

function storeRepositoryAnalysisTaskId(
  taskId: string | null,
): void {
  if (typeof window === "undefined") {
    return
  }

  try {
    if (taskId) {
      window.localStorage.setItem(
        repositoryAnalysisSelectedTaskStorageKey,
        taskId,
      )
      return
    }

    window.localStorage.removeItem(
      repositoryAnalysisSelectedTaskStorageKey,
    )
  } catch {
    // localStorage 不可用时仍允许页面继续使用内存状态。
  }
}

function PageHeader() {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold tracking-tight">
        GitHub 仓库分析
      </h1>

      <p className="max-w-3xl text-sm text-muted-foreground">
        提交公开 GitHub 仓库，后台将解析固定 Commit、
        扫描项目结构、分析前后端流程，并生成带 Evidence
        的仓库概览报告。
      </p>
    </div>
  )
}