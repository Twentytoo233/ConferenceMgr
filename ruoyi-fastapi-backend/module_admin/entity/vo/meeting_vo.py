"""
会议模块值对象定义
用于接口参数传递和响应数据
"""

from datetime import datetime
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from enum import IntEnum

# 枚举类定义（与DO中一致，用于API文档）
class MeetingStatus(IntEnum):
    NOT_STARTED = 0
    IN_PROGRESS = 1
    FINISHED = 2
    CANCELED = 3

class SignStatus(IntEnum):
    NOT_SIGNED = 0
    SIGNED = 1
    LATE = 2
    LEAVE_EARLY = 3

class MeetingBase(BaseModel):
    """会议基础模型"""
    name: str = Field(..., max_length=100, description="会议名称")
    description: Optional[str] = Field(None, description="会议描述")
    location: str = Field(..., max_length=200, description="会议地点")
    start_time: datetime = Field(..., description="会议开始时间")
    end_time: datetime = Field(..., description="会议结束时间")
    sign_start: datetime = Field(..., description="签到开始时间")
    sign_end: datetime = Field(..., description="签到结束时间")
    dept_ids: Optional[List[int]] = Field([], description="允许参加的部门ID列表")
    user_ids: Optional[List[int]] = Field([], description="指定参会人员ID列表")

    @validator('end_time')
    def end_time_after_start_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError("会议结束时间必须晚于开始时间")
        return v

    @validator('sign_end')
    def sign_end_after_sign_start(cls, v, values):
        if 'sign_start' in values and v <= values['sign_start']:
            raise ValueError("签到结束时间必须晚于开始时间")
        return v

    @validator('sign_end')
    def sign_end_before_meeting_start(cls, v, values):
        if 'start_time' in values and v > values['start_time']:
            raise ValueError("签到结束时间不能晚于会议开始时间")
        return v

class MeetingCreate(MeetingBase):
    """创建会议模型"""
    pass

class MeetingUpdate(MeetingBase):
    """更新会议模型"""
    id: int = Field(..., description="会议ID")

class MeetingQuery(BaseModel):
    """会议查询参数"""
    name: Optional[str] = Field(None, description="会议名称")
    status: Optional[int] = Field(None, description="会议状态")
    start_time_begin: Optional[datetime] = Field(None, description="开始时间范围-起始")
    start_time_end: Optional[datetime] = Field(None, description="开始时间范围-结束")
    page_num: int = Field(1, description="页码")
    page_size: int = Field(10, description="每页大小")

class MeetingResponse(BaseModel):
    """会议响应模型"""
    id: int = Field(..., description="会议ID")
    name: str = Field(..., description="会议名称")
    description: Optional[str] = Field(None, description="会议描述")
    location: str = Field(..., description="会议地点")
    start_time: datetime = Field(..., description="会议开始时间")
    end_time: datetime = Field(..., description="会议结束时间")
    sign_start: datetime = Field(..., description="签到开始时间")
    sign_end: datetime = Field(..., description="签到结束时间")
    status: int = Field(..., description="会议状态")
    status_text: str = Field(..., description="会议状态文本")
    creator_name: str = Field(..., description="创建人姓名")
    create_time: datetime = Field(..., description="创建时间")
    dept_names: List[str] = Field([], description="允许参加的部门名称列表")
    user_names: List[str] = Field([], description="指定参会人员姓名列表")

    class Config:
        orm_mode = True

class MeetingAttendeeQuery(BaseModel):
    """参会人员查询参数"""
    meeting_id: int = Field(..., description="会议ID")
    sign_status: Optional[int] = Field(None, description="签到状态")
    user_name: Optional[str] = Field(None, description="用户姓名")
    page_num: int = Field(1, description="页码")
    page_size: int = Field(10, description="每页大小")

class MeetingAttendeeResponse(BaseModel):
    """参会人员响应模型"""
    id: int = Field(..., description="记录ID")
    user_id: int = Field(..., description="用户ID")
    user_name: str = Field(..., description="用户姓名")
    dept_name: str = Field(..., description="部门名称")
    sign_status: int = Field(..., description="签到状态")
    sign_status_text: str = Field(..., description="签到状态文本")
    sign_time: Optional[datetime] = Field(None, description="签到时间")
    similarity: Optional[float] = Field(None, description="人脸相似度")
    sign_device: Optional[str] = Field(None, description="签到设备")
    face_image_path: Optional[str] = Field(None, description="人脸照片路径")

    class Config:
        orm_mode = True

class MeetingStatsResponse(BaseModel):
    """会议统计响应模型"""
    meeting_id: int = Field(..., description="会议ID")
    meeting_name: str = Field(..., description="会议名称")
    total_attendees: int = Field(0, description="总参会人数")
    signed_total: int = Field(0, description="已签到总人数")
    not_signed: int = Field(0, description="未签到人数")
    signed: int = Field(0, description="正常签到人数")
    late: int = Field(0, description="迟到人数")
    leave_early: int = Field(0, description="早退人数")
    sign_rate: float = Field(0.0, description="签到率")
    latest_signs: List[dict] = Field([], description="最新签到记录")

class SignInRequest(BaseModel):
    """签到请求模型"""
    meeting_id: int = Field(..., description="会议ID")
    user_id: int = Field(..., description="用户ID")
    similarity: float = Field(..., description="人脸相似度")
    sign_time: datetime = Field(..., description="签到时间")
    device: Optional[str] = Field("Web终端", description="签到设备")
    location: Optional[str] = Field("未知", description="签到位置")
    image_data: Optional[str] = Field(None, description="签到照片数据（Base64）")

class SignInResponse(BaseModel):
    """签到响应模型"""
    success: bool = Field(..., description="是否成功")
    message: Optional[str] = Field(None, description="结果消息")
    user_id: Optional[int] = Field(None, description="用户ID")
    user_name: Optional[str] = Field(None, description="用户姓名")
    sign_status: Optional[int] = Field(None, description="签到状态")
    sign_time: Optional[str] = Field(None, description="签到时间")

class MeetingExportResponse(BaseModel):
    """会议导出响应模型"""
    meeting_id: int = Field(..., description="会议ID")
    meeting_name: str = Field(..., description="会议名称")
    headers: List[str] = Field(..., description="导出表头")
    rows: List[List[str]] = Field(..., description="导出数据行")

class UserMeetingResponse(BaseModel):
    """用户会议响应模型"""
    id: int = Field(..., description="会议ID")
    name: str = Field(..., description="会议名称")
    location: str = Field(..., description="会议地点")
    start_time: str = Field(..., description="会议开始时间")
    end_time: str = Field(..., description="会议结束时间")
    sign_start: str = Field(..., description="签到开始时间")
    sign_end: str = Field(..., description="签到结束时间")
    status: int = Field(..., description="会议状态")
    sign_status: int = Field(..., description="用户签到状态")