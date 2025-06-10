from sqlalchemy.orm import Session
from app.models.config import SystemConfig
from app.schemas.config import ConfigUpdate

def get_config(db: Session):
    return db.query(SystemConfig).first()

def update_config(db: Session, config_in: ConfigUpdate):
    config = get_config(db)
    if config:
        config.face_threshold = config_in.face_threshold
        config.enable_liveness = config_in.enable_liveness
        db.commit()
        db.refresh(config)
        return config
    return None
