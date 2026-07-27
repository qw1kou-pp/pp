# Repository Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build real-GitHub acceptance tests and a reusable CLI runner that validate repository compatibility, fixed-commit provenance, RAG/Agent source isolation, and history isolation.

**Architecture:** Keep repository cases and acceptance data structures independent of HTTP details. Add a retrying HTTP client, then compose it in a runner that records stage timings and delegates all validation to pure assertion functions. Reuse the runner from pytest and a CLI, and publish JSON/Markdown reports in GitHub Actions.

**Tech Stack:** Python 3.13, pytest, httpx, dataclasses, FastAPI HTTP API, Docker Compose, GitHub Actions.

## Global Constraints

- All repository analysis uses live public GitHub repositories.
- `GITHUB_TOKEN` is required and must never be written to reports or logs.
- Resolve the default branch HEAD at run time; do not hard-code Commit SHA values.
- Retry network requests at most 3 times with 1, 2, and 4 second delays.
- A final network or rate-limit failure fails the acceptance case.
- PR runs smoke cases; weekly and manual workflows can run the complete matrix.
- Acceptance files live under `backend/tests/repository_acceptance/`.

---

### Task 1: Acceptance data model and repository matrix

**Files:**
- Create: `backend/tests/repository_acceptance/acceptance_models.py`
- Create: `backend/tests/repository_acceptance/repository_matrix.py`
- Create: `backend/tests/repository_acceptance/acceptance_assertions.py`
- Test: `backend/tests/repository_acceptance/test_acceptance_models.py`
- Test: `backend/tests/repository_acceptance/test_repository_matrix.py`
- Test: `backend/tests/repository_acceptance/test_acceptance_assertions.py`

**Interfaces:**
- Produces: `RepositoryCase`, `AcceptanceRunResult`, `SourceEvidence`, `AssertionResult`, `REPOSITORY_MATRIX`, `get_repository_case()`, `get_smoke_cases()`, `assert_commit_present()`, and `assert_sources_match_scope()`.

- [ ] Write model, matrix, and source-scope tests before implementation.
- [ ] Run the three tests and confirm import failures because the modules do not exist.
- [ ] Implement the minimal typed data structures, four approved repository cases, and pure source assertions.
- [ ] Run the three tests and confirm all pass.
- [ ] Commit with `test: add repository acceptance foundations`.

### Task 2: Retrying acceptance HTTP client

**Files:**
- Create: `backend/tests/repository_acceptance/acceptance_client.py`
- Create: `backend/tests/repository_acceptance/test_acceptance_client.py`

**Interfaces:**
- Consumes: `RepositoryCase`.
- Produces: `AcceptanceClient`, `AcceptanceApiError`, `RetryPolicy`, authentication, repository-task creation/read/save, knowledge-base creation, deep-import start/read, RAG chat, Agent chat, and history reads.

- [ ] Inspect current repository-analysis and document route operation paths before writing the client.
- [ ] Write a test server that fails twice then succeeds and assert attempts occur after configured delays.
- [ ] Run the test and confirm `AcceptanceClient` is missing.
- [ ] Implement `RetryPolicy(max_attempts=3, delays_seconds=(1.0, 2.0, 4.0))` and an `httpx.Client` wrapper that retries transport errors and 502/503/504 responses, while mapping 403 rate-limit responses to `GITHUB_RATE_LIMITED`.
- [ ] Add endpoint methods using the exact paths found in the current route files.
- [ ] Run client tests and the existing backend unit suite.
- [ ] Commit with `test: add retrying repository acceptance client`.

### Task 3: End-to-end acceptance runner

**Files:**
- Create: `backend/tests/repository_acceptance/acceptance_runner.py`
- Create: `backend/tests/repository_acceptance/test_acceptance_runner.py`

**Interfaces:**
- Consumes: `AcceptanceClient`, `RepositoryCase`.
- Produces: `RepositoryAcceptanceRunner.run(case) -> AcceptanceRunResult`.

- [ ] Write a test with a deterministic in-process fake client that records the expected call order.
- [ ] Confirm the test fails because the runner is missing.
- [ ] Implement stages: create overview task, poll terminal status, save task, create/select knowledge base, start deep import, poll import/index readiness, execute each RAG/Agent question, read scoped histories, and read final task details twice.
- [ ] Record stage start/end times and map terminal backend errors to `AcceptanceFailureCode`.
- [ ] Run runner tests.
- [ ] Commit with `test: add repository acceptance runner`.

