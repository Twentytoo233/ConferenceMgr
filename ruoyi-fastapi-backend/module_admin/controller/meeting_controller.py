from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from module_admin.annotation.log import log
from module_admin.annotation.data_scope import data_scope
from module_admin.service.user_service import UserService
from module_admin.service.meeting_service import MeetingService
from module_admin.entity.vo.meeting_vo import *
from module_admin.entity.vo.common_vo import CrudResponseModel, PageResponse
from module_admin.dao.meeting_dao import MeetingDao, MeetingAttendeeDao
from module_admin.database.db import get_db
from utils.response_util import ResponseUtil
from utils.export_util import export_excel
from config import settings

router = APIRouter()


# -------------------- 会议管理接口 --------------------
@router.get("/meeting/list", response_model=PageResponse)
@data_scope(dept_alias="m", user_alias="m")
async def get_meeting_list(
        name: str = None,
        status: int = None,
        start_time_begin: datetime = None,
        start_time_end: datetime = None,
        page_num: int = 1,
        page_size: int = 10,
        db: Session = Depends(get_db)
):
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
        query_params = {
            "name": name,
            "status": status,
            "start_time_begin": start_time_begin,
            "start_time_end": start_time_end
        }

        # 获取会议列表
        meetings, total = await MeetingDao.get_meetings(
            db, query_params, page_num, page_size
        )

        # 格式化结果
        formatted_meetings = []
        for meeting in meetings:
            formatted_meetings.append({
                "id": meeting.id,
                "name": meeting.name,
                "location": meeting.location,
                "start_time": meeting.start_time.strftime("%Y-%m-%d %H:%M"),
                "end_time": meeting.end_time.strftime("%Y-%m-%d %H:%M"),
                "sign_start": meeting.sign_start.strftime("%Y-%m-%d %H:%M"),
                "sign_end": meeting.sign_end.strftime("%Y-%m-%d %H:%M"),
                "status": meeting.status,
                "status_text": MeetingStatus(meeting.status).name.replace('_', ' '),
                "creator_name": meeting.creator.user_name if meeting.creator else "",
                "create_time": meeting.create_time.strftime("%Y-%m-%d %H:%M"),
            })

        return ResponseUtil.paginate(
            data=formatted_meetings,
            total=total,
            page_num=page_num,
            page_size=page_size
        )
    except Exception as e:
        return ResponseUtil.error(msg=f"查询失败: {str(e)}")


@router.post("/meeting/create", response_model=CrudResponseModel)
@log(title="会议管理", business_type="新增会议")
@data_scope(dept_alias="m", user_alias="m")
async def create_meeting(
        meeting_data: MeetingCreate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(UserService.get_current_user)
):
    """
    创建新会议
    :param meeting_data: 会议数据
    :return: 创建结果
    """
    try:
        result = await MeetingService.create_meeting(
            db, meeting_data, current_user['user_id']
        )
        return result
    except Exception as e:
        return ResponseUtil.error(msg=f"创建失败: {str(e)}")


@router.put("/meeting/update", response_model=CrudResponseModel)
@log(title="会议管理", business_type="修改会议")
@data_scope(dept_alias="m", user_alias="m")
async def update_meeting(
        meeting_data: MeetingUpdate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(UserService.get_current_user)
):
    """
    更新会议信息
    :param meeting_data: 会议数据
    :return: 更新结果
    """
    try:
        result = await MeetingService.update_meeting(
            db, meeting_data, current_user['user_id']
        )
        return result
    except Exception as e:
        return ResponseUtil.error(msg=f"更新失败: {str(e)}")


@router.delete("/meeting/delete/{meeting_id}", response_model=CrudResponseModel)
@log(title="会议管理", business_type="删除会议")
@data_scope(dept_alias="m", user_alias="m")
async def delete_meeting(
        meeting_id: int,
        db: Session = Depends(get_db)
):
    """
    删除会议
    :param meeting_id: 会议ID
    :return: 删除结果
    """
    try:
        result = await MeetingService.delete_meeting(db, meeting_id)
        return result
    except Exception as e:
        return ResponseUtil.error(msg=f"删除失败: {str(e)}")


@router.get("/meeting/detail/{meeting_id}", response_model=MeetingResponse)
async def get_meeting_detail(
        meeting_id: int,
        db: Session = Depends(get_db)
):
    """
    获取会议详情
    :param meeting_id: 会议ID
    :return: 会议详情
    """
    try:
        meeting = await MeetingService.get_meeting_by_id(db, meeting_id)
        if not meeting:
            return ResponseUtil.error(msg="会议不存在")

        # 获取部门名称
        dept_names = [dept.dept_name for dept in meeting.depts]

        # 获取指定参会人员
        attendees = await MeetingAttendeeDao.get_attendees_by_meeting(db, meeting_id)
        user_names = [attendee.user.user_name for attendee in attendees]

        return {
            "id": meeting.id,
            "name": meeting.name,
            "description": meeting.description,
            "location": meeting.location,
            "start_time": meeting.start_time,
            "end_time": meeting.end_time,
            "sign_start": meeting.sign_start,
            "sign_end": meeting.sign_end,
            "status": meeting.status,
            "status_text": MeetingStatus(meeting.status).name.replace('_', ' '),
            "creator_name": meeting.creator.user_name if meeting.creator else "",
            "create_time": meeting.create_time,
            "dept_names": dept_names,
            "user_names": user_names
        }
    except Exception as e:
        return ResponseUtil.error(msg=f"获取详情失败: {str(e)}")


# -------------------- 参会人员管理接口 --------------------
@router.get("/meeting/attendees", response_model=PageResponse)
@data_scope(dept_alias="a", user_alias="u")
async def get_meeting_attendees(
        meeting_id: int,
        sign_status: int = None,
        user_name: str = None,
        page_num: int = 1,
        page_size: int = 10,
        db: Session = Depends(get_db)
):
    """
    分页查询参会人员
    :param meeting_id: 会议ID
    :param sign_status: 签到状态
    :param user_name: 用户姓名
    :param page_num: 页码
    :param page_size: 每页大小
    :return: 分页结果
    """
    try:
        # 构建查询条件
        query_params = {
            "meeting_id": meeting_id,
            "sign_status": sign_status,
            "user_name": user_name
        }

        # 获取参会人员列表
        attendees, total = await MeetingAttendeeDao.get_attendees(
            db, query_params, page_num, page_size
        )

        # 格式化结果
        formatted_attendees = []
        for attendee in attendees:
            user = attendee.user
            formatted_attendees.append({
                "id": attendee.id,
                "user_id": user.id,
                "user_name": user.user_name,
                "dept_name": user.dept.dept_name if user.dept else "",
                "sign_status": attendee.sign_status,
                "sign_status_text": SignStatus(attendee.sign_status).name.replace('_', ' '),
                "sign_time": attendee.sign_time.strftime("%Y-%m-%d %H:%M") if attendee.sign_time else "",
                "similarity": f"{attendee.similarity * 100:.2f}%" if attendee.similarity else "",
                "sign_device": attendee.sign_device,
                "face_image_path": attendee.face_image_path
            })

        return ResponseUtil.paginate(
            data=formatted_attendees,
            total=total,
            page_num=page_num,
            page_size=page_size
        )
    except Exception as e:
        return ResponseUtil.error(msg=f"查询失败: {str(e)}")


@router.post("/meeting/add_attendees", response_model=CrudResponseModel)
@log(title="会议管理", business_type="添加参会人员")
async def add_meeting_attendees(
        attendee_data: MeetingAttendeeAdd,
        db: Session = Depends(get_db)
):
    """
    添加参会人员
    :param attendee_data: 参会人员数据
    :return: 添加结果
    """
    try:
        result = await MeetingService.add_attendees(
            db,
            attendee_data.meeting_id,
            attendee_data.user_ids
        )
        return result
    except Exception as e:
        return ResponseUtil.error(msg=f"添加失败: {str(e)}")


