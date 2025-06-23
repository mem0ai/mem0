"""
SMS utility module for Twilio integration and verification
Handles SMS sending, verification codes, and rate limiting
"""
import os
import random
import string
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SMSConfig:
    """Configuration for SMS functionality"""
    def __init__(self):
        self.TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
        self.TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
        
        # Rate limits
        self.SMS_RATE_LIMIT_PRO = int(os.getenv("SMS_RATE_LIMIT_PRO", "50"))
        self.SMS_RATE_LIMIT_ENTERPRISE = int(os.getenv("SMS_RATE_LIMIT_ENTERPRISE", "200"))
        self.SMS_VERIFICATION_TIMEOUT = int(os.getenv("SMS_VERIFICATION_TIMEOUT", "600"))  # 10 minutes
        
        # Validation
        self.validate()
    
    def validate(self):
        """Validate SMS configuration"""
        if not all([self.TWILIO_ACCOUNT_SID, self.TWILIO_AUTH_TOKEN, self.TWILIO_PHONE_NUMBER]):
            logger.warning("Twilio configuration incomplete. SMS functionality will be disabled.")
            return False
        return True
    
    @property
    def is_configured(self) -> bool:
        """Check if SMS is properly configured"""
        return all([self.TWILIO_ACCOUNT_SID, self.TWILIO_AUTH_TOKEN, self.TWILIO_PHONE_NUMBER])

# Global SMS config instance
sms_config = SMSConfig()

