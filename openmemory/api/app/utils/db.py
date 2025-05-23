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
    # First try to find user by the string user_id
    user = db.query(User).filter(User.user_id == supabase_user_id).first()
    if user:
        # Update email if provided and not set
        if email and not user.email:
            user.email = email
            user.name = user.name or (email.split("@")[0] if email else supabase_user_id)
            try:
                db.commit()
                db.refresh(user)
            except Exception as e:
                db.rollback()
                raise
        return user
    
    # Try to convert string to UUID, or create a deterministic UUID if it fails
    try:
        # If it's already a valid UUID string, use it directly
        user_pk_uuid = uuid.UUID(supabase_user_id)
    except ValueError:
        # If not a valid UUID, create a deterministic UUID from the string
        # Using UUID5 with a namespace to ensure consistency
        user_pk_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, supabase_user_id)
    
    # Check if a user with this UUID already exists (edge case)
    existing_user = db.query(User).filter(User.id == user_pk_uuid).first()
    if existing_user:
        return existing_user
    
    # Create new user
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
