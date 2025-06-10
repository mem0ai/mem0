#!/bin/bash

# Monitor and manage UI container resources
# This script helps track memory usage and restart the container if needed

CONTAINER_NAME="jeanmemory_ui_service"
LOG_FILE="ui-monitor.log"
MEMORY_THRESHOLD=1800000000  # 1.8GB in bytes

echo "Starting UI container monitoring..." | tee -a $LOG_FILE
echo "$(date): Monitoring started" >> $LOG_FILE

while true; do
  # Check if container is running
  if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "$(date): Container not running, attempting to start..." | tee -a $LOG_FILE
    docker-compose up -d ui
    sleep 10
    continue
  fi

  # Get memory usage
  MEMORY_USAGE=$(docker stats --no-stream --format "{{.MemUsage}}" $CONTAINER_NAME | awk '{print $1}' | sed 's/MiB//')
  MEMORY_USAGE_BYTES=$(echo "$MEMORY_USAGE * 1048576" | bc)
  
  echo "$(date): Memory usage: ${MEMORY_USAGE}MiB" >> $LOG_FILE
  
  # Check if memory is too high
  if (( $(echo "$MEMORY_USAGE_BYTES > $MEMORY_THRESHOLD" | bc -l) )); then
    echo "$(date): Memory usage too high (${MEMORY_USAGE}MiB), restarting container..." | tee -a $LOG_FILE
    docker-compose restart ui
    sleep 20
  fi
  
  # Wait before next check
  sleep 30
done 