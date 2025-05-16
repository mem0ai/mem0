import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from your .env file (if you have one for this script)
# Or set them directly
# Make sure this .env file has YOUR_SUPABASE_URL and YOUR_SUPABASE_ANON_KEY
# It's often good to have a separate .env for scripts like this, or copy relevant vars.
# For this example, I'm assuming you might put them in a .env in the same dir as the script.
# If your API's .env is accessible and has the ANON key, you could point to it.

# OPTION 1: Load from .env in the script's directory
# Create a .env file next to get_jwt.py with:
# SUPABASE_URL="https://masapxpxcwvsjpuymbmd.supabase.co"
# SUPABASE_ANON_KEY="eyJhbGciOiJ..." (your anon public key)
load_dotenv() 
url: str = os.environ.get("SUPABASE_URL")
anon_key: str = os.environ.get("SUPABASE_ANON_KEY")

# OPTION 2: Hardcode them for this quick test (less secure, for local testing only)
# url = "https://masapxpxcwvsjpuymbmd.supabase.co"
# anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1hc2FweHB4Y3d2c2pwdXltYm1kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ2NjYxNTgsImV4cCI6MjA2MDI0MjE1OH0.DGZLa-CnI29JDARgS7SrpCcvEiCb9_CI0B1m-RN0ycE"

if not url or not anon_key:
    print("Error: SUPABASE_URL and SUPABASE_ANON_KEY must be set.")
    exit()

supabase: Client = create_client(url, anon_key)

# --- USER CREDENTIALS ---
# Replace with the email and password of a test user you created in Supabase
test_email = "jonathan.politzki@gmail.com" # From your screenshot
test_password = "TEST_JON" # The password you set for this user

print(f"Attempting to sign in user: {test_email}")

try:
    response = supabase.auth.sign_in_with_password({
        "email": test_email,
        "password": test_password
    })
    
    session = response.session
    user = response.user

    if session and session.access_token:
        print("\n--- Sign-in Successful! ---")
        print(f"User ID (from auth response): {user.id if user else 'N/A'}")
        print(f"User Email: {user.email if user else 'N/A'}")
        print("\nAccess Token (JWT):")
        print(session.access_token)
        print("\n---------------------------\n")
        print("You can now use this Access Token in the Authorization: Bearer <token> header for your API tests.")
    else:
        print("\n--- Sign-in Failed ---")
        print("Response data:", response) # Print the whole response for debugging
        if hasattr(response, 'error') and response.error: # Check if error attribute exists
             print("Error:", response.error.message)
        elif not session:
            print("Error: No session returned. Check credentials or Supabase logs.")


except Exception as e:
    print(f"\nAn exception occurred: {e}")
