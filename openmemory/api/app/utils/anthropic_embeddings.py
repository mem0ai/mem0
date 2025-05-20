import os
from anthropic import Anthropic
import numpy as np
from typing import List, Any

class AnthropicEmbeddings:
    """
    A wrapper class to use Anthropic Claude for embeddings in mem0
    This will be used to intercept embedding calls and route to Claude
    """
    
    def __init__(self, api_key=None):
        self.client = Anthropic(api_key=api_key or os.environ.get("EMBEDDING_MODEL_API_KEY"))
        self.model = os.environ.get("EMBEDDING_MODEL_CHOICE", "claude-3-sonnet-20240229")
    
    def create_embedding(self, input_text: str) -> List[float]:
        """Create embeddings for a single text input using Claude."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=input_text,
                dimensions=1536  # Match OpenAI's text-embedding-ada-002 dimension
            )
            return response.embeddings[0]
        except Exception as e:
            print(f"Error creating embedding with Claude: {e}")
            # Return a zero vector as fallback
            return [0.0] * 1536
            
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for multiple text inputs."""
        embeddings = []
        for text in texts:
            embedding = self.create_embedding(text)
            embeddings.append(embedding)
        return embeddings

# Create a global instance for easy import
anthropic_embedder = AnthropicEmbeddings()