#!/usr/bin/env bash

# Jean Memory Bloat File Cleanup
# This script moves identified bloat files to a backup directory

set -e  # Exit immediately if a command fails

echo "🧹 Starting Jean Memory bloat file cleanup"

# Get the base directory
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKUP_DIR="${BASE_DIR}/cleanup_backups/$(date +%Y%m%d_%H%M%S)"

# Create backup directory
mkdir -p "$BACKUP_DIR"
echo "📁 Created backup directory: $BACKUP_DIR"

# Function to safely move files to backup
backup_file() {
  local file_path="$1"
  if [ -f "$file_path" ] || [ -d "$file_path" ]; then
    local rel_path="${file_path#$BASE_DIR/}"
    local backup_path="$BACKUP_DIR/$rel_path"
    mkdir -p "$(dirname "$backup_path")"
    mv "$file_path" "$backup_path"
    echo "✅ Backed up: $rel_path"
  else
    echo "⚠️ Not found: $file_path"
  fi
}

echo "🔍 Identifying and backing up bloat files..."

# Root directory bloat
backup_file "$BASE_DIR/.env.bak"
backup_file "$BASE_DIR/.env.template"
backup_file "$BASE_DIR/setup-hybrid.sh.bak"
backup_file "$BASE_DIR/Makefile.improved"

# Database backup files
backup_file "$BASE_DIR/openmemory/api/openmemory.db.backup_20250524_225722"
backup_file "$BASE_DIR/openmemory/api/openmemory.db.fresh_backup"
backup_file "$BASE_DIR/openmemory/api/openmemory.db.old"

# Duplicate environment files
backup_file "$BASE_DIR/openmemory/api/.env.bak"

echo "✨ Cleanup complete!"
echo "📋 Bloat files have been moved to: $BACKUP_DIR"
echo "⚠️ If you need to restore any files, you can find them in the backup directory."
