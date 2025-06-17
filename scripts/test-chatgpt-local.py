#!/usr/bin/env python3
"""
Test script for ChatGPT MCP integration - LOCAL DEVELOPMENT VERSION
Tests the search and fetch tools with a local user ID
"""

import requests
import json
import sys
import time

# Local Development Configuration
BASE_URL = "http://localhost:8765"  # Local backend URL
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"  # Local development user ID

def test_tools_list():
    """Test that ChatGPT gets only search and fetch tools"""
    print("🔍 Testing tools/list for ChatGPT (LOCAL)...")
    
    url = f"{BASE_URL}/mcp/chatgpt/messages/{TEST_USER_ID}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            tools = data.get("result", {}).get("tools", [])
            tool_names = [tool["name"] for tool in tools]
            
            print(f"Tools returned: {tool_names}")
            
            # Verify ChatGPT gets only search and fetch
            expected_tools = {"search", "fetch"}
            actual_tools = set(tool_names)
            
            if actual_tools == expected_tools:
                print("✅ SUCCESS: ChatGPT gets correct tools (search, fetch)")
                return True
            else:
                print(f"❌ FAIL: Expected {expected_tools}, got {actual_tools}")
                return False
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_search_tool():
    """Test the search tool"""
    print("\n🔍 Testing search tool (LOCAL)...")
    
    url = f"{BASE_URL}/mcp/chatgpt/messages/{TEST_USER_ID}"
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search",
            "arguments": {
                "query": "test"
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("result", {})
            
            # Check if it has the OpenAI-required format
            if "results" in result:
                results = result["results"]
                print(f"Found {len(results)} search results")
                
                if results:
                    # Check first result has required fields
                    first_result = results[0]
                    required_fields = {"id", "title", "text"}
                    actual_fields = set(first_result.keys())
                    
                    if required_fields.issubset(actual_fields):
                        print("✅ SUCCESS: Search results have correct OpenAI format")
                        print(f"Sample result: {first_result['title'][:50]}...")
                        return first_result["id"]  # Return ID for fetch test
                    else:
                        print(f"❌ FAIL: Missing required fields. Expected {required_fields}, got {actual_fields}")
                        return None
                else:
                    print("⚠️  No results found - try adding some memories first")
                    print("💡 You can add memories through the local UI at http://localhost:3000")
                    return None
            else:
                print(f"❌ FAIL: Search result doesn't have 'results' field")
                print(f"Got: {result}")
                return None
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None

def test_fetch_tool(memory_id):
    """Test the fetch tool"""
    if not memory_id:
        print("\n⏭️  Skipping fetch test (no memory ID)")
        return False
        
    print(f"\n🔍 Testing fetch tool with ID: {memory_id} (LOCAL)")
    
    url = f"{BASE_URL}/mcp/chatgpt/messages/{TEST_USER_ID}"
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "fetch",
            "arguments": {
                "id": memory_id
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("result", {})
            
            # Check if it has the OpenAI-required format
            required_fields = {"id", "title", "text"}
            actual_fields = set(result.keys())
            
            if required_fields.issubset(actual_fields):
                print("✅ SUCCESS: Fetch result has correct OpenAI format")
                print(f"Fetched: {result['title'][:50]}...")
                return True
            else:
                print(f"❌ FAIL: Missing required fields. Expected {required_fields}, got {actual_fields}")
                print(f"Got: {result}")
                return False
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def check_setup():
    """Check if the test is properly configured"""
    if TEST_USER_ID == "REPLACE_WITH_LOCAL_UID":
        print("❌ ERROR: Please update TEST_USER_ID in this script!")
        print("\nTo get your local user ID:")
        print("1. Go to http://localhost:3000 and sign up/sign in")
        print("2. Go to http://localhost:54323 (Supabase Studio)")
        print("3. Navigate to Authentication > Users")
        print("4. Copy your user ID and update TEST_USER_ID in this script")
        return False
    return True

def main():
    print("🚀 Testing ChatGPT MCP Integration (LOCAL)")
    print(f"Base URL: {BASE_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print("=" * 50)
    
    # Check setup
    if not check_setup():
        sys.exit(1)
    
    # Test sequence
    success_count = 0
    total_tests = 0
    
    # Test 1: Tools list
    total_tests += 1
    if test_tools_list():
        success_count += 1
    
    # Test 2: Search tool
    total_tests += 1
    memory_id = test_search_tool()
    if memory_id is not None:
        success_count += 1
    
    # Test 3: Fetch tool (only if we got a memory ID)
    total_tests += 1
    if test_fetch_tool(memory_id):
        success_count += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {success_count}/{total_tests} passed")
    
    if success_count == total_tests:
        print("🎉 ALL TESTS PASSED! ChatGPT MCP integration is working locally!")
        print("\nNext steps:")
        print("1. Deploy to production")
        print("2. Test with production user ID")
        print("3. Add to ChatGPT with your production URL")
    elif success_count >= 1:
        print("✅ Partial success - check issues above")
        if memory_id is None:
            print("\n💡 If no memories found, try:")
            print("- Go to http://localhost:3000")
            print("- Add some memories through the UI")
            print("- Run this test again")
    else:
        print("❌ Tests failed. Check the errors above.")

if __name__ == "__main__":
    main() 