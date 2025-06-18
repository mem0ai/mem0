# Database Migration Checklist: Render to Supabase

This document outlines all the necessary changes to migrate your application from the old Render PostgreSQL database (`jonathans-memory-db`) to your new Supabase database.

## Phase 1: Production Environment Update (High Priority)

This is the most critical step to switch your live application to Supabase.

### 1. Update Render API Service Configuration

The production API service (`jean-memory-api`) is configured to use the old database. This needs to be changed to point to Supabase.

**File:** `render.yaml`
**Location:** Line 21-24

**Action Required:**
Modify the `envVars` for the `jean-memory-api` service. Replace the `fromDatabase` block with a direct `value` key pointing to your new Supabase connection string.

**Current Configuration:**
```yaml
      - key: DATABASE_URL
        fromDatabase:
          name: jonathans-memory-db
          property: connectionString
```

**New Configuration (to be applied):**
```yaml
      - key: DATABASE_URL
        value: "postgres://postgres:jeandbtype123@db.masapxpxcwvsjpuymbmd.supabase.co:6543/postgres?pool_mode=transaction"
```

### 2. Decommission Old Render Database

After you have successfully updated the `jean-memory-api` service and verified that it is running correctly with the new Supabase database, you can decommission the old `jonathans-memory-db`.

**File:** `render.yaml`
**Location:** Line 98-105

**Action Required:**
Delete the entire `databases` block from your `render.yaml` file.

**Current Configuration (to be removed):**
```yaml
databases:
  - name: jonathans-memory-db
    databaseName: openmemory
    user: openmemory
    region: oregon
    plan: basic-256mb # Basic tier - 256MB RAM, 1GB storage
    ipAllowList: [] # Allow connections from Render services
```

---

## Phase 2: Local and Development Environments

These files may contain references to the old database for non-production setups.

### 1. Manual `.env` File Verification

The following `.env` files were found in the codebase. You must **manually inspect** each of these files. If you find a `DATABASE_URL` pointing to the old Render database, you should update it to point to your new Supabase database for development or testing purposes.

- `/Users/rohankatakam/Documents/your-memory/embedchain/examples/api_server/variables.env`
- `/Users/rohankatakam/Documents/your-memory/embedchain/examples/discord_bot/variables.env`

As we discovered, your primary `openmemory/.env.local` is configured for local Docker development and should **not** be changed as part of this production migration.

---

## Phase 3: Documentation Update (Low Priority)

These files reference the old database name. They do not affect application behavior but should be updated for future consistency.

- `STATUS.md`
- `PHASE_1_MIGRATION_PROMPT.md`

**Action Required:**
Search for `jonathans-memory-db` in these files and replace it with a reference to the new Supabase database. 