#!/bin/bash

# --- Configuration ---
QDRANT_VOLUME="openmemory"
POSTGRES_VOLUME="openmemory_postgres"
BACKUP_DIR_FILE=".backup_dir"
DEFAULT_BACKUP_DIR="./backup"  # Check this first
COMPOSE_FILE="docker-compose.yml"

# Use default if exists, else saved, else ask
if [ -d "$DEFAULT_BACKUP_DIR" ]; then
    BACKUP_DIR="$DEFAULT_BACKUP_DIR"
    echo "Using default backup directory: $BACKUP_DIR"
elif [ -f "$BACKUP_DIR_FILE" ]; then
    BACKUP_DIR=$(cat "$BACKUP_DIR_FILE" 2>/dev/null)
    if [ -z "$BACKUP_DIR" ]; then
        read -r -p "Enter backup directory path: " BACKUP_DIR
        BACKUP_DIR="${BACKUP_DIR//\\//}"  # Convert \ to /
        BACKUP_DIR="${BACKUP_DIR/E:/\/e}"  # Convert drive letter
        BACKUP_DIR="${BACKUP_DIR/e:/\/e}"
        echo "$BACKUP_DIR" > "$BACKUP_DIR_FILE"
    fi
    echo "Using saved backup directory: $BACKUP_DIR"
else
    read -r -p "Enter backup directory path: " BACKUP_DIR
    BACKUP_DIR="${BACKUP_DIR//\\//}"  # Convert \ to /
    BACKUP_DIR="${BACKUP_DIR/E:/\/e}"  # Convert drive letter
    BACKUP_DIR="${BACKUP_DIR/e:/\/e}"
    echo "$BACKUP_DIR" > "$BACKUP_DIR_FILE"
    echo "Backup directory saved: $BACKUP_DIR"
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
QDRANT_BACKUP="qdrant-backup-${TIMESTAMP}.tar.gz"
POSTGRES_BACKUP="postgres-backup-${TIMESTAMP}.tar.gz"
QDRANT_PATH="${BACKUP_DIR}/${QDRANT_BACKUP}"
POSTGRES_PATH="${BACKUP_DIR}/${POSTGRES_BACKUP}"

echo "Stopping services for consistent backup..."
docker compose -f $COMPOSE_FILE down
echo ""

echo "Backing up Qdrant volume (openmemory)..."
Q_SIZE=$(docker run --rm -v ${QDRANT_VOLUME}:/data alpine du -sb /data | awk '{print $1}')
MSYS_NO_PATHCONV=1 docker run --rm \
    -v ${QDRANT_VOLUME}:/data \
    -v "${BACKUP_DIR}":/backup \
    alpine \
    sh -c "apk add --no-cache pv && tar cz -C /data . | pv -s $Q_SIZE -N 'Compressing Qdrant' > /backup/${QDRANT_BACKUP}"

echo "Backing up Postgres volume (openmemory_postgres)..."
P_SIZE=$(docker run --rm -v ${POSTGRES_VOLUME}:/data alpine du -sb /data | awk '{print $1}')
MSYS_NO_PATHCONV=1 docker run --rm \
    -v ${POSTGRES_VOLUME}:/data \
    -v "${BACKUP_DIR}":/backup \
    alpine \
    sh -c "apk add --no-cache pv && tar cz -C /data . | pv -s $P_SIZE -N 'Compressing Postgres' > /backup/${POSTGRES_BACKUP}"

echo ""
echo "Restarting services..."
docker compose -f $COMPOSE_FILE up -d
echo ""

if [ -f "${QDRANT_PATH}" ] && [ -f "${POSTGRES_PATH}" ]; then
    echo "=================================================="
    echo "✅ Backup completed successfully!"
    echo "=================================================="
    echo "Backup directory: ${BACKUP_DIR}"
    echo "Qdrant backup:  ${QDRANT_BACKUP} ($(ls -lh "${QDRANT_PATH}" | awk '{print $5}'))"
    echo "Postgres backup: ${POSTGRES_BACKUP} ($(ls -lh "${POSTGRES_PATH}" | awk '{print $5}'))"
    echo ""
else
    echo "❌ Backup failed. Check errors above."
fi