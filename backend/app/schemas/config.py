from pydantic import BaseModel

class ConfigUpdate(BaseModel):
    face_threshold: float
    enable_liveness: bool

class ConfigOut(ConfigUpdate):
    id: int

    class Config:
        orm_mode = True
