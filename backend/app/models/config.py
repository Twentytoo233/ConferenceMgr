from sqlalchemy import Column, Integer, Float, Boolean
from app.db.base_class import Base

class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    face_threshold = Column(Float, default=0.7)  # 相似度阈值
    enable_liveness = Column(Boolean, default=False)  # 活体检测开关
