from __future__ import annotations

from tests.repository_acceptance.acceptance_models import (
    RepositoryCase,
    RepositoryCategory,
)


REPOSITORY_MATRIX: tuple[RepositoryCase, ...] = (
    RepositoryCase(
        key="requests",
        repository_url="https://github.com/psf/requests",
        category=RepositoryCategory.PYTHON,
        smoke=True,
        questions=(
            "这个项目的主要入口、核心模块和请求发送流程是什么？",
            "请求发送流程涉及哪些主要函数和文件？",
        ),
        task_timeout_seconds=1800,
    ),
    RepositoryCase(
        key="fastapi",
        repository_url="https://github.com/fastapi/fastapi",
        category=RepositoryCategory.FASTAPI,
        smoke=False,
        questions=(
            "这个仓库的核心包结构和主要入口是什么？",
            "FastAPI 路由、依赖注入和数据模型分别由哪些模块负责？",
        ),
        task_timeout_seconds=3600,
        deep_import_timeout_seconds=3600,
        embedding_timeout_seconds=3600,
    ),
    RepositoryCase(
        key="zustand",
        repository_url="https://github.com/pmndrs/zustand",
        category=RepositoryCategory.REACT_TYPESCRIPT,
        smoke=False,
        questions=(
            "这个 TypeScript 项目的主要入口和核心状态管理实现在哪里？",
            "React Hooks、类型定义和导出结构分别位于哪些文件？",
        ),
        task_timeout_seconds=2400,
    ),
    RepositoryCase(
        key="full-stack-fastapi-template",
        repository_url=(
            "https://github.com/fastapi/full-stack-fastapi-template"
        ),
        category=RepositoryCategory.FULL_STACK,
        smoke=True,
        questions=(
            "这个前后端一体化项目的目录结构和主要启动入口是什么？",
            "前端请求如何到达 FastAPI 路由并继续进入服务和数据库层？",
        ),
        task_timeout_seconds=3000,
        deep_import_timeout_seconds=3000,
        embedding_timeout_seconds=3000,
    ),
)


def get_repository_case(key: str) -> RepositoryCase:
    normalized_key = key.strip().lower()

    for case in REPOSITORY_MATRIX:
        if case.key == normalized_key:
            return case

    available = ", ".join(case.key for case in REPOSITORY_MATRIX)
    raise KeyError(
        f"Unknown repository case {key!r}. Available cases: {available}"
    )


def get_smoke_cases() -> tuple[RepositoryCase, ...]:
    return tuple(case for case in REPOSITORY_MATRIX if case.smoke)


def get_all_cases() -> tuple[RepositoryCase, ...]:
    return REPOSITORY_MATRIX
