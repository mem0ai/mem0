#!/usr/bin/env python3
"""
Test script to verify Jean Memory local development setup
"""

import os
import sys
import time
import requests
import psycopg2
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# Colors for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def print_test(name, passed, details=""):
    """Print test result with color"""
    status = f"{GREEN}✅ PASSED{NC}" if passed else f"{RED}❌ FAILED{NC}"
    print(f"\n{name}: {status}")
    if details:
        print(f"  {details}")

def test_environment():
    """Test environment variables"""
    print(f"\n{BLUE}=== Testing Environment Variables ==={NC}")
    
    # Load environment
    env_path = os.path.join(os.path.dirname(__file__), 'openmemory/api/.env')
    load_dotenv(env_path)
    
    required_vars = [
        'DATABASE_URL',
        'QDRANT_HOST',
        'QDRANT_PORT',
        'USER_ID'
    ]
    
    all_present = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✓ {var}: {value[:50]}...")
        else:
            print(f"  ✗ {var}: NOT SET")
            all_present = False
    
    print_test("Environment Variables", all_present)
    return all_present

def test_postgresql():
    """Test PostgreSQL connection and schema"""
    print(f"\n{BLUE}=== Testing PostgreSQL ==={NC}")
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            host="127.0.0.1",
            port=5432,
            database="jean_memory_db",
            user="jean_memory",
            password="memory_password"
        )
        cur = conn.cursor()
        
        # Test connection
        cur.execute("SELECT 1")
        print_test("PostgreSQL Connection", True)
        
        # Check tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        expected_tables = [
            'alembic_version',
            'memories',
            'memory_associations',
            'memory_entities',
            'memory_messages',
            'memory_relations',
            'memory_tags',
            'messages',
            'users'
        ]
        
        missing_tables = set(expected_tables) - set(tables)
        extra_tables = set(tables) - set(expected_tables)
        
        if missing_tables:
            print(f"  Missing tables: {missing_tables}")
        if extra_tables:
            print(f"  Extra tables: {extra_tables}")
        
        print_test("Database Schema", len(missing_tables) == 0, 
                  f"Found {len(tables)} tables")
        
        # Test user exists
        cur.execute("SELECT id, email FROM users WHERE id = '00000000-0000-0000-0000-000000000001'")
        user = cur.fetchone()
        print_test("Default User", user is not None,
                  f"User: {user[1] if user else 'Not found'}")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print_test("PostgreSQL", False, str(e))
        return False

def test_qdrant():
    """Test Qdrant connection and collection"""
    print(f"\n{BLUE}=== Testing Qdrant ==={NC}")
    
    try:
        # Connect to Qdrant
        client = QdrantClient(host="localhost", port=6333)
        
        # Test connection
        collections = client.get_collections()
        print_test("Qdrant Connection", True, 
                  f"Found {len(collections.collections)} collections")
        
        # Check specific collection
        collection_name = os.getenv('MAIN_QDRANT_COLLECTION_NAME', 'jonathans_memory_main')
        
        try:
            collection_info = client.get_collection(collection_name)
            print_test("Qdrant Collection", True,
                      f"Collection '{collection_name}' exists with {collection_info.points_count} points")
            
            # Check collection configuration
            expected_size = 1536
            actual_size = collection_info.config.params.vectors.size
            print_test("Vector Dimension", actual_size == expected_size,
                      f"Expected: {expected_size}, Actual: {actual_size}")
            
        except Exception as e:
            print_test("Qdrant Collection", False, str(e))
            
        return True
        
    except Exception as e:
        print_test("Qdrant", False, str(e))
        return False

def test_api_server():
    """Test API server endpoints"""
    print(f"\n{BLUE}=== Testing API Server ==={NC}")
    
    api_url = "http://localhost:8765"
    
    try:
        # Test health endpoint
        response = requests.get(f"{api_url}/health", timeout=5)
        print_test("API Health Check", response.status_code == 200,
                  f"Status: {response.status_code}")
        
        # Test root endpoint
        response = requests.get(f"{api_url}/", timeout=5)
        print_test("API Root Endpoint", response.status_code == 200,
                  f"Response: {response.json()}")
        
        # Test memories endpoint with auth
        headers = {
            "Authorization": "Bearer local-dev-token",
            "X-User-Id": "default_user"
        }
        response = requests.get(f"{api_url}/memories", headers=headers, timeout=5)
        print_test("Memories Endpoint", response.status_code == 200,
                  f"Status: {response.status_code}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print_test("API Server", False, 
                  f"Cannot connect to API at {api_url}. Is it running?")
        return False
    except Exception as e:
        print_test("API Server", False, str(e))
        return False

def test_ui_server():
    """Test UI server"""
    print(f"\n{BLUE}=== Testing UI Server ==={NC}")
    
    ui_url = "http://localhost:3000"
    
    try:
        response = requests.get(ui_url, timeout=5)
        print_test("UI Server", response.status_code == 200,
                  f"Status: {response.status_code}")
        return True
        
    except requests.exceptions.ConnectionError:
        print_test("UI Server", False,
                  f"Cannot connect to UI at {ui_url}. Is it running?")
        return False
    except Exception as e:
        print_test("UI Server", False, str(e))
        return False

def test_docker_containers():
    """Test Docker containers are running"""
    print(f"\n{BLUE}=== Testing Docker Containers ==={NC}")
    
    import subprocess
    
    try:
        # Check PostgreSQL container
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=jeanmemory_postgres_service", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        postgres_running = "jeanmemory_postgres_service" in result.stdout
        print_test("PostgreSQL Container", postgres_running)
        
        # Check Qdrant container
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=jeanmemory_qdrant_service", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        qdrant_running = "jeanmemory_qdrant_service" in result.stdout
        print_test("Qdrant Container", qdrant_running)
        
        return postgres_running and qdrant_running
        
    except Exception as e:
        print_test("Docker Containers", False, str(e))
        return False

def main():
    """Run all tests"""
    print(f"{BLUE}🧠 Jean Memory Local Development Test Suite{NC}")
    print(f"{BLUE}==========================================={NC}")
    
    # Run tests
    results = {
        "Environment": test_environment(),
        "Docker": test_docker_containers(),
        "PostgreSQL": test_postgresql(),
        "Qdrant": test_qdrant(),
        "API": test_api_server(),
        "UI": test_ui_server()
    }
    
    # Summary
    print(f"\n{BLUE}=== Test Summary ==={NC}")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = f"{GREEN}✅{NC}" if result else f"{RED}❌{NC}"
        print(f"  {status} {test}")
    
    print(f"\n{BLUE}Total: {passed}/{total} tests passed{NC}")
    
    if passed == total:
        print(f"\n{GREEN}🎉 All tests passed! Your local development environment is ready.{NC}")
    else:
        print(f"\n{YELLOW}⚠️  Some tests failed. Please check the output above.{NC}")
        print(f"\n{BLUE}Common fixes:{NC}")
        print("  - For API/UI failures: Make sure to run ./start-api.sh and ./start-ui.sh")
        print("  - For Docker failures: Make sure Docker is running")
        print("  - For database failures: Try running ./setup-local-complete.sh again")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main()) 