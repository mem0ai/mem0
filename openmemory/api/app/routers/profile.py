"""
Profile management router
Handles user profile data, phone number verification, and SMS settings
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, validator
from typing import Optional
import re
import logging

from app.database import get_db
from app.auth import get_current_supa_user
from gotrue.types import User as SupabaseUser
from app.utils.db import get_or_create_user
from app.models import User, SubscriptionTier
from app.middleware.subscription_middleware import SubscriptionChecker
from app.utils.sms import SMSService, SMSVerification, SMSRateLimit, sms_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

# Pydantic models for request/response
class ProfileResponse(BaseModel):
    user_id: str
    email: Optional[str]
    name: Optional[str]
    firstname: Optional[str]
    lastname: Optional[str]
    subscription_tier: str
    subscription_status: Optional[str]
    phone_number: Optional[str]
    phone_verified: bool
    sms_enabled: bool
    
    class Config:
        from_attributes = True

class PhoneNumberRequest(BaseModel):
    phone_number: str
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        # Remove common formatting characters
        cleaned = re.sub(r'[^\d+]', '', v)
        
        # Check if it's a valid US phone number format
        if cleaned.startswith('+1'):
            cleaned = cleaned[2:]
        elif cleaned.startswith('1'):
            cleaned = cleaned[1:]
        
        if len(cleaned) != 10:
            raise ValueError('Phone number must be a valid 10-digit US number')
        
        # Return in E.164 format
        return f"+1{cleaned}"

class VerificationCodeRequest(BaseModel):
    verification_code: str
    
    @validator('verification_code')
    def validate_code(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('Verification code must be 6 digits')
        return v

class SMSSettingsRequest(BaseModel):
    sms_enabled: bool

class ProfileUpdateRequest(BaseModel):
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    
    @validator('firstname', allow_reuse=True)
    def validate_firstname(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        if v is not None and len(v.strip()) > 100:
            raise ValueError('First name must be less than 100 characters')
        return v.strip() if v else None
    
    @validator('lastname', allow_reuse=True)
    def validate_lastname(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        if v is not None and len(v.strip()) > 100:
            raise ValueError('Last name must be less than 100 characters')
        return v.strip() if v else None

# Profile endpoints
@router.get("", response_model=ProfileResponse)
async def get_profile(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Get user profile information including SMS settings"""
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    return ProfileResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        firstname=user.firstname,
        lastname=user.lastname,
        subscription_tier=user.subscription_tier.value,
        subscription_status=user.subscription_status,
        phone_number=user.phone_number,
        phone_verified=user.phone_verified or False,
        sms_enabled=user.sms_enabled if user.sms_enabled is not None else True
    )

