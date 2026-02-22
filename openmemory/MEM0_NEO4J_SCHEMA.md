# Mem0 Neo4j Schema

## Overview

This document describes mem0's actual Neo4j graph schema based on inspection of a live database.

## Schema Structure

### Nodes (Entities)

Entities are stored **directly as nodes** with their entity type as the label.

#### Common Node Labels

```
person              - People (Sarah, John, etc.)
location            - Places (San Francisco, New York)
organization        - Companies, groups (Google, NASA)
date                - Temporal references (March 20th, 2024)
event               - Occurrences (birthday, meeting)
product             - Items, goods
food                - Cuisine, meals
pet/dog/animal      - Animals
activity            - Actions, hobbies
concept             - Abstract ideas
time                - Time references
object              - Physical things
__User__            - Internal user tracking (filter out)
```

### Node Properties

Common properties on entity nodes:

```json
{
  "name": "Sarah",           // Entity name
  "user_id": "user123",      // Owner of this memory
  "created": 1234567890,     // Timestamp
  "mentions": 5              // How many times mentioned
}
```

### Relationships

Relationships connect entities **directly** (no intermediate Memory nodes).

#### Common Relationship Types

```
has_issues_with    - Problem relationships
works_at           - Employment
lives_in           - Residence
knows              - Social connections
likes              - Preferences
uses               - Tool/technology usage
learns             - Educational interests
related_to         - General associations
```

### Example Graph Structure

```cypher
// Actual mem0 schema
(sarah:person {name: "Sarah", user_id: "user123"})
  -[:works_at]->
(google:organization {name: "Google"})

(sarah)-[:lives_in]->(sf:location {name: "San Francisco"})

(sarah)-[:likes]->(coffee:beverage {name: "coffee"})

// NOT this (common misconception)
(memory:Memory {id: "mem_123"})
  -[:HAS_ENTITY]->
(sarah:person)
```

## Querying the Schema

### Get All Node Labels

```cypher
CALL db.labels()
```

### Get All Relationship Types

```cypher
CALL db.relationshipTypes()
```

### Find Entities by Name

```cypher
MATCH (e)
WHERE toLower(e.name) = toLower("Sarah")
RETURN e, labels(e), properties(e)
```

### Find Entity Relationships

```cypher
MATCH (e {name: "Sarah"})-[r]-(related)
RETURN e, type(r), related
```

### Find Entities by User

```cypher
MATCH (e)
WHERE e.user_id = "user123"
RETURN e, labels(e)
```

## Schema Statistics (Example Database)

```
Total Nodes: 84
Total Relationships: 57

Node Type Distribution:
- person: 12
- __User__: 14 (internal)
- location: 5
- organization: 2
- date: 3
- event: 4
- product: 3
- concept: 4
- pet: 1
- beverage: 2
- [... and more]
```

## Key Differences from Common Assumptions

### ❌ Common Misconception

```cypher
// People often assume this structure:
(Memory)-[:HAS_ENTITY]->(Entity)
```

### ✅ Actual Structure

```cypher
// Mem0 actually uses:
(Entity)-[:relationship_type]->(Entity)

// Entities ARE nodes, not connected to Memory nodes
```

## Integration with Enrichment Service

### How Enrichment Works

1. **Extract entity names** from memory content (capitalized words)
2. **Query Neo4j** for matching entities by name
3. **Find relationships** between discovered entities
4. **Return** entity types and relationships

### Example Enrichment Flow

```python
# Memory content
memory = "Sarah loves coffee and works at Google in San Francisco"

# Step 1: Extract entity names
entities = ["Sarah", "Google", "San Francisco"]

# Step 2: Query Neo4j
MATCH (e)
WHERE e.name IN ["Sarah", "Google", "San Francisco"]
RETURN e, labels(e), properties(e)

# Result:
# - Sarah (PERSON)
# - Google (ORGANIZATION)
# - San Francisco (LOCATION)

# Step 3: Find relationships
MATCH (e1)-[r]->(e2)
WHERE e1.name IN [...] AND e2.name IN [...]
RETURN e1.name, type(r), e2.name

# Result:
# - Sarah -[works_at]-> Google
# - Sarah -[lives_in]-> San Francisco
```

## API Endpoints

### View Graph Data

```bash
# Get graph statistics
curl http://localhost:8765/api/v1/graph/stats

# Get graph data (limited)
curl "http://localhost:8765/api/v1/graph/data?limit=50"

# Search for entity
curl "http://localhost:8765/api/v1/graph/search?query=Sarah"
```

### Enriched Memory Query

```bash
# Get memories with graph enrichment
curl -X POST http://localhost:8765/api/v1/memories/filter/enriched \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "page": 1, "size": 10}'
```

## Schema Evolution

Mem0 automatically creates entities and relationships as memories are added:

1. **Memory Created**: "Sarah works at Google"
2. **Mem0 Extracts**: Entities (Sarah, Google) and relationship (works_at)
3. **Neo4j Updated**:
   - Creates/updates `(sarah:person {name: "Sarah"})`
   - Creates/updates `(google:organization {name: "Google"})`
   - Creates relationship `(sarah)-[:works_at]->(google)`

## Best Practices

### Entity Name Extraction

```python
# Simple: Capitalized words
import re
names = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)

# Better: Use NER (Named Entity Recognition)
# Or check metadata['entities'] if available
```

### Case-Insensitive Queries

Always use case-insensitive matching:

```cypher
WHERE toLower(e.name) = toLower($search_name)
```

### Filter Internal Labels

Remove internal labels like `__User__`:

```python
labels = [l for l in record['labels'] if l != '__User__']
```

### Normalize Entity Types

Convert to uppercase for consistency:

```python
entity_type = labels[0].upper()  # PERSON, LOCATION, etc.
```

## Troubleshooting

### No Entities Found

**Problem**: Enrichment returns no entities

**Causes**:
1. Entity names not in graph yet (memory not processed by mem0)
2. Name extraction failed (no capitalized words)
3. User ID mismatch

**Solution**:
```cypher
// Check if entities exist
MATCH (e)
WHERE e.user_id = "your_user_id"
RETURN count(e), labels(e)
```

### Wrong Relationships

**Problem**: Relationships don't match memory content

**Causes**:
1. Relationships created from different memories
2. Entity name collision (multiple "John"s)

**Solution**:
```cypher
// Check entity uniqueness
MATCH (e:person {name: "John"})
RETURN e, e.user_id, e.mentions
```

## References

- [Neo4j Graph Database Concepts](https://neo4j.com/docs/getting-started/appendix/graphdb-concepts/)
- [Mem0 Graph Memory Documentation](https://docs.mem0.ai/open-source/features/graph-memory)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
