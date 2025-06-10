#!/usr/bin/env python3
"""
A production test script to verify a persistent WebSocket connection 
to the live MCP server via the Cloudflare Worker.
"""
import websocket
import json
import time
import ssl

def test_production_mcp_connection():
    """
    Establishes a WebSocket connection, sends a command, and waits for a response.
    This simulates a real MCP client and verifies the end-to-end system.
    """
    # Use wss for a secure WebSocket connection
    ws_url = "wss://api.jeanmemory.com/mcp/claude/sse/prod-test-user"
    print(f"Attempting to connect to: {ws_url}")

    try:
        # Create a WebSocket connection
        ws = websocket.create_connection(ws_url, sslopt={"cert_reqs": ssl.CERT_NONE})
        print("✓ WebSocket connection established successfully!")
        
        # The MCP server expects an initialization message from the client.
        # We can send a basic one to start the conversation.
        init_message = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "client_name": "production-test-script"
            }
        }
        # print(f"-> Sending initialization...")
        # ws.send(json.dumps(init_message))
        # time.sleep(1) # Give a moment for the server to process it

        # Now, send a command to test the tool functionality
        test_command = {
            "jsonrpc": "2.0",
            "method": "test_connection",
            "params": {},
            "id": 1
        }
        print(f"-> Sending 'test_connection' command...")
        ws.send(json.dumps(test_command))

        print("<- Waiting for response...")
        
        # The new stateless architecture returns the full result in a single message.
        result = ws.recv()
        print("✓ Received response from server.")
        
        try:
            response_data = json.loads(result)
            print("\n--- Response Data ---")
            
            if 'result' in response_data:
                # The result itself can be a JSON string, so we can try to parse it for pretty printing.
                try:
                    result_content = json.loads(response_data['result'])
                    print(json.dumps(result_content, indent=2))
                except (json.JSONDecodeError, TypeError):
                    # If it's not a JSON string, just print it.
                    result_content = response_data['result']
                    print(result_content)

                if "All systems operational" in str(result_content):
                    print("\n✅ SUCCESS: The backend reported a healthy status through the persistent connection.")
                else:
                    print("\n❌ FAILED: Backend responded, but did not report a healthy status.")
            else:
                print("❌ FAILED: Response received, but it was not in the expected format.")
                print(response_data)

        except json.JSONDecodeError:
            print(f"❌ FAILED: Could not decode JSON from response: {result}")

        print("\nConnection remained stable. Closing.")
        ws.close()

    except websocket.WebSocketException as e:
        print(f"❌ FAILED: WebSocket connection error: {e}")
        print("   This could be due to DNS propagation still in progress or a configuration issue.")
    except Exception as e:
        print(f"❌ FAILED: An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_production_mcp_connection() 