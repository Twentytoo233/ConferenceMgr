from sqlalchemy.orm import Session
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate

def get(db: Session, dept_id: int) -> Department | None:
    return db.query(Department).filter(Department.id == dept_id).first()

def get_all(db: Session):
    return db.query(Department).all()

def create(db: Session, dept_in: DepartmentCreate):
    dept = Department(**dept_in.dict())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept

def update(db: Session, db_obj: Department, dept_in: DepartmentUpdate):
    for field, value in dept_in.dict().items():
        setattr(db_obj, field, value)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def remove(db: Session, dept_id: int):
    db_obj = get(db, dept_id)
    if db_obj:
        db.delete(db_obj)
        db.commit()
