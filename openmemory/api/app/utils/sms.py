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
from sqlalchemy.orm.attributes import flag_modified

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

    def send_welcome_with_contact(self, to_phone: str) -> bool:
        """
        Send welcome message with Jean Memory contact card as MMS
        
        Args:
            to_phone: Target phone number in E.164 format
        
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
            
            # Create vCard content
            vcf_content = f"""BEGIN:VCARD
VERSION:3.0
FN:Jean Memory
ORG:Jean Memory
TEL;TYPE=CELL:{sms_config.TWILIO_PHONE_NUMBER}
URL:https://jeanmemory.com
NOTE:Your personal AI memory assistant - text me anything you want to remember!
END:VCARD"""
            
            # Welcome message
            welcome_message = """Welcome to Jean Memory! 🎉 I've sent you my contact card so you can easily save my number.

Here's a quick guide to my main tools:
• 'ask_memory': For quick questions about what you've told me. It's fast but not as deep.
• 'deep_memory': For complex questions. It can synthesize information across all your memories to find patterns and deeper insights.

Try asking: "What did I say about work?" or "deep_memory: what are my main projects this quarter?"

Text me anything you want to remember. I'm here 24/7!"""

            # Create publicly accessible vCard URL
            # We'll use a simple approach: encode the vCard and use our API endpoint
            import base64
            import urllib.parse
            vcf_base64 = base64.b64encode(vcf_content.encode('utf-8')).decode('utf-8')
            
            # Use our API to serve the vCard file temporarily
            # This endpoint will be created to serve vCard files
            vcf_url = f"https://jean-memory-api-virginia.onrender.com/api/v1/vcard?data={urllib.parse.quote(vcf_base64)}"
            
            # Send MMS with contact card
            message = self.client.messages.create(
                body=welcome_message,
                from_=sms_config.TWILIO_PHONE_NUMBER,
                to=to_phone,
                media_url=[vcf_url]
            )
            
            logger.info(f"Welcome MMS with contact card sent successfully to {to_phone}, SID: {message.sid}")
            return True
            
        except TwilioException as e:
            logger.error(f"Failed to send welcome MMS to {to_phone}: {e}")
            # Fallback to regular SMS if MMS fails
            logger.info(f"Falling back to regular SMS for {to_phone}")
            fallback_message = "Welcome to Jean Memory! 🎉 You're all set. Save this number: +13648889368 and text me anything you want to remember. I'm here to help 24/7!"
            return self.send_sms(to_phone, fallback_message)
        except Exception as e:
            logger.error(f"Unexpected error sending welcome MMS to {to_phone}: {e}")
            # Fallback to regular SMS
            fallback_message = "Welcome to Jean Memory! 🎉 You're all set. Save this number: +13648889368 and text me anything you want to remember. I'm here to help 24/7!"
            return self.send_sms(to_phone, fallback_message)
    
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
    
    async def process_command(self, message: str, user_id: str, db=None) -> str:
        """
        Process SMS command using AI to select the appropriate memory tool.
        Available tools: add_memories, ask_memory, deep_memory_query, chat_only
        
        Args:
            message: The SMS message content
            user_id: User ID for context
            db: Database session for conversation history
            
        Returns:
            str: Response message to send back via SMS
        """
        from app.tools.memory import ask_memory, add_memories
        from app.tools.documents import deep_memory_query
        import os
        
        # Get conversation context if database session provided
        conversation_context = ""
        if db:
            conversation_context = SMSContextManager.get_conversation_context(user_id, db)
        
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

            # Use Claude for everything else (superior tool calling)
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            
            # Claude tool calling prompt - much more sophisticated
            # Include conversation context in the prompt
            conversation_part = f"\n\n{conversation_context}" if conversation_context else ""
            
            tool_selection_prompt = f"""You are Jean Memory, an intelligent SMS assistant that helps users manage their personal memories. You have access to powerful memory tools and should use them wisely.{conversation_part}

Current user message: "{message}"

IMPORTANT: You are having a personal conversation via SMS. Always address the user directly as "you" (never "the user is" or third-person language). This is like texting a friend who remembers everything about you.

CONVERSATION CONTINUITY: If there's recent conversation context above, use it to understand references like "that", "it", "what we talked about", "what did I just say", etc. The user may be referring to something from the recent conversation.

You have these tools available:
1. ask_memory - Search and recall existing memories to answer questions about their life, experiences, or information they've shared. Fast but only sees memory snippets. **Use this for questions about the current conversation.**
2. add_memories - Store new information, experiences, thoughts, facts. **Use this when the user explicitly asks to remember something.**
3. deep_memory_query - Comprehensive analysis including full documents, synthesis across many memories, pattern recognition (slower but deeper).
4. chat_only - Respond conversationally without using tools (for greetings, thanks, or if no other tool is appropriate).

Use your intelligence to determine the best response. If the user is asking about the conversation itself (e.g., "what did I just say?"), use the conversation context to answer. If they are asking a question, use `ask_memory`. If they are sharing something new, use `add_memories`.

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
    def store_verification_code(user, code: str, db: Session, commit: bool = True) -> bool:
        """
        Store verification code in user metadata
        
        Args:
            user: User model instance
            code: Verification code
            db: Database session
            commit: Whether to commit the transaction
        
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
            
            if commit:
                db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to store verification code for user {user.id}: {e}")
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
                logger.warning(f"Verification attempt for user {user.id} failed: No verification data found.")
                return False
            
            verification = user.metadata_['sms_verification']
            stored_code = verification.get('code')
            expires_at = verification.get('expires_at')
            
            if not stored_code or not expires_at:
                logger.warning(f"Verification attempt for user {user.id} failed: Incomplete verification data.")
                return False
            
            # Check if code has expired
            expires_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expires_datetime:
                # Clean up expired code
                logger.info(f"Verification attempt for user {user.id} failed: Code expired at {expires_at}.")
                del user.metadata_['sms_verification']
                flag_modified(user, "metadata_")
                db.commit()
                return False
            
            # Check if code matches
            if stored_code == submitted_code:
                # Mark as verified and clean up code
                logger.info(f"Verification successful for user {user.id} with phone {user.phone_number}.")
                user.phone_verified = True
                user.phone_verified_at = datetime.now(timezone.utc)
                del user.metadata_['sms_verification']
                flag_modified(user, "metadata_")
                db.commit()
                return True
            
            logger.warning(f"Verification attempt for user {user.id} failed: Submitted code did not match stored code.")
            return False
            
        except Exception as e:
            logger.error(f"Error during SMS code verification for user {user.id}: {e}")
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


