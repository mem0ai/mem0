#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🚀 Starting Jean Memory Local Development"
echo "========================================"

# Start API in background
echo "Starting API server..."
"$SCRIPT_DIR/start-api.sh" &
API_PID=$!

# Wait a bit for API to start
sleep 5

# Start UI
echo "Starting UI server..."
"$SCRIPT_DIR/start-ui.sh" &
UI_PID=$!

echo ""
echo "Services started:"
echo "- API: http://localhost:8765 (PID: $API_PID)"
echo "- UI: http://localhost:3000 (PID: $UI_PID)"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "echo 'Stopping services...'; kill $API_PID $UI_PID; exit" INT
wait
