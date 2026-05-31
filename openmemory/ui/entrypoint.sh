#!/bin/sh
set -e

# Ensure the working directory is correct
cd /app



# Replace env variable placeholders with real values
printenv | grep NEXT_PUBLIC_ | while read -r line ; do
  key=$(echo $line | cut -d "=" -f1)
  value=$(echo $line | cut -d "=" -f2)

  find .next/ -type f -exec sed -i "s|$key|$value|g" {} \;
done
echo "Done replacing env variables NEXT_PUBLIC_ with real values"


# Execute the container's main process (CMD in Dockerfile)
exec "$@"