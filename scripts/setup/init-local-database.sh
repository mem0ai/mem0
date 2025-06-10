#!/bin/bash
# Initialize the local PostgreSQL database for Jean Memory

echo "🗄️ Initializing local database..."

# Wait for PostgreSQL to be ready
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if docker exec jeanmemory_postgres_service pg_isready -U jean_memory -d jean_memory_db > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    echo "Waiting for PostgreSQL... ($((retry_count + 1))/$max_retries)"
    sleep 2
    retry_count=$((retry_count + 1))
done

if [ $retry_count -eq $max_retries ]; then
    echo "❌ PostgreSQL did not become ready in time"
    exit 1
fi

# Run the initialization SQL
echo "Running database initialization..."
docker exec -i jeanmemory_postgres_service psql -U jean_memory -d jean_memory_db < init-local-db.sql

if [ $? -eq 0 ]; then
    echo "✅ Database initialized successfully!"
else
    echo "❌ Database initialization failed"
    exit 1
fi
