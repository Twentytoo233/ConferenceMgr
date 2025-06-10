def get_participants(db: Session, meeting_id: int):
    meeting = get(db, id=meeting_id)
    return meeting.participants if meeting else []
