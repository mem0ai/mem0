"""
Background task handlers for MCP orchestration.
Handles memory saving and other background operations.
"""

import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class MCPBackgroundTaskHandler:
    """Handles background tasks for MCP orchestration."""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
    
    async def handle_memory_saving(
        self, 
        user_message: str, 
        user_id: str, 
        client_name: str, 
        is_new_conversation: bool
    ):
        """Handle memory saving in background for deep memory orchestration"""
        try:
            # Always save new conversation messages and rich content
            should_save = is_new_conversation or len(user_message) > 50
            
            if should_save:
                logger.info("💾 [Deep Memory] Adding memory saving to background tasks.")
                
                # Get background tasks context
                try:
                    from app.mcp_server import background_tasks_var
                    background_tasks = background_tasks_var.get()
                except (LookupError, ImportError):
                    background_tasks = None
                
                if background_tasks:
                    background_tasks.add_task(
                        self._add_memory_background, 
                        user_message, 
                        user_id, 
                        client_name,
                        priority=is_new_conversation
                    )
                else:
                    # Fallback: Add memory asynchronously
                    asyncio.create_task(self._add_memory_background(
                        user_message, user_id, client_name, priority=is_new_conversation
                    ))
        except Exception as e:
            logger.error(f"❌ [Deep Memory] Background memory saving failed: {e}")

    async def handle_memory_saving_from_plan(
        self, 
        plan: Dict, 
        user_message: str, 
        user_id: str, 
        client_name: str
    ):
        """Handle memory saving in background for standard orchestration"""
        try:
            if plan.get("should_save_memory") and plan.get("memorable_content"):
                logger.info("💾 [Standard] Adding memory saving to background tasks.")
                memorable_content = plan["memorable_content"]
                
                # Get background tasks context
                try:
                    from app.mcp_server import background_tasks_var
                    background_tasks = background_tasks_var.get()
                except (LookupError, ImportError):
                    background_tasks = None
                
                if background_tasks:
                    background_tasks.add_task(
                        self._add_memory_background, 
                        memorable_content, 
                        user_id, 
                        client_name,
                        priority=False
                    )
                else:
                    # Fallback: Add memory asynchronously
                    asyncio.create_task(self._add_memory_background(
                        memorable_content, user_id, client_name, priority=False
                    ))
        except Exception as e:
            logger.error(f"❌ [Standard] Background memory saving failed: {e}")
    
    async def _add_memory_background(self, content: str, user_id: str, client_name: str, priority: bool = False):
        """Add memory in background with enhanced error handling and retry logic"""
        try:
            # Delegate to orchestrator's method
            await self.orchestrator._add_memory_background(content, user_id, client_name, priority)
        except Exception as e:
            logger.error(f"❌ Background memory addition failed: {e}")
    
    async def handle_narrative_generation(self, user_id: str, memories_text: str):
        """Handle narrative generation in background"""
        try:
            # Get background tasks context
            try:
                from app.mcp_server import background_tasks_var
                background_tasks = background_tasks_var.get()
            except (LookupError, ImportError):
                background_tasks = None
            
            if background_tasks:
                background_tasks.add_task(
                    self._generate_narrative_background,
                    user_id,
                    memories_text
                )
            else:
                # Fallback: Generate narrative asynchronously
                asyncio.create_task(self._generate_narrative_background(
                    user_id, memories_text
                ))
        except Exception as e:
            logger.error(f"❌ Background narrative generation failed: {e}")
    
    async def _generate_narrative_background(self, user_id: str, memories_text: str):
        """Generate narrative in background"""
        try:
            # Delegate to orchestrator's method
            await self.orchestrator._generate_and_cache_narrative(user_id, memories_text, None)
        except Exception as e:
            logger.error(f"❌ Background narrative generation failed: {e}")
    
    async def handle_deep_analysis_background(self, plan: Dict, user_id: str, client_name: str):
        """Handle deep analysis in background"""
        try:
            # Get background tasks context
            try:
                from app.mcp_server import background_tasks_var
                background_tasks = background_tasks_var.get()
            except (LookupError, ImportError):
                background_tasks = None
            
            if background_tasks:
                background_tasks.add_task(
                    self._execute_deep_analysis_background,
                    plan,
                    user_id,
                    client_name
                )
            else:
                # Fallback: Execute analysis asynchronously
                asyncio.create_task(self._execute_deep_analysis_background(
                    plan, user_id, client_name
                ))
        except Exception as e:
            logger.error(f"❌ Background deep analysis failed: {e}")
    
    async def _execute_deep_analysis_background(self, plan: Dict, user_id: str, client_name: str):
        """Execute deep analysis in background"""
        try:
            # Delegate to orchestrator's method
            await self.orchestrator._execute_deep_analysis_background(plan, user_id, client_name)
        except Exception as e:
            logger.error(f"❌ Background deep analysis execution failed: {e}")


def get_background_tasks_context():
    """Get the current background tasks context"""
    try:
        from app.mcp_server import background_tasks_var
        return background_tasks_var.get()
    except (LookupError, ImportError):
        return None


def add_background_task(task_func, *args, **kwargs):
    """Add a background task if context is available"""
    background_tasks = get_background_tasks_context()
    
    if background_tasks:
        background_tasks.add_task(task_func, *args, **kwargs)
    else:
        # Fallback: Execute asynchronously
        asyncio.create_task(task_func(*args, **kwargs))