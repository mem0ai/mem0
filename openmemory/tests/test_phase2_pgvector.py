#!/usr/bin/env python3
"""
Phase 2 pgvector Setup Validation Script

This script validates that the pgvector infrastructure is properly set up
for the unified memory migration. Run this before proceeding to Phase 3.

Usage:
    python test_phase2_pgvector.py
"""

import os
import sys
from pathlib import Path

# Add the project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'openmemory' / 'api'))

def main():
    print("🚧 Phase 2 pgvector Setup Validation")
    print("=" * 50)
    
    # Test 1: Import test
    print("\n1. Testing imports...")
    try:
        from app.settings import config
        from app.utils.pgvector_connection import validate_pgvector_for_phase2, get_pgvector_status, install_pgvector_extension
        print("   ✅ All imports successful")
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False
    
    # Test 2: Configuration check
    print("\n2. Checking configuration...")
    print(f"   Environment: {config.ENVIRONMENT}")
    print(f"   pgvector Host: {config.PGVECTOR_HOST}")
    print(f"   pgvector Port: {config.PGVECTOR_PORT}")
    print(f"   pgvector Database: {config.PGVECTOR_DATABASE}")
    print(f"   pgvector User: {config.PGVECTOR_USER}")
    print(f"   Connection Type: {getattr(config, 'PGVECTOR_CONNECTION_TYPE', 'unknown')}")
    
    if config.IS_PRODUCTION:
        print(f"   pgvector Password: {'CONFIGURED' if config.PGVECTOR_PASSWORD else 'NOT SET'}")
        print(f"   Production Mode: Reusing existing DATABASE_URL credentials")
        print(f"   Connection String: postgresql://{config.PGVECTOR_USER}:***@{config.PGVECTOR_HOST}:{config.PGVECTOR_PORT}/{config.PGVECTOR_DATABASE}")
        
        # Show environment variable analysis
        print(f"\n   📊 Environment Variable Analysis:")
        print(f"   ✅ DATABASE_URL: {'FOUND' if config.DATABASE_URL else 'NOT FOUND'}")
        print(f"   ✅ SUPABASE_URL: {'FOUND' if hasattr(config, 'SUPABASE_URL') and config.SUPABASE_URL else 'NOT FOUND'}")
        print(f"   ⚙️  PGVECTOR_USE_DIRECT_CONNECTION: {os.getenv('PGVECTOR_USE_DIRECT_CONNECTION', 'true')}")
        print(f"   🔧 Additional PGVECTOR_* vars needed: NO (reusing existing)")
    else:
        print(f"   pgvector Password: {'SET' if config.PGVECTOR_PASSWORD and config.PGVECTOR_PASSWORD != 'memory_password' else 'DEFAULT/NOT SET'}")
        print(f"   Local Mode: Using local PostgreSQL")
    
    print(f"   Table Prefix: {config.PGVECTOR_TABLE_PREFIX}")
    
    # Test 3: pgvector connection validation
    print("\n3. Validating pgvector connection...")
    is_valid, message = validate_pgvector_for_phase2()
    print(f"   {message}")
    
    if not is_valid:
        print("\n📋 Setup Instructions:")
        if "driver not installed" in message:
            print("   Run: pip install psycopg2-binary pgvector")
        elif "not configured" in message:
            print("   Set environment variables:")
            print("   export PGVECTOR_HOST='localhost'  # or your PostgreSQL host")
            print("   export PGVECTOR_PORT='5432'")
            print("   export PGVECTOR_DATABASE='jean_memory_db'  # or your database name")
            print("   export PGVECTOR_USER='jean_memory'  # or your database user")
            print("   export PGVECTOR_PASSWORD='your_secure_password'")
        elif "connection failed" in message:
            print("   Check that PostgreSQL is running and accessible")
            print("   For local development: Start PostgreSQL container")
            print("   For production: Verify Supabase credentials")
        elif "extension not installed" in message:
            print("   pgvector extension needs to be installed")
            print("   This script can attempt to install it automatically")
            
            # Offer to install extension automatically
            try:
                response = input("\n   Would you like to attempt automatic installation? (y/N): ").lower()
                if response in ['y', 'yes']:
                    print("   Attempting to install pgvector extension...")
                    success, result = install_pgvector_extension()
                    if success:
                        print("   ✅ Extension installed successfully!")
                        # Re-run validation
                        is_valid, message = validate_pgvector_for_phase2()
                        print(f"   {message}")
                    else:
                        print(f"   ❌ Extension installation failed: {result.get('error', 'Unknown error')}")
                        print("   Manual installation required:")
                        print("   Connect to your PostgreSQL database and run:")
                        print("   CREATE EXTENSION IF NOT EXISTS vector;")
                        return False
                else:
                    print("   Manual installation required:")
                    print("   Connect to your PostgreSQL database and run:")
                    print("   CREATE EXTENSION IF NOT EXISTS vector;")
                    return False
            except KeyboardInterrupt:
                print("\n   Installation cancelled")
                return False
        
        # Re-check validation after potential extension installation
        if "extension not installed" in message:
            is_valid, message = validate_pgvector_for_phase2()
    
    # Test 4: Detailed status
    print("\n4. Detailed pgvector status...")
    status = get_pgvector_status()
    for key, value in status.items():
        if key != "result":
            print(f"   {key}: {value}")
    
    # Test 5: Extension specific tests if connected
    if status["connected"]:
        print("\n5. Testing pgvector extension functionality...")
        try:
            from app.utils.pgvector_connection import test_pgvector_connection
            success, result = test_pgvector_connection()
            
            if success and result.get("extension_installed", False):
                print("   ✅ pgvector extension is functional")
                print(f"   PostgreSQL Version: {result.get('pg_version', 'Unknown')}")
            elif success:
                print("   ⚠️ Connected but pgvector extension not installed")
            else:
                print(f"   ❌ Connection test failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"   ⚠️ Extension test failed: {e}")
    
    print("\n🎉 Phase 2 Validation Complete!")
    print("=" * 50)
    
    if is_valid:
        print("✅ pgvector infrastructure is ready")
        print("🚀 You can proceed to Phase 3 (data migration tools)")
        print("\n💡 Next Steps:")
        print("   1. Verify pgvector extension is working in your environment")
        print("   2. Consider creating a test vector table to validate functionality")
        print("   3. Ensure Qdrant system remains untouched (parallel setup)")
        return True
    else:
        print("❌ Issues found - please fix before proceeding")
        print("\n🔧 Common Solutions:")
        print("   • Ensure PostgreSQL is accessible")
        print("   • Install pgvector extension in your database")
        print("   • For Supabase: Enable pgvector in your project settings")
        print("   • Check network connectivity and firewall settings")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 