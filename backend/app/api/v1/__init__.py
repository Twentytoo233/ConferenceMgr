from fastapi import APIRouter

from . import auth, users, departments, meetings, checkins, dashboard, configs, logs

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(departments.router, prefix="/departments", tags=["Departments"])
router.include_router(meetings.router, prefix="/meetings", tags=["Meetings"])
router.include_router(checkins.router, prefix="/checkins", tags=["Check-in"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(configs.router, prefix="/configs", tags=["Configurations"])
router.include_router(logs.router, prefix="/logs", tags=["Logs"])
