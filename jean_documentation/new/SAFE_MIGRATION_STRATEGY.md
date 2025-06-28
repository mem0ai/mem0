# 🛡️ SAFE MIGRATION STRATEGY
## From Unified-Memory-Local-Dev to Production

**Date Created**: December 2024  
**Status**: Phase 2 - pgvector Setup (In Progress)  
**Objective**: Safely migrate the unified memory system from the broken `feature/unified-memory-local-dev` branch to production through incremental, tested phases.

## 📊 **SCOPE OF CHANGES**
- **56 files changed** with ~6,000 lines of changes
- **Major Infrastructure Changes**:
  - Qdrant Cloud → pgvector migration
  - Neo4j Aura integration for graph memory
  - Unified memory ingestion pipeline
  - Enhanced search capabilities
  - MCP server updates

## 🎯 **MIGRATION PHASES**

### **Phase 1: Infrastructure Foundation (Week 1) - ✅ COMPLETE**
**Branch**: `feature/neo4j-setup-clean` (MERGED)  
**Objective**: Set up Neo4j infrastructure without affecting production

**Tasks**:
- [x] Create migration strategy document
- [x] Add Neo4j Aura configuration to settings.py
- [x] Add Neo4j connection utilities (neo4j_connection.py)
- [x] Add feature flags for Neo4j (disabled by default)
- [x] Create Phase 1 validation script (test_phase1_neo4j.py)
- [x] Test Neo4j connectivity independently (validation successful! ✅)
- [x] Merge to main when stable (MERGED & DEPLOYED! ✅)

**Success Criteria**: ✅ **ACHIEVED** - Neo4j accessible, no production impact

---

### **Phase 2: PGVector Setup (Week 2) - 🚧 IN PROGRESS**
**Branch**: `feature/pgvector-setup`  
**Objective**: Set up pgvector infrastructure alongside existing Qdrant

**Tasks**:
- [x] Add pgvector configuration to settings.py (reuses existing DATABASE_URL!)
- [x] Create pgvector connection utilities (pgvector_connection.py)
- [x] Add pgvector health monitoring to main.py
- [x] Create Phase 2 validation script (test_phase2_pgvector.py)
- [x] Update environment configuration (env.example)
- [x] Add pgvector dependency to requirements.txt
- [x] Smart configuration: No new environment variables needed in production
- [ ] Configure pgvector extension in Supabase (manual step)
- [ ] Test pgvector connectivity independently (run validation script)
- [ ] Create unified memory table schema
- [ ] Merge to main when stable

**Success Criteria**: pgvector accessible, parallel to Qdrant

---

### **Phase 3: Data Migration Tools (Week 3)**
**Branch**: `feature/data-migration-tools`  
**Objective**: Build safe data migration with rollback capability

**Tasks**:
- [ ] Copy migration scripts from unified-memory-local-dev
- [ ] Build Qdrant Cloud → backup export
- [ ] Build backup → pgvector import
- [ ] Add validation and rollback mechanisms
- [ ] Test with small user dataset

**Success Criteria**: Data can be safely migrated and rolled back

---

### **Phase 4: Unified Memory Backend (Week 4)**  
**Branch**: `feature/unified-memory-backend`  
**Objective**: Add new system alongside old system

**Tasks**:
- [ ] Add unified_memory.py (backend only)
- [ ] Add feature flag routing (disabled by default)
- [ ] Add new API endpoints with /v2/ prefix
- [ ] Keep all existing endpoints unchanged
- [ ] Test new endpoints independently

**Success Criteria**: New APIs work alongside old APIs

---

### **Phase 5: Bulk Data Migration (Week 5)**
**Objective**: Migrate existing data safely

**Tasks**:
- [ ] Export data from Qdrant Cloud (keep originals)
- [ ] Import to pgvector (test users first)
- [ ] Validate data integrity
- [ ] Import remaining users in batches

**Success Criteria**: All data migrated with validation

---

### **Phase 6: Search Pipeline Migration (Week 6)**
**Branch**: `feature/search-pipeline-v2`  
**Objective**: Enable new search for subset of users

