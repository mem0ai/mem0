import json
import logging

from openai import OpenAI
from google import genai
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
import os

load_dotenv()

if(os.getenv("OPENAI_API_KEY")):
    openai_client = OpenAI()
elif(os.getenv("GEMINI_API_KEY")):
    gemini_client= genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    """Get categories for a memory."""
    try:
        if(openai_client):
            response = openai_client.responses.parse(
            model="gpt-4o-mini",
            instructions=MEMORY_CATEGORIZATION_PROMPT,
            input=memory,
            temperature=0,
            text_format=MemoryCategories,
            )
            response_json =json.loads(response.output[0].content[0].text)
            categories = response_json['categories']
            categories = [cat.strip().lower() for cat in categories]
            
        elif(gemini_client):
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=memory,
                config={
                    "temperature":0,
                    "system_instruction":MEMORY_CATEGORIZATION_PROMPT,
                    "response_mime_type": "application/json",
                    "response_schema": MemoryCategories
                }
            )
            categories = [cat.strip().lower() for cat in response.parsed.categories]        

        # TODO: Validate categories later may be
        return categories
    except Exception as e:
        raise e
