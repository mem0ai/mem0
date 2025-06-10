# Scripts Directory

This directory contains all development and utility scripts for Jean Memory, organized by purpose.

## Directory Structure

### `setup/`
Scripts for initial project setup and configuration:
- `setup-local-complete.sh` - Complete local setup without Docker
- `setup-local-dev.sh` - Local development environment setup
- `setup-hybrid.sh` - Hybrid setup (Docker backend + local UI)
- `fix-local-setup.sh` - Fix common local setup issues
- `init-local-database.sh` - Initialize local database
- `init-local-db.sql` - SQL for local database initialization
- `init-local-db-simple.sql` - Simplified database initialization

### `local-dev/`
Scripts for local development workflow:
- `local-dev-ui.sh` - Run UI locally while connecting to Docker backend
- `restart-ui-local.sh` - Restart local UI development server
- `monitor-ui.sh` - Monitor UI development server
- `ui-dev-tools.sh` - UI development utilities
- `restart-ui.sh` - General UI restart script
- `quick-start-local.sh` - Quick start for local development
- `start-all.sh` - Start all services
- `start-api.sh` - Start API service
- `start-api-local.sh` - Start API locally
- `start-ui.sh` - Start UI service

### `utils/`
Utility scripts for maintenance and testing:
- `cleanup-bloat.sh` - Clean up unnecessary files
- `reset-environment.sh` - Reset development environment
- `fix_qdrant_collection.py` - Fix Qdrant collection issues
- `run_migrations.py` - Run database migrations
- `supabase_bridge.py` - Supabase integration utilities
- `test-complete-local-setup.py` - Test complete local setup
- `test-local-auth.py` - Test local authentication
- Various test scripts for different components

## Usage

Most scripts should be run from the project root directory. The main Makefile provides convenient commands that call these scripts:

```bash
# Recommended local development workflow
make backend        # Start backend services in Docker
make ui-local       # Run UI locally for faster development

# Other useful commands
make status         # Check status of all services
make restart-backend    # Restart backend services
make restart-ui-local   # Restart local UI
```

## Configuration Files

- `docker-compose.yml` - Docker Compose configuration for local development
- `.env.template` - Template for environment variables

## Notes

- Scripts in `local-dev/` are designed to work together for the hybrid development model
- Scripts in `setup/` are typically run once during initial project setup
- Scripts in `utils/` are for maintenance and troubleshooting
- All scripts include proper error handling and colored output for better user experience 