@router.delete("/meeting/remove_attendee", response_model=CrudResponseModel)
@log(title="会议管理", business_type="移除参会人员")
async def remove_meeting_attendee(
        meeting_id: int,
        user_id: int,
        db: Session = Depends(get_db)
):
    """
    移除参会人员
    :param meeting_id: 会议ID
    :param user_id: 用户ID
    :return: 移除结果
    """
    try:
        result = await MeetingService.remove_attendee(db, meeting_id, user_id)
        return result
    except Exception as e:
        return ResponseUtil.error(msg=f"移除失败: {str(e)}")


# -------------------- 人脸签到接口 --------------------
@router.post("/meeting/signin", response_model=SignInResponse)
@log(title="会议签到", business_type="人脸签到")
async def meeting_sign_in(
        sign_data: SignInRequest,
        db: Session = Depends(get_db)
):
    """
    会议人脸签到
    :param sign_data: 签到数据
    :return: 签到结果
    """
    try:
        # 处理签到逻辑
        result = await MeetingService.process_sign_in(db, sign_data)

        # 保存签到照片
        if result['success'] and sign_data.image_data:
            image_path = await MeetingService.save_sign_image(
                sign_data.meeting_id,
                sign_data.user_id,
                sign_data.image_data
            )
            await MeetingService.update_sign_image(
                db, sign_data.meeting_id, sign_data.user_id, image_path
            )

        return result
    except Exception as e:
        return {
            "success": False,
            "message": f"签到失败: {str(e)}"
        }


# -------------------- 数据导出接口 --------------------
@router.get("/meeting/export_attendees")
@log(title="会议管理", business_type="导出参会名单")
async def export_meeting_attendees(
        meeting_id: int,
        db: Session = Depends(get_db)
):
    """
    导出会议参会名单
    :param meeting_id: 会议ID
    :return: Excel文件流
    """
    try:
        # 获取导出数据
        export_data = await MeetingService.export_meeting_attendees(db, meeting_id)
        if not export_data['success']:
            return ResponseUtil.error(msg=export_data['message'])

        # 生成Excel
        excel_buffer = export_excel(
            sheet_name="参会名单",
            headers=export_data['headers'],
            rows=export_data['rows']
        )

        # 返回文件流
        filename = f"参会名单_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        return StreamingResponse(
            io.BytesIO(excel_buffer),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return ResponseUtil.error(msg=f"导出失败: {str(e)}")


# -------------------- 会议统计接口 --------------------
@router.get("/meeting/stats/{meeting_id}", response_model=MeetingStatsResponse)
async def get_meeting_stats(
        meeting_id: int,
        db: Session = Depends(get_db)
):
    """
    获取会议统计信息
    :param meeting_id: 会议ID
    :return: 统计结果
    """
    try:
        stats = await MeetingService.get_meeting_stats(db, meeting_id)
        return stats
    except Exception as e:
        return ResponseUtil.error(msg=f"获取统计信息失败: {str(e)}")


# -------------------- 会议状态控制接口 --------------------
@router.put("/meeting/start/{meeting_id}", response_model=CrudResponseModel)
@log(title="会议管理", business_type="开始会议")
async def start_meeting(
        meeting_id: int,
        db: Session = Depends(get_db)
):
    """
    开始会议
    :param meeting_id: 会议ID
    :return: 操作结果
    """
    try:
        result = await MeetingService.start_meeting(db, meeting_id)
        return result
    except Exception as e:
        return ResponseUtil.error(msg=f"开始会议失败: {str(e)}")


@router.put("/meeting/end/{meeting_id}", response_model=CrudResponseModel)
@log(title="会议管理", business_type="结束会议")
async def end_meeting(
        meeting_id: int,
        db: Session = Depends(get_db)
):
    """
    结束会议
    :param meeting_id: 会议ID
    :return: 操作结果
    """
    try:
        result = await MeetingService.end_meeting(db, meeting_id)
        return result
    except Exception as e:
        return ResponseUtil.error(msg=f"结束会议失败: {str(e)}")