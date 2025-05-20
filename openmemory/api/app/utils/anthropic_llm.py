import os
import logging
from anthropic import Anthropic
from typing import List, Dict, Any, Optional

class AnthropicLLM:
    """
    A wrapper class to use Anthropic Claude for LLM functionality in mem0
    """
    
    def __init__(self, api_key=None):
        self.client = Anthropic(api_key=api_key or os.environ.get("LLM_API_KEY"))
        self.model = os.environ.get("LLM_CHOICE", "claude-3-5-sonnet")
    
    def generate_response(self, prompt=None, system="", max_tokens=500, temperature=0.7, **kwargs):
        """Generate a response using Claude. Compatible with mem0's expected format."""
        try:
            # Log what parameters we're receiving
            print(f"Anthropic LLM generate_response called with kwargs: {kwargs}")
            
            messages = kwargs.get("messages", None)
            response_format = kwargs.get("response_format", None)
            
            # Determine if JSON output is requested
            json_mode = False
            if response_format and isinstance(response_format, dict) and response_format.get("type") == "json_object":
                json_mode = True
                system += "\nYour response must be formatted as a JSON object."
            
            # If messages are provided, format them for Claude
            if messages:
                formatted_messages = []
                for msg in messages:
                    role = msg.get("role", "user")
                    if role == "system":
                        system = msg.get("content", system)
                    else:
                        formatted_messages.append({
                            "role": "user" if role == "user" else "assistant", 
                            "content": msg.get("content", "")
                        })
            else:
                formatted_messages = [{"role": "user", "content": prompt or ""}]
            
            response = self.client.messages.create(
                model=self.model,
                system=system,
                messages=formatted_messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            # Return in a format compatible with the original OpenAI response
            return {
                "choices": [
                    {
                        "message": {
                            "content": response.content[0].text,
                            "role": "assistant"
                        }
                    }
                ],
                "model": self.model
            }
            
        except Exception as e:
            print(f"Error generating response with Claude: {e}")
            # Return a format that won't break downstream processing
            return {
                "choices": [
                    {
                        "message": {
                            "content": f"Error generating response: {str(e)}",
                            "role": "assistant"
                        }
                    }
                ],
                "model": self.model
            }

# Create a global instance for easy import
anthropic_llm = AnthropicLLM()