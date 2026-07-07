#!/bin/bash
set -e

# Create the mem0_app database for user/auth/api-key data.
# The default 'postgres' database is used by pgvector for memory storage.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE mem0_app'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mem0_app')\gexec
EOSQL
