def count_checked_in(db: Session, meeting_id: int):
    return db.query(CheckIn).filter(CheckIn.meeting_id == meeting_id).count()
