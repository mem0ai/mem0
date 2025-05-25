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
    
    async def deep_query(self, memories: List[Dict], documents: List[Document], query: str) -> str:
        """
        Perform a deep, comprehensive query across all user content.
        This is the core innovation - using long-context models to understand everything.
        """
        
        # Build comprehensive context
        context = "=== USER'S KNOWLEDGE BASE ===\n\n"
        
        # Add regular memories first
        if memories:
            context += "--- MEMORIES ---\n\n"
            for i, mem in enumerate(memories, 1):
                memory_text = mem.get('memory', mem.get('content', ''))
                context += f"Memory {i}: {memory_text}\n"
                
                # Add relevant metadata
                metadata = mem.get('metadata', {})
                if metadata:
                    if 'source_app' in metadata:
                        context += f"  Source: {metadata['source_app']}\n"
                    if 'created_at' in mem:
                        context += f"  Created: {mem['created_at']}\n"
                context += "\n"
        
        # Add documents
        if documents:
            context += "\n--- DOCUMENTS ---\n\n"
            for i, doc in enumerate(documents, 1):
                context += f"Document {i}: {doc.title}\n"
                context += f"  Type: {doc.document_type}\n"
                context += f"  Source: {doc.source_url}\n"
                if doc.metadata_.get('published_date'):
                    context += f"  Published: {doc.metadata_['published_date']}\n"
                context += f"  Content ({len(doc.content)} chars):\n"
                context += f"  {doc.content}\n"
                context += "\n--- End of Document ---\n\n"
        
        # Create the comprehensive prompt
        prompt = f"""You are an advanced AI assistant with access to a user's complete knowledge base, including their memories and saved documents.

{context}

=== USER QUERY ===
{query}

=== YOUR TASK ===
Analyze ALL the content above to provide a comprehensive, intelligent response to the user's query.

Guidelines:
1. Draw connections between different memories and documents
2. Synthesize information from multiple sources
3. Identify patterns and insights that might not be obvious from individual pieces
4. If the query asks about specific topics, cite which memories/documents contain that information
5. Be specific and reference actual content when making points
6. If there are contradictions or evolution of thoughts over time, note them

Provide a thoughtful, comprehensive response that demonstrates deep understanding of the user's knowledge base."""

        try:
            # Use async generation with longer output for comprehensive responses
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=4096,  # Longer responses for deep queries
                )
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error in deep query: {e}")
            # Fallback to a simpler query if the full context is too large
            if "context length" in str(e).lower():
                return await self._fallback_query(memories[:10], documents[:3], query)
            return f"Error performing deep query: {str(e)}"
    
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