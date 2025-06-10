from fastapi import APIRouter
from .v1 import (
    auth, users, departments, meetings,
    checkins, dashboard, configs, logs
)

api_router = APIRouter(prefix="/api")

# v1 分组
api_router.include_router(auth.router, prefix="/v1", tags=["Auth"])
api_router.include_router(users.router, prefix="/v1", tags=["Users"])
api_router.include_router(departments.router, prefix="/v1", tags=["Departments"])
api_router.include_router(meetings.router, prefix="/v1", tags=["Meetings"])
api_router.include_router(checkins.router, prefix="/v1", tags=["Check‑ins"])
api_router.include_router(dashboard.router, prefix="/v1", tags=["Dashboard"])
api_router.include_router(configs.router, prefix="/v1", tags=["Configs"])
api_router.include_router(logs.router, prefix="/v1", tags=["Logs"])