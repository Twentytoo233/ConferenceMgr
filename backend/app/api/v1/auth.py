from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.schemas.token import Token
from app.schemas.user import UserCreate, UserOut
from app.core import security
from app.core.config import settings
from app.crud import crud_user
from ..deps import get_db

router = APIRouter()

# 用户登录，返回 access_token
@router.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(),
                           db: Session = Depends(get_db)):
    user = crud_user.authenticate(db, username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="用户名或密码错误")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 用户注册
@router.post("/register", response_model=UserOut)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    user = crud_user.get_by_username(db, username=user_in.username)
    if user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    return crud_user.create(db=db, obj_in=user_in)

# 获取当前用户信息（用于验证 token）
@router.get("/me", response_model=UserOut)
def get_current_user_info(current_user=Depends(security.get_current_user)):
    return current_user
