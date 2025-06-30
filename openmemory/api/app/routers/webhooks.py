import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Form
from pydantic import BaseModel, validator
from twilio.twiml.messaging_response import MessagingResponse

from app.database import SessionLocal
from app.models import User
from app.auth import get_current_user
from app.utils.sms import SMSService, SMSWebhookValidator
from app.context import user_id_var, client_name_var

# Import tools from their new, correct locations
from app.tools.memory import ask_memory, add_memories, search_memory, list_memories
from app.tools.documents import deep_memory_query


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks")

# Pydantic models for request validation
class SMSWebhookPayload(BaseModel):
    MessageSid: str
    SmsSid: str
    AccountSid: str
    MessagingServiceSid: Optional[str] = None
    From: str
    To: str
    Body: str
    NumMedia: int
    
    @validator('From', 'To')
    def validate_phone_number(cls, v):
        if not v.startswith('+') or not v[1:].isdigit() or not (10 <= len(v) <= 15):
            raise ValueError('must be a valid E.164 formatted phone number')
        return v

class VerifyRequest(BaseModel):
    phone_number: str
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not v.startswith('+') or not v[1:].isdigit() or not (10 <= len(v) <= 15):
            raise ValueError('must be a valid E.164 formatted phone number')
        return v

class CheckRequest(BaseModel):
    phone_number: str
    verification_code: str
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not v.startswith('+') or not v[1:].isdigit() or not (10 <= len(v) <= 15):
            raise ValueError('must be a valid E.164 formatted phone number')
        return v

    @validator('verification_code')
    def validate_code(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('must be a 6-digit code')
        return v

sms_service = SMSService()

@router.post("/sms")
async def handle_sms(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
    SmsSid: str = Form(...),
    AccountSid: str = Form(...),
    NumMedia: int = Form(...),
    MessagingServiceSid: Optional[str] = Form(None),
):
    """
    Handle incoming SMS messages from Twilio.
    """
    # 1. Validate Twilio signature (Security First)
    signature = request.headers.get('X-Twilio-Signature', '')
    if not await SMSWebhookValidator.validate_webhook_signature(request, signature):
        logger.warning(f"Invalid Twilio webhook signature from {From}")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 2. Create Pydantic model from Form data for validation and structure
    payload = SMSWebhookPayload(
        From=From, To=To, Body=Body, MessageSid=MessageSid, SmsSid=SmsSid,
        AccountSid=AccountSid, NumMedia=NumMedia, MessagingServiceSid=MessagingServiceSid
    )

    user_phone = payload.From
    message_body = payload.Body.strip()

    db = SessionLocal()
    try:
        from app.utils.db import get_or_create_user
        user = get_or_create_user(db, None, None, phone_number=user_phone)

        if not user.phone_verified:
            await sms_service.send_message(
                to_phone=user_phone,
                body="Welcome to Jean Memory! Please verify your number on the website to get started."
            )
            return Response(content=str(MessagingResponse()), media_type="application/xml")

        # Set context variables for this user and client
        user_id_token = user_id_var.set(str(user.user_id))
        client_name_token = client_name_var.set("sms")

        try:
            # Process the message using the SMS service logic, which calls the tools
            response_message = await sms_service.process_command(message_body, str(user.user_id))
        finally:
            # Reset context variables
            user_id_var.reset(user_id_token)
            client_name_var.reset(client_name_token)
    
    finally:
        db.close()

    # Create TwiML response
    twilio_response = MessagingResponse()
    twilio_response.message(response_message)
    
    return Response(content=str(twilio_response), media_type="application/xml")

@router.post("/verify-phone")
async def verify_phone_number(req: VerifyRequest):
    """
    Sends a verification code to a user's phone number.
    """
    try:
        await sms_service.send_verification_code(req.phone_number)
        return {"status": "success", "message": "Verification code sent."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/check-verification")
async def check_verification_code(req: CheckRequest, current_user: User = Depends(get_current_user)):
    """
    Checks the verification code and links the phone number to the user's account.
    """
    db = SessionLocal()
    try:
        is_verified = await sms_service.check_verification_code(req.phone_number, req.verification_code)
        if is_verified:
            # Update user's phone number in the database
            user_to_update = db.query(User).filter(User.id == current_user.id).first()
            if user_to_update:
                user_to_update.phone_number = req.phone_number
                user_to_update.phone_verified = True
                db.commit()
                return {"status": "success", "message": "Phone number verified and linked."}
            else:
                raise HTTPException(status_code=404, detail="User not found")
        else:
            raise HTTPException(status_code=400, detail="Invalid verification code.")
    finally:
        db.close()

@router.get("/test-entry", include_in_schema=False)
async def test_entrypoint_for_platform():
    """A test entrypoint for the platform to verify service is up."""
    return {
        "service": "openmemory-api-webhooks",
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get("/platform/features", include_in_schema=False)
def get_platform_features():
    """Endpoint for platform feature discovery."""
    return {
        "service_name": "Open Memory Webhooks",
        "version": "1.0",
        "features": ["conversation_context", "ai_tool_selection", "pro_gated"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }