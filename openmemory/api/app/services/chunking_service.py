"""
Document Chunking Service

This service handles chunking of documents for efficient retrieval.
It can be run as a background job or called on-demand.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Document, DocumentChunk
import logging

logger = logging.getLogger(__name__)


class ChunkingService:
    def __init__(self, chunk_size: int = 2000, overlap: int = 200):
        """
        Initialize the chunking service.
        
        Args:
            chunk_size: Target size for each chunk in characters
            overlap: Number of characters to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: The text to chunk
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            # Calculate end position
            end = start + self.chunk_size
            
            # If this is not the last chunk, try to break at a sentence boundary
            if end < text_length:
                # Look for sentence endings near the chunk boundary
                search_start = max(start + self.chunk_size - 100, start)
                search_end = min(start + self.chunk_size + 100, text_length)
                
                # Find the last sentence ending in the search range
                sentence_end = -1
                for i in range(search_end - 1, search_start - 1, -1):
                    if text[i] in '.!?' and i + 1 < text_length and text[i + 1] in ' \n\t':
                        sentence_end = i + 1
                        break
                
                # If we found a sentence boundary, use it
                if sentence_end > 0:
                    end = sentence_end
            
            # Extract the chunk
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move to the next chunk with overlap
            start = end - self.overlap if end < text_length else text_length
        
        return chunks
    
    def chunk_document(self, db: Session, document: Document) -> List[DocumentChunk]:
        """
        Chunk a single document and store the chunks in the database.
        
        Args:
            db: Database session
            document: Document to chunk
            
        Returns:
            List of created DocumentChunk objects
        """
        # Delete existing chunks for this document
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        
        # Create new chunks
        chunks = self.chunk_text(document.content)
        document_chunks = []
        
        for i, chunk_content in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=i,
                content=chunk_content,
                metadata_={
                    "chunk_size": len(chunk_content),
                    "total_chunks": len(chunks),
                    "document_title": document.title,
                    "document_type": document.document_type
                }
            )
            db.add(chunk)
            document_chunks.append(chunk)
        
        db.commit()
        logger.info(f"Created {len(document_chunks)} chunks for document {document.id}")
        return document_chunks
    
    def chunk_all_documents(self, db: Session, user_id: Optional[str] = None) -> int:
        """
        Chunk all documents for a user (or all users if user_id is None).
        
        Args:
            db: Database session
            user_id: Optional user ID to filter documents
            
        Returns:
            Number of documents processed
        """
        query = db.query(Document)
        if user_id:
            query = query.filter(Document.user_id == user_id)
        
        documents = query.all()
        processed = 0
        
        for document in documents:
            try:
                self.chunk_document(db, document)
                processed += 1
            except Exception as e:
                logger.error(f"Error chunking document {document.id}: {e}")
        
        logger.info(f"Processed {processed} documents")
        return processed
    
    def search_chunks(self, db: Session, query: str, user_id: str, limit: int = 10) -> List[DocumentChunk]:
        """
        Simple text search across chunks (can be enhanced with vector search later).
        
        Args:
            db: Database session
            query: Search query
            user_id: User ID to filter documents
            limit: Maximum number of chunks to return
            
        Returns:
            List of relevant DocumentChunk objects
        """
        # For now, use simple ILIKE search
        # This can be enhanced with vector embeddings later
        # Avoid selecting metadata column to prevent schema issues
        chunks = db.query(
            DocumentChunk.id,
            DocumentChunk.document_id, 
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            DocumentChunk.created_at
        ).join(Document).filter(
            Document.user_id == user_id,
            DocumentChunk.content.ilike(f"%{query}%")
        ).limit(limit).all()
        
        # Convert to DocumentChunk objects manually
        result_chunks = []
        for chunk_data in chunks:
            chunk = DocumentChunk()
            chunk.id = chunk_data.id
            chunk.document_id = chunk_data.document_id
            chunk.chunk_index = chunk_data.chunk_index
            chunk.content = chunk_data.content
            chunk.created_at = chunk_data.created_at
            result_chunks.append(chunk)
        
        return result_chunks 