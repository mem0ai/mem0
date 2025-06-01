#!/usr/bin/env python3

from app.database import SessionLocal
from app.models import Memory, User, MemoryState
from sqlalchemy import text
import uuid
import datetime

def investigate_contamination():
    db = SessionLocal()
    try:
        # Find your user record
        your_uuid = '773e2c10-1fd1-48cb-bc15-7674aaa9b09c'
        user = db.query(User).filter(User.user_id == your_uuid).first()
        print(f'🔍 Your user record: ID={user.id}, user_id={user.user_id}, email={user.email}')
        
        # Find ALL memories for your user_id
        all_memories = db.query(Memory).filter(
            Memory.user_id == user.id
        ).all()
        
        active_memories = [m for m in all_memories if m.state != MemoryState.deleted]
        
        print(f'\n📊 Memory Stats:')
        print(f'  - Total memories: {len(all_memories)}')
        print(f'  - Active memories: {len(active_memories)}')
        print(f'  - Deleted memories: {len(all_memories) - len(active_memories)}')
        
        # Define contamination patterns
        contamination_patterns = [
            'pickgroup', 'abstractentityid', 'centertest', 'pickgrouptest', 'centeridtest',
            'pick-planning-manager', 'rebin', 'shipmentdto', 'pickorder', 'junit',
            'equals/hashcode', 'tostring()', 'compilation errors', 'test failures',
            'pralayb', '/users/pralayb', 'faircopyfolder', 'fair copy folder',
            'workplace/pick', 'http client', 'pending-shipments'
        ]
        
        contaminated_memories = []
        for mem in active_memories:
            content_lower = mem.content.lower()
            if any(pattern in content_lower for pattern in contamination_patterns):
                contaminated_memories.append(mem)
                print(f'🚨 CONTAMINATED: [{mem.id}] {mem.content[:100]}...')
                print(f'    Created: {mem.created_at}')
                print(f'    App ID: {mem.app_id}')
                print(f'    Metadata: {mem.metadata_}')
                print()
        
        print(f'\n🔥 CONTAMINATION SUMMARY:')
        print(f'  - Contaminated memories found: {len(contaminated_memories)}')
        print(f'  - Clean memories: {len(active_memories) - len(contaminated_memories)}')
        
        if contaminated_memories:
            print(f'\n💥 CRITICAL: {len(contaminated_memories)} contaminated memories are ACTUALLY STORED in your database!')
            print('These need to be permanently deleted, not just filtered.')
            
            # Show when they were created
            creation_dates = [mem.created_at for mem in contaminated_memories]
            creation_dates.sort()
            print(f'\nContamination timeline:')
            print(f'  - First contaminated memory: {creation_dates[0]}')
            print(f'  - Latest contaminated memory: {creation_dates[-1]}')
            
            # Check if there's a pattern in app_ids
            app_ids = list(set([mem.app_id for mem in contaminated_memories]))
            print(f'\nContaminated memories came from app IDs: {app_ids}')
        
        return contaminated_memories
        
    finally:
        db.close()

def delete_contaminated_memories():
    """Actually delete the contaminated memories from the database"""
    db = SessionLocal()
    try:
        your_uuid = '773e2c10-1fd1-48cb-bc15-7674aaa9b09c'
        user = db.query(User).filter(User.user_id == your_uuid).first()
        
        contamination_patterns = [
            'pickgroup', 'abstractentityid', 'centertest', 'pickgrouptest', 'centeridtest',
            'pick-planning-manager', 'rebin', 'shipmentdto', 'pickorder', 'junit',
            'equals/hashcode', 'tostring()', 'compilation errors', 'test failures',
            'pralayb', '/users/pralayb', 'faircopyfolder', 'fair copy folder',
            'workplace/pick', 'http client', 'pending-shipments'
        ]
        
        memories_to_delete = []
        all_memories = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted
        ).all()
        
        for mem in all_memories:
            content_lower = mem.content.lower()
            if any(pattern in content_lower for pattern in contamination_patterns):
                memories_to_delete.append(mem)
        
        print(f'🗑️  About to PERMANENTLY DELETE {len(memories_to_delete)} contaminated memories...')
        
        for mem in memories_to_delete:
            print(f'Deleting: {mem.content[:60]}...')
            mem.state = MemoryState.deleted
            mem.deleted_at = datetime.datetime.now(datetime.UTC)
        
        db.commit()
        print(f'✅ Successfully deleted {len(memories_to_delete)} contaminated memories!')
        
        return len(memories_to_delete)
        
    except Exception as e:
        db.rollback()
        print(f'❌ Error deleting contaminated memories: {e}')
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    print("🔍 INVESTIGATING DATABASE CONTAMINATION...")
    print("="*50)
    
    contaminated = investigate_contamination()
    
    if contaminated:
        print("\n" + "="*50)
        print("🛠️  FIXING CONTAMINATION...")
        deleted_count = delete_contaminated_memories()
        print(f"\n🎉 CLEANUP COMPLETE: {deleted_count} contaminated memories removed!")
    else:
        print("\n✅ No contamination found!") 