"""
SMS Webhooks router - Full MCP Integration with Context
Uses AI to select from ALL available MCP tools and maintains SMS conversation context
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import redis
import os

from app.database import get_db
from app.models import User, SubscriptionTier
from app.utils.sms import SMSService, SMSRateLimit, SMSWebhookValidator, sms_config
from app.mcp_server import (
    user_id_var, client_name_var, 
    ask_memory, add_memories, search_memory, list_memories, deep_memory_query
)
from app.utils.memory import get_memory_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# --- Redis Setup for Conversation Context ---
# Connect to Redis using environment variables, defaulting to the Docker service name
REDIS_HOST = os.getenv("REDIS_HOST", "redis_db")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CONVERSATION_TTL = timedelta(days=1)  # Conversations expire after 24 hours

try:
    # `decode_responses=True` makes Redis return strings instead of bytes
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    redis_client.ping()
    logger.info(f"Successfully connected to Redis for SMS context at {REDIS_HOST}:{REDIS_PORT}")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Could not connect to Redis: {e}. SMS context will not be persistent.")
    redis_client = None

class SMSContextManager:
    """Manages SMS conversation context in Redis for better responses"""

    @staticmethod
    def get_conversation_context(phone_number: str, limit: int = 5) -> str:
        """Get recent SMS conversation context from Redis"""
        if not redis_client:
            return ""
        
        try:
            conversation_json = redis_client.get(phone_number)
            if not conversation_json:
                return ""

            conversation = json.loads(conversation_json)
            recent_messages = conversation[-limit:]
            context_lines = []

            for msg in recent_messages:
                role = "User" if msg["direction"] == "incoming" else "Assistant"
                context_lines.append(f"{role}: {msg['message']}")

            return "\\n".join(context_lines) if context_lines else ""
        except Exception as e:
            logger.error(f"Error getting context from Redis for {phone_number}: {e}")
            return ""

    @staticmethod
    def add_to_conversation(phone_number: str, message: str, direction: str):
        """Add message to conversation context in Redis"""
        if not redis_client:
            return
            
        try:
            conversation = []
            # Get existing conversation or start a new one
            conversation_json = redis_client.get(phone_number)
            if conversation_json:
                conversation = json.loads(conversation_json)
            
            conversation.append({
                "message": message,
                "direction": direction,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Keep only the last 20 messages to prevent the list from growing indefinitely
            if len(conversation) > 20:
                conversation = conversation[-20:]
            
            # Save the updated conversation back to Redis with a 24-hour expiration
            redis_client.set(phone_number, json.dumps(conversation), ex=CONVERSATION_TTL)
            
        except Exception as e:
            logger.error(f"Error adding context to Redis for {phone_number}: {e}")

class SMSMCPRouter:
    """AI-powered router to select the best MCP tool for SMS messages"""
    
    @staticmethod
    async def select_tool_and_execute(message: str, context: str, user: User) -> str:
        """Use AI to select the best MCP tool and execute it"""
        
        # Get memory client for LLM access
        memory_client = get_memory_client()
        
        # AI prompt to decide which MCP tool to use
        decision_prompt = f"""You are an AI assistant analyzing an SMS message to decide which memory tool to use.

AVAILABLE TOOLS:
1. ask_memory: Fast search for simple questions about existing memories ("What should I buy?", "Tell me about my meetings")
2. add_memories: Store new information ("Remember to buy milk", "Meeting tomorrow at 3pm")  
3. search_memory: Keyword search through memories ("Find all notes about project X")
4. list_memories: Show recent memories ("Show my recent notes", "List my memories")
5. deep_memory_query: Comprehensive analysis of ALL content including documents ("Analyze my writing style", "Summarize all my work notes")

CONVERSATION CONTEXT:
{context}

NEW SMS MESSAGE: "{message}"

RULES:
- For questions about existing information: use ask_memory
- For storing new information: use add_memories
- For specific keyword searches: use search_memory  
- For browsing recent items: use list_memories
- For complex analysis requiring full documents: use deep_memory_query

