"""
Smart Context Orchestration Layer for Jean Memory
Uses Gemini 2.5 Flash for intelligent reasoning instead of hard-coded heuristics.
Follows the bitter lesson: leverage available intelligence rather than programming rules.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Session-based context cache - stores user context profiles
_context_cache: Dict[str, Dict] = {}
_cache_ttl_minutes = 30  # Context cache TTL

class SmartContextOrchestrator:
    """
    AI-Powered Context Orchestrator using Gemini 2.5 Flash for intelligent reasoning.
    Replaces hard-coded heuristics with AI-driven decision making.
    """
    
    def __init__(self):
        # Import tools at runtime to avoid circular imports
        self._tools_cache = None
        self._gemini_service = None
    
    def _get_tools(self):
        """Lazy import of MCP tools to avoid circular imports"""
        if self._tools_cache is None:
            from app.mcp_server import (
                add_memories, search_memory, list_memories, 
                ask_memory, deep_memory_query
            )
            self._tools_cache = {
                'add_memories': add_memories,
                'search_memory': search_memory,
                'list_memories': list_memories,
                'ask_memory': ask_memory,
                'deep_memory_query': deep_memory_query
            }
        return self._tools_cache
    
    def _get_gemini(self):
        """Lazy import of Gemini service to avoid circular imports"""
        if self._gemini_service is None:
            from app.utils.gemini import GeminiService
            self._gemini_service = GeminiService()
        return self._gemini_service
    
    async def orchestrate_smart_context(
        self, 
        user_message: str, 
        user_id: str, 
        client_name: str,
        conversation_context: Optional[str] = None
    ) -> str:
        """
        Main orchestration method that provides intelligent context engineering.
        
        Args:
            user_message: The user's current message
            user_id: Supabase user ID
            client_name: MCP client name
            conversation_context: Optional hints about conversation state
            
        Returns:
            Enhanced context string that provides relevant background
        """
        start_time = time.time()
        
        try:
            # Step 1: Check session cache for user context
            cache_key = f"{user_id}_{client_name}"
            cached_context = self._get_cached_context(cache_key)
            
            # Step 2: Detect conversation type
            is_new_chat = await self._detect_new_conversation(
                user_message, conversation_context, cached_context
            )
            
            # Step 3: Parallel execution - context gathering and memory processing
            context_task = self._gather_intelligent_context(
                user_message, user_id, client_name, is_new_chat, cached_context
            )
            memory_task = self._process_memory_intelligently(
                user_message, user_id, client_name
            )
            
            # Execute both in parallel
            context_result, memory_result = await asyncio.gather(
                context_task, memory_task, return_exceptions=True
            )
            
            # Step 4: Build enhanced context response
            enhanced_context = await self._build_context_response(
                context_result, memory_result, is_new_chat, user_message
            )
            
            # Step 5: Update session cache
            if not isinstance(context_result, Exception):
                self._update_context_cache(cache_key, context_result, user_id)
            
            processing_time = time.time() - start_time
            
            # Add debug info if slow
            if processing_time > 2.0:
                enhanced_context += f"\n⏱️ Processing took {processing_time:.1f}s"
            
            return enhanced_context
            
        except Exception as e:
            logger.error(f"Error in smart context orchestration: {e}", exc_info=True)
            return f"I encountered an issue processing your message: {str(e)}"
    
    def _get_cached_context(self, cache_key: str) -> Optional[Dict]:
        """Get cached context if it exists and is still valid"""
        if cache_key not in _context_cache:
            return None
        
        cached = _context_cache[cache_key]
        cache_time = cached.get('timestamp')
        if not cache_time:
            return None
        
        # Check if cache is still valid
        if datetime.now() - cache_time > timedelta(minutes=_cache_ttl_minutes):
            del _context_cache[cache_key]
            return None
        
        return cached
    
    def _update_context_cache(self, cache_key: str, context_data: Dict, user_id: str):
        """Update the session cache with new context data"""
        try:
            _context_cache[cache_key] = {
                'timestamp': datetime.now(),
                'user_id': user_id,
                'context_data': context_data
            }
            
            # Cleanup old cache entries (keep only 100 most recent)
            if len(_context_cache) > 100:
                oldest_keys = sorted(_context_cache.keys(), 
                                   key=lambda k: _context_cache[k]['timestamp'])[:50]
                for old_key in oldest_keys:
                    del _context_cache[old_key]
                    
        except Exception as e:
            logger.error(f"Error updating context cache: {e}")
    
    async def _detect_new_conversation(
        self, 
        user_message: str, 
        conversation_context: Optional[str],
        cached_context: Optional[Dict]
    ) -> bool:
        """
        Use Gemini 2.5 Flash to intelligently detect if this is a new conversation.
        Leverages AI reasoning instead of hard-coded heuristics.
        """
        try:
            # Quick checks first
            if conversation_context:
                if any(hint in conversation_context.lower() for hint in 
                      ['new_conversation', 'new_chat', 'fresh_start']):
                    return True
                if any(hint in conversation_context.lower() for hint in 
                      ['continuing', 'follow_up', 'same_conversation']):
                    return False
            
            # If no cache, it's definitely new
            if not cached_context:
                return True
            
            # Use Gemini for intelligent analysis
            gemini = self._get_gemini()
            
            # Build context for analysis
            cache_age = ""
            if cached_context and cached_context.get('timestamp'):
                age_minutes = (datetime.now() - cached_context['timestamp']).total_seconds() / 60
                cache_age = f"Last context cached {age_minutes:.0f} minutes ago."
            
            prompt = f"""Analyze this message to determine if it represents a NEW conversation start or CONTINUING an existing conversation.

