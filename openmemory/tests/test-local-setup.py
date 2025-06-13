#!/usr/bin/env python3
"""
Test script to verify Jean Memory local development setup
"""
import os
import sys
import time
import requests
import subprocess
from typing import Dict, Tuple

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{BLUE}=== {text} ==={NC}")

def print_test(name: str, passed: bool, details: str = ""):
    """Print test result"""
    status = f"{GREEN}✓ PASS{NC}" if passed else f"{RED}✗ FAIL{NC}"
    print(f"  {name}: {status}")
    if details and not passed:
        print(f"    {YELLOW}Details: {details}{NC}")

def check_docker_services() -> Dict[str, bool]:
    """Check if Docker services are running"""
    print_header("Docker Services")
    
    services = {
        "jeanmemory_postgres_service": False,
        "jeanmemory_qdrant_service": False,
        "jeanmemory_api_service": False,
        "jeanmemory_ui_service": False
    }
    
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        running_containers = result.stdout.strip().split('\n')
        
        for service in services:
            services[service] = service in running_containers
            print_test(f"Container {service}", services[service])
    
    except Exception as e:
        print(f"{RED}Error checking Docker services: {e}{NC}")
    
    return services

def test_postgresql() -> bool:
    """Test PostgreSQL connection"""
    print_header("PostgreSQL Database")
    
    try:
        # Test using docker exec
        result = subprocess.run(
            ["docker", "exec", "jeanmemory_postgres_service", 
             "pg_isready", "-U", "jean_memory", "-d", "jean_memory_db"],
            capture_output=True
        )
        
        passed = result.returncode == 0
        print_test("PostgreSQL Connection", passed)
        
        if passed:
            # Check if tables exist
            result = subprocess.run(
                ["docker", "exec", "jeanmemory_postgres_service",
                 "psql", "-U", "jean_memory", "-d", "jean_memory_db", 
                 "-c", "\\dt"],
                capture_output=True,
                text=True
            )
            
            has_tables = "users" in result.stdout and "apps" in result.stdout
            print_test("Database Schema", has_tables, 
                      "Run 'make migrate' if schema is missing")
        
        return passed
    
    except Exception as e:
        print_test("PostgreSQL Connection", False, str(e))
        return False

def test_qdrant() -> bool:
    """Test Qdrant connection"""
    print_header("Qdrant Vector Database")
    
    try:
        response = requests.get("http://localhost:6333/readyz", timeout=5)
        passed = response.status_code == 200
        print_test("Qdrant Connection", passed)
        
        if passed:
            # Check collections
            response = requests.get("http://localhost:6333/collections", timeout=5)
            if response.status_code == 200:
                collections = response.json().get("result", {}).get("collections", [])
                print(f"  Collections: {len(collections)} found")
        
        return passed
    
    except Exception as e:
        print_test("Qdrant Connection", False, str(e))
        return False

def test_api() -> Tuple[bool, str]:
    """Test API service"""
    print_header("API Service")
    
    try:
        # Test health endpoint
        response = requests.get("http://localhost:8765/health", timeout=5)
        health_passed = response.status_code == 200
        print_test("API Health Check", health_passed)
        
        if health_passed:
            data = response.json()
            print(f"  API Status: {data.get('status', 'unknown')}")
        
        # Test root endpoint
        response = requests.get("http://localhost:8765/", timeout=5)
        root_passed = response.status_code in [200, 307]  # Redirect is OK
        print_test("API Root Endpoint", root_passed)
        
        # Get user ID from environment
        user_id = os.environ.get("USER", "local_dev_user")
        
        return health_passed and root_passed, user_id
    
    except Exception as e:
        print_test("API Connection", False, str(e))
        return False, ""

def test_ui() -> bool:
    """Test UI service"""
    print_header("UI Service")
    
    try:
        response = requests.get("http://localhost:3000", timeout=10)
        passed = response.status_code == 200
        print_test("UI Connection", passed)
        
        if passed:
            # Check if it's actually Next.js
            is_nextjs = "/_next" in response.text
            print_test("Next.js Application", is_nextjs)
        
        return passed
    
    except Exception as e:
        print_test("UI Connection", False, str(e))
        return False

def check_environment() -> bool:
    """Check environment configuration"""
    print_header("Environment Configuration")
    
    all_good = True
    
    # Check API .env file
    api_env_exists = os.path.exists("api/.env")
    print_test("API .env file", api_env_exists)
    
    if api_env_exists:
        with open("api/.env", "r") as f:
            env_content = f.read()
            
        has_openai = "OPENAI_API_KEY=" in env_content and \
                     "your_openai_api_key_here" not in env_content
        print_test("OpenAI API Key configured", has_openai,
                  "Update OPENAI_API_KEY in api/.env")
        
        has_user_id = "USER_ID=" in env_content
        print_test("USER_ID configured", has_user_id)
        
        all_good = all_good and has_openai and has_user_id
    else:
        all_good = False
    
    # Check UI .env file
    ui_env_exists = os.path.exists("ui/.env")
    print_test("UI .env file", ui_env_exists)
    
    return all_good

def test_api_auth(user_id: str) -> bool:
    """Test API authentication in local mode"""
    print_header("Local Authentication")
    
    try:
        # Test without auth header (should work in local mode)
        response = requests.get("http://localhost:8765/api/v1/memories", timeout=5)
        no_auth_works = response.status_code != 401
        print_test("Local auth bypass", no_auth_works,
                  "Should not require auth in local mode")
        
        # Test with dummy auth header (should also work)
        headers = {"Authorization": "Bearer dummy-token"}
        response = requests.get("http://localhost:8765/api/v1/memories", 
                              headers=headers, timeout=5)
        with_auth_works = response.status_code != 401
        print_test("Accepts any token", with_auth_works)
        
        print(f"  Using USER_ID: {user_id}")
        
        return no_auth_works and with_auth_works
    
    except Exception as e:
        print_test("Authentication test", False, str(e))
        return False

def main():
    """Run all tests"""
    print(f"{BLUE}Jean Memory Local Development Test Suite{NC}")
    print("=" * 50)
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Track overall status
    all_passed = True
    
    # Check Docker services
    services = check_docker_services()
    all_passed = all_passed and all(services.values())
    
    # Only test services if containers are running
    if services["jeanmemory_postgres_service"]:
        all_passed = all_passed and test_postgresql()
    
    if services["jeanmemory_qdrant_service"]:
        all_passed = all_passed and test_qdrant()
    
    if services["jeanmemory_api_service"]:
        api_ok, user_id = test_api()
        all_passed = all_passed and api_ok
        
        if api_ok:
            all_passed = all_passed and test_api_auth(user_id)
    
    if services["jeanmemory_ui_service"]:
        all_passed = all_passed and test_ui()
    
    # Check environment
    all_passed = all_passed and check_environment()
    
    # Summary
    print("\n" + "=" * 50)
    if all_passed:
        print(f"{GREEN}✓ All tests passed!{NC}")
        print("\nYour local development environment is ready.")
        print(f"Access the UI at: {BLUE}http://localhost:3000{NC}")
    else:
        print(f"{RED}✗ Some tests failed.{NC}")
        print("\nTroubleshooting:")
        print("1. Run 'make setup' to set up the environment")
        print("2. Check logs with 'make logs'")
        print("3. Ensure your OPENAI_API_KEY is set in api/.env")
        sys.exit(1)

if __name__ == "__main__":
    main() 