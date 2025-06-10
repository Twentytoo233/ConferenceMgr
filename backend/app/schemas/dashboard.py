from pydantic import BaseModel

class MeetingStatsOut(BaseModel):
    meeting_id: int
    meeting_title: str
    total_participants: int
    checked_in_count: int
    not_checked_in_count: int
    checkin_rate: float