Respond with ONLY the tool name: ask_memory, add_memories, search_memory, list_memories, or deep_memory_query"""

        try:
            # Use the LLM to decide which tool to use
            from mem0.llms.openai import OpenAILLM
            from mem0.configs.llms.base import BaseLlmConfig
            
            llm = OpenAILLM(config=BaseLlmConfig(model="gpt-4o-mini"))
            tool_decision = llm.generate_response([{"role": "user", "content": decision_prompt}])
            
            tool_name = tool_decision.strip().lower()
            logger.info(f"SMS AI selected tool: {tool_name} for message: {message[:50]}...")
            
            # Set MCP context
            user_token = user_id_var.set(user.user_id)
            client_token = client_name_var.set("sms")
            
            try:
                # Execute the selected MCP tool
                if tool_name == "ask_memory":
                    # Add context to the question if available
                    enhanced_message = f"{message}\n\nConversation context:\n{context}" if context else message
                    return await ask_memory(enhanced_message)
                
                elif tool_name == "add_memories":
                    result = await add_memories(message)
                    # Parse the JSON response to get a cleaner message
                    try:
                        parsed = json.loads(result)
                        return f"✅ {parsed.get('message', 'Memory added successfully')}"
                    except:
                        return result
                
                elif tool_name == "search_memory":
                    result = await search_memory(message, limit=5)
                    # Format search results for SMS
                    try:
                        memories = json.loads(result)
                        if memories:
                            formatted = [f"🔍 Found {len(memories)} memories:"]
                            for i, mem in enumerate(memories[:3], 1):
                                content = mem.get('memory', mem.get('content', ''))[:80]
                                formatted.append(f"{i}. {content}...")
                            if len(memories) > 3:
                                formatted.append(f"...and {len(memories) - 3} more")
                            return "\n".join(formatted)
                        else:
                            return f"❓ No memories found for: {message[:50]}..."
                    except:
                        return "🔍 Search completed - check your dashboard for results"
                
                elif tool_name == "list_memories":
                    result = await list_memories(limit=5)
                    # Format list for SMS
                    try:
                        memories = json.loads(result)
                        if memories:
                            formatted = ["📝 Recent memories:"]
                            for i, mem in enumerate(memories[:5], 1):
                                content = mem.get('memory', mem.get('content', ''))[:60]
                                formatted.append(f"{i}. {content}...")
                            return "\n".join(formatted)
                        else:
                            return "📝 No memories found."
                    except:
                        return "📝 Recent memories available in your dashboard"
                
                elif tool_name == "deep_memory_query":
                    # This is a heavy operation, let user know it's processing
                    result = await deep_memory_query(message)
                    # Truncate result for SMS (deep_memory_query can be very long)
                    if len(result) > 500:
                        return result[:497] + "..."
                    return result
                
                else:
                    # Fallback to ask_memory
                    return await ask_memory(message)
            
            finally:
                # Clean up MCP context
                try:
                    user_id_var.reset(user_token)
                    client_name_var.reset(client_token)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Error in MCP tool selection/execution: {e}")
            # Fallback to ask_memory
            try:
                user_token = user_id_var.set(user.user_id)
                client_token = client_name_var.set("sms")
                result = await ask_memory(message)
                user_id_var.reset(user_token)
                client_name_var.reset(client_token)
                return result
            except:
                return "❌ Error processing your message. Please try again."

@router.post("/sms")
async def handle_twilio_sms(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    To: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Handle incoming SMS from Twilio webhook
    Uses AI to select the best MCP tool and maintains conversation context
    """
    
    # Security checks
    if not sms_config.is_configured:
        logger.warning("SMS webhook called but Twilio not configured")
        raise HTTPException(status_code=503, detail="SMS service not configured")
    
    # Validate Twilio signature
    try:
        # Pass the raw request to the validator which will read the body
        signature = request.headers.get('X-Twilio-Signature', '')
        if not await SMSWebhookValidator.validate_webhook_signature(request, signature):
            logger.warning(f"Invalid Twilio webhook signature from {From}")
            raise HTTPException(status_code=403, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Error validating Twilio webhook: {e}")
        raise HTTPException(status_code=403, detail="Webhook validation failed")
    
    logger.info(f"📱 SMS from {From}: {Body}")
    
    # Add incoming message to conversation context
    SMSContextManager.add_to_conversation(From, Body, "incoming")
    
    # Find verified user
    user = db.query(User).filter(
        User.phone_number == From,
        User.phone_verified == True,
        User.sms_enabled == True
    ).first()
    
    if not user:
        logger.info(f"SMS from unregistered phone: {From}")
        return {"status": "ignored"}
    
    # Check Pro subscription
    if user.subscription_tier not in [SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]:
        response = "🚀 Upgrade to Jean Memory Pro for SMS!\n\nPro includes:\n• All MCP memory tools\n• 50 SMS commands/day\n• Conversation context\n\nVisit: app.jeanmemory.com/pro"
        sms_service = SMSService()
        sms_service.send_command_response(From, response)
        SMSContextManager.add_to_conversation(From, response, "outgoing")
        return {"status": "upgrade_required"}
    
    # Check rate limits
    allowed, remaining = SMSRateLimit.check_rate_limit(user, db)
    if not allowed:
        response = f"⏳ Daily SMS limit reached ({remaining} remaining).\n\nLimit resets tomorrow. Upgrade to Enterprise for higher limits!"
        sms_service = SMSService()
        sms_service.send_command_response(From, response)
        SMSContextManager.add_to_conversation(From, response, "outgoing")
        return {"status": "rate_limited"}
    
    # Handle special commands
    message_lower = Body.strip().lower()
    if message_lower in ['help', 'commands']:
        response = """📱 Jean Memory SMS - Natural Language Interface

🤖 ALL MCP TOOLS AVAILABLE:
• Ask questions: "What should I buy?"
• Add memories: "Remember to call mom" 
• Search: "Find my project notes"
• List recent: "Show my recent memories"
• Deep analysis: "Analyze my writing style"

💬 Just text naturally - AI selects the best tool!
🔄 Conversation context maintained
📱 'stop' to disable"""
    
    elif message_lower in ['stop', 'unsubscribe']:
        user.sms_enabled = False
        db.commit()
        response = "⏸️ SMS disabled. All conversation context cleared.\n\nRe-enable in settings: app.jeanmemory.com"
        # Clear conversation context
        if redis_client:
            redis_client.delete(From)
    
    else:
        # Use AI to select best MCP tool with conversation context
        SMSRateLimit.increment_usage(user, db)
        
        # Get conversation context
        context = SMSContextManager.get_conversation_context(From)
        
        try:
            response = await SMSMCPRouter.select_tool_and_execute(Body, context, user)
        except Exception as e:
            logger.error(f"Error in SMS MCP routing: {e}")
            response = "❌ Error processing your message. Please try again."
    
    # Add response to conversation context
    SMSContextManager.add_to_conversation(From, response, "outgoing")
    
    # Send response
    try:
        sms_service = SMSService()
        if sms_service.send_command_response(From, response):
            logger.info(f"✅ SMS response sent to {From}")
            return {"status": "success"}
        else:
            logger.error(f"❌ Failed to send SMS response to {From}")
            return {"status": "send_failed"}
    except Exception as e:
        logger.error(f"Error sending SMS response: {e}")
        return {"status": "error"}

@router.get("/sms/health")
async def sms_webhook_health():
    """Health check for SMS webhook"""
    return {
        "status": "healthy",
        "service": "sms_webhook_full_mcp_with_context",
        "configured": sms_config.is_configured,
        "tools_available": ["ask_memory", "add_memories", "search_memory", "list_memories", "deep_memory_query"],
        "features": ["conversation_context", "ai_tool_selection", "pro_gated"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    } 