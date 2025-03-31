from jinaai import JinaAI
import os

# Get API key from environment variable
api_key = os.getenv("JINACHAT_API_KEY")
print(f"API key length: {len(api_key) if api_key else 'Not found'}")
print(f"First few chars: {api_key[:10] if api_key else 'None'}")

# Initialize the Jina AI client
client = JinaAI(secrets={"jinachat-secret": api_key})

# Make a simple request
try:
    response = client.generate("Hello, how are you?")
    print(f"Response: {response}")
except Exception as e:
    print(f"Error: {str(e)}")
