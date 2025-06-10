#!/usr/bin/env python3
"""Test script for MCP server memory operations via Cloudflare Worker"""
import requests
import json
import time

# Base URL for the local Cloudflare worker
BASE_URL = "http://localhost:8787"

def test_mcp_connection():
    """Test basic MCP SSE connection via WebSocket"""
    print("Testing MCP WebSocket connection via Cloudflare Worker...")
    # Note: The 'requests' library does not support WebSockets directly.
    # This test will attempt a GET request which should be upgraded to a WebSocket by the worker.
    # A successful initial HTTP response (like 101 Switching Protocols) is a good sign,
    # but full WebSocket testing requires a library like 'websocket-client'.
    # For this script, we'll check if the endpoint is responsive.
    try:
        response = requests.get(f"{BASE_URL}/mcp/claude/sse/user", timeout=5)
        # A 426 status code means the server wants to switch to WebSocket, which is correct.
        # A 101 would be ideal but 'requests' doesn't handle the upgrade.
        if response.status_code == 426:
            print("✓ Worker responded with 'Upgrade Required', which is correct for a WebSocket endpoint.")
            return True
        else:
            print(f"✗ Unexpected response from worker: {response.status_code}")
            print(f"  Response body: {response.text}")
            return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Failed to connect to local worker: {e}")
        print("  Is the 'wrangler dev' process still running?")
        return False


def test_api_endpoints():
    """Test the regular API endpoints to ensure the backend is reachable via the worker"""
    print("\nTesting API POST message proxying...")
    
    # This simulates a client sending a message after connection.
    # The worker should proxy this POST request to the backend.
    headers = {'Content-Type': 'application/json'}
    data = {"jsonrpc": "2.0", "method": "test_connection", "params": {}, "id": 1}

    try:
        # We need to target the /messages endpoint as defined in our worker
        response = requests.post(f"{BASE_URL}/mcp/claude/sse/user/messages", headers=headers, data=json.dumps(data), timeout=10)
        
        if response.status_code == 200:
            print("✓ Worker successfully proxied POST request to backend.")
            try:
                response_data = response.json()
                print("  Backend Response (preview):")
                # The response from the python server might be double-encoded json string
                if isinstance(response_data, str):
                    response_data = json.loads(response_data)
                
                if 'result' in response_data:
                     # Truncate long responses for readability
                    result_str = json.dumps(response_data['result'])
                    print(f"    {result_str[:200]}...")
                else:
                    print(f"    {response_data}")

            except json.JSONDecodeError:
                print(f"  Could not decode JSON response from backend: {response.text}")
        else:
            print(f"✗ Worker proxy failed with status: {response.status_code}")
            print(f"  Response body: {response.text}")
    
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to send POST request via worker: {e}")


def main():
    print("=== Cloudflare Worker MCP Test ===\n")
    
    if test_mcp_connection():
        test_api_endpoints()
    
    print("\n=== Test Summary ===")
    print("This script performs a basic check of the local Cloudflare worker.")
    print("It verifies that the worker is running and can proxy requests to the backend.")
    print("For a full end-to-end test, a proper WebSocket client is required.")

if __name__ == "__main__":
    main() 