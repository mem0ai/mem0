#!/usr/bin/env python3
"""
Script to run Alembic migrations for Jean Memory
"""
import os
import sys
import subprocess

def run_migrations():
    """Run database migrations for Jean Memory's backend"""
    print("Running database migrations...")
    
    # Get the absolute path to the openmemory/api directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    api_dir = os.path.join(base_dir, "openmemory", "api")
    
    # Change to the api directory
    os.chdir(api_dir)
    
    # Run alembic upgrade
    result = subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )
    
    # Print output
    print(result.stdout)
    
    if result.returncode != 0:
        print(f"Error running migrations: {result.stderr}")
        return False
    
    print("Migrations completed successfully!")
    return True

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
