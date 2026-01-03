import json
import logging
import re
from typing import List, Optional

import os
import socket
from app.database import SessionLocal
# Note: ConfigModel is imported inside _get_llm_config_from_db() to avoid circular import
# Circular import chain: models.py → categorization.py → memory.py → models.py
# We avoid importing from memory.py by copying _fix_ollama_urls here (minimal change)
from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

# Global client cache to avoid recreating clients on every call
# This follows the pattern used in memory.py for the memory client
_cached_llm_client = None
_cached_provider = None
_cached_config = None


class MemoryCategories(BaseModel):
    categories: List[str]


def _get_docker_host_url():
    """
    Determine the appropriate host URL to reach host machine from inside Docker container.
    
    This is a copy of the function from memory.py to avoid circular import.
    Returns the best available option for reaching the host from inside a container.
    """
    # Check for custom environment variable first
    custom_host = os.environ.get('OLLAMA_HOST')
    if custom_host:
        return custom_host.replace('http://', '').replace('https://', '').split(':')[0]
    
    # Check if we're running inside Docker
    if not os.path.exists('/.dockerenv'):
        # Not in Docker, return localhost as-is
        return "localhost"
    
    # Try different host resolution strategies
    host_candidates = []
    
    # 1. host.docker.internal (works on Docker Desktop for Mac/Windows)
    try:
        socket.gethostbyname('host.docker.internal')
        host_candidates.append('host.docker.internal')
    except socket.gaierror:
        pass
    
    # 2. Docker bridge gateway (typically 172.17.0.1 on Linux)
    try:
        with open('/proc/net/route', 'r') as f:
            for line in f:
                fields = line.strip().split()
                if fields[1] == '00000000':  # Default route
                    gateway_hex = fields[2]
                    gateway_ip = socket.inet_ntoa(bytes.fromhex(gateway_hex)[::-1])
                    host_candidates.append(gateway_ip)
                    break
    except (FileNotFoundError, IndexError, ValueError):
        pass
    
    # 3. Fallback to common Docker bridge IP
    if not host_candidates:
        host_candidates.append('172.17.0.1')
    
    # Return the first available candidate
    return host_candidates[0]


def _fix_ollama_urls(config_section):
    """
    Fix Ollama URLs for Docker environment.
    
    This is a copy of the function from memory.py to avoid circular import.
    Replaces localhost URLs with appropriate Docker host URLs.
    Sets default ollama_base_url if not provided.
    """
    if not config_section or "config" not in config_section:
        return config_section
    
    ollama_config = config_section["config"]
    
    # Set default ollama_base_url if not provided
    if "ollama_base_url" not in ollama_config:
        ollama_config["ollama_base_url"] = "http://host.docker.internal:11434"
    else:
        # Check for ollama_base_url and fix if it's localhost
        url = ollama_config["ollama_base_url"]
        if "localhost" in url or "127.0.0.1" in url:
            docker_host = _get_docker_host_url()
            if docker_host != "localhost":
                new_url = url.replace("localhost", docker_host).replace("127.0.0.1", docker_host)
                ollama_config["ollama_base_url"] = new_url
    
    return config_section


def _get_llm_config_from_db():
    """
    Get LLM configuration from database, following the same pattern as memory.py.
    
    This function:
    1. Creates a database session (same as memory.py does)
    2. Queries the Config table for the "main" config key
    3. Extracts the LLM configuration from mem0.llm
    4. Applies Ollama URL fixes for Docker if needed (same helper as memory.py)
    
    Returns:
        dict: LLM configuration with 'provider' and 'config' keys, or None if not found
    """
    # Import ConfigModel here (lazy import) to avoid circular import
    # Circular import chain: models.py → categorization.py → memory.py → models.py
    # We avoid importing from memory.py by copying _fix_ollama_urls above
    from app.models import Config as ConfigModel
    
    try:
        db = SessionLocal()
        try:
            # Query for the main configuration, same pattern as memory.py line 314
            db_config = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
            
            if db_config and "mem0" in db_config.value:
                mem0_config = db_config.value["mem0"]
                
                # Extract LLM configuration if available
                if "llm" in mem0_config and mem0_config["llm"] is not None:
                    llm_config = mem0_config["llm"].copy()
                    
                    # Apply Ollama URL fixes for Docker environment (same as memory.py line 332-333)
                    # This ensures localhost URLs are converted to host.docker.internal or gateway IP
                    if llm_config.get("provider") == "ollama":
                        llm_config = _fix_ollama_urls(llm_config)
                    
                    return llm_config
            
            return None
        finally:
            db.close()
    except Exception as e:
        logging.error(f"[ERROR] Failed to get LLM config from database: {e}")
        return None