USER MESSAGE: "{user_message}"

CONTEXT:
- {cache_age if cache_age else "No previous context available."}
- User has existing conversation history stored

CRITERIA for NEW conversation:
- Greetings and introductions
- Starting fresh on new topics
- Self-introductions or context setting
- Messages that establish new interaction patterns

CRITERIA for CONTINUING conversation:
- References to previous discussions
- Follow-up questions
- Assumes prior context
- Short queries without introductory elements

Respond with ONLY one word: "NEW" or "CONTINUING"
"""
            
            response = await asyncio.to_thread(
                gemini.model.generate_content,
                prompt,
                generation_config={
                    "temperature": 0.1,  # Low temperature for consistent decisions
                    "max_output_tokens": 10
                }
            )
            
            result = response.text.strip().upper()
            is_new = result == "NEW"
            
            logger.info(f"AI conversation detection: '{user_message[:50]}...' -> {result}")
            return is_new
            
        except Exception as e:
            logger.error(f"Error in AI conversation detection: {e}")
            # Fallback: assume continuing unless it looks like a greeting
            return user_message.lower().strip().startswith(('hello', 'hi ', 'hey '))
    
    async def _gather_intelligent_context(
        self, 
        user_message: str, 
        user_id: str, 
        client_name: str, 
        is_new_chat: bool,
        cached_context: Optional[Dict]
    ) -> Dict:
        """
        Gather context intelligently based on conversation type and cache status.
        """
        try:
            tools = self._get_tools()
            
            if is_new_chat:
                # For new conversations, build comprehensive fresh context
                return await self._build_fresh_context(
                    user_message, user_id, client_name, tools
                )
            else:
                # For continuing conversations, use working memory + targeted search
                return await self._build_continuing_context(
                    user_message, user_id, client_name, tools, cached_context
                )
                
        except Exception as e:
            logger.error(f"Error gathering intelligent context: {e}")
            return {"error": str(e)}
    
    async def _build_fresh_context(
        self, 
        user_message: str, 
        user_id: str, 
        client_name: str, 
        tools: Dict
    ) -> Dict:
        """
        Build comprehensive fresh context for new conversations.
        Uses list_memories as working memory + user profile building.
        """
        try:
            # Run multiple context gathering operations in parallel
            working_memory_task = self._get_working_memory(user_id, tools)
            user_profile_task = self._get_user_profile(user_id, tools)
            query_relevant_task = self._get_query_relevant_context(user_message, user_id, tools)
            
            working_memory, user_profile, query_relevant = await asyncio.gather(
                working_memory_task, user_profile_task, query_relevant_task,
                return_exceptions=True
            )
            
            return {
                "type": "fresh_context",
                "working_memory": working_memory if not isinstance(working_memory, Exception) else None,
                "user_profile": user_profile if not isinstance(user_profile, Exception) else None,
                "query_relevant": query_relevant if not isinstance(query_relevant, Exception) else None,
                "is_new_chat": True
            }
            
        except Exception as e:
            logger.error(f"Error building fresh context: {e}")
            return {"error": str(e), "type": "fresh_context"}
    
    async def _build_continuing_context(
        self, 
        user_message: str, 
        user_id: str, 
        client_name: str, 
        tools: Dict,
        cached_context: Optional[Dict]
    ) -> Dict:
        """
        Build context for continuing conversations using working memory + targeted search.
        """
        try:
            # For continuing conversations, focus on working memory + specific search
            working_memory_task = self._get_working_memory(user_id, tools)
            targeted_search_task = self._get_targeted_search(user_message, user_id, tools)
            
            working_memory, targeted_search = await asyncio.gather(
                working_memory_task, targeted_search_task,
                return_exceptions=True
            )
            
            # Use cached user profile if available
            cached_profile = None
            if cached_context and cached_context.get('context_data'):
                cached_profile = cached_context['context_data'].get('user_profile')
            
            return {
                "type": "continuing_context",
                "working_memory": working_memory if not isinstance(working_memory, Exception) else None,
                "targeted_search": targeted_search if not isinstance(targeted_search, Exception) else None,
                "cached_profile": cached_profile,
                "is_new_chat": False
            }
            
        except Exception as e:
            logger.error(f"Error building continuing context: {e}")
            return {"error": str(e), "type": "continuing_context"}
    
    async def _get_working_memory(self, user_id: str, tools: Dict) -> Dict:
        """
        Get working memory using list_memories with AI-powered theme extraction.
        """
        try:
            # Use list_memories to get recent context (working memory)
            recent_memories_str = await tools['list_memories'](limit=15)
            
            # Handle different response formats
            recent_memories = []
            if recent_memories_str and recent_memories_str.strip():
                try:
                    # Try to parse as JSON
                    recent_memories = json.loads(recent_memories_str)
                except json.JSONDecodeError:
                    # If JSON parsing fails, treat as empty result
                    logger.warning(f"Failed to parse list_memories JSON response: {recent_memories_str[:100]}...")
                    recent_memories = []
            
            # Use AI to extract key themes from recent memories
            themes = await self._ai_extract_themes_from_memories(recent_memories)
            
            return {
                "recent_memories": recent_memories[:10],  # Keep top 10 for context
                "recent_themes": themes,
                "memory_count": len(recent_memories),
                "ai_analysis": "Themes extracted using AI analysis of recent memories"
            }
            
        except Exception as e:
            logger.error(f"Error getting working memory: {e}")
            return {"error": str(e)}
    
    async def _get_user_profile(self, user_id: str, tools: Dict) -> Dict:
        """
        Build user profile using ask_memory for quick profile questions.
        """
        try:
            # Use ask_memory to quickly get user profile information
            profile_questions = [
                "Who am I and what do I do?",
                "What are my main interests and preferences?",
                "What am I currently working on?"
            ]
            
            profile_responses = []
            for question in profile_questions:
                try:
                    response = await tools['ask_memory'](question=question)
                    profile_responses.append({
                        "question": question,
                        "answer": response
                    })
                except Exception as e:
                    logger.error(f"Error with profile question '{question}': {e}")
                    continue
            
            return {
                "profile_responses": profile_responses,
                "profile_summary": self._summarize_profile(profile_responses)
            }
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return {"error": str(e)}
    
    async def _get_query_relevant_context(self, user_message: str, user_id: str, tools: Dict) -> Dict:
        """
        Get context specifically relevant to the user's current query.
        """
        try:
            # Use search_memory to find relevant context
            relevant_memories_str = await tools['search_memory'](query=user_message, limit=8)
            
            # Handle different response formats
            relevant_memories = []
            if relevant_memories_str and relevant_memories_str.strip():
                try:
                    relevant_memories = json.loads(relevant_memories_str)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse search_memory JSON response: {relevant_memories_str[:100]}...")
                    relevant_memories = []
            
            return {
                "relevant_memories": relevant_memories,
                "relevance_count": len(relevant_memories)
            }
            
        except Exception as e:
            logger.error(f"Error getting query relevant context: {e}")
            return {"error": str(e)}
    
    async def _get_targeted_search(self, user_message: str, user_id: str, tools: Dict) -> Dict:
        """
        Perform AI-guided targeted search for continuing conversations.
        """
        try:
            # Use AI to determine if we need deep search or regular search
            search_analysis = await self._ai_needs_deep_search(user_message)
            
            if search_analysis["needs_deep"]:
                # Use deep_memory_query for complex questions
                deep_result = await tools['deep_memory_query'](search_query=user_message)
                return {
                    "search_type": "deep",
                    "result": deep_result,
                    "ai_reasoning": search_analysis["reasoning"]
                }
            else:
                # Use regular search_memory for simple queries
                search_result_str = await tools['search_memory'](query=user_message, limit=10)
                
                # Handle JSON parsing safely
                search_result = []
                if search_result_str and search_result_str.strip():
                    try:
                        search_result = json.loads(search_result_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse search_memory JSON response: {search_result_str[:100]}...")
                        search_result = []
                
                return {
                    "search_type": "regular",
                    "result": search_result,
                    "ai_reasoning": search_analysis["reasoning"]
                }
                
        except Exception as e:
            logger.error(f"Error in targeted search: {e}")
            return {"error": str(e)}
    
    async def _ai_needs_deep_search(self, user_message: str) -> Dict:
        """
        Use Gemini 2.5 Flash to determine if the user message needs deep search analysis.
        """
        try:
            gemini = self._get_gemini()
            
            prompt = f"""Analyze this user message to determine if it requires DEEP SEARCH (comprehensive analysis across all content) or REGULAR SEARCH (simple memory lookup).

