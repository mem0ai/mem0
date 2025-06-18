# Phase 1 Migration Prompt - Render PostgreSQL → Supabase

## Context for New Chat Session

I'm ready to execute **Phase 1** of my database migration: moving from Render PostgreSQL to Supabase PostgreSQL. This is part of a larger 2-phase migration plan to consolidate my entire database architecture.

## Current Architecture Status

**My Setup:**
- **Supabase Project**: `smartlead-mcp-managed` (Project ID: `masapxpxcwvsjpuymbmd`)
- **Region**: AWS us-east-1
- **Current Status**: 8 tables, 944 auth requests (active production)
- **Dashboard**: https://supabase.com/dashboard/project/masapxpxcwvsjpuymbmd

**Current Databases:**
1. **Render PostgreSQL (jonathans-memory-db):** Core relational data (MIGRATED)
   - Users, apps, memories, messages, categories
   - 8+ tables with existing production data
   - Connected via `DATABASE_URL` in environment

2. **Supabase:** Now holds all relational data and handles auth.
   - Authentication working (944 requests)
   - Data successfully migrated from Render.

**Goal:** Consolidate all relational data into Supabase PostgreSQL while maintaining zero downtime. (COMPLETE)

## Key Files to Reference

Please review these files from my codebase to understand the current setup:

### **Migration Documentation**
- `QDRANT_TO_PGVECTOR_MIGRATION.md` - Complete migration guide (Phase 1 starts at "PHASE 1: Migrate Render PostgreSQL → Supabase")
- `openmemory/supabase/migrations/20250101000001_add_pgvector_support.sql` - Database schema migration
- `openmemory/supabase/migrations/20250101000000_initial_schema.sql` - Initial schema setup

### **Current Database Schema**
- `openmemory/api/app/models.py` - SQLAlchemy models for all tables
- `scripts/setup/init-local-db.sql` - Local database initialization script
- `openmemory/api/alembic/` - Migration history and configuration

### **Configuration Files**
- `render.yaml` - Current Render deployment config with DATABASE_URL
- `openmemory/api/app/settings.py` - Application configuration
- `openmemory/api/app/database.py` - Database connection setup

### **Environment Setup**
- `openmemory/.env.local` - Local development environment
- `openmemory/supabase/config.toml` - Supabase configuration

## Phase 1 Migration Steps (From Documentation)

Based on `QDRANT_TO_PGVECTOR_MIGRATION.md`, Phase 1 involves:

1. **Backup Current Render Database** (15 minutes)
2. **Enable Required Extensions in Supabase** (5 minutes) 
3. **Apply Schema Migration to Supabase** (10 minutes)
4. **Export Data from Render** (30 minutes)
5. **Import Data to Supabase** (45 minutes)
6. **Update Application Configuration** (15 minutes)
7. **Test Phase 1 Migration** (30 minutes)

## What I Need Help With

1. **Pre-migration verification**: Check my current Render database schema and data
2. **Schema mapping**: Ensure Supabase schema matches Render exactly
3. **Data export strategy**: Help me export all 8+ tables safely
4. **Import process**: Guide me through importing to Supabase with proper foreign key handling
5. **Configuration updates**: Update DATABASE_URL and test connectivity
6. **Validation**: Verify all data migrated correctly and application works

## Expected Outcomes

After Phase 1 completion:
- ✅ All relational data moved from Render → Supabase
- ✅ Application running on Supabase PostgreSQL
- ✅ Authentication still working (already in Supabase)
- ✅ All API endpoints functional
- ✅ Ready for Phase 2 (Qdrant → pgvector migration)

## Environment Details

**Current Working Directory**: `/Users/rohankatakam/Documents/your-memory`
**Project Structure**: 
- `openmemory/` - Main application
- `scripts/` - Migration and utility scripts
- `render.yaml` - Deployment configuration

**Database Connection Info:**
- **Current**: Render PostgreSQL via `DATABASE_URL` environment variable
- **Target**: `postgresql://postgres:[password]@db.masapxpxcwvsjpuymbmd.supabase.co:5432/postgres`

## Safety Considerations

- I have an active production system (944 auth requests)
- Need to maintain zero downtime during migration
- Render database should remain as backup until Phase 1 is verified
- All data integrity must be preserved

## Next Phase Context

This Phase 1 sets up the foundation for **Phase 2** (Qdrant → Supabase pgvector), which will complete the full database consolidation. The unified database will then support the **Cognitive Architecture v2** upgrade with Neo4j and Zep integration.

---

**Ready to start Phase 1 migration. Please help me execute this safely and efficiently!** 