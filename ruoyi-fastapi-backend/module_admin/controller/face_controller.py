"""
人脸识别管理控制器
处理人脸注册、识别签到和相关管理功能
"""

from fastapi import APIRouter, UploadFile, File, Depends, WebSocket, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime
import numpy as np
import base64
import asyncio
import cv2
import io
import os

# 若依框架依赖
from module_admin.service.user_service import UserService
from module_admin.service.meeting_service import MeetingService
from module_admin.service.face_service import FaceService
from module_admin.service.dept_service import DeptService
from module_admin.entity.vo.face_vo import FaceRegisterModel, FaceSearchModel
from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.dao.face_dao import FaceDao
from module_admin.annotation.log import log
from utils.response_util import ResponseUtil
from utils.face_recognition import FaceRecognition
from utils.upload_util import UploadUtil
from utils.page_util import PageResponse
from utils.common_util import export_excel
from config import settings

# 创建路由器
router = APIRouter()

# 人脸识别服务实例
face_recognition = FaceRecognition()


@router.post("/face/register", response_model=CrudResponseModel)
@log(title="人脸注册", business_type=1)
async def register_face(
        face_data: FaceRegisterModel = Depends(),
        file: UploadFile = File(...)
):
    """
    人脸注册接口
    :param face_data: 注册请求数据
    :param file: 人脸图片文件
    :return: 注册结果
    """
    try:
        # 验证用户是否存在
        user = await UserService.get_user_by_id(face_data.user_id)
        if not user:
            return ResponseUtil.error(msg="用户不存在")

        # 检查用户是否已注册人脸
        if user.face_feature:
            return ResponseUtil.error(msg="该用户已注册人脸信息")

        # 读取文件内容
        file_content = await file.read()

        # 检测人脸
        faces = face_recognition.detect_faces(file_content)
        if not faces:
            return ResponseUtil.error(msg="未检测到人脸，请上传清晰正面照片")

        # 提取特征向量
        embedding = face_recognition.extract_embedding(faces[0])

        # 保存人脸图片
        upload_path = UploadUtil.gen_file_path("faces", file.filename)
        face_image_path = await UploadUtil.save_file(file_content, upload_path)

        # 更新用户信息
        await FaceDao.update_face_data(
            user_id=face_data.user_id,
            face_feature=embedding.tobytes(),
            face_image_path=face_image_path
        )

        # 记录操作日志
        await log(
            title=f"人脸注册-用户:{user.user_name}",
            business_type=1,
            oper_name=face_data.oper_name
        )

        return ResponseUtil.success(msg="人脸注册成功")
    except Exception as e:
        return ResponseUtil.error(msg=f"人脸注册失败: {str(e)}")


