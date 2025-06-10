#!/bin/bash

# UI Development Helper Tools
# A collection of common commands for working with the UI container

function show_help {
  echo "UI Development Helper Tools"
  echo "--------------------------"
  echo "Usage: ./ui-dev-tools.sh [command]"
  echo ""
  echo "Commands:"
  echo "  logs        - Show live UI container logs"
  echo "  stats       - Show real-time container resource usage"
  echo "  restart     - Restart the UI container"
  echo "  clean       - Clean and restart the UI container (removes volumes)"
  echo "  shell       - Open a shell in the UI container"
  echo "  npm [cmd]   - Run an npm command inside the container"
  echo "  monitor     - Start monitoring the UI container (background)"
  echo "  help        - Show this help message"
  echo ""
}

case "$1" in
  logs)
    docker logs -f jeanmemory_ui_service
    ;;
  stats)
    docker stats jeanmemory_ui_service
    ;;
  restart)
    docker-compose restart ui
    ;;
  clean)
    ./restart-ui.sh
    ;;
  shell)
    docker exec -it jeanmemory_ui_service /bin/sh
    ;;
  npm)
    shift
    docker exec -it jeanmemory_ui_service npm $@
    ;;
  monitor)
    ./monitor-ui.sh &
    echo "Monitoring started in background. Check ui-monitor.log for details."
    ;;
  help|*)
    show_help
    ;;
esac 