import logging
import os
from typing import List, Optional

from app.database import SessionLocal
from app.models import Config as ConfigModel
from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()


class MemoryCategories(BaseModel):
    categories: List[str]


def get_llm_config():
    """Get LLM configuration from database or use defaults."""
    try:
        db = SessionLocal()
        db_config = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
        
        if db_config and "mem0" in db_config.value and "llm" in db_config.value["mem0"]:
            llm_config = db_config.value["mem0"]["llm"]
            db.close()
            return llm_config
        
        db.close()
    except Exception as e:
        logging.warning(f"Failed to load LLM config from database: {e}")
    
    # Default configuration
    return {
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "api_key": os.getenv("OPENAI_API_KEY")
        }
    }


def parse_env_value(value):
    """Parse environment variable references in config values."""
    if isinstance(value, str) and value.startswith("env:"):
        env_var = value.split(":", 1)[1]
        return os.getenv(env_var)
    return value


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    try:
        # Get LLM configuration
        llm_config = get_llm_config()
        config = llm_config.get("config", {})
        
        # Parse environment variables
        api_key = parse_env_value(config.get("api_key", os.getenv("OPENAI_API_KEY")))
        model = config.get("model", "gpt-4o-mini")
        base_url = parse_env_value(config.get("openai_base_url")) if "openai_base_url" in config else None
        
        # Create OpenAI client with configured settings
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        openai_client = OpenAI(**client_kwargs)
        
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]

        # Let OpenAI handle the pydantic parsing directly
        completion = openai_client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=MemoryCategories,
            temperature=0
        )

        parsed: MemoryCategories = completion.choices[0].message.parsed
        return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        try:
            logging.debug(f"[DEBUG] Raw response: {completion.choices[0].message.content}")
        except Exception as debug_e:
            logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        raise
