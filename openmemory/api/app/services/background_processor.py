import asyncio
import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.integrations.substack_service import SubstackService
from app.services.chunking_service import ChunkingService
from app.models import User, Document
from sqlalchemy import text
from datetime import datetime

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
                    
                    # Mark as processed
                    if doc.metadata_ is None:
                        doc.metadata_ = {}
                    doc.metadata_["needs_chunking"] = False
                    doc.metadata_["chunked_at"] = datetime.utcnow().isoformat()
                    doc.metadata_["chunks_created"] = len(chunks_created)
                    
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

# Global processor instance
background_processor = BackgroundProcessor() 