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

        Args:
            memory: Memory dict with 'id' and 'memory' fields

        Returns:
            Enriched memory with 'entities' and 'relationships' fields
        """
        if not self.driver:
            return memory

        memory_id = str(memory.get('id'))
        if not memory_id:
            return memory

        try:
            with self.driver.session() as session:
                # Query for entities connected to this memory
                entities_query = """
                MATCH (m:Memory {id: $memory_id})-[:HAS_ENTITY]->(e)
                RETURN e.name as name,
                       labels(e) as labels,
                       properties(e) as properties
                """

                entities_result = session.run(entities_query, memory_id=memory_id)
                entities = []

                for record in entities_result:
                    # Get the primary label (first non-Memory label)
                    labels = [l for l in record['labels'] if l != 'Memory']
                    entity_type = labels[0] if labels else 'Entity'

                    entities.append({
                        'name': record['name'],
                        'type': entity_type,
                        'label': entity_type,
                        'properties': dict(record['properties'])
                    })

                # Query for relationships involving entities in this memory
                relationships_query = """
                MATCH (m:Memory {id: $memory_id})-[:HAS_ENTITY]->(e1)
                MATCH (e1)-[r]->(e2)
                WHERE NOT type(r) = 'HAS_ENTITY'
                RETURN e1.name as source,
                       type(r) as relation,
                       e2.name as target,
                       labels(e1) as source_labels,
                       labels(e2) as target_labels,
                       properties(r) as properties
                LIMIT 20
                """

                relationships_result = session.run(relationships_query, memory_id=memory_id)
                relationships = []

                for record in relationships_result:
                    relationships.append({
                        'source': record['source'],
                        'relation': record['relation'],
                        'target': record['target'],
                        'source_type': record['source_labels'][0] if record['source_labels'] else 'Entity',
                        'target_type': record['target_labels'][0] if record['target_labels'] else 'Entity',
                        'properties': dict(record['properties'])
                    })

                # Add graph data to memory
                enriched = memory.copy()
                enriched['entities'] = entities
                enriched['relationships'] = relationships
                enriched['graph_enriched'] = True

                return enriched

        except Exception as e:
            logger.error(f"Failed to enrich memory {memory_id}: {e}")
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
                # Build query with optional user filter
                query = """
                MATCH (e {name: $entity_name})
                """

                if user_id:
                    query += "WHERE e.user_id = $user_id\n"

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
                """

                params = {"entity_name": entity_name}
                if user_id:
                    params["user_id"] = user_id

                result = session.run(query, params)
                record = result.single()

                if not record:
                    return {}

                entity_labels = [l for l in record['entity_labels'] if l != 'Memory']

                return {
                    'name': entity_name,
                    'type': entity_labels[0] if entity_labels else 'Entity',
                    'labels': entity_labels,
                    'properties': dict(record['entity_props']),
                    'relationships': [
                        {
                            'relation': rel['relation'],
                            'related_entity': rel['related_name'],
                            'related_type': rel['related_labels'][0] if rel['related_labels'] else 'Entity',
                            'direction': rel['direction']
                        }
                        for rel in record['relationships'] if rel['related_name']
                    ]
                }

        except Exception as e:
            logger.error(f"Failed to get entity context for {entity_name}: {e}")
            return {}


# Global instance
_enrichment_service = None


def get_enrichment_service() -> GraphEnrichmentService:
    """Get or create global enrichment service instance"""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = GraphEnrichmentService()
    return _enrichment_service
