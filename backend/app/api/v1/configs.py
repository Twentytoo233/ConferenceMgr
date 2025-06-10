from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.config import ConfigUpdate, ConfigOut
from app.crud import crud_config
from ..deps import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=ConfigOut)
def get_system_config(db: Session = Depends(get_db)):
    config = crud_config.get_config(db)
    if not config:
        raise HTTPException(status_code=404, detail="系统配置未找到")
    return config


@router.put("/", response_model=ConfigOut)
def update_system_config(
        config_in: ConfigUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限修改系统配置")

    config = crud_config.update_config(db, config_in)
    return config
