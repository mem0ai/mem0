#!/usr/bin/env python3

import requests
import json
import time

# Test the ChatGPT tools with the real user ID from the logs
USER_ID = "56092932-7e9f-4934-9bdc-84ed97bc49af"
BASE_URL = "https://api.jeanmemory.com"

def test_chatgpt_tools():
    """Test ChatGPT search and fetch tools"""
    
    print("🧪 Testing ChatGPT Tools Fix")
    print("=" * 50)
    
    # Test 1: Tools list
    print("\n1. Testing tools/list...")
    tools_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    response = requests.post(
        f"{BASE_URL}/mcp/chatgpt/messages/{USER_ID}",
        json=tools_payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
    else:
        print(f"Error: {response.text}")
    
    # Test 2: Search tool
    print("\n2. Testing search tool...")
    search_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search",
            "arguments": {
                "query": "project"
            }
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/mcp/chatgpt/messages/{USER_ID}",
        json=search_payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        # If we got results, try to fetch one
        if 'result' in result and 'results' in result['result'] and result['result']['results']:
            first_result = result['result']['results'][0]
            memory_id = first_result.get('id')
            
            if memory_id:
                print(f"\n3. Testing fetch tool with ID: {memory_id}...")
                fetch_payload = {
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
                
                response = requests.post(
                    f"{BASE_URL}/mcp/chatgpt/messages/{USER_ID}",
                    json=fetch_payload,
                    headers={"Content-Type": "application/json"}
                )
                
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    print(f"Response: {json.dumps(result, indent=2)}")
                else:
                    print(f"Error: {response.text}")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    test_chatgpt_tools() 