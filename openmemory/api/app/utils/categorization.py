import json
import logging

from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
import os
import anthropic

load_dotenv()

# Initialize Claude client using the same API key as your LLM
anthropic_client = anthropic.Client(api_key=os.environ.get("LLM_API_KEY"))


class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    """Get categories for a memory."""
    try:
        # Use Anthropic's Claude for categorization
        response = anthropic_client.messages.create(
            model=os.environ.get("LLM_CHOICE", "claude-3-5-sonnet"),
            max_tokens=300,
            temperature=0,
            system="You are a helpful AI that categorizes text into relevant categories. " + 
                   "Your response should be a JSON object with a 'categories' array containing string values.",
            messages=[
                {"role": "user", "content": f"{MEMORY_CATEGORIZATION_PROMPT}\n\nText to categorize: {memory}"}
            ]
        )
        
        # Extract JSON from response
        response_text = response.content[0].text
        # Parse the response to extract JSON
        try:
            # Try to extract JSON if it's wrapped in code blocks
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_text = response_text
                
            response_json = json.loads(json_text)
            categories = response_json['categories']
            categories = [cat.strip().lower() for cat in categories]
            return categories
        except Exception as e:
            logging.error(f"Error parsing Claude response: {e}")
            logging.error(f"Raw response: {response_text}")
            return ["uncategorized"]  # Fallback category
            
    except Exception as e:
        logging.error(f"Error in categorization: {e}")
        raise e
