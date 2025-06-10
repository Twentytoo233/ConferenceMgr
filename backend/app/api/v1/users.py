from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.schemas.user import UserOut, UserCreate, UserUpdate
from app.crud import crud_user
from ..deps import get_db, get_current_admin

router = APIRouter()

@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db),
               _: str = Depends(get_current_admin)):   # 仅管理员可查
    return crud_user.get_multi(db)

@router.post("/users", response_model=UserOut)
def create_user(user_in: UserCreate,
                db: Session = Depends(get_db),
                _: str = Depends(get_current_admin)):
    return crud_user.create(db, obj_in=user_in)

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, user_in: UserUpdate,
                db: Session = Depends(get_db),
                _: str = Depends(get_current_admin)):
    return crud_user.update(db, db_obj=crud_user.get(db, id=user_id), obj_in=user_in)