@router.put("", response_model=ProfileResponse)
async def update_profile(
    request: ProfileUpdateRequest,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Update user profile information (firstname and lastname)"""
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    # Update fields if provided
    if request.firstname is not None:
        user.firstname = request.firstname
    if request.lastname is not None:
        user.lastname = request.lastname
    
    try:
        db.commit()
        logger.info(f"Successfully updated profile for user {user.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update profile for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")
    
    return ProfileResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        firstname=user.firstname,
        lastname=user.lastname,
        subscription_tier=user.subscription_tier.value,
        subscription_status=user.subscription_status,
        phone_number=user.phone_number,
        phone_verified=user.phone_verified or False,
        sms_enabled=user.sms_enabled if user.sms_enabled is not None else True
    )

@router.post("/phone/add")
async def add_phone_number(
    request: PhoneNumberRequest,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Add and send verification code to a phone number. No subscription required."""
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    logger.info(f"Initiating phone number add for user {user.id} with number {request.phone_number}")

    # NOTE: Subscription check is moved to the webhook that handles incoming SMS.
    # Any user can add and verify a number.
    
    # Check if SMS is configured
    if not sms_config.is_configured:
        raise HTTPException(
            status_code=503, 
            detail="SMS service is not available at this time"
        )
    
    # Check verification attempts to prevent abuse (much more liberal limit)
    if user.phone_verification_attempts and user.phone_verification_attempts >= 20:
        raise HTTPException(
            status_code=429,
            detail="Too many verification attempts today. Please try again tomorrow or reach out to the team."
        )
    
    # Check if phone number is already taken by another user
    existing_user = db.query(User).filter(
        User.phone_number == request.phone_number,
        User.id != user.id
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="This phone number is already registered to another account"
        )
    
    # Generate verification code
    verification_code = SMSVerification.generate_verification_code()
    
    # --- ATOMIC OPERATION: Send SMS first, then update DB ---
    
    # 1. Send SMS
    sms_service = SMSService()
    try:
        sms_sent = sms_service.send_verification_code(request.phone_number, verification_code)
        if not sms_sent:
            # The service itself might return False without raising an exception
            raise Exception("SMS service returned failure")
        logger.info(f"Successfully sent verification SMS to {request.phone_number} for user {user.id}")
    except Exception as e:
        logger.error(f"Failed to send verification SMS to {request.phone_number}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to send verification code. Please try again later."
        )

    # 2. If SMS is successful, now commit all DB changes in one transaction
    try:
        # Store verification code without committing
        if not SMSVerification.store_verification_code(user, verification_code, db, commit=False):
            raise HTTPException(
                status_code=500,
                detail="Failed to prepare verification code for storage"
            )

        # Flag the metadata field as modified to ensure the change is detected
        flag_modified(user, "metadata_")

        # Update user with phone number and increment attempts
        user.phone_number = request.phone_number
        user.phone_verified = False
        user.phone_verification_attempts = (user.phone_verification_attempts or 0) + 1
        
        db.commit()
        logger.info(f"Successfully updated user {user.id} profile with new phone number.")

    except Exception as e:
        db.rollback()
        logger.error(f"Database error after sending SMS for user {user.id}: {e}")
        # Inform the user that SMS was sent but DB update failed
        raise HTTPException(
            status_code=500, 
            detail="Verification code was sent, but we encountered a database error. Please contact support."
        )

    return {
        "message": "Verification code sent to your phone",
        "phone_number": request.phone_number,
        "expires_in_minutes": sms_config.SMS_VERIFICATION_TIMEOUT // 60
    }

@router.post("/phone/verify")
async def verify_phone_number(
    request: VerificationCodeRequest,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Verify phone number with code. No subscription required."""
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    logger.info(f"Initiating phone verification for user {user.id} with number {user.phone_number}")
    
    # NOTE: Subscription check is moved to the webhook that handles incoming SMS.
    
    if not user.phone_number:
        raise HTTPException(
            status_code=400,
            detail="No phone number to verify. Please add a phone number first."
        )
    
    # Verify the code
    if SMSVerification.verify_code(user, request.verification_code, db):
        # Reset verification attempts on success
        user.phone_verification_attempts = 0
        user.sms_enabled = True
        db.commit()
        
        # --- Send a welcome MMS with contact card ---
        try:
            sms_service = SMSService()
            sms_service.send_welcome_with_contact(user.phone_number)
            logger.info(f"Sent welcome MMS with contact card to user {user.id} at {user.phone_number}")
        except Exception as e:
            # Log if the welcome MMS fails, but don't fail the whole request
            # as the verification itself was successful.
            logger.error(f"Failed to send welcome MMS to user {user.id}: {e}")

        return {
            "message": "Phone number verified successfully",
            "phone_number": user.phone_number,
            "verified": True
        }
    else:
        # Logging for failure is handled inside SMSVerification.verify_code
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code"
        )

@router.delete("/phone")
async def remove_phone_number(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Remove phone number from account"""
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    # Clear phone-related fields
    user.phone_number = None
    user.phone_verified = False
    user.phone_verification_attempts = 0
    user.phone_verified_at = None
    user.sms_enabled = False
    
    # Clean up any pending verification in metadata
    if user.metadata_ and 'sms_verification' in user.metadata_:
        del user.metadata_['sms_verification']
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to remove phone number: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    
    return {"message": "Phone number removed successfully"}

@router.put("/sms/settings")
async def update_sms_settings(
    request: SMSSettingsRequest,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Update SMS notification settings"""
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    if not user.phone_verified:
        raise HTTPException(
            status_code=400,
            detail="Phone number must be verified before changing SMS settings"
        )
    
    user.sms_enabled = request.sms_enabled
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update SMS settings: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    
    return {
        "message": "SMS settings updated successfully",
        "sms_enabled": user.sms_enabled
    }

@router.get("/sms/usage")
async def get_sms_usage(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Get SMS usage statistics"""
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    # Get rate limits and current usage
    allowed, remaining = SMSRateLimit.check_rate_limit(user, db)
    
    # Get limit based on subscription tier
    if user.subscription_tier == SubscriptionTier.ENTERPRISE:
        daily_limit = sms_config.SMS_RATE_LIMIT_ENTERPRISE
    elif user.subscription_tier == SubscriptionTier.PRO:
        daily_limit = sms_config.SMS_RATE_LIMIT_PRO
    else:
        daily_limit = 0
    
    used_today = daily_limit - remaining if allowed else daily_limit
    
    return {
        "daily_limit": daily_limit,
        "used_today": used_today,
        "remaining_today": remaining,
        "subscription_tier": user.subscription_tier.value,
        "phone_verified": user.phone_verified or False,
        "sms_enabled": user.sms_enabled if user.sms_enabled is not None else True
    } 