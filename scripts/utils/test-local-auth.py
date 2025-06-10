#!/usr/bin/env python3
"""
Test script to verify local authentication bypass works correctly with PostgreSQL.
This will check if the USER_ID is properly set in the environment and make a simple API request
that requires authentication to verify the local auth bypass works.
"""
import os
import sys
import requests
import json
import re

# Function to read environment variables from .env file
def load_env_from_file(env_file_path):
    """Load environment variables from a .env file"""
    if not os.path.exists(env_file_path):
        print(f"❌ Environment file not found: {env_file_path}")
        return False
        
    try:
        with open(env_file_path, 'r') as file:
            for line in file:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                    
                # Parse key-value pairs
                match = re.match(r'^([A-Za-z0-9_]+)=[\"]?([^\"]*)[\"]?$', line)
                if match:
                    key, value = match.groups()
                    # Set the environment variable
                    os.environ[key] = value
        return True
    except Exception as e:
        print(f"❌ Error reading environment file: {e}")
        return False

# Load environment variables from the backend .env file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_ENV_FILE = os.path.join(BASE_DIR, 'openmemory', 'api', '.env')
load_env_from_file(API_ENV_FILE)

# Default API endpoint
API_URL = "http://localhost:8765"

def check_user_id_env():
    """Check if USER_ID is set in the environment"""
    user_id = os.getenv("USER_ID")
    if not user_id:
        print("❌ ERROR: USER_ID environment variable is not set.")
        print("   This is required for local development mode.")
        print("   Add USER_ID=default_user to your openmemory/api/.env file.")
        print("   The file exists but the variable might not be correctly set.")
        return False
    else:
        print(f"✅ USER_ID environment variable is set to: {user_id}")
        return True

def check_api_running():
    """Check if the API is running"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is running and health check endpoint is accessible.")
            return True
        else:
            print(f"❌ API health check failed with status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Error connecting to API: {e}")
        print("   Make sure the API is running with ./start-api.sh")
        return False

def test_authenticated_endpoint():
    """Test an authenticated endpoint to verify local auth bypass works"""
    try:
        # Try to access the stats endpoint, which requires authentication
        # Include an empty Authorization header to trigger the local auth bypass
        headers = {
            'Authorization': 'Bearer dummy-token-for-local-dev'
        }
        response = requests.get(f"{API_URL}/api/v1/stats", headers=headers)
        response.raise_for_status()
        
        # Check if we got a valid response
        data = response.json()
        print("✅ Successfully accessed authenticated endpoint!")
        print("   This confirms local auth bypass is working correctly.")
        print(f"   User ID from response: {data.get('user_id')}")
        return True
    except requests.exceptions.HTTPError as e:
        # If we get a 401 or 403, the local auth bypass isn't working
        if e.response.status_code in (401, 403):
            print("❌ Authentication failed with status code:", e.response.status_code)
            print("   Local auth bypass is not working correctly.")
            try:
                error_message = e.response.json()
                print(f"   Error details: {json.dumps(error_message, indent=2)}")
            except:
                print(f"   Error response: {e.response.text}")
        else:
            print(f"❌ HTTP error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing authenticated endpoint: {e}")
        return False

def main():
    """Run all verification tests"""
    print("\n===== LOCAL AUTHENTICATION VERIFICATION =====\n")
    
    # Check environment variables
    env_check = check_user_id_env()
    
    # Check if API is running
    api_check = check_api_running()
    
    if env_check and api_check:
        # Test authenticated endpoint
        auth_check = test_authenticated_endpoint()
        
        if auth_check:
            print("\n✅✅✅ SUCCESS! Local authentication is working correctly.")
            print("   Your local development environment is now using PostgreSQL for authentication")
            print("   without requiring Supabase or email verification.")
        else:
            print("\n❌❌❌ FAILED! Local authentication bypass is not working correctly.")
            print("   Please check the logs for more details.")
    else:
        print("\n⚠️ Skipping authentication test due to previous failures.")
    
    print("\n=============================================\n")

if __name__ == "__main__":
    main()
