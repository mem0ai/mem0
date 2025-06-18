import uuid # Import Python's uuid module
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import User, App
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def get_or_create_user(db: Session, supabase_user_id: str, email: Optional[str] = None) -> User:
    """
    Get or create a user based on the Supabase User ID.
    The Supabase User ID (a UUID string) will be stored in User.id (PK, UUID type)
    and also in User.user_id (String type) for compatibility or future use.
    
    Uses database-level constraints to prevent race conditions and duplicate users.
    """
    # First try to find user by the string user_id
    user = db.query(User).filter(User.user_id == supabase_user_id).first()
    if user:
        # Update email if provided and not set, but only if no other user has this email
        if email and not user.email:
            # Check if another user already has this email
            existing_user_with_email = db.query(User).filter(User.email == email).first()
            # Check if the email is taken by a *different* user
            if existing_user_with_email and existing_user_with_email.user_id != supabase_user_id:
                logger.warning(f"Cannot update user {supabase_user_id} ({user.id}) with email {email} - email already exists for a different user {existing_user_with_email.user_id} ({existing_user_with_email.id})")
                # Don't update the email to avoid constraint violation
                return user
            
            # Safe to update email
            user.email = email
            user.name = user.name or (email.split("@")[0] if email else supabase_user_id)
            try:
                db.commit()
                db.refresh(user)
            except IntegrityError as e:
                db.rollback()
                logger.error(f"Integrity error updating user {supabase_user_id}: {e}")
                # Return user without email update rather than failing
                return user
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating user {supabase_user_id}: {e}")
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
    
    # RACE CONDITION FIX: Use database-level ON CONFLICT to handle concurrent inserts
    # Create new user with proper error handling for race conditions
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
    except IntegrityError as e:
        db.rollback()
        # RACE CONDITION HANDLING: If there's an integrity error, another thread likely created the user
        # Try to find the existing user by user_id (most reliable) or email
        logger.info(f"IntegrityError creating user {supabase_user_id}, attempting to find existing user: {e}")
        
        # First try by user_id (most reliable)
        existing_user = db.query(User).filter(User.user_id == supabase_user_id).first()
        if existing_user:
            logger.info(f"Found existing user by user_id: {existing_user.user_id}")
            return existing_user
        
        # If email was provided and caused the conflict, try by email
        if email:
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                logger.info(f"Found existing user by email: {existing_user.email}")
                return existing_user
        
        # If we still can't find the user, this is a real error
        logger.error(f"Could not create or find user {supabase_user_id} after IntegrityError: {e}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user {supabase_user_id}: {e}")
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
