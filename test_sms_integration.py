#!/usr/bin/env python3
"""
Local SMS Integration Test Script
---------------------------------
This script simulates receiving SMS messages from Twilio to test the
full local backend integration, including AI tool selection and Redis
conversation context, without needing a verified Twilio number.

Prerequisites:
1. Ensure your local backend is running (`make backend`).
2. Make sure you have a `.env.local` file in `openmemory/` with your
   `TWILIO_AUTH_TOKEN` and a `TEST_PHONE_NUMBER` (e.g., +15551234567).
3. The user associated with the test phone number should exist in your local DB
   and have Pro/Enterprise subscription tier for the test to pass.
"""
import os
import time
import hmac
import hashlib
import base64
from urllib.parse import urlencode
import requests
from dotenv import load_dotenv

# --- Configuration ---
# Load environment variables from .env.local
dotenv_path = os.path.join(os.path.dirname(__file__), 'openmemory', '.env.local')
load_dotenv(dotenv_path=dotenv_path)

WEBHOOK_URL = "http://localhost:8765/webhooks/sms"
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
# Use a dedicated test number from env, or default
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER", "+15551234567") 
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# --- Helper Function to Simulate Twilio Request ---
def send_simulated_sms(message: str):
    """
    Simulates a Twilio SMS webhook request by generating a valid signature
    and sending a POST request to the local server.
    """
    if not all([TWILIO_AUTH_TOKEN, TEST_PHONE_NUMBER, TWILIO_PHONE_NUMBER]):
        print("❌ Error: Missing TWILIO_AUTH_TOKEN, TEST_PHONE_NUMBER, or TWILIO_PHONE_NUMBER in .env.local")
        return

    print(f"📱 Sending SMS: '{message}'")
    
    # Twilio sends POST data as a form
    post_params = {
        'From': TEST_PHONE_NUMBER,
        'To': TWILIO_PHONE_NUMBER,
        'Body': message
    }
    
    # To create a valid signature, Twilio concatenates the URL with the sorted POST params
    # The body of the request for signing must be the raw, urlencoded string of sorted params.
    sorted_params = sorted(post_params.items())
    post_body = urlencode(sorted_params).encode('utf-8')

    # --- BEGIN TEMPORARY DEBUGGING ---
    string_to_sign_client = (WEBHOOK_URL).encode('utf-8') + post_body
    print("--- SIGNATURE VALIDATION (CLIENT-SIDE) ---")
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"POST Body (raw): {post_body}")
    print(f"String to Sign: {string_to_sign_client}")
    # --- END TEMPORARY DEBUGGING ---

    # Generate the signature using the same logic as the validator
    expected_signature = hmac.new(
        TWILIO_AUTH_TOKEN.encode('utf-8'),
        string_to_sign_client,
        hashlib.sha1
    ).digest()
    
    signature = base64.b64encode(expected_signature).decode('utf-8')

    headers = {
        'X-Twilio-Signature': signature,
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        # The data argument must be the raw, sorted, urlencoded string to match the signature.
        # Sending the dict `post_params` would result in a different order.
        response = requests.post(WEBHOOK_URL, data=post_body, headers=headers)
        
        if response.status_code == 200:
            print(f"✅ Server received message. Response: {response.json()}")
        elif response.status_code == 403:
            print("❌ Server rejected message with 403 Forbidden. Is the signature logic correct?")
        else:
            print(f"⚠️ Server responded with status {response.status_code}: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Is the backend server running with `make backend`?")
        
    print("-" * 40)


# --- Main Test Execution ---
if __name__ == "__main__":
    print("🚀 Starting Local SMS Integration Test...")
    print("This will simulate a conversation to test context and AI tool selection.")
    print("-" * 40)
    
    # --- Test 1: Add a new memory ---
    print("Step 1: Adding a new memory. The AI should select 'add_memories'.")
    send_simulated_sms("Remember my favorite color is blue")
    time.sleep(5)  # Give the server time to process

    # --- Test 2: Ask a question using conversation context ---
    print("Step 2: Asking a question. The AI should use context and select 'ask_memory'.")
    send_simulated_sms("what is my favorite color?")
    time.sleep(5)

    # --- Test 3: Simple search ---
    print("Step 3: Performing a search. The AI should select 'search_memory'.")
    send_simulated_sms("search for notes about colors")
    time.sleep(5)
    
    # --- Test 4: List recent memories ---
    print("Step 4: Listing recent memories. The AI should select 'list_memories'.")
    send_simulated_sms("show my recent notes")
    time.sleep(5)
    
    # --- Test 5: Help command ---
    print("Step 5: Testing the help command.")
    send_simulated_sms("help")
    
    print("�� Test complete.") 