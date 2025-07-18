"""
Memory analysis utilities for MCP orchestration.
Handles memory processing, extraction, and analysis.
"""

import logging
import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Narrative cache TTL in days
NARRATIVE_TTL_DAYS = 7


class MemoryAnalyzer:
    """Handles memory analysis and processing."""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
    
    def extract_memorable_content(self, user_message: str) -> str:
        """Extract memorable content from user message using heuristics"""
        # Remove common filler words and phrases
        memorable = re.sub(r'\b(um|uh|like|you know|basically|actually)\b', '', user_message, flags=re.IGNORECASE)
        
        # Remove excessive whitespace
        memorable = re.sub(r'\s+', ' ', memorable).strip()
        
        # If the message is too short or generic, don't save it
        if len(memorable) < 10:
            return ""
        
        # Check for generic responses
        generic_patterns = [
            r'^(yes|no|ok|okay|sure|thanks|thank you)\.?$',
            r'^(hi|hello|hey|goodbye|bye)\.?$',
            r'^(what|how|why|when|where)\?$'
        ]
        
        for pattern in generic_patterns:
            if re.match(pattern, memorable, re.IGNORECASE):
                return ""
        
        return memorable
    
    def should_use_deep_analysis(self, user_message: str, is_new_conversation: bool) -> bool:
        """
        Smart decision on whether to use deep analysis.
        Uses enhanced heuristics for better accuracy.
        """
        # Always use deep analysis for new conversations
        if is_new_conversation:
            return True
        
        # Message length and complexity indicators
        if len(user_message) > 200:
            return True
        
        # Deep analysis keywords (expanded list)
        deep_keywords = [
            'analyze', 'explain', 'understand', 'learn', 'insights', 'patterns',
            'tell me about', 'what do you know', 'summarize', 'overview',
            'help me understand', 'break down', 'compare', 'contrast',
            'relationship', 'connection', 'trend', 'pattern', 'theme'
        ]
        
        user_lower = user_message.lower()
        if any(keyword in user_lower for keyword in deep_keywords):
            return True
        
        # Question indicators that might benefit from deep analysis
        question_indicators = ['?', 'how', 'why', 'what', 'when', 'where', 'who']
        has_question = any(indicator in user_lower for indicator in question_indicators)
        
        # Complex sentences (multiple clauses)
        complex_indicators = [';', ',', 'and', 'but', 'however', 'because', 'since', 'although']
        has_complex_structure = sum(1 for indicator in complex_indicators if indicator in user_lower) >= 2
        
        # Use deep analysis for complex questions
        if has_question and (has_complex_structure or len(user_message) > 100):
            return True
        
        return False
    
    def process_memory_intelligently(self, user_message: str, analysis_result: Dict) -> Dict:
        """Process memory content intelligently based on analysis"""
        try:
            # Extract key information from analysis
            should_save = analysis_result.get('should_save', False)
            memorable_content = analysis_result.get('memorable_content')
            categories = analysis_result.get('categories', [])
            priority = analysis_result.get('priority', 'medium')
            
            if not should_save or not memorable_content:
                return {
                    'action': 'skip',
                    'reason': 'Content not memorable or saving not required'
                }
            
            # Enhance memorable content
            enhanced_content = self._enhance_memorable_content(memorable_content, user_message)
            
            # Validate categories
            validated_categories = self._validate_categories(categories)
            
            # Determine memory metadata
            metadata = {
                'priority': priority,
                'categories': validated_categories,
                'processed_at': datetime.now().isoformat(),
                'source': 'intelligent_processing'
            }
            
            return {
                'action': 'save',
                'content': enhanced_content,
                'metadata': metadata,
                'priority': priority
            }
            
        except Exception as e:
            logger.error(f"❌ Error in intelligent memory processing: {e}")
            return {
                'action': 'skip',
                'reason': f'Processing error: {str(e)}'
            }
    
    def _enhance_memorable_content(self, memorable_content: str, original_message: str) -> str:
        """Enhance memorable content with context if needed"""
        # If memorable content is too short, include more context
        if len(memorable_content) < 20 and len(original_message) > 20:
            return original_message[:200] + "..." if len(original_message) > 200 else original_message
        
        return memorable_content
    
    def _validate_categories(self, categories: List[str]) -> List[str]:
        """Validate and normalize categories"""
        valid_categories = []
        
        for category in categories:
            if isinstance(category, str) and category.strip():
                # Normalize category name
                normalized = category.strip().lower()
                if normalized not in valid_categories:
                    valid_categories.append(normalized)
        
        # Ensure at least one category
        if not valid_categories:
            valid_categories = ['general']
        
        return valid_categories
    
    def summarize_profile(self, profile_responses: List[Dict]) -> str:
        """Create a concise profile summary from profile responses"""
        if not profile_responses:
            return "No profile information available."
        
        # Extract key information
        key_points = []
        for response in profile_responses:
            if isinstance(response, dict) and 'content' in response:
                content = response['content']
                if isinstance(content, str) and len(content.strip()) > 0:
                    # Extract first sentence or key point
                    first_sentence = content.split('.')[0].strip()
                    if first_sentence and len(first_sentence) > 10:
                        key_points.append(first_sentence)
        
        if not key_points:
            return "Profile information available but not summarizable."
        
        # Create summary
        if len(key_points) == 1:
            return key_points[0]
        elif len(key_points) <= 3:
            return ". ".join(key_points)
        else:
            # Take first 3 key points
            return ". ".join(key_points[:3]) + "..."
    
    async def get_cached_narrative(self, user_id: str) -> Optional[str]:
        """Get cached narrative for user if it exists and is fresh"""
        try:
            from app.database import SessionLocal
            from app.models import UserNarrative
            
            with SessionLocal() as db:
                narrative = db.query(UserNarrative).filter(
                    UserNarrative.user_id == user_id
                ).first()
                
                if narrative:
                    # Check if narrative is still fresh
                    if datetime.now() - narrative.created_at < timedelta(days=NARRATIVE_TTL_DAYS):
                        logger.info(f"📖 Using cached narrative for user {user_id}")
                        return narrative.content
                    else:
                        logger.info(f"📖 Cached narrative expired for user {user_id}")
                        # Delete expired narrative
                        db.delete(narrative)
                        db.commit()
                
                return None
                
        except Exception as e:
            logger.error(f"❌ Error retrieving cached narrative: {e}")
            return None
    
    async def save_narrative_to_cache(self, user_id: str, narrative_content: str):
        """Save narrative to cache/database"""
        try:
            from app.database import SessionLocal
            from app.models import UserNarrative
            
            with SessionLocal() as db:
                # Delete existing narrative
                existing = db.query(UserNarrative).filter(
                    UserNarrative.user_id == user_id
                ).first()
                if existing:
                    db.delete(existing)
                
                # Create new narrative
                narrative = UserNarrative(
                    user_id=user_id,
                    content=narrative_content,
                    created_at=datetime.now()
                )
                db.add(narrative)
                db.commit()
                
                logger.info(f"📖 Saved narrative to cache for user {user_id}")
                
        except Exception as e:
            logger.error(f"❌ Error saving narrative to cache: {e}")
    
    async def get_user_memories(self, user_id: str, limit: int = 50) -> List[str]:
        """Get user memories for narrative generation"""
        try:
            from app.database import SessionLocal
            from app.models import Memory, MemoryState
            
            with SessionLocal() as db:
                memories = db.query(Memory).filter(
                    Memory.user_id == user_id,
                    Memory.state == MemoryState.active
                ).order_by(Memory.created_at.desc()).limit(limit).all()
                
                return [memory.content for memory in memories if memory.content]
                
        except Exception as e:
            logger.error(f"❌ Error retrieving user memories: {e}")
            return []


def extract_memorable_content(user_message: str) -> str:
    """Extract memorable content from user message using heuristics"""
    analyzer = MemoryAnalyzer(None)
    return analyzer.extract_memorable_content(user_message)


def should_use_deep_analysis(user_message: str, is_new_conversation: bool) -> bool:
    """Smart decision on whether to use deep analysis"""
    analyzer = MemoryAnalyzer(None)
    return analyzer.should_use_deep_analysis(user_message, is_new_conversation)