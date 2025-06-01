from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.memory import get_memory_client
from app.models import Memory, User, MemoryState
import datetime
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

# Admin security key - you should set this in your environment
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION")

def verify_admin_access(x_admin_key: str = Header(None)):
    """Verify admin access with secret key"""
    if x_admin_key != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Admin access required")
    return True

@router.post("/cleanup-contaminated-memories")
async def cleanup_contaminated_memories_admin(
    user_uuid: str,
    admin_verified: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """
    ADMIN ONLY: Clean up contaminated memories from both SQL and vector store.
    This endpoint connects to the production vector store.
    """
    
    logger.info(f"🚨 ADMIN CLEANUP INITIATED for user: {user_uuid}")
    
    try:
        # Get memory client (will use production configuration)
        memory_client = get_memory_client()
        
        # Get user from database
        user = db.query(User).filter(User.user_id == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        cleanup_report = {
            "user_id": user_uuid,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "sql_cleaned": 0,
            "vector_cleaned": 0,
            "total_cleaned": 0,
            "errors": []
        }
        
        # Define contamination patterns
        contamination_patterns = [
            'pickgroup', 'abstractentityid', 'centertest', 'pickgrouptest', 'centeridtest',
            'pick-planning-manager', 'rebin', 'shipmentdto', 'pickorder', 'junit',
            'equals/hashcode', 'tostring()', 'compilation errors', 'test failures',
            'pralayb', '/users/pralayb', 'faircopyfolder', 'fair copy folder',
            'workplace/pick', 'http client', 'pending-shipments',
            'test files referencing non-existent', 'correct version of', 'from fair copy'
        ]
        
        # 1. Clean SQL Database
        logger.info("🗑️  Cleaning SQL database...")
        sql_memories = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted
        ).all()
        
        sql_cleanup_count = 0
        for mem in sql_memories:
            content_lower = mem.content.lower()
            if any(pattern in content_lower for pattern in contamination_patterns):
                logger.info(f"Deleting SQL memory: {mem.content[:60]}...")
                mem.state = MemoryState.deleted
                mem.deleted_at = datetime.datetime.now(datetime.UTC)
                sql_cleanup_count += 1
        
        if sql_cleanup_count > 0:
            db.commit()
            cleanup_report["sql_cleaned"] = sql_cleanup_count
            logger.info(f"✅ SQL cleanup: {sql_cleanup_count} memories deleted")
        
        # 2. Clean Vector Store
        logger.info("🗑️  Cleaning vector store...")
        try:
            # Get all memories from vector store
            all_memories = memory_client.get_all(user_id=user_uuid, limit=1000)
            memories_list = []
            if isinstance(all_memories, dict) and 'results' in all_memories:
                memories_list = all_memories['results']
            elif isinstance(all_memories, list):
                memories_list = all_memories
            
            vector_cleanup_count = 0
            for mem in memories_list:
                content = mem.get('memory', mem.get('content', ''))
                content_lower = content.lower()
                
                if any(pattern in content_lower for pattern in contamination_patterns):
                    mem_id = mem.get('id')
                    if mem_id:
                        try:
                            logger.info(f"Deleting vector memory: {content[:60]}...")
                            memory_client.delete(memory_id=mem_id)
                            vector_cleanup_count += 1
                        except Exception as e:
                            error_msg = f"Failed to delete vector memory {mem_id}: {e}"
                            logger.error(error_msg)
                            cleanup_report["errors"].append(error_msg)
            
            cleanup_report["vector_cleaned"] = vector_cleanup_count
            logger.info(f"✅ Vector cleanup: {vector_cleanup_count} memories deleted")
            
        except Exception as e:
            error_msg = f"Vector store cleanup failed: {e}"
            logger.error(error_msg)
            cleanup_report["errors"].append(error_msg)
        
        # 3. Calculate totals
        cleanup_report["total_cleaned"] = cleanup_report["sql_cleaned"] + cleanup_report["vector_cleaned"]
        
        logger.info(f"🎉 CLEANUP COMPLETE: {cleanup_report['total_cleaned']} total memories removed")
        
        return {
            "status": "success",
            "message": f"Cleanup completed: {cleanup_report['total_cleaned']} contaminated memories removed",
            "details": cleanup_report
        }
        
    except Exception as e:
        logger.error(f"❌ Admin cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get("/audit-user-memories")
async def audit_user_memories(
    user_uuid: str,
    admin_verified: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """
    ADMIN ONLY: Audit a user's memories for contamination.
    """
    
    logger.info(f"🔍 ADMIN AUDIT INITIATED for user: {user_uuid}")
    
    try:
        memory_client = get_memory_client()
        user = db.query(User).filter(User.user_id == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        audit_report = {
            "user_id": user_uuid,
            "user_email": user.email,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "sql_total": 0,
            "sql_contaminated": 0,
            "vector_total": 0,
            "vector_contaminated": 0,
            "contaminated_samples": []
        }
        
        contamination_patterns = [
            'pickgroup', 'abstractentityid', 'centertest', 'junit',
            'pralayb', 'faircopyfolder', 'pick-planning'
        ]
        
        # Check SQL
        sql_memories = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted
        ).all()
        
        audit_report["sql_total"] = len(sql_memories)
        
        for mem in sql_memories:
            content_lower = mem.content.lower()
            if any(pattern in content_lower for pattern in contamination_patterns):
                audit_report["sql_contaminated"] += 1
                if len(audit_report["contaminated_samples"]) < 5:
                    audit_report["contaminated_samples"].append({
                        "source": "sql",
                        "content": mem.content[:100] + "..." if len(mem.content) > 100 else mem.content
                    })
        
        # Check Vector Store
        try:
            all_memories = memory_client.get_all(user_id=user_uuid, limit=200)
            memories_list = []
            if isinstance(all_memories, dict) and 'results' in all_memories:
                memories_list = all_memories['results']
            elif isinstance(all_memories, list):
                memories_list = all_memories
            
            audit_report["vector_total"] = len(memories_list)
            
            for mem in memories_list:
                content = mem.get('memory', mem.get('content', ''))
                content_lower = content.lower()
                if any(pattern in content_lower for pattern in contamination_patterns):
                    audit_report["vector_contaminated"] += 1
                    if len(audit_report["contaminated_samples"]) < 10:
                        audit_report["contaminated_samples"].append({
                            "source": "vector",
                            "content": content[:100] + "..." if len(content) > 100 else content
                        })
        
        except Exception as e:
            audit_report["vector_error"] = str(e)
        
        return {
            "status": "success",
            "audit": audit_report
        }
        
    except Exception as e:
        logger.error(f"❌ Admin audit failed: {e}")
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}") 