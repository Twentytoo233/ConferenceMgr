import asyncio
import base64
import json
import time
import cv2
import numpy as np
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
from config import settings
from utils.log_util import logger
from utils.face_recognition import face_service
from module_admin.service.meeting_service import MeetingService
from module_admin.service.user_service import UserService
from module_admin.dao.redis_dao import RedisDao
from module_admin.entity.vo.websocket_vo import SignInResult


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # 活跃连接: {meeting_id: [WebSocket]}
        self.active_connections: Dict[int, List[WebSocket]] = {}

        # 会议特征缓存: {meeting_id: (user_ids, face_encodings)}
        self.feature_cache: Dict[int, tuple] = {}

        # 连接状态: {websocket_id: {"meeting_id": int, "last_active": float}}
        self.connection_status: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, meeting_id: int):
        """接受WebSocket连接并初始化"""
        await websocket.accept()

        # 生成唯一连接ID
        conn_id = f"{id(websocket)}_{time.time()}"
        self.connection_status[conn_id] = {
            "meeting_id": meeting_id,
            "last_active": time.time(),
            "client_ip": websocket.client.host if websocket.client else "unknown"
        }

        # 添加到活跃连接
        if meeting_id not in self.active_connections:
            self.active_connections[meeting_id] = []
        self.active_connections[meeting_id].append(websocket)

        logger.info(f"WebSocket连接建立: 会议ID={meeting_id}, 连接ID={conn_id}")
        return conn_id

    def disconnect(self, conn_id: str, websocket: WebSocket):
        """断开WebSocket连接"""
        status = self.connection_status.get(conn_id, {})
        meeting_id = status.get("meeting_id")

        if meeting_id and meeting_id in self.active_connections:
            if websocket in self.active_connections[meeting_id]:
                self.active_connections[meeting_id].remove(websocket)
                logger.info(f"WebSocket连接移除: 会议ID={meeting_id}, 连接ID={conn_id}")

            # 如果该会议没有活跃连接，清除特征缓存
            if not self.active_connections[meeting_id]:
                if meeting_id in self.feature_cache:
                    del self.feature_cache[meeting_id]
                    logger.info(f"清除会议特征缓存: 会议ID={meeting_id}")

        if conn_id in self.connection_status:
            del self.connection_status[conn_id]

    async def load_meeting_features(self, meeting_id: int) -> tuple:
        """
        加载会议人脸特征数据
        :param meeting_id: 会议ID
        :return: (user_ids, face_encodings)
        """
        # 检查缓存
        if meeting_id in self.feature_cache:
            logger.debug(f"使用缓存特征数据: 会议ID={meeting_id}")
            return self.feature_cache[meeting_id]

        # 从Redis缓存获取
        cache_key = f"meeting_features:{meeting_id}"
        cached_data = await RedisDao.get(cache_key)

        if cached_data:
            try:
                data = json.loads(cached_data)
                user_ids = data["user_ids"]
                encodings = [np.array(enc) for enc in data["encodings"]]
                self.feature_cache[meeting_id] = (user_ids, encodings)
                logger.info(f"从Redis加载特征数据: 会议ID={meeting_id}, 人数={len(user_ids)}")
                return user_ids, encodings
            except Exception as e:
                logger.error(f"解析缓存特征失败: {str(e)}")

        # 从数据库加载
        logger.info(f"从数据库加载特征数据: 会议ID={meeting_id}")
        features = await MeetingService.get_meeting_features(meeting_id)

        if not features:
            return [], []

        user_ids = []
        face_encodings = []

        for user_id, encoding in features.items():
            user_ids.append(user_id)
            face_encodings.append(encoding)

        # 缓存到内存
        self.feature_cache[meeting_id] = (user_ids, face_encodings)

        # 缓存到Redis (过期时间1小时)
        cache_data = {
            "user_ids": user_ids,
            "encodings": [enc.tolist() for enc in face_encodings]
        }
        await RedisDao.set(cache_key, json.dumps(cache_data), ex=3600)

        return user_ids, face_encodings

    async def process_frame(self, conn_id: str, frame_data: bytes) -> Optional[SignInResult]:
        """
        处理视频帧并进行人脸识别
        :param conn_id: 连接ID
        :param frame_data: 视频帧二进制数据
        :return: 签到结果
        """
        # 获取连接状态
        status = self.connection_status.get(conn_id)
        if not status:
            return None

        meeting_id = status["meeting_id"]
        status["last_active"] = time.time()  # 更新活跃时间

        try:
            # 转换二进制数据为OpenCV图像
            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                logger.warning("视频帧解码失败")
                return None

            # 转换为RGB格式
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 加载会议特征数据
            user_ids, known_encodings = await self.load_meeting_features(meeting_id)
            if not known_encodings:
                return SignInResult(
                    success=False,
                    message="本次会议无人脸数据",
                    face_image=None
                )

            # 检测人脸位置
            face_locations = face_service.detect_faces(rgb_frame)
            if not face_locations:
                return SignInResult(
                    success=False,
                    message="未检测到人脸",
                    face_image=None
                )

            # 提取人脸特征
            face_encodings = face_service.extract_encodings(rgb_frame, face_locations)
            if not face_encodings:
                return SignInResult(
                    success=False,
                    message="特征提取失败",
                    face_image=None
                )

            # 取第一张人脸进行识别
            face_encoding = face_encodings[0]

            # 查找最佳匹配
            best_match_index, similarity = face_service.find_best_match(known_encodings, face_encoding)

            # 检查相似度是否达到阈值
            if similarity < settings.FACE_RECOGNITION_THRESHOLD:
                return SignInResult(
                    success=False,
                    message=f"匹配失败 (相似度: {similarity * 100:.1f}%)",
                    face_image=self._extract_face_image(rgb_frame, face_locations[0])
                )

            # 获取匹配用户
            user_id = user_ids[best_match_index]
            user = await UserService.get_user_by_id(user_id)
            if not user:
                return SignInResult(
                    success=False,
                    message="用户不存在",
                    face_image=self._extract_face_image(rgb_frame, face_locations[0])
                )

            # 处理签到
            sign_result = await MeetingService.process_sign_in(
                meeting_id=meeting_id,
                user_id=user_id,
                similarity=similarity,
                sign_time=datetime.now()
            )

            if not sign_result.success:
                return SignInResult(
                    success=False,
                    message=sign_result.message,
                    user_id=user_id,
                    user_name=user.user_name,
                    similarity=similarity,
                    face_image=self._extract_face_image(rgb_frame, face_locations[0])
                )

            # 保存签到照片
            face_image_path = await MeetingService.save_sign_image(
                meeting_id, user_id,
                self._extract_face_image(rgb_frame, face_locations[0])
            )

            # 更新签到记录
            await MeetingService.update_sign_image(
                meeting_id, user_id, face_image_path
            )

            return SignInResult(
                success=True,
                message="签到成功",
                user_id=user_id,
                user_name=user.user_name,
                similarity=similarity,
                sign_time=datetime.now().strftime("%H:%M:%S"),
                face_image=face_image_path
            )

        except Exception as e:
            logger.error(f"处理视频帧失败: {str(e)}")
            return SignInResult(
                success=False,
                message="处理失败",
                face_image=None
            )

    def _extract_face_image(self, frame: np.ndarray, face_location: tuple) -> bytes:
        """
        提取人脸区域图像
        :param frame: RGB格式图像
        :param face_location: 人脸位置 (top, right, bottom, left)
        :return: JPEG格式的二进制数据
        """
        top, right, bottom, left = face_location
        face_img = frame[top:bottom, left:right]

        # 调整大小 (最大300px)
        height, width = face_img.shape[:2]
        if height > 300 or width > 300:
            scale = 300 / max(height, width)
            new_size = (int(width * scale), int(height * scale))
            face_img = cv2.resize(face_img, new_size)

        # 转换为JPEG
        _, jpeg_data = cv2.imencode('.jpg', cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR),
                                    [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        return jpeg_data.tobytes()

    async def broadcast_meeting_stats(self, meeting_id: int):
        """
        广播会议统计信息
        :param meeting_id: 会议ID
        """
        stats = await MeetingService.get_meeting_stats(meeting_id)
        if not stats.success:
            return

        message = {
            "type": "stats_update",
            "data": {
                "signed_total": stats.signed_total,
                "not_signed": stats.not_signed,
                "sign_rate": stats.sign_rate,
                "latest_signs": stats.latest_signs
            }
        }

        await self._send_to_meeting(meeting_id, json.dumps(message))

    async def _send_to_meeting(self, meeting_id: int, message: str):
        """向会议的所有连接发送消息"""
        if meeting_id not in self.active_connections:
            return

        for websocket in self.active_connections[meeting_id]:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.warning(f"发送消息失败: {str(e)}")

    async def check_inactive_connections(self):
        """检查并关闭不活跃的连接"""
        current_time = time.time()
        inactive_ids = []

        for conn_id, status in self.connection_status.items():
            # 超过5分钟无活动视为不活跃
            if current_time - status["last_active"] > 300:
                inactive_ids.append(conn_id)

        for conn_id in inactive_ids:
            status = self.connection_status.get(conn_id)
            if status:
                logger.info(f"关闭不活跃连接: 连接ID={conn_id}, 会议ID={status['meeting_id']}")
                # 实际断开操作由主循环处理
                self.connection_status[conn_id]["inactive"] = True


# 全局连接管理器
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, meeting_id: int):
    """WebSocket端点处理函数"""
    conn_id = await manager.connect(websocket, meeting_id)

    try:
        # 发送初始消息
        await websocket.send_json({
            "type": "connection_established",
            "message": f"已连接到会议 {meeting_id} 的签到系统",
            "timestamp": int(time.time())
        })

        # 主循环
        while True:
            try:
                # 接收消息 (支持文本或二进制)
                data = await asyncio.wait_for(websocket.receive(), timeout=30.0)

                if data.get('type') == 'websocket.disconnect':
                    break

                # 处理二进制帧 (视频帧)
                if 'bytes' in data:
                    frame_data = data['bytes']
                    result = await manager.process_frame(conn_id, frame_data)

                    if result:
                        # 发送识别结果
                        await websocket.send_json(result.dict())

                        # 如果签到成功，广播统计更新
                        if result.success:
                            await manager.broadcast_meeting_stats(meeting_id)

                # 处理文本消息 (控制命令)
                elif 'text' in data:
                    message = json.loads(data['text'])
                    await handle_text_message(websocket, conn_id, message)

            except asyncio.TimeoutError:
                # 发送心跳保持连接
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": int(time.time())
                    })
                except:
                    break

            except WebSocketDisconnect:
                break

            except Exception as e:
                logger.error(f"WebSocket处理错误: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"处理错误: {str(e)}"
                })
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket异常: {str(e)}")
    finally:
        manager.disconnect(conn_id, websocket)
        logger.info(f"WebSocket连接关闭: 连接ID={conn_id}")


