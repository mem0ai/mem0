#!/usr/bin/env python3
"""
Debug script to test Smart Context components individually
"""
import asyncio
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.mcp_orchestration import SmartContextOrchestrator
from app.utils.gemini import GeminiService

async def test_components():
    orchestrator = SmartContextOrchestrator()
    
    # Test 1: Gemini API basic call
    print("🧪 Testing Gemini API...")
    start = time.time()
    try:
        # We need to get the gemini service from the orchestrator
        gemini_service = orchestrator._get_gemini()
        result = await gemini_service.generate_response("Hello, respond with 'OK'")
        print(f"✅ Gemini basic test: {time.time() - start:.2f}s - Result: {result}")
    except Exception as e:
        print(f"❌ Gemini basic test failed: {e}")
    
    # Test 2: Conversation detection
    print("🧪 Testing conversation detection...")
    start = time.time()
    try:
        result = await orchestrator._detect_new_conversation("Hello", None, None)
        print(f"✅ Conversation detection: {time.time() - start:.2f}s - Result: {result}")
    except Exception as e:
        print(f"❌ Conversation detection failed: {e}")
    
    # Test 3: Memory analysis
    print("🧪 Testing memory analysis...")
    start = time.time()
    try:
        result = await orchestrator._ai_memory_analysis("I like Python programming")
        print(f"✅ Memory analysis: {time.time() - start:.2f}s - Result: {result}")
    except Exception as e:
        print(f"❌ Memory analysis failed: {e}")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    # Load env vars from the project root and api directory
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
    
    asyncio.run(test_components()) 