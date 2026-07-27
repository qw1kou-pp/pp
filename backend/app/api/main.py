from fastapi import APIRouter

from app.api.routes import items, knowledge_bases, login, private, users, utils, documents, code_skill, repository_analyses
from app.core.config import settings

#总路由
api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(documents.router)
api_router.include_router(code_skill.router)
api_router.include_router(
    repository_analyses.router,
)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
