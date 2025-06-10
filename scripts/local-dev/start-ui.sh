#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/openmemory/ui"
echo "🚀 Starting UI server on http://localhost:3000"
npm run dev
