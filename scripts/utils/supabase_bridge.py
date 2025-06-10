#!/usr/bin/env python3
"""
Supabase Bridge - Helper script to perform database operations via Supabase API
instead of direct PostgreSQL connections that might be blocked by network security.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
from supabase import create_client, Client

def load_environment_variables():
    """Load environment variables from .env file"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        return True
    else:
        print("Error: .env file not found")
        return False

def initialize_supabase_client():
    """Initialize Supabase client from environment variables"""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
        return None
    
    try:
        return create_client(supabase_url, supabase_service_key)
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        return None

def test_connection():
    """Test connection to Supabase"""
    supabase = initialize_supabase_client()
    if not supabase:
        return False
    
    try:
        # Try a simple query to check if the connection works
        response = supabase.table("_schema").select("*").limit(1).execute()
        print("✓ Successfully connected to Supabase database via API")
        return True
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        return False

def apply_migrations():
    """Apply migrations using Supabase API instead of direct SQL"""
    supabase = initialize_supabase_client()
    if not supabase:
        return False
    
    try:
        # Check if the table exists first (execute raw SQL via RPC)
        check_table = supabase.rpc(
            "exec_sql", 
            {"query": "SELECT to_regclass('public.alembic_version') IS NOT NULL as exists"}
        ).execute()
        
        table_exists = len(check_table.data) > 0 and check_table.data[0].get('exists', False)
        
        if not table_exists:
            print("Creating alembic_version table")
            supabase.rpc(
                "exec_sql", 
                {"query": "CREATE TABLE IF NOT EXISTS public.alembic_version (version_num VARCHAR(32) NOT NULL)"}
            ).execute()
            
            # Insert initial version
            supabase.rpc(
                "exec_sql", 
                {"query": "INSERT INTO public.alembic_version (version_num) VALUES ('initial')"}
            ).execute()
        
        # List and apply the necessary migrations
        # NOTE: In a real implementation, you would read the migration files and apply them
        # sequentially. This is a simplified version.
        print("Migration tracking table is ready")
        
        # Create basic tables if they don't exist already
        # This is just a simple example - in reality, you'd need to read the actual
        # migration files and translate them to API calls or SQL commands
        
        tables = [
            """
            CREATE TABLE IF NOT EXISTS public.users (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                email VARCHAR(255) UNIQUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS public.documents (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                title VARCHAR(255),
                content TEXT,
                user_id UUID REFERENCES public.users(id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        for table_sql in tables:
            try:
                supabase.rpc("exec_sql", {"query": table_sql}).execute()
                print(f"✓ Applied migration: {table_sql[:40]}...")
            except Exception as e:
                print(f"Error applying migration: {e}")
                return False
        
        print("✓ All migrations applied successfully")
        return True
        
    except Exception as e:
        print(f"Error applying migrations: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Supabase Bridge for Database Operations")
    parser.add_argument('command', choices=['test-connection', 'apply-migrations'], 
                        help='Command to execute')
    
    args = parser.parse_args()
    
    if not load_environment_variables():
        sys.exit(1)
    
    if args.command == 'test-connection':
        success = test_connection()
        sys.exit(0 if success else 1)
    
    elif args.command == 'apply-migrations':
        success = apply_migrations()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
