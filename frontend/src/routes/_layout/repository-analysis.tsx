import { createFileRoute } from "@tanstack/react-router"

import { RepositoryAnalysisWorkbench } from "@/components/RepositoryAnalysis/RepositoryAnalysisWorkbench"

export const Route = createFileRoute("/_layout/repository-analysis")({
  component: RepositoryAnalysisPage,
  head: () => ({
    meta: [
      {
        title: "仓库分析 - RepoGuard",
      },
    ],
  }),
})

function RepositoryAnalysisPage() {
  return <RepositoryAnalysisWorkbench />
}
