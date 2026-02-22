from typing import Tuple

from app.models import App, User
from sqlalchemy import or_
from sqlalchemy.orm import Session


def get_or_create_user(db: Session, user_id: str) -> User:
    """Get or create a user with the given user_id.

    If user_id contains '@', also matches against the email field,
    so callers can pass an email address as the user identifier.
    """
    if "@" in user_id:
        user = db.query(User).filter(
            or_(User.user_id == user_id, User.email == user_id)
        ).first()
    else:
        user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        user = User(user_id=user_id)
        if "@" in user_id:
            user.email = user_id
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
