from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router

router = APIRouter(prefix="/v1")
router.include_router(health_router, tags=["health"])
router.include_router(jobs_router, tags=["jobs"])
