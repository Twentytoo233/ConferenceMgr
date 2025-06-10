from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    username: str
    real_name: Optional[str]
    department_id: Optional[int]

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int
    role: str
    face_status: str

    class Config:
        orm_mode = True
