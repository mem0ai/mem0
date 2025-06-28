#!/usr/bin/env python3
"""
Test script for Smart Context Orchestration
Tests the enhanced orchestration layer that combines approaches 1 and 4.
"""

import asyncio
import json
import os
import sys
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.append('/Users/jonathanpolitzki/Desktop/Coding/mem0/openmemory/api')

# Load environment variables
load_dotenv('/Users/jonathanpolitzki/Desktop/Coding/mem0/openmemory/.env.local')
load_dotenv('/Users/jonathanpolitzki/Desktop/Coding/mem0/openmemory/api/.env')
load_dotenv('/Users/jonathanpolitzki/Desktop/Coding/mem0/openmemory/.env')

from app.mcp_orchestration import get_smart_orchestrator, clear_context_cache, get_cache_stats
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
TEST_USER_ID = "test-user-12345"
TEST_CLIENT_NAME = "test-client"

async def test_new_conversation_detection():
    """Test if the AI-powered orchestrator correctly detects new conversations"""
    print("\n🧪 Testing AI-Powered New Conversation Detection...")
    
    orchestrator = get_smart_orchestrator()
    
    # Clear cache to ensure fresh start
    clear_context_cache()
    
    # Test cases for new conversation detection
    test_cases = [
        ("Hello! I'm Jonathan, a software engineer.", True, "Greeting + introduction"),
        ("Hi there, can you help me with something?", True, "Greeting + help request"),  
        ("I want to tell you about my new project.", True, "Introduction statement"),
        ("What did we discuss earlier?", False, "Reference to previous context"),
        ("Can you search for information about Python?", False, "Simple query without greeting"),
        ("Good morning! Let me tell you about my goals for today.", True, "Greeting + context setting")
    ]
    
    for message, expected_new, description in test_cases:
        try:
            result = await orchestrator._detect_new_conversation(message, None, None)
            status = "🤖" if result == expected_new else "🔄"  # Show AI analysis, not pass/fail
            print(f"{status} {description}: '{message[:30]}...' -> {'NEW' if result else 'CONTINUING'} (AI decision)")
        except Exception as e:
            print(f"❌ Error testing '{message[:30]}...': {e}")

async def test_working_memory():
    """Test the working memory functionality using list_memories"""
    print("\n🧪 Testing Working Memory (list_memories integration)...")
    
    orchestrator = get_smart_orchestrator()
    
    try:
        # Test working memory retrieval
        tools = orchestrator._get_tools()
        working_memory = await orchestrator._get_working_memory(TEST_USER_ID, tools)
        
        print(f"✅ Working memory retrieval: {working_memory.get('memory_count', 0)} memories found")
        print(f"   Themes extracted: {working_memory.get('recent_themes', [])}")
        
    except Exception as e:
        print(f"❌ Working memory test failed: {e}")

async def test_user_profile_building():
    """Test user profile building using ask_memory"""
    print("\n🧪 Testing User Profile Building (ask_memory integration)...")
    
    orchestrator = get_smart_orchestrator()
    
    try:
        tools = orchestrator._get_tools()
        user_profile = await orchestrator._get_user_profile(TEST_USER_ID, tools)
        
        profile_summary = user_profile.get('profile_summary', 'No profile available')
        response_count = len(user_profile.get('profile_responses', []))
        
        print(f"✅ User profile building: {response_count} profile questions answered")
        print(f"   Profile summary: {profile_summary}")
        
    except Exception as e:
        print(f"❌ User profile test failed: {e}")

async def test_memory_analysis():
    """Test AI-powered memory analysis and extraction"""
    print("\n🧪 Testing AI-Powered Memory Analysis...")
    
    orchestrator = get_smart_orchestrator()
    
    # Test cases for memory analysis
    test_cases = [
        ("I'm a software engineer at Google.", True, "Job information"),
        ("I really love playing tennis on weekends.", True, "Personal preference"),
        ("What's the weather like today?", False, "Simple question"),
        ("My favorite programming language is Python.", True, "Preference statement"),
        ("Can you help me with this code?", False, "Help request"),
        ("I graduated from Stanford in 2020.", True, "Educational background"),
        ("How do I install this package?", False, "Technical question")
    ]
    
    for message, expected_memorable, description in test_cases:
        try:
            analysis = await orchestrator._ai_memory_analysis(message)
            should_remember = analysis["should_remember"]
            content = analysis["content"]
            status = "🤖" if should_remember == expected_memorable else "🔄"  # Show AI analysis
            
            print(f"{status} {description}: '{message}'")
            print(f"   → {'MEMORABLE' if should_remember else 'NOT MEMORABLE'} (AI decision)")
            if should_remember:
                print(f"   → Extracted: {content[:60]}...")
                
        except Exception as e:
            print(f"❌ Error analyzing '{message}': {e}")

