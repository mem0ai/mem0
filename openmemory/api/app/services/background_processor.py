import asyncio
import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.integrations.substack_service import SubstackService
from app.services.chunking_service import ChunkingService
from app.models import User, Document, Chunk
from sqlalchemy import text
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

class BackgroundProcessor:
    """Service to handle background processing tasks that don't need to be visible to users"""
    
    def __init__(self):
        self.is_running = False
        self.process_interval = 30  # Process every 30 seconds
    
    async def start(self):
        """Start the background processor"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Background processor started")
        
        # One-time fix for stuck documents
        await self.clear_stuck_documents()
        
        while self.is_running:
            try:
                await self.process_pending_documents()
                await asyncio.sleep(self.process_interval)
            except Exception as e:
                logger.error(f"Error in background processor: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def stop(self):
        """Stop the background processor"""
        self.is_running = False
        logger.info("Background processor stopped")
    
    async def process_pending_documents(self):
        """Process documents that need chunking"""
        db = SessionLocal()
        try:
            # Find documents that need chunking (limit to prevent memory issues)
            # Use consistent boolean check for needs_chunking
            documents = db.query(Document).filter(
                Document.metadata_['needs_chunking'].astext == 'true'
            ).limit(5).all()  # Process 5 at a time
            
            if not documents:
                return
            
            logger.info(f"Processing {len(documents)} documents for chunking")
            
            chunking_service = ChunkingService()
            processed = 0
            
            for doc in documents:
                try:
                    # Process chunks for this document
                    chunks_created = chunking_service.chunk_document(db, doc)
                    
                    # Mark as processed - ensure metadata exists and update correctly
                    if doc.metadata_ is None:
                        doc.metadata_ = {}
                    
                    # Create new metadata dict to ensure proper update
                    updated_metadata = dict(doc.metadata_) if doc.metadata_ else {}
                    updated_metadata["needs_chunking"] = False
                    updated_metadata["chunked_at"] = datetime.utcnow().isoformat()
                    updated_metadata["chunks_created"] = len(chunks_created)
                    
                    # Assign the updated metadata
                    doc.metadata_ = updated_metadata
                    
                    # Force SQLAlchemy to recognize the change
                    flag_modified(doc, 'metadata_')
                    
                    db.commit()
                    processed += 1
                    
                    logger.info(f"Background chunking completed for: {doc.title} ({len(chunks_created)} chunks)")
                    
                    # Small delay to prevent memory buildup
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error chunking document {doc.id}: {e}")
                    db.rollback()
                    continue
            
            if processed > 0:
                logger.info(f"Background processor completed {processed} documents")
        
        except Exception as e:
            logger.error(f"Error in process_pending_documents: {e}")
        finally:
            db.close()

    async def clear_stuck_documents(self):
        """One-time fix to clear documents that are stuck in chunking loop"""
        db = SessionLocal()
        try:
            # Find documents that might be stuck (have chunks but still marked for chunking)
            stuck_docs = db.query(Document).filter(
                Document.metadata_['needs_chunking'].astext == 'true'
            ).all()
            
            cleared = 0
            for doc in stuck_docs:
                # Check if this document already has chunks
                existing_chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).count()
                
                if existing_chunks > 0:
                    # Document already has chunks, clear the flag
                    updated_metadata = dict(doc.metadata_) if doc.metadata_ else {}
                    updated_metadata["needs_chunking"] = False
                    updated_metadata["chunks_cleared_at"] = datetime.utcnow().isoformat()
                    updated_metadata["existing_chunks"] = existing_chunks
                    
                    doc.metadata_ = updated_metadata
                    flag_modified(doc, 'metadata_')
                    cleared += 1
            
            if cleared > 0:
                db.commit()
                logger.info(f"Cleared stuck chunking flag for {cleared} documents that already have chunks")
            
        except Exception as e:
            logger.error(f"Error clearing stuck documents: {e}")
            db.rollback()
        finally:
            db.close()

# Global processor instance
background_processor = BackgroundProcessor() 