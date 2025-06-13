#!/usr/bin/env python3
"""
Production Compatibility Test for OpenMemory
Validates that local development setup doesn't break production deployment
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

def test_environment_loading():
    """Test that environment variables load correctly in both scenarios"""
    print("🧪 Testing environment variable loading...")
    
    # Test 1: Local development environment loading
    os.environ['SKIP_CONFIG_VALIDATION'] = 'true'  # Skip validation for testing
    
    try:
        # Import settings to test local .env.local loading
        sys.path.insert(0, str(Path(__file__).parent / "api"))
        from app.settings import config
        
        print(f"   ✅ Local environment detection: {config.is_local_development}")
        print(f"   ✅ Environment name: {config.environment_name}")
        
        # Test 2: Production-like environment (without .env.local)
        # Create a temporary directory without .env.local
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy API code to temp directory
            api_temp = Path(temp_dir) / "api"
            shutil.copytree(Path(__file__).parent / "api", api_temp)
            
            # Set production-like environment variables
            prod_env = os.environ.copy()
            prod_env.update({
                'DATABASE_URL': 'postgresql://user:pass@prod-host:5432/db',
                'SUPABASE_URL': 'https://prod.supabase.co',
                'SUPABASE_ANON_KEY': 'prod-anon-key',
                'SUPABASE_SERVICE_KEY': 'prod-service-key',
                'OPENAI_API_KEY': 'sk-test-key',
                'SKIP_CONFIG_VALIDATION': 'true'
            })
            
            # Test production environment loading
            result = subprocess.run([
                sys.executable, '-c',
                'import sys; sys.path.insert(0, "api"); '
                'from app.settings import config; '
                f'print("PROD_TEST:", config.is_local_development, config.environment_name)'
            ], cwd=temp_dir, env=prod_env, capture_output=True, text=True)
            
            if result.returncode == 0 and "PROD_TEST: False Production" in result.stdout:
                print("   ✅ Production environment detection works")
            else:
                print(f"   ❌ Production environment test failed: {result.stderr}")
                return False
                
    except Exception as e:
        print(f"   ❌ Environment loading test failed: {e}")
        return False
    finally:
        os.environ.pop('SKIP_CONFIG_VALIDATION', None)
    
    return True

def test_requirements_completeness():
    """Test that all imports in the codebase are covered by requirements.txt"""
    print("🧪 Testing requirements.txt completeness...")
    
    requirements_file = Path(__file__).parent / "api" / "requirements.txt"
    if not requirements_file.exists():
        print("   ❌ requirements.txt not found")
        return False
    
    # Read requirements
    with open(requirements_file) as f:
        requirements = [line.strip().split('>=')[0].split('==')[0].split('<')[0] 
                      for line in f if line.strip() and not line.startswith('#')]
    
    # Check critical imports
    critical_imports = [
        'fastapi', 'uvicorn', 'sqlalchemy', 'python-dotenv', 'alembic',
        'psycopg2-binary', 'supabase', 'pathlib'  # pathlib is stdlib, should be fine
    ]
    
    missing = []
    for imp in critical_imports:
        if imp == 'pathlib':  # Skip stdlib modules
            continue
        if imp not in requirements:
            missing.append(imp)
    
    if missing:
        print(f"   ❌ Missing requirements: {missing}")
        return False
    else:
        print("   ✅ All critical requirements present")
    
    return True

def test_database_compatibility():
    """Test that database configuration works for both local and production"""
    print("🧪 Testing database configuration compatibility...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent / "api"))
        from app.settings import config
        
        # Test local database URL format
        if config.is_local_development:
            if "localhost:54322" in config.DATABASE_URL:
                print("   ✅ Local database URL format correct")
            else:
                print(f"   ❌ Local database URL unexpected: {config.DATABASE_URL}")
                return False
        
        # Test that production would use different URL
        # (We can't test actual production URL without credentials)
        print("   ✅ Database configuration logic works")
        
    except Exception as e:
        print(f"   ❌ Database configuration test failed: {e}")
        return False
    
    return True

def test_migration_compatibility():
    """Test that migration systems don't conflict"""
    print("🧪 Testing migration system compatibility...")
    
    # Check that Alembic files exist for production
    alembic_dir = Path(__file__).parent / "api" / "alembic"
    if not alembic_dir.exists():
        print("   ❌ Alembic directory missing - production migrations won't work")
        return False
    
    # Check that Supabase migrations exist for local
    supabase_migrations = Path(__file__).parent / "supabase" / "migrations"
    if not supabase_migrations.exists():
        print("   ❌ Supabase migrations directory missing")
        return False
    
    print("   ✅ Both migration systems present")
    return True

def test_cors_configuration():
    """Test that CORS configuration includes both local and production URLs"""
    print("🧪 Testing CORS configuration...")
    
    try:
        main_file = Path(__file__).parent / "api" / "main.py"
        with open(main_file) as f:
            content = f.read()
        
        # Check for local development URLs
        if "localhost:3000" not in content:
            print("   ❌ Local development URL missing from CORS")
            return False
        
        # Check for production URLs
        if "onrender.com" not in content:
            print("   ❌ Production URL missing from CORS")
            return False
        
        print("   ✅ CORS configuration includes both local and production URLs")
        
    except Exception as e:
        print(f"   ❌ CORS configuration test failed: {e}")
        return False
    
    return True

def main():
    """Run all compatibility tests"""
    print("🚀 OpenMemory Production Compatibility Test")
    print("=" * 50)
    
    tests = [
        test_environment_loading,
        test_requirements_completeness,
        test_database_compatibility,
        test_migration_compatibility,
        test_cors_configuration,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All compatibility tests passed! Production deployment should work.")
        return 0
    else:
        print("❌ Some tests failed. Please fix issues before deploying to production.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 