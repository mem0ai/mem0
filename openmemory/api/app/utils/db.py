import uuid # Import Python's uuid module
from sqlalchemy.orm import Session
from app.models import User, App
from typing import Tuple, Optional


def get_or_create_user(db: Session, supabase_user_id: str, email: Optional[str] = None) -> User:
    """
    Get or create a user based on the Supabase User ID.
    The Supabase User ID (a UUID string) will be stored in User.id (PK, UUID type)
    and also in User.user_id (String type) for compatibility or future use.
    """
    # Convert string Supabase ID to UUID object for querying User.id
    user_pk_uuid = uuid.UUID(supabase_user_id)

    user = db.query(User).filter(User.id == user_pk_uuid).first()
    if not user:
        user = User(
            id=user_pk_uuid, # Set the PK directly
            user_id=supabase_user_id, # Also set the string user_id field
            email=email,
            name=email.split("@")[0] if email else supabase_user_id # Basic name generation
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception as e:
            db.rollback()
            # Log the error, e.g., logger.error(f"Error creating user {supabase_user_id}: {e}")
            raise # Re-raise after rollback
    elif email and not user.email: # If user exists but email was not set
        user.email = email
        user.name = user.name or (email.split("@")[0] if email else supabase_user_id) # Update name if not set
        try:
            db.commit()
            db.refresh(user)
        except Exception as e:
            db.rollback()
            # Log error
            raise
    return user


def get_or_create_app(db: Session, user: User, app_name: str) -> App:
    """Get or create an app for the given user by app_name."""
    # Ensure user.id is a UUID, which it should be if fetched/created by get_or_create_user
    if not isinstance(user.id, uuid.UUID):
        # This case should ideally not happen if user object is correctly managed
        # Consider logging a warning or raising an error.
        pass # Assuming user.id is already a Python UUID object from the User model

    app = db.query(App).filter(App.owner_id == user.id, App.name == app_name).first()
    if not app:
        app = App(owner_id=user.id, name=app_name, description=f"App '{app_name}' for user {user.id}")
        db.add(app)
        try:
            db.commit()
            db.refresh(app)
        except Exception as e:
            db.rollback()
            # Log error
            raise
    return app


def get_user_and_app(db: Session, supabase_user_id: str, app_name: str, email: Optional[str] = None) -> Tuple[User, App]:
    """Get or create both user (from Supabase ID) and their app by name."""
    user = get_or_create_user(db, supabase_user_id, email=email)
    app = get_or_create_app(db, user, app_name)
    return user, app
