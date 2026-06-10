from fastapi import APIRouter

from app.analyses.router import router as analyses_router
from app.auth.router import router as auth_router
from app.health.router import router as health_router
from app.notifications.router import router as notifications_router
from app.resumes.router import router as resumes_router
from app.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(analyses_router)
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(notifications_router)
api_router.include_router(resumes_router)
api_router.include_router(users_router)
