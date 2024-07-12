from models import AppModel
from sqlalchemy.orm import Session


def get_app(db: Session, app_id: str):
    return db.query(AppModel).filter(AppModel.app_id == app_id).first()


def get_apps(db: Session, skip: int = 0, limit: int = 100):
    return db.query(AppModel).offset(skip).limit(limit).all()


def save_app(db: Session, app_id: str, config: str):
    db_app = AppModel(app_id=app_id, config=config)
    db.add(db_app)
    db.commit()
    db.refresh(db_app)
    return db_app


def remove_app(db: Session, app_id: str):
    db_app = db.query(AppModel).filter(AppModel.app_id == app_id).first()
    db.delete(db_app)
    db.commit()
    return db_app
