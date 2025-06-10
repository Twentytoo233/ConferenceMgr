from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.schemas.meeting import MeetingCreate, MeetingOut, MeetingUpdate
from app.crud import crud_meeting
from ..deps import get_db, get_current_user, get_current_admin

router = APIRouter()

# 用户可见会议列表
@router.get("/meetings", response_model=List[MeetingOut])
def list_meetings(db: Session = Depends(get_db),
                  user = Depends(get_current_user)):
    return crud_meeting.get_all_visible(db, user_id=user.id)

# 管理员增删改
@router.post("/meetings", response_model=MeetingOut, dependencies=[Depends(get_current_admin)])
def create_meeting(meeting_in: MeetingCreate, db: Session = Depends(get_db)):
    return crud_meeting.create(db, obj_in=meeting_in)

@router.put("/meetings/{meeting_id}", response_model=MeetingOut, dependencies=[Depends(get_current_admin)])
def update_meeting(meeting_id: int, meeting_in: MeetingUpdate, db: Session = Depends(get_db)):
    return crud_meeting.update(db, db_obj=crud_meeting.get(db, meeting_id), obj_in=meeting_in)

@router.delete("/meetings/{meeting_id}", dependencies=[Depends(get_current_admin)])
def delete_meeting(meeting_id: int, db: Session = Depends(get_db)):
    crud_meeting.remove(db, id=meeting_id)
    return {"msg": "deleted"}
