#!/usr/bin/env python3
"""Test script for the LIVE Cloudflare Worker"""
import requests
import json
import time

# Base URL for the LIVE custom domain, which is routed to the worker
BASE_URL = "https://api.jeanmemory.com"

def test_websocket_endpoint():
    """Checks if the worker's WebSocket endpoint is responsive."""
    print("Testing live WebSocket endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/mcp/claude/sse/user", timeout=10)
        # A 426 status code means the server wants to switch to WebSocket, which is correct.
        if response.status_code == 426:
            print("✓ Live domain responded with 'Upgrade Required'. Endpoint is correct.")
            return True
        else:
            print(f"✗ Unexpected response from live domain: {response.status_code}")
            print(f"  Response body: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to connect to live domain: {e}")
        return False


def test_api_proxy():
    """Tests if the worker can proxy a request to the live backend and get a valid response."""
    print("\nTesting live API proxy...")
    
    headers = {'Content-Type': 'application/json'}
    # Use the 'test_connection' tool as a simple, harmless test
    data = {"jsonrpc": "2.0", "method": "test_connection", "params": {}, "id": 1}

    try:
        response = requests.post(f"{BASE_URL}/mcp/claude/sse/user/messages", headers=headers, data=json.dumps(data), timeout=15)
        
        if response.status_code == 200:
            print("✓ Live domain successfully proxied POST request.")
            try:
                # The backend returns a JSON acknowledgement in the body of the POST response.
                # The actual result of the tool is sent over the WebSocket, which we can't see here.
                response_data = response.json()
                if response_data.get('status') == 'ok' and response_data.get('session_id'):
                     print("✓ Backend acknowledged the request successfully.")
                     print("  This confirms the end-to-end connection is working.")
                     print(f"  Backend acknowledgement: {response_data}")
                else:
                    print("✗ Backend returned an unexpected acknowledgement:")
                    print(f"    {response_data}")

            except json.JSONDecodeError as e:
                print(f"✗ Could not decode JSON acknowledgement from backend: {e}")
                print(f"  Raw response: {response.text}")
        else:
            print(f"✗ Worker proxy from live domain failed with status: {response.status_code}")
            print(f"  Response body: {response.text}")
    
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to send POST request via live domain: {e}")


def main():
    print("=== Final End-to-End Live System Test ===\n")
    print("This script tests the full user-facing flow: api.jeanmemory.com -> Cloudflare Worker -> Render Backend")
    
    if test_websocket_endpoint():
        test_api_proxy()
    
    print("\n========================================================")
    print("✅ Test complete. If all checks are green, your system is working end-to-end.")

if __name__ == "__main__":
    main() 