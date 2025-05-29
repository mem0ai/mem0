import asyncio
import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.integrations.substack_service import SubstackService
from app.services.chunking_service import ChunkingService
from app.models import User, Document, DocumentChunk, Memory, MemoryState
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
            # Find documents that need chunking AND have active memories
            documents = db.query(Document).filter(
                Document.metadata_['needs_chunking'].astext == 'true'
            ).filter(
                # Only process documents that have at least one active memory
                Document.id.in_(
                    db.query(Document.id).join(
                        Memory,
                        text("memories.metadata->>'document_id' = CAST(documents.id AS TEXT)")
                    ).filter(
                        Memory.state == MemoryState.active
                    )
                )
            ).limit(10).all()  # Process 10 at a time with 2GB (was 5)
            
            if not documents:
                # Also clean up orphaned documents (no active memories)
                await self.cleanup_orphaned_documents(db)
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
                    await asyncio.sleep(0.3)  # Reduced delay with more memory available
                    
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

    async def cleanup_orphaned_documents(self, db: Session):
        """Clean up documents that have no active memories"""
        try:
            # Find documents that need chunking but have no active memories
            orphaned_docs = db.query(Document).filter(
                Document.metadata_['needs_chunking'].astext == 'true'
            ).filter(
                ~Document.id.in_(
                    db.query(Document.id).join(
                        Memory,
                        text("memories.metadata->>'document_id' = CAST(documents.id AS TEXT)")
                    ).filter(
                        Memory.state == MemoryState.active
                    )
                )
            ).all()
            
            if orphaned_docs:
                cleared = 0
                for doc in orphaned_docs:
                    # Clear the chunking flag for orphaned documents
                    updated_metadata = dict(doc.metadata_) if doc.metadata_ else {}
                    updated_metadata["needs_chunking"] = False
                    updated_metadata["orphaned_cleanup"] = datetime.utcnow().isoformat()
                    updated_metadata["reason"] = "No active memories"
                    
                    doc.metadata_ = updated_metadata
                    flag_modified(doc, 'metadata_')
                    cleared += 1
                
                db.commit()
                logger.info(f"Cleared chunking flag for {cleared} orphaned documents (no active memories)")
                
        except Exception as e:
            logger.error(f"Error in cleanup_orphaned_documents: {e}")
            db.rollback()

    async def clear_stuck_documents(self):
        """One-time fix to clear documents that are stuck in chunking loop"""
        db = SessionLocal()
        try:
            # Find documents that might be stuck AND have active memories
            stuck_docs = db.query(Document).filter(
                Document.metadata_['needs_chunking'].astext == 'true'
            ).filter(
                # Only process documents that have at least one active memory
                Document.id.in_(
                    db.query(Document.id).join(
                        Memory,
                        text("memories.metadata->>'document_id' = CAST(documents.id AS TEXT)")
                    ).filter(
                        Memory.state == MemoryState.active
                    )
                )
            ).all()
            
            cleared = 0
            for doc in stuck_docs:
                # Check if this document already has chunks
                existing_chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
                
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
            
            # Also run orphaned cleanup at startup
            await self.cleanup_orphaned_documents(db)
            
        except Exception as e:
            logger.error(f"Error clearing stuck documents: {e}")
            db.rollback()
        finally:
            db.close()

# Global processor instance
background_processor = BackgroundProcessor() 