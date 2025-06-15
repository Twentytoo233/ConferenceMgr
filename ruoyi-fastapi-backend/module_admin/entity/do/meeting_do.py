"""
会议模块数据对象定义
对应数据库表结构
"""

from datetime import datetime
from tortoise import fields, models
from enum import IntEnum
from module_admin.entity.do.user_do import SysUser
from module_admin.entity.do.dept_do import SysDept


class MeetingStatus(IntEnum):
    """会议状态枚举"""
    NOT_STARTED = 0  # 未开始
    IN_PROGRESS = 1  # 进行中
    FINISHED = 2  # 已结束
    CANCELED = 3  # 已取消


class SignStatus(IntEnum):
    """签到状态枚举"""
    NOT_SIGNED = 0  # 未签到
    SIGNED = 1  # 已签到
    LATE = 2  # 迟到
    LEAVE_EARLY = 3  # 早退


class Meeting(models.Model):
    """
    会议主表模型
    """
    id = fields.IntField(pk=True, description="会议ID")
    name = fields.CharField(max_length=100, description="会议名称")
    description = fields.TextField(null=True, description="会议描述")
    location = fields.CharField(max_length=200, description="会议地点")

    # 时间相关字段
    start_time = fields.DatetimeField(description="会议开始时间")
    end_time = fields.DatetimeField(description="会议结束时间")
    sign_start = fields.DatetimeField(description="签到开始时间")
    sign_end = fields.DatetimeField(description="签到结束时间")

    # 状态字段
    status = fields.IntEnumField(
        MeetingStatus,
        default=MeetingStatus.NOT_STARTED,
        description="会议状态"
    )

    # 组织关系
    creator: fields.ForeignKeyRelation[SysUser] = fields.ForeignKeyField(
        'models.SysUser',
        related_name='created_meetings',
        description="创建人"
    )
    depts: fields.ManyToManyRelation[SysDept] = fields.ManyToManyField(
        'models.SysDept',
        related_name='meetings',
        through='meeting_dept',
        description="允许参加的部门"
    )

    # 时间戳
    create_time = fields.DatetimeField(
        auto_now_add=True,
        description="创建时间"
    )
    update_time = fields.DatetimeField(
        auto_now=True,
        description="更新时间"
    )

    class Meta:
        table = "sys_meeting"
        table_description = "会议信息表"
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.name} ({self.start_time})"


class MeetingAttendee(models.Model):
    """
    会议参与人模型
    """
    id = fields.IntField(pk=True)
    meeting: fields.ForeignKeyRelation[Meeting] = fields.ForeignKeyField(
        'models.Meeting',
        related_name='attendees',
        description="所属会议"
    )
    user: fields.ForeignKeyRelation[SysUser] = fields.ForeignKeyField(
        'models.SysUser',
        related_name='attended_meetings',
        description="参与人"
    )

    # 签到信息
    sign_status = fields.IntEnumField(
        SignStatus,
        default=SignStatus.NOT_SIGNED,
        description="签到状态"
    )
    sign_time = fields.DatetimeField(
        null=True,
        description="签到时间"
    )
    sign_device = fields.CharField(
        max_length=100,
        null=True,
        description="签到设备"
    )
    sign_location = fields.CharField(
        max_length=200,
        null=True,
        description="签到位置"
    )

    # 人脸识别相关
    similarity = fields.FloatField(
        null=True,
        description="人脸识别相似度"
    )
    face_image_path = fields.CharField(
        max_length=255,
        null=True,
        description="签到人脸照片路径"
    )

    # 时间戳
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "sys_meeting_attendee"
        table_description = "会议参会人员表"
        unique_together = (("meeting", "user"),)

    def __str__(self):
        return f"{self.user.user_name} in {self.meeting.name}"


# 会议-部门关联表（多对多中间表）
class MeetingDept(models.Model):
    """
    会议-部门关联表
    """
    meeting: fields.ForeignKeyRelation[Meeting] = fields.ForeignKeyField(
        'models.Meeting',
        related_name='meeting_depts',
        description="会议ID"
    )
    dept: fields.ForeignKeyRelation[SysDept] = fields.ForeignKeyField(
        'models.SysDept',
        related_name='dept_meetings',
        description="部门ID"
    )

    class Meta:
        table = "meeting_dept"
        table_description = "会议-部门关联表"
        unique_together = (("meeting", "dept"),)