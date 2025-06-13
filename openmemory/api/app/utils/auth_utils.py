import secrets
import hashlib

def generate_api_key() -> str:
    """
    Generates a secure, random API key with a 'jean_sk_' prefix.
    """
    return f"jean_sk_{secrets.token_urlsafe(32)}"

def get_key_hash(api_key: str) -> str:
    """
    Hashes an API key using SHA-256 for secure storage.
    """
    return hashlib.sha256(api_key.encode()).hexdigest() 