from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.schemas.dashboard import MeetingStatsOut
from app.core.security import get_current_user
from app.models.user import User
from app.crud import crud_meeting, crud_checkin
from ..deps import get_db

router = APIRouter()

@router.get("/meeting/{meeting_id}", response_model=MeetingStatsOut)
def get_meeting_dashboard(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限查看会议统计")

    meeting = crud_meeting.get(db, id=meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    participants = crud_meeting.get_participants(db, meeting_id)
    total = len(participants)
    checked_in = crud_checkin.count_checked_in(db, meeting_id)
    rate = round((checked_in / total * 100), 2) if total > 0 else 0.0

    return MeetingStatsOut(
        meeting_id=meeting_id,
        meeting_title=meeting.title,
        total_participants=total,
        checked_in_count=checked_in,
        not_checked_in_count=total - checked_in,
        checkin_rate=rate
    )
