#!/bin/bash
set -e

echo "🔧 Initializing database..."

# Function to check if alembic_version table exists
check_alembic_version() {
    python3 -c "
import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv('DATABASE_URL', 'sqlite:///./openmemory.db')
engine = create_engine(db_url)
inspector = inspect(engine)
tables = inspector.get_table_names()

if 'alembic_version' in tables:
    print('EXISTS')
else:
    print('MISSING')
" 2>/dev/null || echo "ERROR"
}

# Function to check if core tables exist (from initial migration)
check_core_tables() {
    python3 -c "
import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv('DATABASE_URL', 'sqlite:///./openmemory.db')
engine = create_engine(db_url)
inspector = inspect(engine)
tables = inspector.get_table_names()

# Check if at least one core table from initial migration exists
core_tables = ['users', 'apps', 'memories']
existing = [t for t in core_tables if t in tables]

if len(existing) > 0:
    print('EXISTS')
else:
    print('MISSING')
" 2>/dev/null || echo "ERROR"
}

# Check database state
ALEMBIC_STATUS=$(check_alembic_version)
TABLES_STATUS=$(check_core_tables)

echo "📊 Database state: alembic_version=$ALEMBIC_STATUS, core_tables=$TABLES_STATUS"

# Handle different scenarios
if [ "$TABLES_STATUS" = "MISSING" ]; then
    # Fresh database - run migrations normally
    echo "✨ Fresh database detected. Running all migrations..."
    alembic upgrade head
elif [ "$ALEMBIC_STATUS" = "MISSING" ]; then
    # Tables exist but alembic_version doesn't - stamp to head
    echo "🔖 Existing tables found without Alembic tracking. Stamping to head..."
    alembic stamp head
    echo "✅ Database marked as up-to-date"
elif [ "$ALEMBIC_STATUS" = "EXISTS" ]; then
    # Normal case - just upgrade to head
    echo "🔄 Applying any pending migrations..."
    alembic upgrade head
else
    # Error case - try to recover
    echo "⚠️  Error checking database state. Attempting to upgrade..."
    alembic upgrade head || {
        echo "🔧 Migration failed. Attempting to stamp and retry..."
        alembic stamp head
        alembic upgrade head
    }
fi

echo "✅ Database initialization complete!"