**Tasks**:
- [ ] Enable unified memory for test users only
- [ ] Add search performance monitoring
- [ ] A/B test search results
- [ ] Keep old search as fallback

**Success Criteria**: Search performance equals or exceeds old system

---

### **Phase 7: UI Updates (Week 7)**
**Branch**: `feature/ui-unified-memory`  
**Objective**: Update frontend gradually

**Tasks**:
- [ ] Update UI components to support both APIs
- [ ] Add frontend feature flags
- [ ] Test with small user group
- [ ] Keep old UI as fallback

**Success Criteria**: UI works with both old and new backends

---

### **Phase 8: MCP Integration (Week 8)**
**Branch**: `feature/mcp-unified-memory`  
**Objective**: Update MCP server carefully (HIGH RISK)

**Tasks**:
- [ ] Update MCP server with feature flags
- [ ] Test MCP functionality extensively
- [ ] Deploy to staging first
- [ ] Enable for test users only initially

**Success Criteria**: MCP functions without timeouts or errors

---

### **Phase 9: Gradual Rollout (Weeks 9-12)**
**Objective**: Gradually migrate users to new system

**Timeline**:
- Week 9: 5% of users
- Week 10: 25% of users
- Week 11: 50% of users
- Week 12: 75% of users
- Week 13: 100% of users

**Success Criteria**: 100% migration, old system deprecated

## 🔧 **SAFETY MECHANISMS**

### **Feature Flags Strategy**
```python
# In settings.py
UNIFIED_MEMORY_ENABLED = os.getenv("UNIFIED_MEMORY_ENABLED", "false")
UNIFIED_MEMORY_USER_PERCENT = int(os.getenv("UNIFIED_MEMORY_USER_PERCENT", "0"))
UNIFIED_MEMORY_FALLBACK_ENABLED = os.getenv("UNIFIED_MEMORY_FALLBACK_ENABLED", "true")
```

### **User Routing Logic**
```python
def should_use_unified_memory(user_id: str) -> bool:
    if not UNIFIED_MEMORY_ENABLED:
        return False
    
    # Test users always use new system
    if user_id in TEST_USER_IDS:
        return True
    
    # Gradual rollout based on user hash
    user_hash = hash(user_id) % 100
    return user_hash < UNIFIED_MEMORY_USER_PERCENT
```

### **Rollback Plan**
1. **Database rollback**: Keep Qdrant Cloud active until 100% migration
2. **Code rollback**: Feature flags allow instant disabling
3. **Data rollback**: Keep backups of all original data
4. **Emergency rollback**: Instant switch back to old system

## ⚠️ **HIGH-RISK COMPONENTS**
1. **MCP Server** - Broke in previous attempt
2. **Data Migration** - Risk of data loss
3. **Search Pipeline** - Core functionality
4. **User Authentication** - Session management changes

## 📋 **FILES TO MIGRATE FROM UNIFIED-MEMORY-LOCAL-DEV**

### **Phase 1 - Neo4j Files** ✅:
- Neo4j configuration in `openmemory/api/app/settings.py` (3 variables only)
- Neo4j connection utilities in `openmemory/api/app/utils/neo4j_connection.py` 
- Neo4j validation script `test_phase1_neo4j.py`
- Neo4j syntax fix already in `mem0/memory/graph_memory.py` (was already merged)

### **Phase 2 - PGVector Files**:
- PGVector configuration (to be added to settings.py in Phase 2)
- Docker compose setup for pgvector
- Supabase pgvector configuration

### **Phase 3 - Migration Scripts**:
- All files from `scripts/local-dev/unified-memory/`
- Migration utilities from `scripts/`

## 🎯 **CURRENT STATUS**
- **Active Branch**: `main`
- **Next Step**: Create `feature/neo4j-setup` branch
- **Previous Work**: Stashed in `feature/unified-memory-local-dev`

## 📝 **NOTES**
- Keep unified-memory-local-dev branch as reference
- All changes must be backwards compatible
- Test thoroughly before each merge
- Monitor production metrics at each phase 