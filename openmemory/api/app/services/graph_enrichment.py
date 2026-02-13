"""
Graph Enrichment Service

Enriches memory responses with entity and relationship data from Neo4j graph store.
This solves the problem where LLMs query memories but don't get semantic context
about what entities mean (e.g., "Josephine" is a Person, not just a string).
"""

import logging
import os
from typing import Dict, List, Optional
from uuid import UUID

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class GraphEnrichmentService:
    """Service to enrich memories with graph data"""

    def __init__(self):
        """Initialize Neo4j connection"""
        self.driver = None
        self._initialize_driver()

    def _initialize_driver(self):
        """Initialize Neo4j driver if configured"""
        url = os.environ.get('NEO4J_URL')
        username = os.environ.get('NEO4J_USERNAME')
        password = os.environ.get('NEO4J_PASSWORD')

        if not all([url, username, password]):
            logger.warning("Neo4j not configured - graph enrichment disabled")
            return

        try:
            self.driver = GraphDatabase.driver(url, auth=(username, password))
            logger.info("Graph enrichment service initialized")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.driver = None

    def close(self):
        """Close Neo4j driver"""
        if self.driver:
            self.driver.close()

    async def enrich_memory(self, memory: Dict) -> Dict:
        """
        Enrich a single memory with graph data

        Mem0's Neo4j schema:
        - Entities are stored as nodes with labels: person, location, organization, etc.
        - Entities have properties: name, user_id, created, mentions
        - Relationships connect entities directly (no Memory nodes)

        Args:
            memory: Memory dict with 'id' and 'memory' fields

        Returns:
            Enriched memory with 'entities' and 'relationships' fields
        """
        if not self.driver:
            return memory

        memory_content = memory.get('memory') or memory.get('content', '')
        metadata = memory.get('metadata_', {}) or memory.get('metadata', {})

        if not memory_content:
            return memory

        try:
            with self.driver.session() as session:
                # Extract entity names from memory content (simple word extraction)
                # In production, you'd use NER or mem0's entity extraction
                import re
                words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', memory_content)

                # Also check metadata for entity names
                if 'entities' in metadata and isinstance(metadata['entities'], list):
                    words.extend(metadata['entities'])

                if not words:
                    return memory

                # Query for entities by name (case-insensitive)
                entities_query = """
                UNWIND $names as search_name
                MATCH (e)
                WHERE toLower(e.name) = toLower(search_name)
                RETURN DISTINCT e.name as name,
                       labels(e) as labels,
                       properties(e) as properties
                LIMIT 20
                """

                entities_result = session.run(entities_query, names=list(set(words)))
                entities = []
                entity_names = set()

                for record in entities_result:
                    # Get the primary label (entity type)
                    labels = [l for l in record['labels'] if l != '__User__']
                    entity_type = labels[0].upper() if labels else 'ENTITY'

                    entity_name = record['name']
                    entity_names.add(entity_name)

                    entities.append({
                        'name': entity_name,
                        'type': entity_type.upper(),
                        'label': entity_type.title(),
                        'properties': dict(record['properties'])
                    })

                # Query for relationships between found entities
                if entity_names:
                    relationships_query = """
                    UNWIND $names as search_name
                    MATCH (e1)-[r]->(e2)
                    WHERE toLower(e1.name) = toLower(search_name)
                    RETURN e1.name as source,
                           type(r) as relation,
                           e2.name as target,
                           labels(e1) as source_labels,
                           labels(e2) as target_labels,
                           properties(r) as properties
                    LIMIT 20
                    """

                    relationships_result = session.run(relationships_query, names=list(entity_names))
                    relationships = []

                    for record in relationships_result:
                        source_labels = [l for l in record['source_labels'] if l != '__User__']
                        target_labels = [l for l in record['target_labels'] if l != '__User__']

                        relationships.append({
                            'source': record['source'],
                            'relation': record['relation'].upper().replace('_', '_'),
                            'target': record['target'],
                            'source_type': source_labels[0].upper() if source_labels else 'ENTITY',
                            'target_type': target_labels[0].upper() if target_labels else 'ENTITY',
                            'properties': dict(record['properties']) if record['properties'] else {}
                        })

                # Add graph data to memory
                enriched = memory.copy()
                enriched['entities'] = entities
                enriched['relationships'] = relationships
                enriched['graph_enriched'] = len(entities) > 0 or len(relationships) > 0

                return enriched

        except Exception as e:
            logger.error(f"Failed to enrich memory: {e}")
            logger.exception(e)
            return memory

    async def enrich_memories(self, memories: List[Dict]) -> List[Dict]:
        """
        Enrich multiple memories with graph data

        Args:
            memories: List of memory dicts

        Returns:
            List of enriched memories
        """
        if not self.driver:
            return memories

        enriched_memories = []
        for memory in memories:
            enriched = await self.enrich_memory(memory)
            enriched_memories.append(enriched)

        return enriched_memories

    async def get_entity_context(self, entity_name: str, user_id: Optional[str] = None) -> Dict:
        """
        Get full context for an entity (all relationships and properties)

        Args:
            entity_name: Name of the entity to look up
            user_id: Optional user ID to filter by

        Returns:
            Dict with entity details, related entities, and relationships
        """
        if not self.driver:
            return {}

        try:
            with self.driver.session() as session:
                # Build query with case-insensitive name match and optional user filter
                query = """
                MATCH (e)
                WHERE toLower(e.name) = toLower($entity_name)
                """

                if user_id:
                    query += "AND e.user_id = $user_id\n"

                query += """
                OPTIONAL MATCH (e)-[r]-(related)
                RETURN e,
                       labels(e) as entity_labels,
                       properties(e) as entity_props,
                       collect({
                           relation: type(r),
                           related_name: related.name,
                           related_labels: labels(related),
                           direction: CASE WHEN startNode(r) = e THEN 'outgoing' ELSE 'incoming' END
                       }) as relationships
                LIMIT 1
                """

                params = {"entity_name": entity_name}
                if user_id:
                    params["user_id"] = user_id

                result = session.run(query, params)
                record = result.single()

                if not record:
                    return {}

                # Filter out internal labels
                entity_labels = [l for l in record['entity_labels'] if l != '__User__']

                return {
                    'name': entity_name,
                    'type': entity_labels[0].upper() if entity_labels else 'ENTITY',
                    'labels': entity_labels,
                    'properties': dict(record['entity_props']),
                    'relationships': [
                        {
                            'relation': rel['relation'],
                            'related_entity': rel['related_name'],
                            'related_type': rel['related_labels'][0].upper() if rel['related_labels'] else 'ENTITY',
                            'direction': rel['direction']
                        }
                        for rel in record['relationships'] if rel['related_name']
                    ]
                }

        except Exception as e:
            logger.error(f"Failed to get entity context for {entity_name}: {e}")
            logger.exception(e)
            return {}


# Global instance
_enrichment_service = None


def get_enrichment_service() -> GraphEnrichmentService:
    """Get or create global enrichment service instance"""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = GraphEnrichmentService()
    return _enrichment_service
