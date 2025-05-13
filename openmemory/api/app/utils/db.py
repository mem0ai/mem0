from sqlalchemy.orm import Session
from app.models import User, App
from typing import Tuple


def get_or_create_user(db: Session, user_id: str) -> User:
    """Get or create a user with the given user_id"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(user_id=user_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_or_create_app(db: Session, user: User, app_id: str) -> App:
    """Get or create an app for the given user"""
    app = db.query(App).filter(App.owner_id == user.id, App.name == app_id).first()
    if not app:
        app = App(owner_id=user.id, name=app_id)
        db.add(app)
        db.commit()
        db.refresh(app)
    return app


def get_user_and_app(db: Session, user_id: str, app_id: str) -> Tuple[User, App]:
    """Get or create both user and their app"""
    user = get_or_create_user(db, user_id)
    app = get_or_create_app(db, user, app_id)
    return user, app
