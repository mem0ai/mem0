# MongoDB Integration Tests

This document explains how to run MongoDB integration tests using a real MongoDB instance.

## Prerequisites

- Docker installed and running
- Python dependencies installed (`pymongo`)

## Quick Start with MongoDB Atlas Local

MongoDB Atlas Local is a Docker image that provides MongoDB with Atlas Search and Vector Search capabilities locally.

### Check for Existing MongoDB Instances

Before starting, check if MongoDB is already running:

```bash
# Check if port 27017 is in use
lsof -i :27017

# Check for existing MongoDB containers
docker ps -a | grep -E "(atlas-local|mongo)"
```

**If MongoDB is already running**, you have two options:
1. **Use the existing MongoDB instance** (see "Using an Existing MongoDB Instance" below)
2. **Stop the existing instance** and start a new one for testing

### Option 1: Use Existing MongoDB Instance

If you already have MongoDB running (e.g., `chit_chat_mongodb`), you can use it directly:

```bash
export RUN_MONGODB_INTEGRATION=true
export MONGO_URI="mongodb://localhost:27017/?directConnection=true"
pytest tests/vector_stores/test_mongodb.py::TestMongoDBIntegration -v
```

### Option 2: Start Fresh MongoDB Atlas Local

#### 1. Clean up any existing containers (if needed)

```bash
# Stop and remove existing atlas-local container
docker stop atlas-local 2>/dev/null || true
docker rm atlas-local 2>/dev/null || true
```

#### 2. Pull the MongoDB Atlas Local image

```bash
docker pull mongodb/mongodb-atlas-local
```

#### 3. Run MongoDB Atlas Local

**If port 27017 is free:**
```bash
docker run -d \
  -p 27017:27017 \
  --name atlas-local \
  mongodb/mongodb-atlas-local
```

**If port 27017 is in use, use a different port:**
```bash
docker run -d \
  -p 27018:27017 \
  --name atlas-local \
  mongodb/mongodb-atlas-local

# Then use port 27018 in your tests
export MONGO_URI="mongodb://localhost:27018/?directConnection=true"
```

#### 4. Wait for the container to be healthy

```bash
# Better health check command (works even if container doesn't have health check configured)
until docker exec atlas-local mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
  echo "Waiting for MongoDB to be ready..."
  sleep 2
done
echo "MongoDB is ready!"

# Or check manually
docker ps | grep atlas-local
```

### 4. Run the integration tests

```bash
export RUN_MONGODB_INTEGRATION=true
export MONGO_URI="mongodb://localhost:27017/?directConnection=true"
export MONGO_TEST_DB="test_db"
export MONGO_TEST_COLLECTION="test_collection_integration"

pytest tests/vector_stores/test_mongodb.py::TestMongoDBIntegration -v
```

## Using Docker Compose

You can also use Docker Compose for easier management:

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  mongodb:
    image: mongodb/mongodb-atlas-local
    ports:
      - "27017:27017"
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 5s
      timeout: 5s
      retries: 5
    environment:
      - DO_NOT_TRACK=1  # Optional: disable telemetry
```

Run with:

```bash
docker-compose -f docker-compose.test.yml up -d
export RUN_MONGODB_INTEGRATION=true
pytest tests/vector_stores/test_mongodb.py::TestMongoDBIntegration -v
docker-compose -f docker-compose.test.yml down
```

## Using a Real MongoDB Instance

If you have a MongoDB instance running (local or remote):

```bash
export RUN_MONGODB_INTEGRATION=true
export MONGO_URI="mongodb://username:password@host:27017/database"
export MONGO_TEST_DB="test_db"
export MONGO_TEST_COLLECTION="test_collection_integration"

pytest tests/vector_stores/test_mongodb.py::TestMongoDBIntegration -v
```

## Environment Variables

- `RUN_MONGODB_INTEGRATION`: Set to `true` to enable integration tests (required)
- `MONGO_URI`: MongoDB connection URI (default: `mongodb://localhost:27017/?directConnection=true`)
- `MONGO_TEST_DB`: Database name for tests (default: `test_db`)
- `MONGO_TEST_COLLECTION`: Collection name for tests (default: `test_collection_integration`)

## Test Coverage

The integration tests cover:

- ✅ Insert and retrieve vectors
- ✅ Update vector and payload (separately and together)
- ✅ Partial payload updates (dot notation merging)
- ✅ Delete vectors
- ✅ List vectors with filters and limits
- ✅ Vector similarity search
- ✅ Search with filters
- ✅ Collection info
- ✅ List collections

## Cleanup

The tests automatically clean up after themselves, but you can manually clean up:

```bash
# Stop and remove the container
docker stop atlas-local
docker rm atlas-local

# Or if using docker-compose
docker-compose -f docker-compose.test.yml down -v
```

## Troubleshooting

### Port 27017 already allocated

**Error:** `Bind for 0.0.0.0:27017 failed: port is already allocated`

**Solutions:**

1. **Use the existing MongoDB instance:**
   ```bash
   # Find the running container
   docker ps | grep mongo
   
   # Use it directly (no need to start a new one)
   export RUN_MONGODB_INTEGRATION=true
   export MONGO_URI="mongodb://localhost:27017/?directConnection=true"
   pytest tests/vector_stores/test_mongodb.py::TestMongoDBIntegration -v
   ```

2. **Stop the existing container temporarily:**
   ```bash
   # Find and stop the container using port 27017
   docker ps | grep 27017
   docker stop <container_id_or_name>
   
   # Then start atlas-local
   docker run -d -p 27017:27017 --name atlas-local mongodb/mongodb-atlas-local
   ```

3. **Use a different port:**
   ```bash
   # Start on port 27018 instead
   docker run -d -p 27018:27017 --name atlas-local mongodb/mongodb-atlas-local
   
   # Update MONGO_URI to use port 27018
   export MONGO_URI="mongodb://localhost:27018/?directConnection=true"
   ```

### Container exists but not running

**Error:** `template parsing error: map has no entry for key "Health"`

This happens when the container was created but never started. Fix it:

```bash
# Remove the created container
docker rm atlas-local

# Start fresh
docker run -d -p 27017:27017 --name atlas-local mongodb/mongodb-atlas-local
```

### Index not ready

If search tests fail, MongoDB Atlas Local may need time to build the vector search index. The tests include a 2-second wait, but you may need to increase it:

```python
time.sleep(5)  # Increase wait time
```

### Connection refused

Make sure MongoDB is running and accessible:

```bash
# Check container status
docker ps | grep atlas-local

# Test connection
mongosh "mongodb://localhost:27017/?directConnection=true"

# Or if using a different port
mongosh "mongodb://localhost:27018/?directConnection=true"
```

### Authentication issues

If your MongoDB requires authentication, include credentials in the URI:

```bash
export MONGO_URI="mongodb://username:password@localhost:27017/?directConnection=true"
```

## Notes

- Integration tests are skipped by default (require `RUN_MONGODB_INTEGRATION=true`)
- Tests use a separate collection to avoid conflicts with other tests
- Each test cleans up before and after execution
- MongoDB Atlas Local includes Atlas Vector Search, which is required for vector search tests
