from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session

from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentOut
from app.models.user import User
from app.core.security import get_current_user
from app.crud import crud_department
from ..deps import get_db

router = APIRouter()


@router.get("/", response_model=List[DepartmentOut])
def list_departments(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    return crud_department.get_all(db)


@router.post("/", response_model=DepartmentOut)
def create_department(
        department_in: DepartmentCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限创建部门")

    return crud_department.create(db, department_in)


@router.put("/{dept_id}", response_model=DepartmentOut)
def update_department(
        dept_id: int,
        department_in: DepartmentUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限修改部门")

    dept = crud_department.get(db, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")

    return crud_department.update(db, dept, department_in)


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
        dept_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限删除部门")

    dept = crud_department.get(db, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")

    crud_department.remove(db, dept_id)
    return