@router.websocket("/meeting/signin/{meeting_id}")
async def realtime_signin(websocket: WebSocket, meeting_id: int):
    """
    实时人脸识别签到接口 (WebSocket)
    :param websocket: WebSocket连接
    :param meeting_id: 会议ID
    """
    await websocket.accept()

    try:
        # 验证会议有效性
        meeting = await MeetingService.get_meeting_by_id(meeting_id)
        if not meeting:
            await websocket.send_json({
                "status": "error",
                "msg": "会议不存在或已结束"
            })
            return

        # 检查会议状态
        now = datetime.now()
        if now < meeting.sign_start:
            await websocket.send_json({
                "status": "error",
                "msg": f"签到尚未开始，开始时间: {meeting.sign_start.strftime('%Y-%m-%d %H:%M')}"
            })
            return

        if now > meeting.sign_end:
            await websocket.send_json({
                "status": "error",
                "msg": f"签到已结束，结束时间: {meeting.sign_end.strftime('%Y-%m-%d %H:%M')}"
            })
            return

        # 获取参会人员人脸特征
        attendees = await MeetingService.get_meeting_attendees(meeting_id)
        if not attendees:
            await websocket.send_json({
                "status": "error",
                "msg": "本次会议无参会人员"
            })
            return

        # 构建特征数据库 {user_id: feature_vector}
        face_db = {}
        for attendee in attendees:
            if attendee.user and attendee.user.face_feature:
                face_db[attendee.user.user_id] = np.frombuffer(
                    attendee.user.face_feature, dtype=np.float32
                )

        # 设置识别参数
        threshold = settings.FACE_RECOGNITION_THRESHOLD
        similarity_threshold = threshold / 100.0

        # 实时处理视频帧
        while True:
            try:
                # 接收视频帧数据
                frame_data = await websocket.receive_bytes()

                # 转换字节数据为图像
                nparr = np.frombuffer(frame_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                # 人脸检测
                faces = face_recognition.detect_faces(frame)
                if not faces:
                    await websocket.send_json({
                        "status": "detect",
                        "msg": "未检测到人脸，请正对摄像头"
                    })
                    continue

                # 提取特征
                embedding = face_recognition.extract_embedding(faces[0])

                # 特征比对
                max_similarity = 0
                matched_user_id = None

                for user_id, feature in face_db.items():
                    similarity = face_recognition.calculate_similarity(embedding, feature)
                    if similarity > max_similarity:
                        max_similarity = similarity
                        matched_user_id = user_id

                # 签到判定
                if max_similarity > similarity_threshold:
                    # 处理签到
                    sign_result = await MeetingService.process_sign_in(
                        meeting_id=meeting_id,
                        user_id=matched_user_id,
                        similarity=max_similarity,
                        sign_time=datetime.now()
                    )

                    # 获取用户信息
                    user = await UserService.get_user_by_id(matched_user_id)

                    # 保存签到照片
                    _, img_encoded = cv2.imencode('.jpg', faces[0])
                    sign_image_path = await UploadUtil.save_sign_image(
                        img_encoded.tobytes(),
                        f"sign_{meeting_id}_{matched_user_id}.jpg"
                    )

                    # 更新签到记录
                    await MeetingService.update_sign_image(
                        meeting_id=meeting_id,
                        user_id=matched_user_id,
                        face_image_path=sign_image_path
                    )

                    # 发送成功响应
                    await websocket.send_json({
                        "status": "success",
                        "user_id": matched_user_id,
                        "user_name": user.user_name,
                        "dept_name": user.dept.dept_name if user.dept else "",
                        "similarity": f"{max_similarity * 100:.2f}%",
                        "sign_time": datetime.now().strftime("%H:%M:%S")
                    })
                else:
                    # 相似度不足
                    await websocket.send_json({
                        "status": "fail",
                        "msg": f"身份验证失败 (最高相似度: {max_similarity * 100:.2f}%)"
                    })

                # 降低CPU占用
                await asyncio.sleep(0.1)

            except Exception as e:
                await websocket.send_json({
                    "status": "error",
                    "msg": f"处理失败: {str(e)}"
                })
                break

    except HTTPException as e:
        await websocket.send_json({
            "status": "error",
            "msg": f"连接错误: {e.detail}"
        })
    except Exception as e:
        await websocket.send_json({
            "status": "error",
            "msg": f"系统错误: {str(e)}"
        })


@router.post("/face/search", response_model=PageResponse)
async def search_faces(search_model: FaceSearchModel):
    """
    人脸信息查询接口
    :param search_model: 查询参数
    :return: 分页查询结果
    """
    try:
        # 执行查询
        result = await FaceService.get_face_list(search_model)
        return ResponseUtil.success(data=result)
    except Exception as e:
        return ResponseUtil.error(msg=f"查询失败: {str(e)}")


@router.get("/face/export")
async def export_faces(search_model: FaceSearchModel = Depends()):
    """
    导出人脸信息
    :param search_model: 查询参数
    :return: Excel文件流
    """
    try:
        # 获取数据
        data = await FaceService.get_face_list(search_model)

        # 准备Excel数据
        headers = ["用户ID", "用户名", "部门", "注册时间", "人脸状态"]
        rows = []

        for item in data.rows:
            rows.append([
                item.user_id,
                item.user_name,
                item.dept_name,
                item.register_time,
                "已注册" if item.face_feature else "未注册"
            ])

        # 生成Excel
        excel_buffer = export_excel(
            sheet_name="人脸信息",
            headers=headers,
            rows=rows
        )

        # 返回文件流
        return StreamingResponse(
            io.BytesIO(excel_buffer),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=face_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"}
        )
    except Exception as e:
        return ResponseUtil.error(msg=f"导出失败: {str(e)}")


@router.post("/face/delete/{user_id}", response_model=CrudResponseModel)
@log(title="删除人脸信息", business_type=3)
async def delete_face(
        user_id: int,
        oper_name: str = Depends()
):
    """
    删除人脸信息
    :param user_id: 用户ID
    :param oper_name: 操作人
    :return: 删除结果
    """
    try:
        # 验证用户是否存在
        user = await UserService.get_user_by_id(user_id)
        if not user:
            return ResponseUtil.error(msg="用户不存在")

        # 检查是否有人脸信息
        if not user.face_feature:
            return ResponseUtil.error(msg="该用户未注册人脸信息")

        # 删除人脸信息
        await FaceDao.delete_face_data(user_id)

        # 记录操作日志
        await log(
            title=f"删除人脸信息-用户:{user.user_name}",
            business_type=3,
            oper_name=oper_name
        )

        return ResponseUtil.success(msg="人脸信息删除成功")
    except Exception as e:
        return ResponseUtil.error(msg=f"删除失败: {str(e)}")


@router.get("/face/features/{meeting_id}")
async def export_meeting_features(meeting_id: int):
    """
    导出会议人脸特征（用于离线签到）
    :param meeting_id: 会议ID
    :return: 特征数据
    """
    try:
        # 验证会议是否存在
        meeting = await MeetingService.get_meeting_by_id(meeting_id)
        if not meeting:
            return ResponseUtil.error(msg="会议不存在")

        # 获取参会人员
        attendees = await MeetingService.get_meeting_attendees(meeting_id)
        if not attendees:
            return ResponseUtil.error(msg="本次会议无参会人员")

        # 构建特征数据
        features = {}
        for attendee in attendees:
            if attendee.user and attendee.user.face_feature:
                # 将二进制特征转换为Base64字符串
                features[attendee.user.user_id] = base64.b64encode(
                    attendee.user.face_feature
                ).decode('utf-8')

        return ResponseUtil.success(data={
            "meeting_id": meeting_id,
            "meeting_name": meeting.name,
            "features": features,
            "count": len(features)
        })
    except Exception as e:
        return ResponseUtil.error(msg=f"导出特征失败: {str(e)}")


@router.post("/face/batch/register")
@log(title="批量人脸注册", business_type=1)
async def batch_register_faces(
        dept_id: int,
        oper_name: str = Depends(),
        zip_file: UploadFile = File(...)
):
    """
    批量人脸注册（按部门）
    :param dept_id: 部门ID
    :param oper_name: 操作人
    :param zip_file: 包含人脸图片的ZIP文件
    :return: 批量注册结果
    """
    try:
        # 验证部门是否存在
        dept = await DeptService.get_dept_by_id(dept_id)
        if not dept:
            return ResponseUtil.error(msg="部门不存在")

        # 获取部门所有用户
        users = await UserService.get_users_by_dept(dept_id)
        if not users:
            return ResponseUtil.error(msg="该部门下无用户")

        # 保存ZIP文件
        zip_content = await zip_file.read()
        zip_path = await UploadUtil.save_zip(zip_content, "batch_faces")

        # 解压ZIP文件
        face_images = await UploadUtil.extract_zip(zip_path)

        # 批量注册
        success_count = 0
        fail_count = 0
        results = []

        for user in users:
            # 查找匹配的图片文件
            img_file = next((f for f in face_images if f.startswith(user.user_name) or f.startswith(str(user.user_id))),
                            None)

            if not img_file:
                results.append({
                    "user_id": user.user_id,
                    "user_name": user.user_name,
                    "status": "fail",
                    "msg": "未找到匹配的人脸图片"
                })
                fail_count += 1
                continue

            try:
                # 读取图片
                with open(os.path.join(UploadUtil.get_upload_dir(), img_file), "rb") as f:
                    img_data = f.read()

                # 检测人脸
                faces = face_recognition.detect_faces(img_data)
                if not faces:
                    results.append({
                        "user_id": user.user_id,
                        "user_name": user.user_name,
                        "status": "fail",
                        "msg": "未检测到人脸"
                    })
                    fail_count += 1
                    continue

                # 提取特征
                embedding = face_recognition.extract_embedding(faces[0])

                # 更新用户信息
                await FaceDao.update_face_data(
                    user_id=user.user_id,
                    face_feature=embedding.tobytes(),
                    face_image_path=img_file
                )

                results.append({
                    "user_id": user.user_id,
                    "user_name": user.user_name,
                    "status": "success",
                    "msg": "注册成功"
                })
                success_count += 1

            except Exception as e:
                results.append({
                    "user_id": user.user_id,
                    "user_name": user.user_name,
                    "status": "fail",
                    "msg": str(e)
                })
                fail_count += 1

        # 记录操作日志
        await log(
            title=f"批量人脸注册-部门:{dept.dept_name}",
            business_type=1,
            oper_name=oper_name
        )

        return ResponseUtil.success(data={
            "total": len(users),
            "success": success_count,
            "fail": fail_count,
            "results": results
        })

    except Exception as e:
        return ResponseUtil.error(msg=f"批量注册失败: {str(e)}")