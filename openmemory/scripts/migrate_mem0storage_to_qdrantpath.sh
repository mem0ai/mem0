#!/bin/bash
set -euo pipefail

# ===============================================
# OpenMemory Qdrant Data Migration Script
# ===============================================
# This script migrates your Qdrant data from /mem0/storage to /qdrant/storage
# within the same Docker volume (mem0_storage).
#
# IMPORTANT:
# - Do NOT stop or interrupt this script while it is running.
# - Let it finish to ensure your data is safely migrated and backed up.
# - This script will only run if /mem0/storage exists and /qdrant/storage does NOT exist in the volume.
# - If your data is already in /qdrant/storage, nothing will happen.
# ===============================================

VOLUME="mem0_storage"
BACKUP_FILE="mem0_storage_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
LOGFILE="mem0storage_to_qdrantpath_migration.log"

# Check if the volume exists
VOLUME_EXISTS=$(docker volume ls -q | grep -w "$VOLUME" || true)
if [ -z "$VOLUME_EXISTS" ]; then
  echo "❌ Docker volume $VOLUME does not exist. No migration needed."
  exit 0
fi

echo "==== mem0_storage to /qdrant/storage Migration Log ====" > "$LOGFILE"
date >> "$LOGFILE"

echo "🔍 Checking for existing data in $VOLUME:/mem0/storage ..." | tee -a "$LOGFILE"
# Check if /mem0/storage exists and is non-empty
HAS_OLD_DATA=$(docker run --rm -v ${VOLUME}:/data busybox sh -c "[ -d /data/mem0/storage ] && [ \"\$(ls -A /data/mem0/storage 2>/dev/null)\" ] && echo yes || echo no")
if [ "$HAS_OLD_DATA" != "yes" ]; then
  echo "No data found in /mem0/storage. No migration needed." | tee -a "$LOGFILE"
  exit 0
fi

# Check if /qdrant/storage already exists and is non-empty
HAS_NEW_DATA=$(docker run --rm -v ${VOLUME}:/data busybox sh -c "[ -d /data/qdrant/storage ] && [ \"\$(ls -A /data/qdrant/storage 2>/dev/null)\" ] && echo yes || echo no")
if [ "$HAS_NEW_DATA" = "yes" ]; then
  echo "/qdrant/storage already exists and is non-empty. Migration not needed." | tee -a "$LOGFILE"
  exit 0
fi

echo "📦 Creating backup of /mem0/storage as $BACKUP_FILE ..." | tee -a "$LOGFILE"
docker run --rm -v ${VOLUME}:/data -v $(pwd):/backup busybox tar czf /backup/$BACKUP_FILE -C /data/mem0/storage . || {
  echo "Backup failed! Aborting migration." | tee -a "$LOGFILE"
  exit 1
}
echo "Backup created at $(pwd)/$BACKUP_FILE" | tee -a "$LOGFILE"

echo "📁 Copying data from /mem0/storage to /qdrant/storage ..." | tee -a "$LOGFILE"
docker run --rm -v ${VOLUME}:/data busybox sh -c "mkdir -p /data/qdrant/storage && cp -a /data/mem0/storage/. /data/qdrant/storage/" || {
  echo "Data copy failed! Aborting migration." | tee -a "$LOGFILE"
  exit 1
}
echo "Data copied successfully." | tee -a "$LOGFILE"

echo "Migration complete. Your Qdrant data is now in $VOLUME:/qdrant/storage." | tee -a "$LOGFILE"
echo "The old data in /mem0/storage and backup ($BACKUP_FILE) are retained for safety." | tee -a "$LOGFILE"
echo "==== Migration finished at $(date) ====" >> "$LOGFILE"

echo
cat <<EOM
==== mem0_storage to /qdrant/storage Migration Summary ====
✔ Data copied from /mem0/storage to /qdrant/storage in $VOLUME
✔ Backup created: $(pwd)/$BACKUP_FILE
✔ Migration log: $(pwd)/$LOGFILE
✔ Old data in /mem0/storage NOT deleted for safety.
If you encounter any issues, restore from the backup tarball.
EOM 