USER MESSAGE: "{user_message}"

DEEP SEARCH is needed for:
- Requests to analyze, summarize, or compare across multiple sources
- Questions about patterns, trends, or themes in the user's life/work
- Comprehensive queries (e.g., "everything about", "all my", "overall")
- Complex analytical questions requiring synthesis of multiple memories/documents
- Requests for insights, explanations, or understanding of complex topics

REGULAR SEARCH is sufficient for:
- Simple factual questions
- Looking up specific information
- Quick queries about preferences or basic facts
- Direct questions with straightforward answers

RESPONSE FORMAT:
Decision: DEEP or REGULAR
Reasoning: [Brief explanation of why this level of search is needed]

Example:
Decision: DEEP
Reasoning: Request to analyze patterns across user's goals requires comprehensive analysis

Example:
Decision: REGULAR
Reasoning: Simple factual question about a preference can be answered with basic search"""
            
            response = await asyncio.to_thread(
                gemini.model.generate_content,
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 150
                }
            )
            
            result = response.text.strip()
            
            # Parse the response
            lines = result.split('\n')
            decision_line = next((line for line in lines if line.startswith('Decision:')), '')
            reasoning_line = next((line for line in lines if line.startswith('Reasoning:')), '')
            
            needs_deep = 'DEEP' in decision_line.upper()
            reasoning = reasoning_line.replace('Reasoning:', '').strip() if reasoning_line else "AI analysis"
            
            logger.info(f"AI search depth decision: '{user_message[:30]}...' -> {'DEEP' if needs_deep else 'REGULAR'}")
            
            return {
                "needs_deep": needs_deep,
                "reasoning": reasoning,
                "search_type": "deep" if needs_deep else "regular"
            }
            
        except Exception as e:
            logger.error(f"Error in AI deep search detection: {e}")
            # Fallback to simple heuristic
            simple_check = any(indicator in user_message.lower() for indicator in 
                             ['analyze', 'summarize', 'compare', 'patterns', 'everything about'])
            return {
                "needs_deep": simple_check,
                "reasoning": "Fallback heuristic analysis",
                "search_type": "deep" if simple_check else "regular"
            }
    
    async def _process_memory_intelligently(
        self, 
        user_message: str, 
        user_id: str, 
        client_name: str
    ) -> Dict:
        """
        Use AI to intelligently process the user message for memorable content.
        Uses background processing to avoid blocking the response.
        """
        try:
            # Use AI to analyze memory worthiness
            memory_analysis = await self._ai_memory_analysis(user_message)
            
            if memory_analysis["should_remember"]:
                tools = self._get_tools()
                memorable_content = memory_analysis["content"]
                
                # Add memory in background (fire and forget)
                asyncio.create_task(self._add_memory_background(
                    memorable_content, user_id, client_name, tools
                ))
                
                return {
                    "memory_added": True,
                    "content": memorable_content,
                    "processing": "background",
                    "ai_reasoning": "AI determined this contains memorable personal information"
                }
            else:
                return {
                    "memory_added": False,
                    "reason": memory_analysis["content"],  # AI's explanation of why not memorable
                    "ai_reasoning": "AI determined this doesn't contain memorable information"
                }
                
        except Exception as e:
            logger.error(f"Error processing memory intelligently: {e}")
            return {"error": str(e), "memory_added": False}
    
    async def _ai_memory_analysis(self, user_message: str) -> Dict:
        """
        Use Gemini 2.5 Flash to intelligently analyze if message contains memorable content.
        Returns analysis with decision and extracted content.
        """
        try:
            gemini = self._get_gemini()
            
            prompt = f"""Analyze this message to determine if it contains information worth remembering in a personal memory system.

