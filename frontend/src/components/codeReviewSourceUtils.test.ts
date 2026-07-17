import {
  describe,
  expect,
  test,
} from "bun:test"

import type {
  CodeReviewSourceResolvedPublic,
} from "@/client"

import {
  formatCodeReviewSourceLabel,
  toCodeReviewSourceSnapshot,
} from "./codeReviewSourceUtils"

const buildResolvedSource =
  (): CodeReviewSourceResolvedPublic => ({
    provider: "github",

    source_url:
      "https://github.com/example/project/pull/12",

    repository: "example/project",
    change_number: 12,

    title:
      "Fix authentication validation",

    author: "example-user",

    base_ref: "main",

    head_ref:
      "fix/auth-validation",

    base_sha:
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",

    head_sha:
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",

    diff_hash:
      "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",

    fetched_at:
      "2026-07-15T12:00:00Z",

    diff_text:
      "diff --git a/app.py b/app.py\n" +
      "--- a/app.py\n" +
      "+++ b/app.py\n",
  })

describe(
  "codeReviewSourceUtils",
  () => {
    test(
      "removes diff text from source snapshot",
      () => {
        const resolvedSource =
          buildResolvedSource()

        const snapshot =
          toCodeReviewSourceSnapshot(
            resolvedSource,
          )

        expect(
          "diff_text" in snapshot,
        ).toBe(false)

        expect(snapshot.provider).toBe(
          "github",
        )

        expect(
          snapshot.repository,
        ).toBe("example/project")

        expect(
          snapshot.change_number,
        ).toBe(12)

        expect(
          snapshot.diff_hash,
        ).toBe(
          resolvedSource.diff_hash,
        )
      },
    )

    test(
      "formats github source label",
      () => {
        const label =
          formatCodeReviewSourceLabel(
            buildResolvedSource(),
          )

        expect(label).toBe(
          "GitHub PR #12",
        )
      },
    )

    test(
      "formats gitlab source label",
      () => {
        const source = {
          ...buildResolvedSource(),

          provider:
            "gitlab" as const,

          source_url:
            "https://gitlab.com/example/project/-/merge_requests/8",

          change_number: 8,
        }

        const label =
          formatCodeReviewSourceLabel(
            source,
          )

        expect(label).toBe(
          "GitLab MR !8",
        )
      },
    )
  },
)