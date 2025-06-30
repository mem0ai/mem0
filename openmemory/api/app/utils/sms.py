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
    
    async def process_command(self, message: str, user_id: str) -> str:
        """
        Process SMS command using AI to select the appropriate memory tool.
        Limited to: add_memories, ask_memory, deep_memory_query
        
        Args:
            message: The SMS message content
            user_id: User ID for context
            
        Returns:
            str: Response message to send back via SMS
        """
        from openai import OpenAI
        from app.tools.memory import ask_memory, add_memories
        from app.tools.documents import deep_memory_query
        import os
        import json
        
        try:
            # Handle special commands first
            if message.lower().strip() in ['help', 'commands', '?']:
                return """Hi! I'm Jean Memory, your personal AI memory assistant. Text me like you're talking to a trusted friend who remembers everything:

💾 Save memories:
"Remember I had a great meeting with Sarah today"
"I'm feeling anxious about tomorrow's presentation"
"My favorite coffee spot is Blue Bottle on Market St"

🔍 Find memories:
"What do I remember about Sarah?"
"When did I last feel anxious about work?"
"Tell me about my favorite places"

🧠 Understand patterns:
"How do my work meetings usually go?"
"What patterns do you see in my mood?"
"Analyze my relationship with anxiety"

I'm here to help you capture, organize, and understand your life experiences. Just text naturally!

Reply STOP to unsubscribe."""

            # Initialize OpenAI client
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # AI prompt to determine which tool to use
            tool_selection_prompt = f"""
You are Jean Memory's SMS assistant - a friendly, conversational AI that helps users manage their personal memories via text. You're like texting a smart friend who remembers everything about their life.

IMPORTANT: You are a CHATBOT FIRST, memory tool SECOND. Many messages just need friendly conversation - not every message needs a memory tool.

User's message: "{message}"

CONVERSATIONAL CONTEXT - Choose the right response type:

🗣️ **CHAT ONLY** (no tool) - Use for:
- Greetings: "Hey", "Hi", "Yo", "What's up"
- General conversation: "How are you?", "What's going on?"
- Thanks/acknowledgments: "Thanks", "Cool", "Awesome"
- Quick questions about YOU: "What's your name?", "What do you do?"

💾 **add_memories** - Use for:
- Personal experiences: "I just had dinner with Sarah", "Feeling stressed about work"
- Facts to remember: "My favorite coffee is Blue Bottle", "I live in Seattle"
- Goals/plans: "I want to learn Spanish", "Meeting Tom tomorrow"
- Feelings/thoughts: "I'm excited about the project", "Worried about the presentation"

🔍 **ask_memory** - Use for:
- Specific questions about their past: "What do I remember about Sarah?", "When did I last go to that restaurant?"
- Recall requests: "Tell me about my meetings this week", "What did I say about my job?"

🧠 **deep_memory_query** - Use for:
- Pattern analysis: "How do I usually feel on Mondays?", "What patterns do you see in my relationships?"
- Insights: "Analyze my mood this month", "What trends do you notice?"

RESPONSE FORMAT:
- If CHAT ONLY: {{"response_type": "chat", "message": "your friendly response here"}}
- If using a tool: {{"response_type": "tool", "tool": "tool_name", "reasoning": "brief reason", "processed_message": "optimized message"}}

Examples:
- "Yo" → {{"response_type": "chat", "message": "Hey! Good to hear from you! What's going on?"}}
- "What's your name?" → {{"response_type": "chat", "message": "I'm Jean Memory! I'm your personal AI assistant who helps you remember and organize your thoughts and experiences. What's on your mind?"}}
- "I just had an amazing lunch" → {{"response_type": "tool", "tool": "add_memories", "reasoning": "storing positive experience", "processed_message": "Had an amazing lunch"}}
- "What did I say about my job?" → {{"response_type": "tool", "tool": "ask_memory", "reasoning": "recalling specific topic", "processed_message": "What did I say about my job?"}}
"""

            # Get AI decision
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": tool_selection_prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            # Parse AI response
            try:
                ai_decision = json.loads(response.choices[0].message.content.strip())
                response_type = ai_decision.get("response_type")
                
                if response_type == "chat":
                    # Direct chat response - no tool needed
                    response_msg = ai_decision.get("message", "Hey! I'm here to help with your thoughts and memories. What's on your mind?")
                    logger.info(f"SMS AI responded with chat-only message for '{message}'")
                    return response_msg
                
                elif response_type == "tool":
                    # Tool-based response
                    selected_tool = ai_decision.get("tool")
                    processed_message = ai_decision.get("processed_message", message)
                    reasoning = ai_decision.get("reasoning", "")
                    
                    logger.info(f"SMS AI selected tool '{selected_tool}' for message '{message}' - reasoning: {reasoning}")
                else:
                    logger.warning(f"Unknown response_type: {response_type}. Defaulting to ask_memory")
                    selected_tool = "ask_memory"
                    processed_message = message
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse AI tool selection: {e}. Defaulting to chat response")
                # Default to friendly chat response for parsing errors
                return "Hey! I'm here to help with your thoughts and memories. What would you like to talk about?"
            
            # Execute the selected tool
            if selected_tool == "add_memories":
                result = await add_memories(processed_message)
                # Natural, conversational confirmations
                confirmations = [
                    f"Got it! I'll remember that.",
                    f"Noted! Thanks for sharing that with me.",
                    f"I've added that to your memories 👍",
                    f"Cool, I'll keep that in mind!",
                    f"Saved! I won't forget that.",
                    f"Perfect, I've got that stored for you."
                ]
                import random
                response_msg = random.choice(confirmations)
                
            elif selected_tool == "deep_memory_query":
                result = await deep_memory_query(processed_message)
                # Keep deep analysis but make it more conversational
                if len(result) > 1300:
                    response_msg = f"{result[:1250]}...\n\nThere's more to explore - just ask!"
                else:
                    response_msg = result
                    
            else:  # Default to ask_memory  
                result = await ask_memory(processed_message)
                # More natural search responses
                if len(result) > 1300:
                    response_msg = f"{result[:1250]}...\n\nWant me to dig deeper into any of that?"
                else:
                    response_msg = result
            
            # Add natural help hints for very short responses
            if len(response_msg) < 50:
                response_msg += "\n\nAnything else you'd like to remember or ask about?"
                
            return response_msg
            
        except Exception as e:
            logger.error(f"Error processing SMS command '{message}': {e}")
            return "Hmm, I had trouble with that one. Could you rephrase it? I'm here to help with your memories - text 'help' for examples of what I can do!"


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
    def validate_webhook_signature(request_url: str, post_data: dict, signature: str) -> bool:
        """
        Validate Twilio webhook signature using official Twilio RequestValidator
        
        Args:
            request_url: The full request URL as string
            post_data: The form data as a dictionary
            signature: X-Twilio-Signature header value
        
        Returns:
            bool: True if signature is valid
        """
        if not sms_config.TWILIO_AUTH_TOKEN:
            logger.warning("Cannot validate webhook signature - no auth token configured")
            return False
        
        try:
            from twilio.request_validator import RequestValidator
            
            validator = RequestValidator(sms_config.TWILIO_AUTH_TOKEN)
            is_valid = validator.validate(request_url, post_data, signature)
            
            logger.info(f"Twilio signature validation result: {is_valid}")
            if not is_valid:
                logger.warning(f"Invalid signature for URL: {request_url}")
                logger.warning(f"Post data: {post_data}")
            
            return is_valid
            
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