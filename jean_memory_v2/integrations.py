"""
Jean Memory V2 Integrations
===========================

This module copies the exact working integration patterns from the openmemory services
to ensure compatibility and proper functionality with Mem0 and Graphiti.
Enhanced with ontology support for structured entity extraction.
"""

import logging
import asyncio
import time
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from mem0 import Memory
from neo4j import AsyncGraphDatabase

from .ontology import get_ontology_config

logger = logging.getLogger(__name__)


class Mem0Integration:
    """
    Mem0 integration copied from working openmemory service
    Handles entities, relationships, and semantic connections with user isolation
    """
    
    def __init__(self, config: Dict):
        """Initialize mem0 service with configuration"""
        self.config = config
        self.memory = None
        self.neo4j_driver = None
        self.initialized = False
        
        # Extract configuration
        self.neo4j_uri = config.get("NEO4J_URI")
        self.neo4j_user = config.get("NEO4J_USER") 
        self.neo4j_password = config.get("NEO4J_PASSWORD")
        self.qdrant_url = config.get("QDRANT_URL")
        self.qdrant_api_key = config.get("QDRANT_API_KEY")
        self.openai_api_key = config.get("OPENAI_API_KEY")
        self.collection_prefix = config.get("COLLECTION_PREFIX", "jean_memory_v2")
        
    def _get_mem0_config(self, collection_suffix: str = "default") -> Dict:
        """Build mem0 configuration dictionary with exact working pattern"""
        timestamp = int(time.time())
        
        return {
            "graph_store": {
                "provider": "neo4j",
                "config": {
                    "url": self.neo4j_uri,
                    "username": self.neo4j_user,
                    "password": self.neo4j_password
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "url": self.qdrant_url,
                    "api_key": self.qdrant_api_key,
                    "collection_name": f"{self.collection_prefix}_{collection_suffix}_{timestamp}",
                    "embedding_model_dims": 1536  # OpenAI text-embedding-3-small dimension
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "api_key": self.openai_api_key,
                    "model": "gpt-4o-mini"
                }
            },
            "embedder": {
                "provider": "openai", 
                "config": {
                    "api_key": self.openai_api_key,
                    "model": "text-embedding-3-small"
                }
            },
            "version": "v1.1",
            "history_db_path": f"/tmp/mem0_history_{timestamp}_{collection_suffix}.db",
            "custom_fact_extraction_prompt": """
Extract only factual, personal, and contextual information that would be useful for future reference. 
Focus on user preferences, experiences, behaviors, and important details. Ignore generic responses.

Examples:
Input: "Hello there"
Output: {"facts": []}

Input: "The weather is nice today"  
Output: {"facts": []}

Input: "I love Italian food, especially pasta carbonara"
Output: {"facts": ["User loves Italian food", "User particularly enjoys pasta carbonara"]}

Input: "I'm planning a trip to Japan next month for business"
Output: {"facts": ["User planning trip to Japan", "Trip scheduled for next month", "Business purpose travel"]}

Input: "I've been working as a software engineer for 5 years at Google"
Output: {"facts": ["User works as software engineer", "5 years experience", "Works at Google"]}

Input: "I prefer morning workouts at the gym"
Output: {"facts": ["User prefers morning workouts", "User goes to gym"]}

Return facts in JSON format as shown above, focusing on personal preferences, experiences, and contextual information.
"""
        }
        
    async def _ensure_qdrant_collection_ready(self, collection_name: str):
        """Ensure Qdrant collection exists and has proper user_id indexing - copied from working code"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            
            # Create Qdrant client
            client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
            
            # Wait for collection to be created by mem0
            max_retries = 15
            collection_found = False
            
            logger.info(f"Waiting for collection {collection_name} to be created by Mem0...")
            
            for attempt in range(max_retries):
                try:
                    collections = client.get_collections().collections
                    collection_names = [col.name for col in collections]
                    if collection_name in collection_names:
                        logger.info(f"✅ Collection {collection_name} found")
                        collection_found = True
                        break
                    else:
                        logger.debug(f"Collection {collection_name} not found yet, waiting... (attempt {attempt + 1})")
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.debug(f"Error checking collections (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(1)
            
            if not collection_found:
                logger.warning(f"Collection {collection_name} not found after {max_retries} attempts")
                return
            
            # Create indexes for this new collection
            logger.info(f"Setting up indexes for new collection: {collection_name}")
            
            # Create user_id keyword index with retry logic
            keyword_success = False
            for attempt in range(3):
                try:
                    client.create_payload_index(
                        collection_name=collection_name,
                        field_name="user_id",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    logger.info(f"✅ user_id keyword index created for {collection_name}")
                    keyword_success = True
                    break
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.info(f"✅ user_id keyword index already exists for {collection_name}")
                        keyword_success = True
                        break
                    else:
                        if attempt < 2:
                            logger.debug(f"Keyword index creation attempt {attempt + 1} failed, retrying...")
                            await asyncio.sleep(1)
                        else:
                            logger.warning(f"Could not create keyword index after 3 attempts: {e}")
            
            # Create user_id UUID index with retry logic
            uuid_success = False
            for attempt in range(3):
                try:
                    client.create_payload_index(
                        collection_name=collection_name,
                        field_name="user_id",
                        field_schema=models.PayloadSchemaType.UUID,
                    )
                    logger.info(f"✅ user_id UUID index created for {collection_name}")
                    uuid_success = True
                    break
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.info(f"✅ user_id UUID index already exists for {collection_name}")
                        uuid_success = True
                        break
                    else:
                        if attempt < 2:
                            logger.debug(f"UUID index creation attempt {attempt + 1} failed, retrying...")
                            await asyncio.sleep(1)
                        else:
                            logger.warning(f"Could not create UUID index after 3 attempts: {e}")
            
            # Verify both indexes are working
            if keyword_success and uuid_success:
                logger.info(f"✅ All indexes ready for {collection_name}")
                # await asyncio.sleep(2)  # REMOVED: Eliminated index wait for performance
                
        except Exception as e:
            logger.error(f"Failed to ensure collection readiness for {collection_name}: {e}")
            raise
    
    async def initialize(self, collection_suffix: str = "default"):
        """Initialize mem0 instance - copied from working code"""
        if self.initialized:
            return
            
        logger.info("Initializing Mem0 integration service...")
        
        try:
            # Get mem0 configuration
            mem0_config = self._get_mem0_config(collection_suffix)
            self.collection_name = mem0_config["vector_store"]["config"]["collection_name"]
            
            # Initialize mem0 Memory instance using exact working pattern
            self.memory = Memory.from_config(config_dict=mem0_config)
            
            # Ensure collection has proper indexes
            await self._ensure_qdrant_collection_ready(self.collection_name)
            
            # Initialize direct Neo4j driver for validation
            self.neo4j_driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            self.initialized = True
            logger.info("Mem0 integration service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Mem0 service: {e}")
            raise

    async def close(self):
        """Clean up resources"""
        if self.neo4j_driver:
            await self.neo4j_driver.close()
        self.initialized = False
        
    async def ingest_memory(self, user_id: str, memory_text: str, metadata: Dict = None) -> str:
        """Ingest a single memory - using working pattern"""
        if not self.initialized:
            await self.initialize()
            
        try:
            result = self.memory.add(
                memory_text,
                user_id=user_id,
                metadata=metadata or {}
            )
            
            logger.debug(f"Added memory to Mem0 for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to ingest memory for user {user_id}: {e}")
            raise
            
    async def search_memories(self, user_id: str, query: str, limit: int = 10) -> List[Dict]:
        """Search memories using working pattern"""
        if not self.initialized:
            await self.initialize()
            
        try:
            results = self.memory.search(
                query=query,
                user_id=user_id,
                limit=limit
            )
            
            logger.debug(f"Searched memories for user {user_id}, found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search memories for user {user_id}: {e}")
            raise
            
    async def delete_all_memories(self, user_id: str) -> Dict:
        """Delete all memories for a user"""
        if not self.initialized:
            await self.initialize()
            
        try:
            result = self.memory.delete_all(user_id=user_id)
            logger.debug(f"Deleted all memories for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete memories for user {user_id}: {e}")
            raise


class GraphitiIntegration:
    """
    Graphiti integration copied from working openmemory service
    Handles episodes, temporal context, and time-based relationships with user isolation
    """
    
    def __init__(self, config: Dict):
        """Initialize Graphiti service with configuration"""
        self.config = config
        self.graphiti = None
        self.neo4j_driver = None
        self.initialized = False
        
        # Extract configuration
        self.neo4j_uri = config.get("NEO4J_URI")
        self.neo4j_user = config.get("NEO4J_USER")
        self.neo4j_password = config.get("NEO4J_PASSWORD")
        self.openai_api_key = config.get("OPENAI_API_KEY")
        
    async def initialize(self):
        """Initialize Graphiti instance - copied from working code"""
        if self.initialized:
            return
            
        logger.info("Initializing Graphiti integration service...")
        
        try:
            # Import necessary Graphiti components for proper OpenAI configuration
            from openai import AsyncOpenAI
            from graphiti_core import Graphiti
            from graphiti_core.llm_client import OpenAIClient
            from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
            
            # Create properly configured OpenAI client
            openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            
            # Initialize Graphiti with explicit OpenAI configuration
            self.graphiti = Graphiti(
                uri=self.neo4j_uri,
                user=self.neo4j_user,
                password=self.neo4j_password,
                llm_client=OpenAIClient(client=openai_client),
                embedder=OpenAIEmbedder(
                    config=OpenAIEmbedderConfig(
                        embedding_model="text-embedding-3-small"
                    ),
                    client=openai_client
                )
            )
            
            # Build indices and constraints
            try:
                await self.graphiti.build_indices_and_constraints()
                logger.info("Graphiti indices and constraints built successfully")
            except Exception as e:
                logger.debug(f"Indices might already exist: {e}")
                
            # Initialize direct Neo4j driver for validation
            self.neo4j_driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            self.initialized = True
            logger.info("Graphiti integration service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Graphiti service: {e}")
            raise

    def _format_for_openai(self, content: Any) -> str:
        """Formats data for OpenAI API compatibility - copied from working code"""
        content_str = ""
        if isinstance(content, str):
            content_str = content
        elif isinstance(content, (dict, list)):
            try:
                content_str = json.dumps(content)
            except Exception:
                content_str = str(content)
        else:
            content_str = str(content)

        return content_str
            
    async def close(self):
        """Clean up resources"""
        if self.graphiti:
            await self.graphiti.close()
        if self.neo4j_driver:
            await self.neo4j_driver.close()
        self.initialized = False
        
    async def ingest_memory(self, user_id: str, memory_text: str, metadata: Dict = None) -> str:
        """Ingest a single memory as a Graphiti episode with ontology support"""
        if not self.initialized:
            await self.initialize()
            
        try:
            from graphiti_core.nodes import EpisodeType
            
            # Use current timestamp
            created_at = datetime.now(timezone.utc)
            
            # Format content for OpenAI
            formatted_content = self._format_for_openai(memory_text)

            # Add episode with user namespacing (group_id)
            episode_name = f"memory_{user_id}_{created_at.timestamp()}"
            
            # Get ontology configuration for structured entity extraction
            ontology_config = get_ontology_config()
            
            logger.info(f"🕸️ APPLYING ONTOLOGY TO GRAPHITI EPISODE: {episode_name}")
            logger.info(f"   Entity types: {len(ontology_config.get('entity_types', {}))}")
            logger.info(f"   Edge types: {len(ontology_config.get('edge_types', {}))}")
            logger.info(f"   Edge mappings: {len(ontology_config.get('edge_type_map', {}))}")
            
            result = await self.graphiti.add_episode(
                name=episode_name,
                episode_body=formatted_content,
                source=EpisodeType.text,
                source_description=f"Memory from user {user_id}",
                reference_time=created_at,
                group_id=user_id,  # Use user_id as namespace
                # Include ontology for structured entity extraction
                entity_types=ontology_config.get("entity_types", {}),
                edge_types=ontology_config.get("edge_types", {}),
                edge_type_map=ontology_config.get("edge_type_map", {}),
                excluded_entity_types=ontology_config.get("excluded_entity_types", [])
            )
            
            logger.info(f"✅ ONTOLOGY APPLIED TO GRAPHITI EPISODE: {episode_name}")
            logger.debug(f"   Episode result: {result}")
            return episode_name
            
        except Exception as e:
            logger.error(f"Failed to ingest memory as episode for user {user_id}: {e}")
            raise
            
    async def search_episodes(self, user_id: str, query: str, limit: int = 10) -> List[Dict]:
        """Search episodes using working pattern"""
        if not self.initialized:
            await self.initialize()
            
        try:
            results = await self.graphiti.search(
                query=query,
                group_id=user_id,  # Use user_id for isolation
                limit=limit
            )
            
            # Convert results to dictionaries
            search_results = []
            for edge in results:
                search_results.append({
                    'id': edge.uuid,
                    'fact': edge.fact,
                    'score': getattr(edge, 'score', None),
                    'created_at': edge.created_at
                })
            
            logger.debug(f"Searched episodes for user {user_id}, found {len(search_results)} results")
            return search_results
            
        except Exception as e:
            logger.error(f"Failed to search episodes for user {user_id}: {e}")
            raise 