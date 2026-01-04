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

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Backup directory not found: $BACKUP_DIR"
    exit 1
fi

echo ""
echo "Available pairs in $BACKUP_DIR (newest first):"
echo "-----------------------------------------------------------------------------------------------------------"
printf "%-4s %-19s %-12s %-35s %-35s\n" "No." "Date & Time" "Size" "Qdrant File" "Postgres File"

# Find and pair
QDRANT_FILES=($(ls -r "$BACKUP_DIR"/qdrant-backup-*.tar.gz 2>/dev/null))
POSTGRES_FILES=($(ls -r "$BACKUP_DIR"/postgres-backup-*.tar.gz 2>/dev/null))

pair_num=1
for q_file in "${QDRANT_FILES[@]}"; do
    ts=$(basename "$q_file" | sed -E 's/qdrant-backup-([0-9]{8}_[0-9]{6})\.tar\.gz/\1/')
    p_file="$BACKUP_DIR/postgres-backup-${ts}.tar.gz"
    if [ -f "$p_file" ]; then
        dt=$(date -d "${ts:0:8} ${ts:9:2}:${ts:11:2}:${ts:13:2}" +"%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$ts")
        q_size=$(ls -lh "$q_file" | awk '{print $5}')
        p_size=$(ls -lh "$p_file" | awk '{print $5}')
        total="$q_size + $p_size"
        printf "%-4s %-19s %-12s %-35s %-35s\n" "$pair_num" "$dt" "$total" "$(basename "$q_file")" "$(basename "$p_file")"
        eval "PAIR_${pair_num}_Q='$q_file'"
        eval "PAIR_${pair_num}_P='$p_file'"
        ((pair_num++))
    fi
done

echo "-----------------------------------------------------------------------------------------------------------"
echo ""

if [ $((pair_num - 1)) -eq 0 ]; then
    echo "❌ No complete backup pairs found."
    exit 1
fi

read -r -p "Enter pair number to restore (1-$((pair_num-1))): " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ $choice -lt 1 ] || [ $choice -ge $pair_num ]; then
    echo "❌ Invalid choice"
    exit 1
fi

QDRANT_PATH=$(eval echo "\$PAIR_${choice}_Q")
POSTGRES_PATH=$(eval echo "\$PAIR_${choice}_P")

echo ""
echo "Selected pair $choice:"
echo "  Qdrant:  $(basename "$QDRANT_PATH") ($(ls -lh "$QDRANT_PATH" | awk '{print $5}'))"
echo "  Postgres: $(basename "$POSTGRES_PATH") ($(ls -lh "$POSTGRES_PATH" | awk '{print $5}'))"
echo ""
echo "WARNING: This will overwrite ALL current memory data!"
read -r -p "Proceed? [y/N]: " confirm
[[ ! "$confirm" =~ ^[yY]$ ]] && echo "Cancelled." && exit 0

echo ""
echo "Stopping services..."
docker compose -f $COMPOSE_FILE down

# Restore Qdrant
echo "Restoring Qdrant..."
docker run --rm -v ${QDRANT_VOLUME}:/data alpine sh -c "rm -rf /data/* /data/.* || true"
Q_SIZE=$(du -sb "$QDRANT_PATH" | awk '{print $1}')
MSYS_NO_PATHCONV=1 docker run --rm \
    -v ${QDRANT_VOLUME}:/data \
    -v "$BACKUP_DIR":/backup \
    alpine \
    sh -c "apk add --no-cache pv && pv -s $Q_SIZE -N 'Qdrant' /backup/$(basename "$QDRANT_PATH") | tar xz -C /data"

# Restore Postgres
echo "Restoring Postgres..."
docker run --rm -v ${POSTGRES_VOLUME}:/data alpine sh -c "rm -rf /data/* /data/.* || true"
P_SIZE=$(du -sb "$POSTGRES_PATH" | awk '{print $1}')
MSYS_NO_PATHCONV=1 docker run --rm \
    -v ${POSTGRES_VOLUME}:/data \
    -v "$BACKUP_DIR":/backup \
    alpine \
    sh -c "apk add --no-cache pv && pv -s $P_SIZE -N 'Postgres' /backup/$(basename "$POSTGRES_PATH") | tar xz -C /data"

echo ""
echo "Restarting services..."
docker compose -f $COMPOSE_FILE up -d

echo ""
echo "=================================================="
echo "✅ Restore complete! Pair #$choice restored."
echo "=================================================="
echo "UI:  http://localhost:10004"
echo "API: http://localhost:10003/docs"
echo ""