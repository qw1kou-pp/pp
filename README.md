# RepoGuard

RepoGuard 是一个基于 FastAPI + React 的 GitHub 仓库分析与知识库平台。它的目标是帮助你把感兴趣的 GitHub 项目拉取到本地平台中，先做初步分析，再把值得深入研究的项目导入知识库，后续通过 RAG 或 Agent 对项目进行更细致的理解和问答。

核心使用流程：

1. 输入一个 GitHub 仓库地址。
2. 后端自动拉取、快照并分析仓库。
3. 查看项目初步分析结果，判断这个项目是否值得继续研究。
4. 将选中的仓库内容导入知识库。
5. 生成向量索引。
6. 通过 RAG 或 Agent 继续提问，比如项目是做什么的、依赖什么、有哪些功能、代码结构如何。

## 功能

- 提交 GitHub 仓库地址并创建异步分析任务。
- 仓库分析 Worker，支持租约、重试、恢复和故障注入验收测试。
- 知识库管理，支持上传文档和导入仓库内容。
- RAG 聊天和 Agent 聊天，用于围绕项目内容进行问答。
- 代码审查对比工作台，用于查看结构化 review 结果。
- 基于原 FastAPI 全栈模板的用户登录、管理员和权限体系。
- Docker Compose 本地开发环境，包含 PostgreSQL、后端、Worker、前端、Adminer 和 Mailcatcher。

## 技术栈

- 后端：FastAPI、SQLModel、Alembic、PostgreSQL、Pytest。
- 前端：React、TypeScript、Vite、TanStack Router、Tailwind CSS、shadcn 风格组件。
- 运行环境：Docker Compose。
- 包管理工具：后端使用 `uv`，前端使用 `bun`。

## 环境要求

- Docker Desktop，并支持 Docker Compose。
- Git。
- 可选本地开发工具：Python 3.10+、`uv`、`bun`。

## 快速启动

```bash
git clone <你的仓库地址>
cd full-stack-fastapi-template-master
cp .env.example .env
docker compose up --build
```

服务启动后可以访问：

- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs
- Adminer：http://localhost:8080
- Mailcatcher：http://localhost:1080

`.env.example` 中默认的本地管理员账号：

- 邮箱：`admin@example.com`
- 密码：`changethis`

如果要部署到公网，请务必修改 `.env` 中的 `SECRET_KEY`、`FIRST_SUPERUSER_PASSWORD`、`POSTGRES_PASSWORD` 等敏感配置。

## 可选配置

公开 GitHub 仓库可以不配置 Token 直接分析，但 GitHub API 会有更严格的限流。建议按需配置：

```env
GITHUB_TOKEN=github_pat_xxx
```

RAG、Agent 回答和向量生成需要配置对应的大模型与 Embedding 服务：

```env
LLM_API_KEY=
LLM_API_BASE=
LLM_MODEL=
EMBEDDING_API_KEY=
EMBEDDING_API_BASE=
EMBEDDING_MODEL=
```

请只把真实密钥放在本地 `.env` 或部署平台的 Secret Manager 中，不要提交到 GitHub。

## 第一次使用流程

1. 打开 http://localhost:5173 并登录。
2. 进入仓库分析页面。
3. 输入一个公开的 GitHub 仓库地址。
4. 等待仓库分析 Worker 完成任务。
5. 查看项目摘要、依赖信息、文件统计和分析状态。
6. 如果这个项目值得深入研究，将仓库内容导入或绑定到知识库。
7. 为知识库生成 Embedding。
8. 在知识库的 RAG 或 Agent 聊天界面继续提问。

## 常用命令

启动完整开发环境：

```bash
docker compose up --build
```

查看服务状态：

```bash
docker compose ps
```

查看后端和仓库分析 Worker 日志：

```bash
docker compose logs -f backend repository-analysis-worker
```

停止服务：

```bash
docker compose down
```

停止服务并删除本地数据库卷：

```bash
docker compose down -v
```

本地构建前端：

```bash
cd frontend
bun run build
```

本地检查后端入口和 Alembic 配置：

```bash
cd backend
uv run python -c "import app.main"
uv run alembic check
```

校验 Docker Compose 配置：

```bash
docker compose -f compose.yml -f compose.override.yml config --quiet
```

校验仓库恢复验收测试的 Compose 配置：

```bash
docker compose -f compose.yml -f docker-compose.repository-recovery.yml --profile acceptance config --quiet
```

## 上传 GitHub 前检查

- 提交 `.env.example`，不要提交 `.env`。
- 不要提交 `backend/storage/`、本地仓库快照、数据库 dump、`secrets/` 或生成的报告文件。
- API Key、GitHub Token、数据库密码等只放在本地 `.env` 或 GitHub Actions Secrets 中。
- 重要改动推送前，建议至少跑一次前端构建和后端配置检查。
- 如果启动方式、端口、环境变量发生变化，请同步更新 README。

## 说明

这个项目最初基于 FastAPI Full Stack Template，但当前业务重点已经调整为 GitHub 仓库分析、知识库管理和项目理解辅助。