async def handle_text_message(websocket: WebSocket, conn_id: str, message: dict):
    """处理文本控制消息"""
    msg_type = message.get("type")

    if msg_type == "request_stats":
        # 请求当前会议统计
        status = manager.connection_status.get(conn_id)
        if status:
            meeting_id = status["meeting_id"]
            stats = await MeetingService.get_meeting_stats(meeting_id)
            if stats.success:
                await websocket.send_json({
                    "type": "current_stats",
                    "data": stats.dict()
                })

    elif msg_type == "manual_sign_in":
        # 手动签到
        user_id = message.get("user_id")
        status = manager.connection_status.get(conn_id)
        if status and user_id:
            meeting_id = status["meeting_id"]
            result = await MeetingService.process_sign_in(
                meeting_id=meeting_id,
                user_id=user_id,
                similarity=1.0,  # 手动签到相似度100%
                sign_time=datetime.now()
            )

            await websocket.send_json({
                "type": "manual_sign_result",
                "success": result.success,
                "message": result.message,
                "user_id": user_id
            })

            if result.success:
                await manager.broadcast_meeting_stats(meeting_id)


async def connection_cleanup_task():
    """定期清理不活跃连接的任务"""
    while True:
        await asyncio.sleep(60)  # 每分钟检查一次
        try:
            await manager.check_inactive_connections()
        except Exception as e:
            logger.error(f"清理任务错误: {str(e)}")


# 启动时运行清理任务
def start_cleanup_task():
    loop = asyncio.get_event_loop()
    loop.create_task(connection_cleanup_task())