def _get_or_create_llm_client():
    """
    Get or create the appropriate LLM client based on current configuration.
    
    This function:
    1. Checks if we have a cached client that matches current config
    2. If not, gets fresh config from database
    3. Creates appropriate client (OpenAI or Ollama) based on provider
    4. Caches the client to avoid recreation on every categorization call
    
    This follows the caching pattern used in memory.py for the memory client.
    
    Returns:
        tuple: (client, provider_name) or (None, None) if config unavailable
    """
    global _cached_llm_client, _cached_provider, _cached_config
    
    # Get current configuration from database
    llm_config = _get_llm_config_from_db()
    
    if not llm_config:
        logging.warning("[WARNING] No LLM config found in database, using default OpenAI")
        # Fallback to default OpenAI if no config found (backward compatibility)
        return OpenAI(), "openai"
    
    # Check if cached client matches current config
    # This avoids recreating clients when config hasn't changed
    if (_cached_llm_client is not None and 
        _cached_provider == llm_config.get("provider") and
        _cached_config == llm_config):
        return _cached_llm_client, _cached_provider
    
    # Create new client based on provider
    provider = llm_config.get("provider", "openai")
    config = llm_config.get("config", {})
    
    if provider == "ollama":
        # Import ollama client (same pattern as mem0/llms/ollama.py)
        try:
            from ollama import Client
        except ImportError:
            logging.error("[ERROR] Ollama library not installed. Install with: pip install ollama")
            raise ImportError("Ollama library required but not installed")
        
        # Get Ollama base URL from config, with fallback
        # This matches the pattern in mem0/llms/ollama.py line 39
        ollama_base_url = config.get("ollama_base_url", "http://localhost:11434")
        
        # Create Ollama client (same as mem0/llms/ollama.py line 39)
        client = Client(host=ollama_base_url)
        
        # Cache the client and config
        _cached_llm_client = client
        _cached_provider = provider
        _cached_config = llm_config
        
        logging.info(f"[INFO] Created Ollama client for categorization (base_url: {ollama_base_url})")
        return client, provider
    
    elif provider == "openai":
        # Create OpenAI client (backward compatible with original code)
        # Get API key from config, with fallback to environment variable
        api_key = config.get("api_key")
        if api_key and api_key.startswith("env:"):
            # Handle "env:OPENAI_API_KEY" format
            env_key = api_key.split(":", 1)[1]
            import os
            api_key = os.getenv(env_key)
        
        client = OpenAI(api_key=api_key) if api_key else OpenAI()
        
        # Cache the client and config
        _cached_llm_client = client
        _cached_provider = provider
        _cached_config = llm_config
        
        logging.info("[INFO] Created OpenAI client for categorization")
        return client, provider
    
    else:
        # Unknown provider, fallback to OpenAI
        logging.warning(f"[WARNING] Unknown LLM provider '{provider}', falling back to OpenAI")
        client = OpenAI()
        return client, "openai"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    """
    Get categories for a memory using the configured LLM provider.
    
    This function:
    1. Gets the appropriate LLM client (OpenAI or Ollama) based on database config
    2. Calls the LLM with the categorization prompt
    3. Parses the response to extract categories
    4. Handles provider-specific API differences
    
    Args:
        memory: The memory text to categorize
        
    Returns:
        List[str]: List of category names (lowercased and stripped)
        
    Raises:
        Exception: If categorization fails after retries
    """
    try:
        # Get the appropriate LLM client based on current configuration
        # This ensures categorization uses the same LLM provider as the main mem0 system
        client, provider = _get_or_create_llm_client()
        
        # Build messages for the LLM (same format for both providers)
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]
        
        if provider == "ollama":
            # Ollama API handling
            # Ollama doesn't support structured output parsing like OpenAI's beta.parse()
            # So we need to request JSON format and parse it manually
            config = _get_llm_config_from_db()
            model = config.get("config", {}).get("model", "mistral:7b-instruct-q4_K_M") if config else "mistral:7b-instruct-q4_K_M"
            temperature = config.get("config", {}).get("temperature", 0) if config else 0
            
            # Build the prompt to request JSON format (Ollama needs explicit instruction)
            # We include the JSON schema in the system prompt to guide the model
            json_prompt = f"""{MEMORY_CATEGORIZATION_PROMPT}

Return your response as a JSON object with this exact format:
{{"categories": ["category1", "category2", ...]}}

JSON Response:"""
            
            ollama_messages = [
                {"role": "system", "content": json_prompt},
                {"role": "user", "content": memory}
            ]
            
            # Call Ollama API (same pattern as mem0/llms/ollama.py line 115-120)
            response = client.chat(
                model=model,
                messages=ollama_messages,
                options={
                    "temperature": temperature,
                    "format": "json"  # Request JSON format from Ollama
                }
            )
            
            # Extract response content
            response_content = response.get("message", {}).get("content", "")
            
            # Parse JSON response manually (since Ollama doesn't have structured output)
            try:
                # Try to parse as JSON
                parsed_json = json.loads(response_content)
                categories = parsed_json.get("categories", [])
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract JSON from markdown code blocks
                # Some models wrap JSON in ```json ... ``` blocks
                if "```json" in response_content:
                    json_start = response_content.find("```json") + 7
                    json_end = response_content.find("```", json_start)
                    json_str = response_content[json_start:json_end].strip()
                    parsed_json = json.loads(json_str)
                    categories = parsed_json.get("categories", [])
                elif "```" in response_content:
                    # Try extracting from generic code block
                    json_start = response_content.find("```") + 3
                    json_end = response_content.find("```", json_start)
                    json_str = response_content[json_start:json_end].strip()
                    if json_str.startswith("json"):
                        json_str = json_str[4:].strip()
                    parsed_json = json.loads(json_str)
                    categories = parsed_json.get("categories", [])
                else:
                    # Last resort: try to find JSON object in the response
                    # Use regex to extract JSON object from potentially malformed response
                    json_match = re.search(r'\{[^{}]*"categories"[^{}]*\[[^\]]*\][^{}]*\}', response_content)
                    if json_match:
                        parsed_json = json.loads(json_match.group())
                        categories = parsed_json.get("categories", [])
                    else:
                        logging.warning(f"[WARNING] Could not parse Ollama response as JSON: {response_content}")
                        raise ValueError("Failed to parse Ollama response as JSON")
            
            # Validate and return categories (same format as OpenAI path)
            parsed = MemoryCategories(categories=categories)
            return [cat.strip().lower() for cat in parsed.categories]
        
        else:
            # OpenAI API handling (original code path, now configurable)
            config = _get_llm_config_from_db()
            model = config.get("config", {}).get("model", "gpt-4o-mini") if config else "gpt-4o-mini"
            temperature = config.get("config", {}).get("temperature", 0) if config else 0
            
            # Use OpenAI's structured output parsing (beta.chat.completions.parse)
            # This is more reliable than manual JSON parsing
            completion = client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=MemoryCategories,
                temperature=temperature
            )
            
            # Extract parsed categories (OpenAI handles Pydantic parsing automatically)
            parsed: MemoryCategories = completion.choices[0].message.parsed
            return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        try:
            # Try to log the raw response for debugging (if available)
            if provider == "ollama" and 'response' in locals():
                logging.debug(f"[DEBUG] Raw Ollama response: {response}")
            elif provider == "openai" and 'completion' in locals():
                logging.debug(f"[DEBUG] Raw OpenAI response: {completion.choices[0].message.content}")
        except Exception as debug_e:
            logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        raise
