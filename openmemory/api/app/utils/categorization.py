import json
import logging
import os
import re
from typing import List

from app.database import SessionLocal
from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()
openai_client = OpenAI()

deepseek_client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url=os.environ.get("DEEPSEEK_BASE_URL")
)

class MemoryCategories(BaseModel):
    categories: List[str]

class UnsupportedProviderError(Exception):
    pass

def _get_categories_from_deepseek(memory: str, model: str = "deepseek-chat") -> List[str]:
    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT + "\n\nPlease respond with a JSON object containing a 'categories' array of strings."},
            {"role": "user", "content": memory}
        ]
    
        completion = deepseek_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0
        )
    
        response_text = completion.choices[0].message.content
        
        # Try to extract JSON from response
    
        # Look for JSON in the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            parsed_json = json.loads(json_str)
            if "categories" in parsed_json:
                return [cat.strip().lower() for cat in parsed_json["categories"]]
        
        # If no JSON found, try to parse as simple list
        lines = response_text.strip().split('\n')
        categories = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('Categories:'):
                # Remove bullet points, numbers, etc.
                clean_line = re.sub(r'^[-*•\d\.]\s*', '', line).strip()
                if clean_line:
                    categories.append(clean_line.lower())
        
        # Limit to 10 categories or default
        return categories[:10] if categories else ["general"]  
    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        try:
            logging.debug(f"[DEBUG] Raw response: {completion.choices[0].message.content}")
        except Exception as debug_e:
            logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        raise

def _get_categories_from_openai(memory: str, model: str = "gpt-4o-mini") -> List[str]:
    try:
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


def get_llm_config() -> dict:
    """Get LLM configuration from database."""
    try:
        # Import here to avoid circular import
        from app.models import Config as ConfigModel
        
        db = SessionLocal()
        db_config = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
        
        if db_config and "mem0" in db_config.value and "llm" in db_config.value["mem0"]:
            llm_config = db_config.value["mem0"]["llm"]
            if llm_config:
                db.close()
                return llm_config
        
        db.close()
        return {"provider": "unknown", "config": {"model": "unknown"}}
        
    except Exception as e:
        logging.error(f"[ERROR] Failed to load LLM config from database: {e}")
        return {"provider": "unknown", "config": {"model": "unknown"}}

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=15),
    retry=retry_if_not_exception_type(UnsupportedProviderError),
    reraise=True
)
def get_categories_for_memory(memory: str) -> List[str]:
    llm_config = get_llm_config()
    provider = llm_config.get("provider", "unknown")
    config = llm_config.get("config", {})
    model = config.get("model")
    
    if provider == "openai":
        model = model or "gpt-4o-mini"
        return _get_categories_from_openai(memory, model)
    elif provider == "deepseek":
        model = model or "deepseek-chat"
        return _get_categories_from_deepseek(memory, model)
    else:
        supported = ("openai", "deepseek")
        raise UnsupportedProviderError(
            f"Unsupported LLM provider: '{provider or 'empty'}'. Supported: {', '.join(supported)}"
        )


