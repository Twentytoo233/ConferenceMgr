from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from app.schemas.checkin import CheckinResult
from app.services.face_service import verify_and_checkin
from ..deps import get_db, get_current_user

router = APIRouter()

@router.post("/checkin/{meeting_id}", response_model=CheckinResult)
async def face_checkin(meeting_id: int,
                       image: UploadFile = File(...),
                       db: Session = Depends(get_db),
                       user = Depends(get_current_user)):
    """
    上传一张照片完成签到。
    移动端或电脑摄像头均可将 base64 / multipart 文件发送到此接口。
    """
    result = await verify_and_checkin(
        db=db,
        meeting_id=meeting_id,
        user_id=user.id,
        image_file=image
    )
    return result