### Task 4: Assertions and reproducibility checks

**Files:**
- Modify: `backend/tests/repository_acceptance/acceptance_assertions.py`
- Create: `backend/tests/repository_acceptance/test_repository_reproducibility.py`
- Create: `backend/tests/repository_acceptance/test_repository_isolation.py`

**Interfaces:**
- Produces: assertions for task completion, report presence, repeated-read equality, RAG source scope, Agent source scope, RAG history scope, Agent history scope, and cross-repository isolation.

- [ ] Write failing tests for missing Commit, changed task result between two reads, foreign task IDs, foreign Commit SHAs, and empty source paths.
- [ ] Implement one pure assertion per behavior, returning `AssertionResult` rather than raising immediately.
- [ ] Aggregate results and mark the case failed when any required assertion fails.
- [ ] Run assertion and runner tests.
- [ ] Commit with `test: validate repository scope and reproducibility`.

### Task 5: JSON and Markdown reports

**Files:**
- Create: `backend/tests/repository_acceptance/acceptance_report.py`
- Create: `backend/tests/repository_acceptance/test_acceptance_report.py`

**Interfaces:**
- Consumes: `Sequence[AcceptanceRunResult]`.
- Produces: `write_json_report()` and `write_markdown_report()`.

- [ ] Write failing tests asserting enums, nested sources, timings, failures, and assertion results are serialized.
- [ ] Implement UTF-8 JSON output and a Markdown summary table followed by per-repository details.
- [ ] Ensure secrets and authorization headers are never accepted by report model types.
- [ ] Run report tests.
- [ ] Commit with `test: add repository acceptance reports`.

### Task 6: pytest live-GitHub entry points

**Files:**
- Create: `backend/tests/repository_acceptance/conftest.py`
- Create: `backend/tests/repository_acceptance/test_repository_smoke.py`
- Create: `backend/tests/repository_acceptance/test_repository_matrix.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Produces pytest markers `repository_smoke`, `repository_matrix`, `repository_isolation`, and `repository_reproducibility`.

- [ ] Add fixtures that require `GITHUB_TOKEN`, base URL, test-user credentials, and running backend/worker services.
- [ ] Parametrize smoke tests with `get_smoke_cases()` and matrix tests with `get_all_cases()`.
- [ ] Fail rather than skip when required live-test environment variables are missing in CI; allow an explicit local collection guard through `RUN_REPOSITORY_ACCEPTANCE=1`.
- [ ] Run collection locally and one live smoke repository against Docker Compose.
- [ ] Commit with `test: add live repository acceptance tests`.

### Task 7: Local CLI runner

**Files:**
- Create: `backend/scripts/run_repository_acceptance.py`
- Create: `backend/tests/repository_acceptance/test_acceptance_cli.py`

**Interfaces:**
- Produces CLI options `--repository KEY`, `--smoke`, `--all`, `--base-url`, and `--output-dir`.

- [ ] Write parser tests for mutually exclusive selection modes.
- [ ] Implement CLI environment validation, runner invocation, report creation, and non-zero exit on failed assertions.
- [ ] Run CLI help and parser tests.
- [ ] Commit with `test: add repository acceptance CLI`.

### Task 8: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/repository-acceptance.yml`

**Interfaces:**
- Consumes: Docker Compose services, `GITHUB_TOKEN`, acceptance CLI.
- Produces PR smoke, weekly matrix, and manual selection workflows with uploaded reports.

- [ ] Add `pull_request`, Monday 02:00 UTC schedule, and `workflow_dispatch` inputs.
- [ ] Build and start database, backend, repository worker, recovery worker, snapshot cleaner, and frontend dependencies required by the API flow.
- [ ] Wait on service health checks before acceptance execution.
- [ ] Execute smoke or matrix selection based on event type.
- [ ] Always upload `artifacts/repository-acceptance/` and relevant service logs.
- [ ] Validate workflow YAML and run a manual smoke workflow.
- [ ] Commit with `ci: run live repository acceptance matrix`.