class SMSContextManager:
    """Manages SMS conversation context and history"""
    
    @staticmethod
    def add_message_to_conversation(user_id: str, phone_number: str, content: str, role: str, db) -> bool:
        """
        Add a message to the SMS conversation history
        
        Args:
            user_id: UUID of the user
            phone_number: Phone number for logging
            content: Message content
            role: 'user' for incoming, 'assistant' for outgoing
            db: Database session
        
        Returns:
            bool: True if added successfully
        """
        try:
            from app.models import SMSConversation, SMSRole, User
            from uuid import UUID
            
            # Get user by user_id to ensure we have the correct UUID
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                logger.error(f"User not found for user_id {user_id}")
                return False
            
            # Map string role to enum
            sms_role = SMSRole.USER if role == 'user' else SMSRole.ASSISTANT
            
            # Create conversation record
            conversation = SMSConversation(
                user_id=user.id,  # Use the UUID primary key
                role=sms_role,
                content=content
            )
            
            db.add(conversation)
            db.commit()
            
            logger.info(f"Added SMS message to conversation history: user={user_id}, role={role}, content_length={len(content)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add SMS message to conversation: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def get_conversation_context(user_id: str, db, limit: int = 6) -> str:
        """
        Get recent conversation history for context
        
        Args:
            user_id: User ID string
            db: Database session
            limit: Number of recent messages to include
        
        Returns:
            str: Formatted conversation context
        """
        try:
            from app.models import SMSConversation, SMSRole, User
            
            # Get user by user_id 
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                return ""
            
            # Get recent conversation messages
            recent_messages = db.query(SMSConversation).filter(
                SMSConversation.user_id == user.id
            ).order_by(
                SMSConversation.created_at.desc()
            ).limit(limit).all()
            
            if not recent_messages:
                return ""
            
            # Format conversation history (reverse to show chronological order)
            context_lines = []
            for msg in reversed(recent_messages):
                role_label = "You" if msg.role == SMSRole.USER else "Jean Memory"
                context_lines.append(f"{role_label}: {msg.content}")
            
            context = "Recent conversation:\n" + "\n".join(context_lines)
            logger.info(f"Retrieved conversation context for user {user_id}: {len(recent_messages)} messages")
            return context
            
        except Exception as e:
            logger.error(f"Failed to get conversation context: {e}")
            return ""


# Export main classes and functions
__all__ = [
    'SMSService',
    'SMSVerification', 
    'SMSRateLimit',
    'SMSWebhookValidator',
    'SMSContextManager',
    'sms_config'
] 