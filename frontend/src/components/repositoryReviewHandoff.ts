export const repositoryReviewSource =
  "repository-analysis" as const

export type CodeReviewRepositoryPrefill = {
  repositoryOwner: string
  repositoryName: string
  repositoryUrl: string
  resolvedCommitSha?: string | null
}

export function buildGitHubPullRequestUrl(
  repository:
    CodeReviewRepositoryPrefill,
  pullRequestNumber: string | number,
): string {
  const normalizedNumber = String(
    pullRequestNumber,
  ).trim()

  if (
    !/^[1-9]\d*$/.test(
      normalizedNumber,
    )
  ) {
    throw new Error(
      "请输入有效的 Pull Request 编号",
    )
  }

  const owner =
    repository.repositoryOwner.trim()

  const name =
    repository.repositoryName.trim()

  if (!owner || !name) {
    throw new Error(
      "仓库 owner 或仓库名称缺失",
    )
  }

  return [
    "https://github.com",
    encodeURIComponent(owner),
    encodeURIComponent(name),
    "pull",
    normalizedNumber,
  ].join("/")
}

export function formatRepositoryReviewName(
  repository:
    CodeReviewRepositoryPrefill,
): string {
  return [
    repository.repositoryOwner,
    repository.repositoryName,
  ].join("/")
}