class SMSService:
    """Service for SMS operations using Twilio"""
    
    def __init__(self):
        if sms_config.is_configured:
            self.client = Client(sms_config.TWILIO_ACCOUNT_SID, sms_config.TWILIO_AUTH_TOKEN)
        else:
            self.client = None
            logger.warning("SMS service initialized without Twilio configuration")
    
    def send_sms(self, to_phone: str, message: str) -> bool:
        """
        Send SMS message to phone number
        
        Args:
            to_phone: Target phone number in E.164 format
            message: Message content
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.client:
            logger.error("SMS service not configured")
            return False
        
        try:
            # Ensure phone number is in E.164 format
            if not to_phone.startswith('+'):
                to_phone = f"+1{to_phone.replace('-', '').replace('(', '').replace(')', '').replace(' ', '')}"
            
            message = self.client.messages.create(
                body=message,
                from_=sms_config.TWILIO_PHONE_NUMBER,
                to=to_phone
            )
            
            logger.info(f"SMS sent successfully to {to_phone}, SID: {message.sid}")
            return True
            
        except TwilioException as e:
            logger.error(f"Failed to send SMS to {to_phone}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {to_phone}: {e}")
            return False
    
    def send_verification_code(self, to_phone: str, code: str) -> bool:
        """
        Send verification code to phone number
        
        Args:
            to_phone: Target phone number
            code: Verification code
        
        Returns:
            bool: True if sent successfully
        """
        message = f"Your Jean Memory verification code is: {code}\n\nThis code expires in {sms_config.SMS_VERIFICATION_TIMEOUT // 60} minutes."
        return self.send_sms(to_phone, message)
    
    def send_command_response(self, to_phone: str, response: str) -> bool:
        """
        Send response to SMS command
        
        Args:
            to_phone: Target phone number
            response: Response message
        
        Returns:
            bool: True if sent successfully
        """
        # Truncate long responses
        if len(response) > 1600:  # SMS limit is 1600 chars
            response = response[:1550] + "...\n\nSend 'help' for commands."
        
        return self.send_sms(to_phone, response)


class SMSVerification:
    """Handle SMS verification codes"""
    
    @staticmethod
    def generate_verification_code() -> str:
        """Generate a 6-digit verification code"""
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def store_verification_code(user, code: str, db: Session) -> bool:
        """
        Store verification code in user metadata
        
        Args:
            user: User model instance
            code: Verification code
            db: Database session
        
        Returns:
            bool: True if stored successfully
        """
        try:
            if not user.metadata_:
                user.metadata_ = {}
            
            user.metadata_['sms_verification'] = {
                'code': code,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'expires_at': (datetime.now(timezone.utc) + timedelta(seconds=sms_config.SMS_VERIFICATION_TIMEOUT)).isoformat()
            }
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to store verification code: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def verify_code(user, submitted_code: str, db: Session) -> bool:
        """
        Verify submitted code against stored code
        
        Args:
            user: User model instance
            submitted_code: Code submitted by user
            db: Database session
        
        Returns:
            bool: True if code is valid
        """
        try:
            if not user.metadata_ or 'sms_verification' not in user.metadata_:
                return False
            
            verification = user.metadata_['sms_verification']
            stored_code = verification.get('code')
            expires_at = verification.get('expires_at')
            
            if not stored_code or not expires_at:
                return False
            
            # Check if code has expired
            expires_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expires_datetime:
                # Clean up expired code
                del user.metadata_['sms_verification']
                db.commit()
                return False
            
            # Check if code matches
            if stored_code == submitted_code:
                # Mark as verified and clean up code
                user.phone_verified = True
                user.phone_verified_at = datetime.now(timezone.utc)
                del user.metadata_['sms_verification']
                db.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying SMS code: {e}")
            return False


class SMSRateLimit:
    """Handle SMS rate limiting"""
    
    @staticmethod
    def check_rate_limit(user, db: Session) -> tuple[bool, int]:
        """
        Check if user is within SMS rate limits
        
        Args:
            user: User model instance
            db: Database session
        
        Returns:
            tuple: (allowed: bool, remaining: int)
        """
        from app.models import SubscriptionTier
        
        # Get rate limit based on subscription tier
        if user.subscription_tier == SubscriptionTier.ENTERPRISE:
            daily_limit = sms_config.SMS_RATE_LIMIT_ENTERPRISE
        elif user.subscription_tier == SubscriptionTier.PRO:
            daily_limit = sms_config.SMS_RATE_LIMIT_PRO
        else:
            return False, 0  # Free users can't use SMS
        
        # Get today's usage from metadata
        today = datetime.now(timezone.utc).date().isoformat()
        
        if not user.metadata_:
            user.metadata_ = {}
        
        sms_usage = user.metadata_.get('sms_usage', {})
        today_usage = sms_usage.get(today, 0)
        
        remaining = daily_limit - today_usage
        allowed = remaining > 0
        
        return allowed, remaining
    
    @staticmethod
    def increment_usage(user, db: Session) -> bool:
        """
        Increment SMS usage counter
        
        Args:
            user: User model instance
            db: Database session
        
        Returns:
            bool: True if incremented successfully
        """
        try:
            today = datetime.now(timezone.utc).date().isoformat()
            
            if not user.metadata_:
                user.metadata_ = {}
            
            if 'sms_usage' not in user.metadata_:
                user.metadata_['sms_usage'] = {}
            
            user.metadata_['sms_usage'][today] = user.metadata_['sms_usage'].get(today, 0) + 1
            
            # Clean up old usage data (keep only last 7 days)
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
            user.metadata_['sms_usage'] = {
                date: count for date, count in user.metadata_['sms_usage'].items()
                if date >= cutoff_date
            }
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to increment SMS usage: {e}")
            db.rollback()
            return False


class SMSWebhookValidator:
    """Validate Twilio webhook requests"""
    
    @staticmethod
    async def validate_webhook_signature(request: Any, signature: str) -> bool:
        """
        Validate Twilio webhook signature for security
        
        Args:
            request: The full FastAPI request object
            signature: X-Twilio-Signature header value
        
        Returns:
            bool: True if signature is valid
        """
        if not sms_config.TWILIO_AUTH_TOKEN:
            logger.warning("Cannot validate webhook signature - no auth token configured")
            return False
        
        try:
            request_url = str(request.url)
            post_body = await request.body()
            
            # --- BEGIN TEMPORARY DEBUGGING ---
            logger.info("--- SIGNATURE VALIDATION (SERVER-SIDE) ---")
            logger.info(f"Received URL: {request_url}")
            logger.info(f"Received POST Body (raw): {post_body}")
            string_to_sign = request_url.encode('utf-8') + post_body
            logger.info(f"String to Sign: {string_to_sign}")
            # --- END TEMPORARY DEBUGGING ---

            # Create the expected signature
            expected_signature = hmac.new(
                sms_config.TWILIO_AUTH_TOKEN.encode('utf-8'),
                string_to_sign,
                hashlib.sha1
            ).digest()
            
            # Encode to base64
            import base64
            expected_signature_b64 = base64.b64encode(expected_signature).decode('utf-8')
            
            return hmac.compare_digest(signature, expected_signature_b64)
            
        except Exception as e:
            logger.error(f"Error validating webhook signature: {e}")
            return False


# Export main classes and functions
__all__ = [
    'SMSService',
    'SMSVerification', 
    'SMSRateLimit',
    'SMSWebhookValidator',
    'sms_config'
] 