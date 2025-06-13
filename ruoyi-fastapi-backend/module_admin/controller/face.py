from fastapi import APIRouter, UploadFile, Depends, WebSocket
from module_admin.models import User, MeetingAttendee
from module_admin.schemas.face_schema import FaceRegisterRequest
from utils.face_recognition import InsightFaceService
from utils.permission import requires

router = APIRouter()
face_service = InsightFaceService()  # 全局InsightFace服务实例


# -------------------- 人脸注册接口 --------------------
@router.post("/face/register")
@requires("system:user:face:register")  # 权限控制:cite[1]
async def register_face(req: FaceRegisterRequest, file: UploadFile):
    """
    人脸注册流程：
    1. 验证用户权限和状态
    2. 提取人脸特征向量
    3. 存储特征到数据库
    """
    user = await User.get_or_none(id=req.user_id)
    if not user:
        return {"code": 404, "msg": "用户不存在"}

    # 提取512维特征向量
    face_embedding = face_service.extract_embedding(await file.read())

    # 更新用户人脸数据
    await user.update(
        face_feature=face_embedding.tobytes(),  # 存储为二进制
        face_image_path=f"faces/{user.id}_{file.filename}"
    )
    return {"code": 200, "msg": "人脸注册成功"}


# -------------------- 实时签到接口 --------------------
@router.websocket("/meeting/signin/{meeting_id}")
async def realtime_signin(websocket: WebSocket, meeting_id: int):
    """
    实时签到流程：
    1. 建立WebSocket连接
    2. 接收视频帧进行人脸检测
    3. 与参会人员特征比对
    4. 返回签到结果
    """
    await websocket.accept()
    # 获取会议参会人员特征（提前缓存）
    attendees = await MeetingAttendee.filter(meeting_id=meeting_id).prefetch_related("user")
    face_db = {user.id: user.face_feature for attendee in attendees if (user := attendee.user)}

    while True:
        frame_data = await websocket.receive_bytes()
        # 1. 人脸检测
        faces = face_service.detect_faces(frame_data)
        if not faces:
            await websocket.send_json({"status": "error", "msg": "未检测到人脸"})
            continue

        # 2. 特征提取与比对
        embedding = face_service.extract_embedding(faces[0])
        max_similarity = 0
        matched_user = None

        for user_id, feature in face_db.items():
            similarity = face_service.calculate_similarity(
                embedding,
                np.frombuffer(feature, dtype=np.float32)  # 二进制转特征向量
            )
            if similarity > max_similarity:
                max_similarity = similarity
                matched_user = user_id

        # 3. 签到判定（阈值从系统配置获取）
        if max_similarity > 0.7:
            await MeetingAttendee.filter(user_id=matched_user, meeting_id=meeting_id).update(
                sign_status=1, sign_time=datetime.now())
            await websocket.send_json({
                "status": "success",
                "name": (await User.get(id=matched_user)).name
            })
        else:
            await websocket.send_json({"status": "fail", "msg": "身份验证失败"})


# -------------------- 特征管理接口 --------------------
@router.get("/face/features/{meeting_id}")
@requires("system:meeting:manage")
async def export_features(meeting_id: int):
    """
    导出会议人脸特征（用于终端设备离线签到）
    返回特征向量字典：{user_id: feature_base64}
    """
    attendees = await MeetingAttendee.filter(meeting_id=meeting_id).prefetch_related("user")
    return {
        attendee.user.id: base64.b64encode(attendee.user.face_feature).decode()
        for attendee in attendees if attendee.user.face_feature
    }