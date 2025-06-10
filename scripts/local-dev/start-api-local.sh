#!/bin/bash
# Start API for local development

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Navigate to the API directory
cd "$SCRIPT_DIR/openmemory/api" || exit 1

# Activate virtual environment
source ../venv/bin/activate || exit 1

# Show current directory for debugging
echo "Current directory: $(pwd)"
echo "Python: $(which python)"
echo "Starting API server..."

# Start the API
python -m uvicorn main:app --host 0.0.0.0 --port 8765 --reload 