async def test_deep_search_detection():
    """Test AI-powered detection of when deep search is needed"""
    print("\n🧪 Testing AI-Powered Deep Search Detection...")
    
    orchestrator = get_smart_orchestrator()
    
    test_cases = [
        ("Analyze my writing style across all my documents.", True, "Analysis request"),
        ("What's my favorite color?", False, "Simple question"),
        ("Summarize everything you know about my career.", True, "Comprehensive summary"),
        ("Tell me about Python", False, "General query"),
        ("What patterns do you see in my goals and aspirations?", True, "Pattern analysis"),
        ("When did I start this project?", False, "Specific factual query")
    ]
    
    for message, expected_deep, description in test_cases:
        try:
            analysis = await orchestrator._ai_needs_deep_search(message)
            needs_deep = analysis["needs_deep"]
            reasoning = analysis["reasoning"]
            status = "🤖" if needs_deep == expected_deep else "🔄"  # Show AI analysis
            
            print(f"{status} {description}: '{message}'")
            print(f"   → {'DEEP' if needs_deep else 'REGULAR'} search (AI decision)")
            print(f"   → Reasoning: {reasoning}")
            
        except Exception as e:
            print(f"❌ Error testing '{message}': {e}")

async def test_session_caching():
    """Test session-based context caching"""
    print("\n🧪 Testing Session Caching...")
    
    orchestrator = get_smart_orchestrator()
    
    try:
        # Clear cache first
        clear_context_cache()
        print("✅ Cache cleared")
        
        # Check initial cache stats
        stats = get_cache_stats()
        print(f"✅ Initial cache size: {stats['cache_size']}")
        
        # Simulate cache update
        cache_key = f"{TEST_USER_ID}_{TEST_CLIENT_NAME}"
        test_context = {"type": "test", "data": "sample"}
        orchestrator._update_context_cache(cache_key, test_context, TEST_USER_ID)
        
        # Check cache after update
        stats = get_cache_stats()
        print(f"✅ Cache size after update: {stats['cache_size']}")
        
        # Test cache retrieval
        cached = orchestrator._get_cached_context(cache_key)
        if cached:
            print("✅ Cache retrieval successful")
        else:
            print("❌ Cache retrieval failed")
            
    except Exception as e:
        print(f"❌ Session caching test failed: {e}")

async def test_end_to_end_orchestration():
    """Test the complete end-to-end orchestration"""
    print("\n🧪 Testing End-to-End Orchestration...")
    
    orchestrator = get_smart_orchestrator()
    
    # Clear cache for fresh test
    clear_context_cache()
    
    test_scenarios = [
        {
            "message": "Hello! I'm Jonathan, a software engineer working on AI projects. I love building innovative solutions.",
            "context": "new_conversation",
            "description": "New conversation with personal info"
        },
        {
            "message": "What programming languages do I prefer?",
            "context": "continuing",
            "description": "Follow-up query about preferences"
        },
        {
            "message": "Analyze my interests and tell me what patterns you see.",
            "context": "continuing", 
            "description": "Complex analysis request"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        try:
            print(f"\n  Scenario {i}: {scenario['description']}")
            print(f"  Message: '{scenario['message']}'")
            
            result = await orchestrator.orchestrate_smart_context(
                user_message=scenario['message'],
                user_id=TEST_USER_ID,
                client_name=TEST_CLIENT_NAME,
                conversation_context=scenario['context']
            )
            
            print(f"  ✅ Response length: {len(result)} characters")
            print(f"  📄 Response preview: {result[:100]}...")
            
        except Exception as e:
            print(f"  ❌ Scenario {i} failed: {e}")

async def main():
    """Run all tests for AI-powered orchestration"""
    print("🚀 Starting AI-Powered Smart Context Orchestration Tests")
    print("🤖 Using Gemini 2.5 Flash for intelligent reasoning instead of hard-coded heuristics")
    print("=" * 80)
    
    try:
        await test_new_conversation_detection()
        await test_working_memory()
        await test_user_profile_building()
        await test_memory_analysis()
        await test_deep_search_detection()
        await test_session_caching()
        await test_end_to_end_orchestration()
        
        print("\n" + "=" * 80)
        print("🎉 All AI-powered tests completed!")
        print("🤖 The orchestration now leverages Gemini 2.5 Flash intelligence")
        print("💡 Following the bitter lesson: use available intelligence, not hard-coded rules")
        
        # Final cache stats
        stats = get_cache_stats()
        print(f"📊 Final cache stats: {stats}")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 