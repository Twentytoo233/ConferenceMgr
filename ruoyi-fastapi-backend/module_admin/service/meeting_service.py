"""
会议管理服务层
处理会议管理、签到、统计等核心业务逻辑
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from tortoise.expressions import Q
from tortoise.transactions import in_transaction
import numpy as np
import math

# 模型和枚举
from module_admin.entity.do.meeting_do import Meeting, MeetingAttendee, MeetingStatus, SignStatus
from module_admin.entity.vo.meeting_vo import MeetingModel, MeetingAttendeeModel
from module_admin.dao.meeting_dao import MeetingDao, MeetingAttendeeDao
from module_admin.dao.user_dao import UserDao
from module_admin.entity.do.user_do import User
from module_admin.entity.vo.common_vo import CrudResponseModel, PageResponse
from utils.page_util import PageUtil
from utils.common_util import format_time
from config import settings
from utils.face_recognition import FaceRecognition
from utils.log_util import logger


class MeetingService:

    @staticmethod
    async def create_meeting(meeting_data: MeetingModel, creator_id: int) -> CrudResponseModel:
        """
        创建会议
        :param meeting_data: 会议数据
        :param creator_id: 创建者ID
        :return: 创建结果
        """
        try:
            # 验证时间有效性
            if meeting_data.sign_start >= meeting_data.sign_end:
                return CrudResponseModel(
                    success=False,
                    message="签到结束时间必须晚于开始时间"
                )

            if meeting_data.start_time >= meeting_data.end_time:
                return CrudResponseModel(
                    success=False,
                    message="会议结束时间必须晚于开始时间"
                )

            if meeting_data.sign_end > meeting_data.start_time:
                return CrudResponseModel(
                    success=False,
                    message="签到结束时间不能晚于会议开始时间"
                )

            # 创建会议记录
            meeting = await MeetingDao.create_meeting(
                name=meeting_data.name,
                description=meeting_data.description,
                location=meeting_data.location,
                start_time=meeting_data.start_time,
                end_time=meeting_data.end_time,
                sign_start=meeting_data.sign_start,
                sign_end=meeting_data.sign_end,
                status=MeetingStatus.NOT_STARTED,
                creator_id=creator_id
            )

            # 添加参会人员
            if meeting_data.dept_ids:
                await MeetingService.add_attendees_by_depts(meeting.id, meeting_data.dept_ids)

            # 添加指定人员
            if meeting_data.user_ids:
                await MeetingService.add_specific_attendees(meeting.id, meeting_data.user_ids)

            return CrudResponseModel(
                success=True,
                message="会议创建成功",
                data={"meeting_id": meeting.id}
            )
        except Exception as e:
            logger.error(f"创建会议失败: {str(e)}")
            return CrudResponseModel(
                success=False,
                message=f"创建会议失败: {str(e)}"
            )

    @staticmethod
    async def update_meeting(meeting_id: int, meeting_data: MeetingModel) -> CrudResponseModel:
        """
        更新会议信息
        :param meeting_id: 会议ID
        :param meeting_data: 会议数据
        :return: 更新结果
        """
        try:
            meeting = await MeetingDao.get_meeting_by_id(meeting_id)
            if not meeting:
                return CrudResponseModel(
                    success=False,
                    message="会议不存在"
                )

            # 已开始的会议不能修改
            if meeting.status != MeetingStatus.NOT_STARTED:
                return CrudResponseModel(
                    success=False,
                    message="已开始或已结束的会议不能修改"
                )

            # 更新会议信息
            await MeetingDao.update_meeting(
                meeting_id=meeting_id,
                name=meeting_data.name,
                description=meeting_data.description,
                location=meeting_data.location,
                start_time=meeting_data.start_time,
                end_time=meeting_data.end_time,
                sign_start=meeting_data.sign_start,
                sign_end=meeting_data.sign_end
            )

            # 更新参会人员
            if meeting_data.dept_ids or meeting_data.user_ids:
                # 先删除现有参会人员
                await MeetingAttendeeDao.delete_attendees_by_meeting(meeting_id)

                # 添加新参会人员
                if meeting_data.dept_ids:
                    await MeetingService.add_attendees_by_depts(meeting_id, meeting_data.dept_ids)

                if meeting_data.user_ids:
                    await MeetingService.add_specific_attendees(meeting_id, meeting_data.user_ids)

            return CrudResponseModel(
                success=True,
                message="会议更新成功"
            )
        except Exception as e:
            logger.error(f"更新会议失败: {str(e)}")
            return CrudResponseModel(
                success=False,
                message=f"更新会议失败: {str(e)}"
            )

    @staticmethod
    async def delete_meeting(meeting_id: int) -> CrudResponseModel:
        """
        删除会议
        :param meeting_id: 会议ID
        :return: 删除结果
        """
        try:
            meeting = await MeetingDao.get_meeting_by_id(meeting_id)
            if not meeting:
                return CrudResponseModel(
                    success=False,
                    message="会议不存在"
                )

            # 已开始的会议不能删除
            if meeting.status != MeetingStatus.NOT_STARTED:
                return CrudResponseModel(
                    success=False,
                    message="已开始或已结束的会议不能删除"
                )

            # 删除会议及相关数据
            async with in_transaction():
                # 删除参会记录
                await MeetingAttendeeDao.delete_attendees_by_meeting(meeting_id)
                # 删除会议
                await MeetingDao.delete_meeting(meeting_id)

            return CrudResponseModel(
                success=True,
                message="会议删除成功"
            )
        except Exception as e:
            logger.error(f"删除会议失败: {str(e)}")
            return CrudResponseModel(
                success=False,
                message=f"删除会议失败: {str(e)}"
            )

    @staticmethod
    async def get_meeting_by_id(meeting_id: int) -> Optional[Meeting]:
        """
        根据ID获取会议详情
        :param meeting_id: 会议ID
        :return: 会议对象
        """
        try:
            meeting = await MeetingDao.get_meeting_by_id(meeting_id)
            if meeting:
                # 更新会议状态（动态计算）
                current_status = MeetingService.calculate_meeting_status(meeting)
                if meeting.status != current_status:
                    meeting.status = current_status
                    await meeting.save()
            return meeting
        except Exception as e:
            logger.error(f"获取会议详情失败: {str(e)}")
            return None

    @staticmethod
    def calculate_meeting_status(meeting: Meeting) -> MeetingStatus:
        """
        计算会议当前状态
        :param meeting: 会议对象
        :return: 会议状态
        """
        now = datetime.now()
        if meeting.status == MeetingStatus.CANCELED:
            return MeetingStatus.CANCELED

        if now < meeting.start_time:
            return MeetingStatus.NOT_STARTED
        elif meeting.start_time <= now <= meeting.end_time:
            return MeetingStatus.IN_PROGRESS
        else:
            return MeetingStatus.FINISHED

    @staticmethod
    async def get_meeting_list(
            name: Optional[str] = None,
            status: Optional[int] = None,
            start_time_begin: Optional[datetime] = None,
            start_time_end: Optional[datetime] = None,
            page_num: int = 1,
            page_size: int = 10
    ) -> PageResponse:
        """
        分页查询会议列表
        :param name: 会议名称
        :param status: 会议状态
        :param start_time_begin: 开始时间范围-起始
        :param start_time_end: 开始时间范围-结束
        :param page_num: 页码
        :param page_size: 每页大小
        :return: 分页结果
        """
        try:
            # 构建查询条件
            conditions = []
            if name:
                conditions.append(Q(name__icontains=name))
            if status is not None:
                conditions.append(Q(status=status))
            if start_time_begin:
                conditions.append(Q(start_time__gte=start_time_begin))
            if start_time_end:
                conditions.append(Q(start_time__lte=start_time_end))

            # 执行查询
            meetings, total = await MeetingDao.get_meetings(
                conditions=conditions,
                page_num=page_num,
                page_size=page_size
            )

            # 格式化数据
            formatted_meetings = []
            for meeting in meetings:
                # 动态计算状态
                current_status = MeetingService.calculate_meeting_status(meeting)
                if meeting.status != current_status:
                    meeting.status = current_status
                    await meeting.save()

                formatted_meetings.append({
                    "id": meeting.id,
                    "name": meeting.name,
                    "location": meeting.location,
                    "start_time": format_time(meeting.start_time),
                    "end_time": format_time(meeting.end_time),
                    "sign_start": format_time(meeting.sign_start),
                    "sign_end": format_time(meeting.sign_end),
                    "status": meeting.status,
                    "status_text": MeetingStatus(meeting.status).name.replace('_', ' '),
                    "creator": meeting.creator.user_name if meeting.creator else "",
                    "create_time": format_time(meeting.create_time),
                })

            # 返回分页结果
            return PageUtil.get_page_response(
                rows=formatted_meetings,
                total=total,
                page_num=page_num,
                page_size=page_size
            )
        except Exception as e:
            logger.error(f"查询会议列表失败: {str(e)}")
            return PageUtil.get_empty_page()

    @staticmethod
    async def add_attendees_by_depts(meeting_id: int, dept_ids: List[int]) -> CrudResponseModel:
        """
        根据部门添加参会人员
        :param meeting_id: 会议ID
        :param dept_ids: 部门ID列表
        :return: 添加结果
        """
        try:
            # 获取部门下的所有用户
            users = await UserDao.get_users_by_depts(dept_ids)
            if not users:
                return CrudResponseModel(
                    success=True,
                    message="所选部门下无用户"
                )

            # 添加参会记录
            attendees = [
                MeetingAttendee(meeting_id=meeting_id, user_id=user.id)
                for user in users
            ]

            await MeetingAttendeeDao.bulk_create_attendees(attendees)

            return CrudResponseModel(
                success=True,
                message=f"成功添加 {len(users)} 名参会人员"
            )
        except Exception as e:
            logger.error(f"添加参会人员失败: {str(e)}")
            return CrudResponseModel(
                success=False,
                message=f"添加参会人员失败: {str(e)}"
            )

    @staticmethod
    async def add_specific_attendees(meeting_id: int, user_ids: List[int]) -> CrudResponseModel:
        """
        添加指定参会人员
        :param meeting_id: 会议ID
        :param user_ids: 用户ID列表
        :return: 添加结果
        """
        try:
            # 获取用户信息
            users = await UserDao.get_users_by_ids(user_ids)
            if not users:
                return CrudResponseModel(
                    success=True,
                    message="未找到指定用户"
                )

            # 添加参会记录
            attendees = [
                MeetingAttendee(meeting_id=meeting_id, user_id=user.id)
                for user in users
            ]

            await MeetingAttendeeDao.bulk_create_attendees(attendees)

            return CrudResponseModel(
                success=True,
                message=f"成功添加 {len(users)} 名参会人员"
            )
        except Exception as e:
            logger.error(f"添加指定参会人员失败: {str(e)}")
            return CrudResponseModel(
                success=False,
                message=f"添加指定参会人员失败: {str(e)}"
            )

    @staticmethod
    async def get_meeting_attendees(
            meeting_id: int,
            sign_status: Optional[int] = None,
            user_name: Optional[str] = None,
            page_num: int = 1,
            page_size: int = 10
    ) -> PageResponse:
        """
        获取会议参会人员列表
        :param meeting_id: 会议ID
        :param sign_status: 签到状态
        :param user_name: 用户姓名
        :param page_num: 页码
        :param page_size: 每页大小
        :return: 分页结果
        """
        try:
            # 构建查询条件
            conditions = [Q(meeting_id=meeting_id)]
            if sign_status is not None:
                conditions.append(Q(sign_status=sign_status))
            if user_name:
                conditions.append(Q(user__user_name__icontains=user_name))

            # 执行查询
            attendees, total = await MeetingAttendeeDao.get_attendees(
                conditions=conditions,
                page_num=page_num,
                page_size=page_size
            )

            # 格式化数据
            formatted_attendees = []
            for attendee in attendees:
                user = attendee.user
                formatted_attendees.append({
                    "id": attendee.id,
                    "user_id": user.id if user else "",
                    "user_name": user.user_name if user else "",
                    "dept_name": user.dept.dept_name if user and user.dept else "",
                    "sign_status": attendee.sign_status,
                    "sign_status_text": SignStatus(attendee.sign_status).name.replace('_', ' '),
                    "sign_time": format_time(attendee.sign_time) if attendee.sign_time else "",
                    "similarity": f"{attendee.similarity * 100:.2f}%" if attendee.similarity else "",
                    "sign_device": attendee.sign_device or "",
                })

            # 返回分页结果
            return PageUtil.get_page_response(
                rows=formatted_attendees,
                total=total,
                page_num=page_num,
                page_size=page_size
            )
        except Exception as e:
            logger.error(f"获取参会人员列表失败: {str(e)}")
            return PageUtil.get_empty_page()

    @staticmethod
    async def process_sign_in(
            meeting_id: int,
            user_id: int,
            similarity: float,
            sign_time: datetime,
            device: str = "Web终端",
            location: str = "未知"
    ) -> Dict[str, Any]:
        """
        处理签到逻辑
        :param meeting_id: 会议ID
        :param user_id: 用户ID
        :param similarity: 人脸相似度
        :param sign_time: 签到时间
        :param device: 签到设备
        :param location: 签到位置
        :return: 签到结果
        """
        try:
            # 获取参会记录
            attendee = await MeetingAttendeeDao.get_attendee(meeting_id, user_id)
            if not attendee:
                return {
                    "success": False,
                    "message": "您未参加本次会议"
                }

            # 检查是否已签到
            if attendee.sign_status != SignStatus.NOT_SIGNED:
                return {
                    "success": False,
                    "message": "您已签到，请勿重复操作"
                }

            # 获取会议信息
            meeting = await MeetingDao.get_meeting_by_id(meeting_id)
            if not meeting:
                return {
                    "success": False,
                    "message": "会议不存在"
                }

            # 检查签到时间
            if sign_time < meeting.sign_start:
                return {
                    "success": False,
                    "message": f"签到尚未开始，开始时间: {meeting.sign_start.strftime('%H:%M')}"
                }

            if sign_time > meeting.sign_end:
                return {
                    "success": False,
                    "message": f"签到已结束，结束时间: {meeting.sign_end.strftime('%H:%M')}"
                }

            # 确定签到状态（正常/迟到/早退）
            sign_status = SignStatus.SIGNED
            if sign_time > meeting.start_time:
                sign_status = SignStatus.LATE
            elif sign_time < meeting.end_time - timedelta(minutes=settings.EARLY_LEAVE_THRESHOLD):
                sign_status = SignStatus.LEAVE_EARLY

            # 更新签到记录
            await MeetingAttendeeDao.update_sign_info(
                attendee_id=attendee.id,
                sign_status=sign_status,
                sign_time=sign_time,
                similarity=similarity,
                sign_device=device,
                sign_location=location
            )

            # 获取用户信息
            user = await UserDao.get_user_by_id(user_id)

            return {
                "success": True,
                "user_id": user_id,
                "user_name": user.user_name if user else "",
                "dept_name": user.dept.dept_name if user and user.dept else "",
                "sign_status": sign_status,
                "sign_time": sign_time.strftime("%H:%M:%S"),
                "similarity": f"{similarity * 100:.2f}%"
            }
        except Exception as e:
            logger.error(f"处理签到失败: {str(e)}")
            return {
                "success": False,
                "message": f"签到处理失败: {str(e)}"
            }

    @staticmethod
    async def get_meeting_stats(meeting_id: int) -> Dict[str, Any]:
        """
        获取会议统计信息
        :param meeting_id: 会议ID
        :return: 统计结果
        """
        try:
            # 获取会议信息
            meeting = await MeetingDao.get_meeting_by_id(meeting_id)
            if not meeting:
                return {
                    "success": False,
                    "message": "会议不存在"
                }

            # 获取所有参会人员
            attendees = await MeetingAttendeeDao.get_all_attendees(meeting_id)
            total = len(attendees)

            # 统计各状态人数
            status_count = {
                SignStatus.NOT_SIGNED.value: 0,
                SignStatus.SIGNED.value: 0,
                SignStatus.LATE.value: 0,
                SignStatus.LEAVE_EARLY.value: 0
            }

            for attendee in attendees:
                status_count[attendee.sign_status] += 1

            # 计算签到率
            signed_total = status_count[SignStatus.SIGNED.value] + \
                           status_count[SignStatus.LATE.value] + \
                           status_count[SignStatus.LEAVE_EARLY.value]

            sign_rate = 0
            if total > 0:
                sign_rate = round((signed_total / total) * 100, 2)

            # 获取最新签到记录
            latest_signs = await MeetingAttendeeDao.get_latest_signs(meeting_id, 5)

            # 格式化最新签到记录
            formatted_signs = []
            for sign in latest_signs:
                user = sign.user
                formatted_signs.append({
                    "user_name": user.user_name if user else "",
                    "dept_name": user.dept.dept_name if user and user.dept else "",
                    "sign_time": format_time(sign.sign_time),
                    "status": SignStatus(sign.sign_status).name.replace('_', ' ')
                })

            return {
                "success": True,
                "meeting_id": meeting_id,
                "meeting_name": meeting.name,
                "total_attendees": total,