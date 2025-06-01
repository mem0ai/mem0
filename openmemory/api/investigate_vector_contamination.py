#!/usr/bin/env python3

from app.utils.memory import get_memory_client
import json

def investigate_vector_contamination():
    print("🔍 INVESTIGATING VECTOR STORE CONTAMINATION...")
    print("="*50)
    
    your_uuid = '773e2c10-1fd1-48cb-bc15-7674aaa9b09c'
    
    try:
        # Get memory client
        memory_client = get_memory_client()
        
        # Get ALL memories from vector store for your user
        print(f"🔍 Fetching all memories for user: {your_uuid}")
        all_memories = memory_client.get_all(user_id=your_uuid, limit=1000)
        
        # Handle different response formats
        memories_list = []
        if isinstance(all_memories, dict) and 'results' in all_memories:
            memories_list = all_memories['results']
        elif isinstance(all_memories, list):
            memories_list = all_memories
        else:
            memories_list = []
        
        print(f"📊 Found {len(memories_list)} memories in vector store")
        
        # Define contamination patterns
        contamination_patterns = [
            'pickgroup', 'abstractentityid', 'centertest', 'pickgrouptest', 'centeridtest',
            'pick-planning-manager', 'rebin', 'shipmentdto', 'pickorder', 'junit',
            'equals/hashcode', 'tostring()', 'compilation errors', 'test failures',
            'pralayb', '/users/pralayb', 'faircopyfolder', 'fair copy folder',
            'workplace/pick', 'http client', 'pending-shipments'
        ]
        
        contaminated_memories = []
        clean_memories = []
        
        for i, mem in enumerate(memories_list):
            content = mem.get('memory', mem.get('content', ''))
            content_lower = content.lower()
            
            if any(pattern in content_lower for pattern in contamination_patterns):
                contaminated_memories.append(mem)
                print(f'🚨 CONTAMINATED [{i+1}]: {content[:80]}...')
                print(f'    ID: {mem.get("id")}')
                print(f'    Created: {mem.get("created_at")}')
                print(f'    Metadata: {mem.get("metadata", {})}')
                print()
            else:
                clean_memories.append(mem)
        
        print(f'\n🔥 VECTOR STORE CONTAMINATION SUMMARY:')
        print(f'  - Total memories in vector store: {len(memories_list)}')
        print(f'  - Contaminated memories: {len(contaminated_memories)}')
        print(f'  - Clean memories: {len(clean_memories)}')
        
        if contaminated_memories:
            print(f'\n💥 CRITICAL: {len(contaminated_memories)} contaminated memories found in VECTOR STORE!')
            print('These are the memories showing up in your dashboard!')
            
            # Show metadata patterns
            metadata_patterns = {}
            for mem in contaminated_memories:
                metadata = mem.get('metadata', {})
                for key, value in metadata.items():
                    if key not in metadata_patterns:
                        metadata_patterns[key] = set()
                    metadata_patterns[key].add(str(value))
            
            print(f'\nMetadata patterns in contaminated memories:')
            for key, values in metadata_patterns.items():
                print(f'  {key}: {list(values)[:5]}...' if len(values) > 5 else f'  {key}: {list(values)}')
        
        return contaminated_memories
        
    except Exception as e:
        print(f'❌ Error investigating vector store: {e}')
        return []

def delete_contaminated_vector_memories():
    """Delete contaminated memories from vector store"""
    print("🗑️  DELETING CONTAMINATED MEMORIES FROM VECTOR STORE...")
    print("="*50)
    
    your_uuid = '773e2c10-1fd1-48cb-bc15-7674aaa9b09c'
    
    try:
        memory_client = get_memory_client()
        
        # Get all memories
        all_memories = memory_client.get_all(user_id=your_uuid, limit=1000)
        memories_list = []
        if isinstance(all_memories, dict) and 'results' in all_memories:
            memories_list = all_memories['results']
        elif isinstance(all_memories, list):
            memories_list = all_memories
        
        contamination_patterns = [
            'pickgroup', 'abstractentityid', 'centertest', 'pickgrouptest', 'centeridtest',
            'pick-planning-manager', 'rebin', 'shipmentdto', 'pickorder', 'junit',
            'equals/hashcode', 'tostring()', 'compilation errors', 'test failures',
            'pralayb', '/users/pralayb', 'faircopyfolder', 'fair copy folder',
            'workplace/pick', 'http client', 'pending-shipments'
        ]
        
        deleted_count = 0
        for mem in memories_list:
            content = mem.get('memory', mem.get('content', ''))
            content_lower = content.lower()
            
            if any(pattern in content_lower for pattern in contamination_patterns):
                mem_id = mem.get('id')
                if mem_id:
                    try:
                        print(f'🗑️  Deleting: {content[:60]}...')
                        memory_client.delete(memory_id=mem_id)
                        deleted_count += 1
                    except Exception as e:
                        print(f'❌ Failed to delete memory {mem_id}: {e}')
        
        print(f'\n✅ Successfully deleted {deleted_count} contaminated memories from vector store!')
        return deleted_count
        
    except Exception as e:
        print(f'❌ Error deleting from vector store: {e}')
        return 0

if __name__ == "__main__":
    contaminated = investigate_vector_contamination()
    
    if contaminated:
        print("\n" + "="*50)
        print("🛠️  CLEANING VECTOR STORE...")
        deleted_count = delete_contaminated_vector_memories()
        print(f"\n🎉 VECTOR STORE CLEANUP COMPLETE: {deleted_count} contaminated memories removed!")
        print("\n🔄 Please refresh your dashboard to see the changes.")
    else:
        print("\n✅ No contamination found in vector store!") 