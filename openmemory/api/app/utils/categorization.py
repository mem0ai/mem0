import logging
import json
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from mem0.utils.factory import LlmFactory
from dotenv import load_dotenv
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    from app.utils.memory import get_memory_client
    try:
        # 1. Get initialized memory client to access global config
        memory_client = get_memory_client()
        if not memory_client:
            logging.warning("Memory client not initialized, using default OpenAI fallback for categorization")
            # Fallback to simple default or raise error? 
            # For now let's try to proceed with a default config if possible or raise
            raise ValueError("Memory client not initialized")
        
        # 2. Create LLM instance using the same config as the main memory client
        llm_config = memory_client.config.llm
        llm = LlmFactory.create(llm_config.provider, llm_config.config)

        # 3. Construct messages with explicit JSON instruction
        # We append JSON instruction to system prompt to ensure models like Ollama/DeepSeek comply
        json_instruction = "\nReturn ONLY a valid JSON object with a 'categories' key containing a list of strings. Example: {\"categories\": [\"work\", \"personal\"]}. Do not include markdown formatting."
        
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT + json_instruction},
            {"role": "user", "content": memory}
        ]

        # 4. Generate response
        # We use response_format={"type": "json_object"} which is supported by some providers (OpenAI, Ollama)
        # But we also rely on the prompt instruction for others
        response = llm.generate_response(messages=messages, response_format={"type": "json_object"})
        
        # 5. Parse response
        content = response
        # Handle different return types if necessary (though mem0 usually returns string content)
        if hasattr(response, "content"): 
            content = response.content
        elif isinstance(response, dict) and "content" in response:
             content = response["content"]
             
        # Clean up potential markdown code blocks
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        # Parse JSON
        try:
            data = json.loads(content)
            categories = data.get("categories", [])
            return [cat.strip().lower() for cat in categories]
        except json.JSONDecodeError:
            logging.error(f"Failed to parse JSON response: {content}")
            # Fallback: try to extract list from string if JSON fails
            return []

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        raise
