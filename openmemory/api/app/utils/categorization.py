import logging
import os
from typing import List, Optional

from app.database import SessionLocal
from app.models import Config as ConfigModel
from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class MemoryCategories(BaseModel):
    categories: List[str]


def _get_categorization_config() -> dict:
    """
    Load categorization configuration from the database.
    
    Falls back to defaults if no custom config is found:
    - provider: "openai"
    - model: "gpt-4o-mini"
    
    Returns:
        dict with 'provider', 'model', and optional provider-specific settings
    """
    default_config = {
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    
    try:
        db = SessionLocal()
        db_config = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
        
        if db_config and "openmemory" in db_config.value:
            openmemory_config = db_config.value["openmemory"]
            if "categorization" in openmemory_config and openmemory_config["categorization"]:
                cat_config = openmemory_config["categorization"]
                # Merge with defaults
                default_config.update(cat_config)
        
        db.close()
    except Exception as e:
        logger.warning(f"Error loading categorization config from database: {e}")
    
    return default_config


def _resolve_api_key(config: dict) -> Optional[str]:
    """
    Resolve API key from config, supporting env:VAR_NAME syntax.
    """
    api_key = config.get("api_key")
    if api_key and isinstance(api_key, str) and api_key.startswith("env:"):
        env_var = api_key.split(":", 1)[1]
        return os.environ.get(env_var)
    return api_key


def _categorize_with_openai(memory: str, config: dict) -> List[str]:
    """Categorize memory using OpenAI-compatible API."""
    from openai import OpenAI
    
    api_key = _resolve_api_key(config)
    client_kwargs = {}
    if api_key:
        client_kwargs["api_key"] = api_key
    
    # Support custom base URL for OpenAI-compatible providers
    if config.get("base_url"):
        client_kwargs["base_url"] = config["base_url"]
    
    client = OpenAI(**client_kwargs)
    
    messages = [
        {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
        {"role": "user", "content": memory}
    ]
    
    completion = client.beta.chat.completions.parse(
        model=config.get("model", "gpt-4o-mini"),
        messages=messages,
        response_format=MemoryCategories,
        temperature=0
    )
    
    parsed: MemoryCategories = completion.choices[0].message.parsed
    return [cat.strip().lower() for cat in parsed.categories]


def _categorize_with_ollama(memory: str, config: dict) -> List[str]:
    """Categorize memory using Ollama API."""
    from openai import OpenAI
    
    base_url = config.get("ollama_base_url", "http://localhost:11434/v1")
    # Ensure URL has /v1 suffix for OpenAI compatibility
    if not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"
    
    client = OpenAI(base_url=base_url, api_key="ollama")
    
    messages = [
        {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
        {"role": "user", "content": f"Return the categories as a JSON object with a 'categories' key containing an array of strings. Memory: {memory}"}
    ]
    
    completion = client.chat.completions.create(
        model=config.get("model", "llama3.1:latest"),
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"}
    )
    
    content = completion.choices[0].message.content
    import json
    parsed = json.loads(content)
    return [cat.strip().lower() for cat in parsed.get("categories", [])]


def _categorize_with_litellm(memory: str, config: dict) -> List[str]:
    """Categorize memory using LiteLLM (supports many providers)."""
    try:
        import litellm
    except ImportError:
        raise ImportError(
            "litellm is required for LiteLLM categorization. "
            "Install it with: pip install litellm"
        )
    
    messages = [
        {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
        {"role": "user", "content": memory}
    ]
    
    kwargs = {
        "model": config.get("model", "gpt-4o-mini"),
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"}
    }
    
    api_key = _resolve_api_key(config)
    if api_key:
        kwargs["api_key"] = api_key
    
    if config.get("base_url"):
        kwargs["api_base"] = config["base_url"]
    
    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content
    
    import json
    parsed = json.loads(content)
    return [cat.strip().lower() for cat in parsed.get("categories", [])]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    """
    Categorize a memory entry using the configured LLM provider.
    
    Supports multiple providers:
    - openai (default): Uses OpenAI API or OpenAI-compatible endpoints
    - ollama: Uses local Ollama instance
    - litellm: Uses LiteLLM for any supported provider
    - anthropic: Uses Anthropic Claude API
    - deepseek: Uses DeepSeek API
    
    The provider is configured in the openmemory.categorization section
    of the database config. Falls back to OpenAI gpt-4o-mini if not configured.
    
    Args:
        memory: The memory content to categorize
        
    Returns:
        List of category strings
    """
    config = _get_categorization_config()
    provider = config.get("provider", "openai").lower()
    
    logger.info(f"Categorizing memory with provider: {provider}")
    
    try:
        if provider == "ollama":
            return _categorize_with_ollama(memory, config)
        elif provider == "litellm":
            return _categorize_with_litellm(memory, config)
        elif provider in ("openai", "anthropic", "deepseek", "groq", "together", "azure_openai"):
            # All these providers have OpenAI-compatible APIs
            return _categorize_with_openai(memory, config)
        else:
            # Unknown provider - try OpenAI-compatible API as fallback
            logger.warning(
                f"Unknown categorization provider '{provider}', "
                f"falling back to OpenAI-compatible API"
            )
            return _categorize_with_openai(memory, config)
    except Exception as e:
        logger.error(f"[ERROR] Failed to get categories with provider {provider}: {e}")
        raise
