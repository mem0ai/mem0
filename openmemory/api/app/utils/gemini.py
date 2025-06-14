"""
Gemini service for long-context document queries.
Uses Gemini 2.0 Flash for efficient processing of large documents.
"""
import os
import google.generativeai as genai
from typing import List, Dict
from app.models import Document
import logging
import asyncio

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        genai.configure(api_key=api_key)
        # Use Gemini 2.0 Flash for fast, long-context processing
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

        genai.configure(api_key=api_key)
        # Use Gemini 2.5 Pro Preview for enhanced reasoning and long-context processing
        self.model = genai.GenerativeModel('gemini-2.5-pro-preview-05-06')
    
    async def query_documents(self, documents: List[Document], query: str) -> str:
        """Query documents using Gemini's long context capabilities"""
        
        if not documents:
            return "No documents found to query."
        
        # Format documents into context
        context = "Here are the user's documents:\n\n"
        for i, doc in enumerate(documents, 1):
            context += f"--- Document {i}: {doc.title} ---\n"
            context += f"Type: {doc.document_type}\n"
            context += f"Source: {doc.source_url}\n"
            if doc.metadata_.get('published_date'):
                context += f"Published: {doc.metadata_['published_date']}\n"
            context += f"\nContent:\n{doc.content}\n\n"
            context += "--- End of Document ---\n\n"
        
        # Create the prompt
        prompt = f"""You are an intelligent assistant helping a user understand their saved documents.

{context}

User Query: {query}

Please analyze the documents above and provide a comprehensive answer to the user's query. 
Focus on extracting relevant information from the documents and synthesizing insights.
If the query asks about specific topics, make sure to reference which documents contain that information.
Be specific and cite document titles when referencing information."""

        try:
            # Use async generation
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                )
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error querying Gemini: {e}")
            return f"Error querying documents with Gemini: {str(e)}"
    
    async def deep_query(self, documents: List[str], query: str) -> str:
        """Query documents using Gemini's long context capabilities"""
        try:
            full_text = "\n".join(documents)
            prompt = f"Based on the following documents, answer the question: {query}\n\n{full_text}"
            
            response = await self.model.generate_content_async(prompt)
            
            return response.text
        except Exception as e:
            logger.error(f"Error querying Gemini: {e}")
            return f"Error querying documents with Gemini: {str(e)}"
    
    async def _fallback_query(self, memories: List[Dict], documents: List[Document], query: str) -> str:
        """Fallback for when context is too large"""
        context = "=== RELEVANT CONTENT (Summarized) ===\n\n"
        
        # Add fewer memories
        context += "--- KEY MEMORIES ---\n"
        for i, mem in enumerate(memories, 1):
            memory_text = mem.get('memory', mem.get('content', ''))
            context += f"{i}. {memory_text[:200]}...\n"
        
        # Add document summaries only
        if documents:
            context += "\n--- DOCUMENT SUMMARIES ---\n"
            for i, doc in enumerate(documents, 1):
                context += f"{i}. {doc.title}: {doc.content[:500]}...\n"
        
        prompt = f"""{context}

User Query: {query}

Provide a helpful response based on the available content. Note that full document content was truncated due to length constraints."""
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                )
            )
            return response.text
        except Exception as e:
            return f"Error in fallback query: {str(e)}"
    
    async def extract_insights(self, document_content: str, document_title: str) -> List[str]:
        """Extract key insights from a document"""
        
        prompt = f"""Extract 3-5 key insights from this document. Each insight should be:
- A complete, standalone statement
- Specific and actionable
- No more than 2 sentences

Document Title: {document_title}

Document Content:
{document_content[:8000]}  # Limit to first 8000 chars for insight extraction

Return only the insights, one per line, without numbering or bullet points."""

        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.5,
                    max_output_tokens=500,
                )
            )
            
            # Split response into individual insights
            insights = [line.strip() for line in response.text.split('\n') if line.strip()]
            return insights[:5]  # Limit to 5 insights
            
        except Exception as e:
            logger.error(f"Error extracting insights: {e}")
            return [] 

    async def generate_narrative(self, memories: List[str]) -> str:
        """Generate a user narrative from a list of memories."""
        try:
            if not memories:
                return "No memories provided to generate a narrative."

            full_text = "\n".join(memories)
            prompt = (
                "You are an expert biographer. Based on the following memories, write a brief, "
                "insightful, and coherent narrative about this person's life, focusing on key themes, "
                "growth, and recurring ideas. The narrative should be in the third person.\n\n"
                "Memories:\n"
                f"{full_text}"
            )
            
            response = await self.model.generate_content_async(prompt)
            
            return response.text
        except Exception as e:
            logger.error(f"Error generating narrative with Gemini: {e}")
            raise Exception(f"Failed to generate narrative with Gemini: {str(e)}") 