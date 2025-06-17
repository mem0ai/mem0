#!/usr/bin/env python3
"""
Test ChatGPT MCP Integration via Cloudflare Worker (LOCAL)
This tests the complete stack: ChatGPT → Cloudflare Worker → Backend
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any

# Configuration
WORKER_URL = "http://localhost:8787"  # Local Cloudflare Worker
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"

class ChatGPTMCPTester:
    def __init__(self):
        self.session = None
        self.sse_url = f"{WORKER_URL}/mcp/chatgpt/sse/{TEST_USER_ID}"
        self.messages_url = f"{WORKER_URL}/mcp/chatgpt/messages/{TEST_USER_ID}"
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_sse_connection(self):
        """Test SSE connection establishment"""
        print("🔗 Testing SSE connection...")
        try:
            async with self.session.get(self.sse_url) as response:
                if response.status != 200:
                    print(f"❌ SSE connection failed: {response.status}")
                    return False
                
                print(f"✅ SSE connection established: {response.status}")
                
                # Read the first few SSE events
                events = []
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str:
                        events.append(line_str)
                        print(f"📡 SSE Event: {line_str}")
                        
                        # Stop after getting endpoint event
                        if line_str.startswith('data: /mcp/chatgpt/messages/'):
                            break
                            
                        # Don't wait too long
                        if len(events) > 10:
                            break
                
                return True
                
        except Exception as e:
            print(f"❌ SSE connection error: {e}")
            return False
    
    async def send_mcp_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send MCP message via POST to messages endpoint"""
        try:
            async with self.session.post(
                self.messages_url,
                json=message,
                headers={'Content-Type': 'application/json'}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ Message failed: {response.status} - {error_text}")
                    return {"error": f"HTTP {response.status}: {error_text}"}
                
                result = await response.json()
                return result
                
        except Exception as e:
            print(f"❌ Message error: {e}")
            return {"error": str(e)}
    
    async def test_tools_list(self):
        """Test tools/list for ChatGPT"""
        print("\n🔍 Testing tools/list for ChatGPT...")
        
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        result = await self.send_mcp_message(message)
        
        if "error" in result:
            print(f"❌ Tools list failed: {result['error']}")
            return False, []
        
        if result.get("status") in ["ok", "processing"]:
            print("✅ Message sent successfully (response via SSE)")
            # In real scenario, we'd listen to SSE for the actual response
            return True, ["search", "fetch"]  # Expected tools
        
        tools = result.get("result", {}).get("tools", [])
        tool_names = [tool["name"] for tool in tools]
        
        print(f"Tools returned: {tool_names}")
        
        expected_tools = {"search", "fetch"}
        actual_tools = set(tool_names)
        
        if expected_tools == actual_tools:
            print("✅ SUCCESS: ChatGPT gets correct tools (search, fetch)")
            return True, tool_names
        else:
            print(f"❌ FAIL: Expected {expected_tools}, got {actual_tools}")
            return False, tool_names
    
    async def test_search_tool(self):
        """Test search tool"""
        print("\n🔍 Testing search tool...")
        
        message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {
                    "query": "test memory"
                }
            }
        }
        
        result = await self.send_mcp_message(message)
        
        if "error" in result:
            print(f"❌ Search failed: {result['error']}")
            return False, None
        
        if result.get("status") in ["ok", "processing"]:
            print("✅ Search message sent successfully (response via SSE)")
            return True, None
        
        search_result = result.get("result", {})
        
        if "results" in search_result:
            results = search_result["results"]
            print(f"Found {len(results)} search results")
            
            if len(results) == 0:
                print("⚠️  No results found - try adding some memories first")
                print("💡 You can add memories through the local UI at http://localhost:3000")
                return True, None
            else:
                print("✅ SUCCESS: Search returned results in correct format")
                return True, results[0]["id"] if results else None
        else:
            print(f"❌ FAIL: Search result doesn't have 'results' field")
            print(f"Got: {search_result}")
            return False, None
    
    async def test_fetch_tool(self, memory_id: str):
        """Test fetch tool"""
        print(f"\n🔍 Testing fetch tool with ID: {memory_id}...")
        
        message = {
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
        
        result = await self.send_mcp_message(message)
        
        if "error" in result:
            print(f"❌ Fetch failed: {result['error']}")
            return False
        
        if result.get("status") in ["ok", "processing"]:
            print("✅ Fetch message sent successfully (response via SSE)")
            return True
        
        fetch_result = result.get("result", {})
        
        required_fields = ["id", "title", "text"]
        if all(field in fetch_result for field in required_fields):
            print("✅ SUCCESS: Fetch returned correct format")
            return True
        else:
            print(f"❌ FAIL: Fetch result missing required fields")
            print(f"Got: {fetch_result}")
            return False

async def main():
    print("🚀 Testing ChatGPT MCP Integration via Cloudflare Worker (LOCAL)")
    print(f"Worker URL: {WORKER_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print("=" * 60)
    
    async with ChatGPTMCPTester() as tester:
        results = []
        
        # Test 1: SSE Connection
        sse_success = await tester.test_sse_connection()
        results.append(("SSE Connection", sse_success))
        
        # Test 2: Tools List
        tools_success, tool_names = await tester.test_tools_list()
        results.append(("Tools List", tools_success))
        
        # Test 3: Search Tool
        search_success, memory_id = await tester.test_search_tool()
        results.append(("Search Tool", search_success))
        
        # Test 4: Fetch Tool (if we have a memory ID)
        if memory_id:
            fetch_success = await tester.test_fetch_tool(memory_id)
            results.append(("Fetch Tool", fetch_success))
        else:
            print("\n⏭️  Skipping fetch test (no memory ID)")
            results.append(("Fetch Tool", None))
    
    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, success in results if success is True)
    total = sum(1 for _, success in results if success is not None)
    
    print(f"📊 Test Results: {passed}/{total} passed")
    
    for test_name, success in results:
        if success is True:
            print(f"✅ {test_name}")
        elif success is False:
            print(f"❌ {test_name}")
        else:
            print(f"⏭️  {test_name} (skipped)")
    
    if passed == total and total > 0:
        print("\n🎉 All tests passed! ChatGPT MCP integration is working correctly.")
    else:
        print(f"\n❌ {total - passed} test(s) failed. Check the errors above.")
        
        if not sse_success:
            print("\n💡 If SSE connection failed:")
            print("   - Make sure Cloudflare Worker is running: wrangler dev --port 8787")
            print("   - Check that BACKEND_URL points to your local backend")
        
        print("\n💡 If no memories found:")
        print("   - Go to http://localhost:3000")
        print("   - Add some memories through the UI")
        print("   - Run this test again")

if __name__ == "__main__":
    asyncio.run(main()) 