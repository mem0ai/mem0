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
        Available tools: add_memories, ask_memory, deep_memory_query, chat_only
        
        Args:
            message: The SMS message content
            user_id: User ID for context
            
        Returns:
            str: Response message to send back via SMS
        """
        from app.tools.memory import ask_memory, add_memories
        from app.tools.documents import deep_memory_query
        import os
        
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

🧠 Deep analysis & synthesis:
"How do my work meetings usually go?"
"What patterns do you see in my mood?"
"Analyze my relationship with anxiety"
"Find insights across all my documents"

I can search your memories AND analyze full documents for deeper insights. Just text naturally!

Reply STOP to unsubscribe."""

            # Hard-coded patterns for reliability (fallback if AI fails)
            message_lower = message.lower().strip()
            
            # ALWAYS use ask_memory for these common patterns
            if any(pattern in message_lower for pattern in [
                "what do you know about me",
                "what do you remember about",
                "tell me about my",
                "what did I say about",
                "what have I told you",
                "what memories do",
                "do you remember",
                "remind me about"
            ]):
                logger.info(f"SMS hard-coded pattern match: using ask_memory for '{message}'")
                result = await ask_memory(message)
                if len(result) > 1300:
                    return f"{result[:1250]}...\n\nWant me to dig deeper into any of that?"
                else:
                    return result
            
            # ALWAYS use add_memories for clear storage patterns
            if any(pattern in message_lower for pattern in [
                "remember that",
                "don't forget",
                "i just",
                "today i",
                "i'm feeling",
                "my favorite"
            ]) or message_lower.startswith(("remember", "save", "store")):
                logger.info(f"SMS hard-coded pattern match: using add_memories for '{message}'")
                result = await add_memories(message)
                confirmations = [
                    "Got it! I'll remember that.",
                    "Noted! Thanks for sharing that with me.",
                    "I've added that to your memories 👍",
                    "Cool, I'll keep that in mind!",
                    "Saved! I won't forget that.",
                    "Perfect, I've got that stored for you."
                ]
                import random
                return random.choice(confirmations)

            # ALWAYS use deep_memory_query for complex analysis patterns
            if any(pattern in message_lower for pattern in [
                "analyze",
                "what patterns",
                "understand patterns",
                "how do my",
                "what insights",
                "synthesize",
                "find insights",
                "across all my",
                "in my documents",
                "deep dive",
                "comprehensive",
                "relationship between"
            ]):
                logger.info(f"SMS hard-coded pattern match: using deep_memory_query for '{message}'")
                result = await deep_memory_query(message)
                if len(result) > 1300:
                    return f"{result[:1250]}...\n\nThis was a deep analysis - I can go into more detail if you'd like!"
                else:
                    return result

            # Use Claude for everything else (superior tool calling)
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            
            # Claude tool calling prompt - much more sophisticated
            tool_selection_prompt = f"""You are Jean Memory, an intelligent SMS assistant that helps users manage their personal memories. You have access to powerful memory tools and should use them wisely.

User message: "{message}"

IMPORTANT: You are having a personal conversation via SMS. Always address the user directly as "you" (never "the user is" or third-person language). This is like texting a friend who remembers everything about you.

You have these tools available:
1. ask_memory - Search and recall existing memories to answer questions (fast, snippets only)
2. add_memories - Store new information, experiences, thoughts, or facts
3. deep_memory_query - Comprehensive analysis including full documents, synthesis across many memories, pattern recognition (slower but deeper)
4. chat_only - Respond conversationally without using tools

Use your intelligence to determine the best response. Consider:

- For simple questions about existing memories → use ask_memory
- When the user shares something to remember → use add_memories  
- For complex analysis, document searches, or "understand patterns" requests → use deep_memory_query
- For greetings or general conversation → use chat_only

Deep memory is perfect for: synthesis across many memories, finding needle-in-haystack information, analyzing full documents, understanding patterns and relationships.

Be smart, helpful, and conversational like you would be in any other Claude conversation. Remember: address them as "you" since this is a personal SMS conversation."""

            # Define tools for Claude
            tools = [
                {
                    "name": "ask_memory",
                    "description": "Search the user's memories to answer questions about their life, experiences, or information they've shared. Fast but only sees memory snippets.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The question or topic to search for in the user's memories"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "add_memories",
                    "description": "Store new information, experiences, thoughts, facts, or anything the user wants to remember",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string", 
                                "description": "The information to store in memory"
                            }
                        },
                        "required": ["content"]
                    }
                },
                {
                    "name": "deep_memory_query",
                    "description": "Comprehensive analysis including full documents, synthesis across many memories, pattern recognition. Use for complex questions that need deep analysis or document searching.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The complex question or analysis request"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "chat_only",
                    "description": "Respond conversationally without using memory tools - for greetings, questions about Jean Memory, or general chat",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "response": {
                                "type": "string",
                                "description": "The conversational response to send to the user"
                            }
                        },
                        "required": ["response"]
                    }
                }
            ]

            # Get Claude's decision with tool calling
            response = client.messages.create(
                model="claude-sonnet-4-20250514",  # Fast and smart for SMS
                max_tokens=300,
                messages=[{"role": "user", "content": tool_selection_prompt}],
                tools=tools
            )
            
            # Parse Claude's response
            try:
                # Check if Claude used a tool
                if response.content and any(isinstance(block, anthropic.types.ToolUseBlock) for block in response.content):
                    # Claude chose to use a tool
                    for block in response.content:
                        if isinstance(block, anthropic.types.ToolUseBlock):
                            tool_name = block.name
                            tool_input = block.input
                            
                            logger.info(f"SMS Claude selected tool '{tool_name}' for message '{message}'")
                            
                            if tool_name == "ask_memory":
                                result = await ask_memory(tool_input.get("query", message))
                                if len(result) > 1300:
                                    return f"{result[:1250]}...\n\nWant me to dig deeper into any of that?"
                                else:
                                    return result
                                    
                            elif tool_name == "add_memories":
                                result = await add_memories(tool_input.get("content", message))
                                confirmations = [
                                    "Got it! I'll remember that.",
                                    "Noted! Thanks for sharing that with me.",
                                    "I've added that to your memories 👍",
                                    "Cool, I'll keep that in mind!",
                                    "Saved! I won't forget that.",
                                    "Perfect, I've got that stored for you."
                                ]
                                import random
                                return random.choice(confirmations)
                                
                            elif tool_name == "deep_memory_query":
                                result = await deep_memory_query(tool_input.get("query", message))
                                if len(result) > 1300:
                                    return f"{result[:1250]}...\n\nThis was a deep analysis - I can go into more detail if you'd like!"
                                else:
                                    return result
                                    
                            elif tool_name == "chat_only":
                                return tool_input.get("response", "Hey! I'm here to help with your thoughts and memories. What's on your mind?")
                                
                else:
                    # Claude chose not to use tools, extract text response
                    text_response = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            text_response += block.text
                    
                    logger.info(f"SMS Claude responded with chat-only message for '{message}'")
                    return text_response or "Hey! I'm here to help with your thoughts and memories. What's on your mind?"
                
            except Exception as e:
                logger.warning(f"Failed to parse Claude response: {e}. Falling back to ask_memory")
                # Fallback to ask_memory for any parsing errors
                result = await ask_memory(message)
                if len(result) > 1300:
                    return f"{result[:1250]}...\n\nWant me to dig deeper into any of that?"
                else:
                    return result
            
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