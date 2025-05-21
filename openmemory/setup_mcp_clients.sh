#!/bin/bash

# Function to set up a single MCP client
setup_mcp_client() {
    local client_name=$1
    local user_id=$2
    
    echo "Setting up MCP client for $client_name with user $user_id..."
    
    # Create a temporary Node.js container to run the setup
    docker run --rm \
        --network openmemory_default \
        -v "$(pwd):/app" \
        node:18-alpine \
        sh -c "cd /app && \
               npm install install-mcp && \
               echo 'openmemory' | npx install-mcp i http://openmemory-mcp:8765/mcp/$client_name/sse/$user_id --client $client_name"
}

# Check if we have the minimum number of arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <client_name> <user_id> [client_name user_id ...]"
    echo "Example: $0 cursor brendan"
    exit 1
fi

# Process pairs of client names and user IDs
while [ $# -ge 2 ]; do
    client_name=$1
    user_id=$2
    setup_mcp_client "$client_name" "$user_id"
    shift 2
done

echo "MCP client setup complete!" 