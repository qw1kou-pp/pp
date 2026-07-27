# RepoGuard

RepoGuard is a full-stack FastAPI + React platform for pulling GitHub repositories into a project workspace, running an initial repository analysis, and then turning selected repositories into knowledge-base material for deeper RAG/Agent-style exploration.

The intended workflow is simple:

1. Paste a GitHub repository URL.
2. Let the backend clone, snapshot, and analyze the repository.
3. Review the initial analysis and decide whether the project is worth deeper study.
4. Import selected repository content into a knowledge base.
5. Generate embeddings and ask questions about the project through RAG or Agent tools.

## Features

- GitHub repository submission and asynchronous analysis tasks.
- Repository analysis worker with lease, retry, recovery, and fault-injection acceptance support.
- Knowledge-base management for uploaded documents and repository imports.
- RAG chat and Agent chat surfaces for project-level Q&A.
- Code-review comparison workspace for structured review results.
- Admin/user authentication based on the original FastAPI full-stack template.
- Docker Compose development stack with PostgreSQL, backend, worker, frontend, Adminer, and Mailcatcher.

## Tech Stack

- Backend: FastAPI, SQLModel, Alembic, PostgreSQL, Pytest.
- Frontend: React, TypeScript, Vite, TanStack Router, Tailwind CSS, shadcn-style components.
- Runtime: Docker Compose for the full local stack.
- Package tools: `uv` for Python and `bun` for frontend scripts.

## Requirements

- Docker Desktop with Docker Compose.
- Git.
- Optional for local development without Docker: Python 3.10+, `uv`, and `bun`.

## Quick Start

```bash
git clone <your-repository-url>
cd full-stack-fastapi-template-master
cp .env.example .env
docker compose up --build
```

After the services are ready:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Adminer: http://localhost:8080
- Mailcatcher: http://localhost:1080

Default local admin account from `.env.example`:

- Email: `admin@example.com`
- Password: `changethis`

Change these values in `.env` before exposing the project outside your local machine.

## Optional Configuration

Public GitHub repositories can be analyzed without a token, but GitHub rate limits will be stricter. Add this when needed:

```env
GITHUB_TOKEN=github_pat_xxx
```

RAG, Agent answers, and embedding generation require provider settings that match your backend configuration:

```env
LLM_API_KEY=
LLM_API_BASE=
LLM_MODEL=
EMBEDDING_API_KEY=
EMBEDDING_API_BASE=
EMBEDDING_MODEL=
```

Keep secrets only in `.env` or your deployment secret manager. Do not commit `.env`.

## First Run Workflow

1. Open http://localhost:5173 and log in.
2. Go to the repository analysis page.
3. Submit a public GitHub repository URL.
4. Wait for the repository analysis worker to finish the task.
5. Review the project summary, dependency hints, file statistics, and analysis status.
6. If the project is interesting, import or bind the repository content into a knowledge base.
7. Generate embeddings for the knowledge base.
8. Ask project questions through the knowledge-base RAG or Agent chat interface.

## Useful Commands

Start the full development stack:

```bash
docker compose up --build
```

View service status:

```bash
docker compose ps
```

Follow backend and repository worker logs:

```bash
docker compose logs -f backend repository-analysis-worker
```

Stop services:

```bash
docker compose down
```

Stop services and remove local database volumes:

```bash
docker compose down -v
```

Build the frontend locally:

```bash
cd frontend
bun run build
```

Check backend import and Alembic configuration locally:

```bash
cd backend
uv run python -c "import app.main"
uv run alembic check
```

Validate Docker Compose configuration:

```bash
docker compose -f compose.yml -f compose.override.yml config --quiet
```

Run repository recovery acceptance compose validation:

```bash
docker compose -f compose.yml -f docker-compose.repository-recovery.yml --profile acceptance config --quiet
```

## GitHub Upload Checklist

- Commit `.env.example`, not `.env`.
- Do not commit `backend/storage/`, local repository snapshots, database dumps, `secrets/`, or generated reports.
- Keep API keys and tokens in local `.env` files or GitHub Actions secrets.
- Run the frontend build and backend checks before pushing important changes.
- Update this README whenever the startup flow, required variables, or service ports change.

## Notes

This project started from the FastAPI full-stack template, but the current application is focused on GitHub repository analysis and knowledge-base driven project understanding.
