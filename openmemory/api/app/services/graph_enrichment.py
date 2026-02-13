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

                # Query for entities by name - aggregate ALL nodes with same name
                # This handles cases like "Skye" having 3 nodes with different properties
                entities_query = """
                UNWIND $names as search_name
                MATCH (e)
                WHERE toLower(e.name) = toLower(search_name)
                WITH e.name as name,
                     collect(DISTINCT labels(e)) as all_labels,
                     collect(properties(e)) as all_properties,
                     sum(COALESCE(e.mentions, 0)) as total_mentions,
                     min(e.created) as first_created
                RETURN name,
                       all_labels,
                       all_properties,
                       total_mentions,
                       first_created
                LIMIT 20
                """

                entities_result = session.run(entities_query, names=list(set(words)))
                entities = []
                entity_names = set()
                seen_entities = set()  # Track which entities we've already added
                relationships = []  # Initialize here to avoid UnboundLocalError

                for record in entities_result:
                    entity_name = record['name']

                    # Get all unique labels across all nodes with this name
                    all_label_sets = record['all_labels']
                    all_labels = []
                    for label_set in all_label_sets:
                        all_labels.extend([l for l in label_set if l != '__User__'])
                    all_labels = list(set(all_labels))

                    # Use the first label as primary type
                    entity_type = all_labels[0].upper() if all_labels else 'ENTITY'

                    # Skip if we've already added this entity
                    entity_key = entity_name.lower()
                    if entity_key in seen_entities:
                        continue

                    seen_entities.add(entity_key)
                    entity_names.add(entity_name)

                    # Merge properties from all nodes with this name
                    all_properties = record['all_properties']
                    merged_props = {}
                    for props in all_properties:
                        for k, v in props.items():
                            if k not in ['embedding', 'embeddings', 'vector', 'name', 'user_id', 'created', 'mentions'] and not k.startswith('_'):
                                merged_props[k] = v  # Later values override earlier ones

                    entity_dict = {
                        'name': entity_name,
                        'type': entity_type.upper(),
                        'types': [t.upper() for t in all_labels],  # All types across nodes
                        'label': entity_type.title(),
                        'properties': merged_props if merged_props else None
                    }

                    # Add aggregated mentions and earliest created timestamp
                    if record['total_mentions'] and record['total_mentions'] > 0:
                        entity_dict['mentions'] = record['total_mentions']
                    if record['first_created']:
                        entity_dict['created_at'] = record['first_created']

                    entities.append(entity_dict)

                # Query for relationships - include both entity-to-entity AND user-to-entity
                if entity_names:
                    relationships_query = """
                    UNWIND $names as search_name
                    // Find relationships where entity is source OR target
                    MATCH (e1)-[r]->(e2)
                    WHERE toLower(e1.name) = toLower(search_name)
                       OR toLower(e2.name) = toLower(search_name)
                    RETURN e1.name as source,
                           type(r) as relation,
                           e2.name as target,
                           labels(e1) as source_labels,
                           labels(e2) as target_labels,
                           properties(r) as properties
                    LIMIT 50
                    """

                    relationships_result = session.run(relationships_query, names=list(entity_names))
                    seen_rels = set()  # Deduplicate relationships

                    for record in relationships_result:
                        source_labels = record['source_labels']
                        target_labels = record['target_labels']

                        # Handle __User__ nodes - translate to "You" or user's identity
                        source_name = record['source']
                        target_name = record['target']

                        # Filter labels
                        source_labels_filtered = [l for l in source_labels if l != '__User__']
                        target_labels_filtered = [l for l in target_labels if l != '__User__']

                        # If source is __User__, show it as "You"
                        if '__User__' in source_labels and not source_labels_filtered:
                            source_name = "You"
                            source_type = "USER"
                        else:
                            source_type = source_labels_filtered[0].upper() if source_labels_filtered else 'ENTITY'

                        # If target is __User__, show it as "You"
                        if '__User__' in target_labels and not target_labels_filtered:
                            target_name = "You"
                            target_type = "USER"
                        else:
                            target_type = target_labels_filtered[0].upper() if target_labels_filtered else 'ENTITY'

                        # Create unique key for deduplication
                        rel_key = (source_name.lower(), record['relation'].lower(), target_name.lower())
                        if rel_key in seen_rels:
                            continue
                        seen_rels.add(rel_key)

                        relationships.append({
                            'source': source_name,
                            'relation': record['relation'].upper().replace('_', '_'),
                            'target': target_name,
                            'source_type': source_type,
                            'target_type': target_type,
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