USER MESSAGE: "{user_message}"

MEMORABLE CONTENT includes:
- Personal facts (name, job, location, background)
- Preferences and opinions (likes, dislikes, beliefs)
- Goals, plans, and aspirations
- Important life events or experiences
- Skills, expertise, and knowledge areas
- Relationships and connections
- Explicit requests to remember something

NOT MEMORABLE:
- Simple questions without personal context
- General requests for help
- Casual conversation without personal information
- Temporary states (current mood, today's weather)

RESPONSE FORMAT:
Decision: REMEMBER or SKIP
Content: [If REMEMBER, extract the specific memorable information. If SKIP, explain why.]

Example:
Decision: REMEMBER
Content: User is a software engineer at Google who loves playing tennis on weekends

Example:
Decision: SKIP
Content: Simple question about weather with no personal information
"""
            
            response = await asyncio.to_thread(
                gemini.model.generate_content,
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 200
                }
            )
            
            result = response.text.strip()
            
            # Parse the response
            lines = result.split('\n')
            decision_line = next((line for line in lines if line.startswith('Decision:')), '')
            content_line = next((line for line in lines if line.startswith('Content:')), '')
            
            should_remember = 'REMEMBER' in decision_line.upper()
            content = content_line.replace('Content:', '').strip() if content_line else user_message
            
            logger.info(f"AI memory analysis: '{user_message[:30]}...' -> {'REMEMBER' if should_remember else 'SKIP'}")
            
            return {
                "should_remember": should_remember,
                "content": content,
                "original_message": user_message
            }
            
        except Exception as e:
            logger.error(f"Error in AI memory analysis: {e}")
            # Fallback to simple heuristic
            simple_check = any(indicator in user_message.lower() for indicator in 
                             ['i am', 'i\'m', 'my ', 'i like', 'i work', 'i live'])
            return {
                "should_remember": simple_check,
                "content": user_message if simple_check else "",
                "original_message": user_message
            }
    
    def _extract_memorable_content(self, user_message: str) -> str:
        """
        Extract the most memorable/important content from the user message.
        """
        # For now, return the full message, but could be enhanced with NLP
        # to extract specific facts, preferences, or key information
        return user_message.strip()
    
    async def _add_memory_background(
        self, 
        content: str, 
        user_id: str, 
        client_name: str, 
        tools: Dict
    ):
        """
        Add memory in background without blocking the main response.
        """
        try:
            await tools['add_memories'](text=content)
            logger.info(f"Background memory added for user {user_id}: {content[:50]}...")
        except Exception as e:
            logger.error(f"Error adding memory in background: {e}")
    
    async def _build_context_response(
        self, 
        context_result: Dict, 
        memory_result: Dict, 
        is_new_chat: bool, 
        user_message: str
    ) -> str:
        """
        Build the final enhanced context response string.
        """
        try:
            if isinstance(context_result, Exception):
                return "I'm ready to help! Ask me anything."
            
            if context_result.get("error"):
                return "I'm ready to help! Ask me anything."
            
            response_parts = []
            
            # Build context based on conversation type
            if is_new_chat:
                context_text = self._format_fresh_context(context_result)
            else:
                context_text = self._format_continuing_context(context_result)
            
            if context_text:
                response_parts.append(context_text)
            
            # Add status indicators
            status_parts = []
            
            if is_new_chat:
                status_parts.append("🆕 New conversation - I've gathered fresh context about you")
            
            if isinstance(memory_result, dict) and memory_result.get("memory_added"):
                status_parts.append("💾 Processing new information to remember")
            
            if status_parts:
                response_parts.append(" | ".join(status_parts))
            
            return "\n".join(response_parts) if response_parts else "I'm ready to help! Ask me anything."
            
        except Exception as e:
            logger.error(f"Error building context response: {e}")
            return "I'm ready to help! Ask me anything."
    
    def _format_fresh_context(self, context_data: Dict) -> str:
        """
        Format fresh context for new conversations.
        """
        try:
            context_parts = []
            
            # Add user profile summary
            user_profile = context_data.get("user_profile", {})
            if user_profile and not user_profile.get("error"):
                profile_summary = user_profile.get("profile_summary")
                if profile_summary:
                    context_parts.append(f"About you: {profile_summary}")
            
            # Add recent activity from working memory
            working_memory = context_data.get("working_memory", {})
            if working_memory and not working_memory.get("error"):
                themes = working_memory.get("recent_themes", [])
                if themes:
                    context_parts.append(f"Recent focus: {', '.join(themes[:3])}")
            
            # Add query-relevant context
            query_relevant = context_data.get("query_relevant", {})
            if query_relevant and not query_relevant.get("error"):
                relevant_count = query_relevant.get("relevance_count", 0)
                if relevant_count > 0:
                    context_parts.append(f"Found {relevant_count} relevant memories")
            
            if context_parts:
                return f"Here's helpful context I know: {' | '.join(context_parts)}\n"
            
            return ""
            
        except Exception as e:
            logger.error(f"Error formatting fresh context: {e}")
            return ""
    
    def _format_continuing_context(self, context_data: Dict) -> str:
        """
        Format context for continuing conversations.
        """
        try:
            context_parts = []
            
            # Add working memory insights
            working_memory = context_data.get("working_memory", {})
            if working_memory and not working_memory.get("error"):
                themes = working_memory.get("recent_themes", [])
                memory_count = working_memory.get("memory_count", 0)
                if themes and memory_count > 0:
                    context_parts.append(f"Recent context: {', '.join(themes[:2])} ({memory_count} recent memories)")
            
            # Add targeted search results
            targeted_search = context_data.get("targeted_search", {})
            if targeted_search and not targeted_search.get("error"):
                search_type = targeted_search.get("search_type", "regular")
                if search_type == "deep":
                    context_parts.append("Using comprehensive analysis")
                else:
                    result = targeted_search.get("result", [])
                    if isinstance(result, list) and len(result) > 0:
                        context_parts.append(f"Found {len(result)} relevant memories")
            
            if context_parts:
                return f"Context for your question: {' | '.join(context_parts)}\n"
            
            return ""
            
        except Exception as e:
            logger.error(f"Error formatting continuing context: {e}")
            return ""
    
    async def _ai_extract_themes_from_memories(self, memories: List[Dict]) -> List[str]:
        """
        Use Gemini 2.5 Flash to intelligently extract themes from recent memories.
        """
        try:
            if not memories:
                return []
            
            # Combine memory content
            memory_texts = []
            for memory in memories[:15]:  # Look at more memories for better analysis
                if isinstance(memory, dict):
                    content = memory.get('memory', memory.get('content', ''))
                    if content:
                        memory_texts.append(content)
            
            if not memory_texts:
                return []
            
            combined_text = "\n".join(memory_texts)
            
            # Limit text length for API efficiency
            if len(combined_text) > 3000:
                combined_text = combined_text[:3000] + "..."
            
            gemini = self._get_gemini()
            
            prompt = f"""Analyze these recent memories and extract the main themes/topics that represent what this person is focused on or interested in.

MEMORIES:
{combined_text}

Extract 3-5 concise theme keywords that capture the main areas of focus, interests, or activities. Themes should be:
- Single words or short phrases (1-2 words)
- Focused on key life areas, interests, or activities
- Representative of recurring patterns in the memories

Examples of good themes: work, technology, health, travel, learning, family, goals, creativity, entrepreneurship

Return ONLY the theme words separated by commas, no explanations.

Example output: work, technology, fitness, travel, learning"""
            
            response = await asyncio.to_thread(
                gemini.model.generate_content,
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 100
                }
            )
            
            result = response.text.strip()
            themes = [theme.strip() for theme in result.split(',') if theme.strip()]
            
            # Limit to 5 themes and clean them
            themes = themes[:5]
            themes = [theme.lower().replace(' ', '_') for theme in themes if len(theme) > 1]
            
            logger.info(f"AI extracted themes: {themes}")
            return themes
            
        except Exception as e:
            logger.error(f"Error in AI theme extraction: {e}")
            return ["recent_context"]  # Fallback theme
    
    def _summarize_profile(self, profile_responses: List[Dict]) -> str:
        """
        Create a brief summary from profile responses.
        """
        try:
            if not profile_responses:
                return "No profile information available"
            
            # Extract key information from responses
            summary_parts = []
            
            for response in profile_responses:
                answer = response.get('answer', '')
                if answer and not answer.startswith('Error') and len(answer) > 10:
                    # Extract first sentence or key phrase
                    first_sentence = answer.split('.')[0].strip()
                    if len(first_sentence) > 10 and len(first_sentence) < 100:
                        summary_parts.append(first_sentence)
            
            if summary_parts:
                return "; ".join(summary_parts[:2])  # Top 2 insights
            else:
                return "Building your profile from conversations"
                
        except Exception as e:
            logger.error(f"Error summarizing profile: {e}")
            return "Profile information processing"


# Global orchestrator instance
_orchestrator = None

def get_smart_orchestrator() -> SmartContextOrchestrator:
    """Get or create the global smart orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SmartContextOrchestrator()
    return _orchestrator

def clear_context_cache():
    """Clear the context cache (useful for testing)"""
    global _context_cache
    _context_cache.clear()

def get_cache_stats() -> Dict:
    """Get context cache statistics"""
    return {
        "cache_size": len(_context_cache),
        "cache_keys": list(_context_cache.keys()),
        "ttl_minutes": _cache_ttl_minutes
    } 