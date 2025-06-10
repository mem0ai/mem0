#!/bin/bash
# Jean Memory Quick Start Script for Local Development
# This script ensures everything is set up and starts the services

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧠 Jean Memory Quick Start${NC}"
echo -e "${BLUE}==========================${NC}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Step 1: Check if setup has been run
echo -e "\n${YELLOW}Step 1: Checking setup status...${NC}"

SETUP_NEEDED=false

# Check for virtual environment
if [ ! -d "openmemory/venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found${NC}"
    SETUP_NEEDED=true
fi

# Check for .env files
if [ ! -f "openmemory/api/.env" ]; then
    echo -e "${YELLOW}⚠️  API .env file not found${NC}"
    SETUP_NEEDED=true
fi

# Check Docker containers
if ! docker ps | grep -q jeanmemory_postgres_service || ! docker ps | grep -q jeanmemory_qdrant_service; then
    echo -e "${YELLOW}⚠️  Docker containers not running${NC}"
    SETUP_NEEDED=true
fi

# Run setup if needed
if [ "$SETUP_NEEDED" = true ]; then
    echo -e "\n${YELLOW}Running setup...${NC}"
    ./setup-local-complete.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Setup failed!${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Setup already complete${NC}"
    
    # Ensure Docker containers are running
    echo -e "\n${YELLOW}Step 2: Ensuring Docker containers are running...${NC}"
    docker-compose up -d
    sleep 3
fi

# Step 3: Run tests
echo -e "\n${YELLOW}Step 3: Running system tests...${NC}"
cd openmemory && source venv/bin/activate && cd .. && python test-complete-local-setup.py

# Check test results
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ All tests passed!${NC}"
else
    echo -e "\n${YELLOW}⚠️  Some tests failed, but continuing...${NC}"
fi

# Step 4: Start services
echo -e "\n${YELLOW}Step 4: Starting services...${NC}"

# Check what to start
START_API=true
START_UI=true

# Check if API is already running
if curl -s http://localhost:8765/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API is already running${NC}"
    START_API=false
fi

# Check if UI is already running
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ UI is already running${NC}"
    START_UI=false
fi

# Start services if needed
if [ "$START_API" = true ] || [ "$START_UI" = true ]; then
    echo -e "\n${BLUE}Starting services...${NC}"
    
    if [ "$START_API" = true ] && [ "$START_UI" = true ]; then
        # Start both
        ./start-all.sh
    elif [ "$START_API" = true ]; then
        # Start only API
        ./start-api.sh
    elif [ "$START_UI" = true ]; then
        # Start only UI
        ./start-ui.sh
    fi
else
    echo -e "\n${GREEN}🎉 All services are already running!${NC}"
    echo -e "\n${BLUE}Access the application at:${NC}"
    echo -e "- API: ${YELLOW}http://localhost:8765${NC}"
    echo -e "- UI: ${YELLOW}http://localhost:3000${NC}"
fi 