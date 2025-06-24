#!/usr/bin/env python3
"""
Phase 1 Neo4j Setup Validation Script

This script validates that the Neo4j infrastructure is properly set up
for the unified memory migration. Run this before proceeding to Phase 2.

Usage:
    python test_phase1_neo4j.py
"""

import os
import sys
from pathlib import Path

# Add the project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'openmemory' / 'api'))

def main():
    print("🚧 Phase 1 Neo4j Setup Validation")
    print("=" * 50)
    
    # Test 1: Import test
    print("\n1. Testing imports...")
    try:
        from app.settings import config
        from app.utils.neo4j_connection import validate_neo4j_for_phase1, get_neo4j_status
        print("   ✅ All imports successful")
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False
    
    # Test 2: Configuration check
    print("\n2. Checking configuration...")
    print(f"   Environment: {config.ENVIRONMENT}")
    print(f"   Neo4j URI: {config.NEO4J_URI}")
    print(f"   Neo4j User: {config.NEO4J_USER}")
    print(f"   Neo4j Password: {'SET' if config.NEO4J_PASSWORD and config.NEO4J_PASSWORD != 'password' else 'DEFAULT/NOT SET'}")
    
    # Test 3: Neo4j connection validation
    print("\n3. Validating Neo4j connection...")
    is_valid, message = validate_neo4j_for_phase1()
    print(f"   {message}")
    
    if not is_valid:
        print("\n📋 Setup Instructions:")
        if "driver not installed" in message:
            print("   Run: pip install neo4j")
        elif "not configured" in message:
            print("   Set environment variables:")
            print("   export NEO4J_URI='bolt://localhost:7687'  # or your Neo4j URI")
            print("   export NEO4J_USER='neo4j'")
            print("   export NEO4J_PASSWORD='your_secure_password'")
        elif "connection failed" in message:
            print("   Check that Neo4j is running and accessible")
            print("   For local development: Start Neo4j Docker container")
            print("   For production: Verify Neo4j Aura credentials")
        
        return False
    
    # Test 4: Detailed status
    print("\n4. Detailed Neo4j status...")
    status = get_neo4j_status()
    for key, value in status.items():
        if key != "result":
            print(f"   {key}: {value}")
    
    print("\n🎉 Phase 1 Validation Complete!")
    print("=" * 50)
    
    if is_valid:
        print("✅ Neo4j infrastructure is ready")
        print("🚀 You can proceed to Phase 2 (pgvector setup)")
        return True
    else:
        print("❌ Issues found - please fix before proceeding")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 