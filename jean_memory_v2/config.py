"""
Jean Memory V2 Configuration
============================

Configuration management for API keys, database connections, and system settings.

Updated to rely on environment variables only (no .env file loading)
Use the set_env_all.sh script to set environment variables before running Jean Memory V2
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from .exceptions import ConfigurationError
from .ontology import get_ontology_config
from .custom_fact_extraction import CUSTOM_FACT_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

@dataclass
class JeanMemoryConfig:
    """Configuration class for Jean Memory V2"""
    
    # Core API Keys
    openai_api_key: str
    qdrant_api_key: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    gemini_api_key: Optional[str] = None
    
    # Qdrant Configuration
    qdrant_host: Optional[str] = None
    qdrant_port: Optional[str] = None
    qdrant_url: Optional[str] = None
    qdrant_collection_prefix: str = "jeanmemory_v2"
    
    # Search Configuration
    default_search_limit: int = 20
    max_search_limit: int = 100
    enable_graph_memory: bool = True
    enable_gemini_synthesis: bool = True
    
    # Ingestion Configuration
    batch_size: int = 100
    enable_safety_checks: bool = True
    enable_deduplication: bool = True
    
    # Performance Configuration
    connection_timeout: int = 30
    max_retries: int = 3
    
    # Dynamic Index Configuration
    qdrant_index_wait_time: int = 5
    auto_create_indexes: bool = True
    qdrant_index_retry_count: int = 3
    enable_collection_validation: bool = True
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_required_fields()
        self._setup_qdrant_url()
        self._validate_api_keys()
    
    def _validate_required_fields(self):
        """Validate that all required fields are provided"""
        # Always required fields
        required_fields = [
            'openai_api_key', 'neo4j_uri', 'neo4j_user', 'neo4j_password'
        ]
        
        for field in required_fields:
            value = getattr(self, field)
            if not value or not isinstance(value, str) or not value.strip():
                raise ConfigurationError(f"Required field '{field}' is missing or empty")
        
        # qdrant_api_key is only required for cloud deployments (non-localhost)
        if self.qdrant_host and self.qdrant_host != "localhost":
            if not self.qdrant_api_key or not self.qdrant_api_key.strip():
                raise ConfigurationError("qdrant_api_key is required for cloud Qdrant deployments")
    
    def _setup_qdrant_url(self):
        """Setup Qdrant URL from components if not provided directly"""
        if not self.qdrant_url:
            if self.qdrant_host and self.qdrant_port:
                # Use http for localhost (Docker), https for cloud
                protocol = "http" if self.qdrant_host == "localhost" else "https"
                self.qdrant_url = f"{protocol}://{self.qdrant_host}:{self.qdrant_port}"
            else:
                raise ConfigurationError(
                    "Either 'qdrant_url' or both 'qdrant_host' and 'qdrant_port' must be provided"
                )
    
    def _validate_api_keys(self):
        """Validate API key formats"""
        if not self.openai_api_key.startswith('sk-'):
            raise ConfigurationError("OpenAI API key should start with 'sk-'")
        
        if self.gemini_api_key and not self.gemini_api_key.startswith('AIza'):
            raise ConfigurationError("Gemini API key should start with 'AIza'")
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'JeanMemoryConfig':
        """Create configuration from dictionary"""
        return cls(
            openai_api_key=config_dict.get('OPENAI_API_KEY', ''),
            qdrant_api_key=config_dict.get('QDRANT_API_KEY', ''),
            qdrant_host=config_dict.get('QDRANT_HOST'),
            qdrant_port=config_dict.get('QDRANT_PORT'),
            qdrant_url=config_dict.get('QDRANT_URL'),
            neo4j_uri=config_dict.get('NEO4J_URI', ''),
            neo4j_user=config_dict.get('NEO4J_USER', ''),
            neo4j_password=config_dict.get('NEO4J_PASSWORD', ''),
            gemini_api_key=config_dict.get('GEMINI_API_KEY'),
            qdrant_collection_prefix=config_dict.get('QDRANT_COLLECTION_PREFIX', 'jeanmemory_v2'),
            default_search_limit=int(config_dict.get('DEFAULT_SEARCH_LIMIT', 20)),
            max_search_limit=int(config_dict.get('MAX_SEARCH_LIMIT', 100)),
            enable_graph_memory=config_dict.get('ENABLE_GRAPH_MEMORY', 'true').lower() == 'true',
            enable_gemini_synthesis=config_dict.get('ENABLE_GEMINI_SYNTHESIS', 'true').lower() == 'true',
            batch_size=int(config_dict.get('BATCH_SIZE', 100)),
            enable_safety_checks=config_dict.get('ENABLE_SAFETY_CHECKS', 'true').lower() == 'true',
            enable_deduplication=config_dict.get('ENABLE_DEDUPLICATION', 'true').lower() == 'true',
            connection_timeout=int(config_dict.get('CONNECTION_TIMEOUT', 30)),
            max_retries=int(config_dict.get('MAX_RETRIES', 3)),
            # Dynamic Index Configuration
            qdrant_index_wait_time=int(config_dict.get('QDRANT_INDEX_WAIT_TIME', 5)),
            auto_create_indexes=config_dict.get('AUTO_CREATE_INDEXES', 'true').lower() == 'true',
            qdrant_index_retry_count=int(config_dict.get('QDRANT_INDEX_RETRY_COUNT', 3)),
            enable_collection_validation=config_dict.get('ENABLE_COLLECTION_VALIDATION', 'true').lower() == 'true'
        )
    
    @classmethod
    def from_environment(cls) -> 'JeanMemoryConfig':
        """Create configuration from environment variables"""
        return cls.from_dict(dict(os.environ))
    
    def to_mem0_config(self) -> Dict[str, Any]:
        """
        Convert to Mem0 configuration format with ENHANCED DEDUPLICATION and CUSTOM FACT EXTRACTION
        Uses Jean Memory V2 custom fact extraction prompt for structured entity extraction
        """
        logger.info("🎯 APPLYING CUSTOM FACT EXTRACTION PROMPT TO MEM0 CONFIG")
        logger.info(f"   Prompt length: {len(CUSTOM_FACT_EXTRACTION_PROMPT)} characters")
        logger.info(f"   Prompt examples: {CUSTOM_FACT_EXTRACTION_PROMPT.count('Input:')}")
        
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "url": self.qdrant_url,
                    "api_key": self.qdrant_api_key,
                    "collection_name": f"{self.qdrant_collection_prefix}_mem0"
                }
            },
            "graph_store": {
                "provider": "neo4j",
                "config": {
                    "url": self.neo4j_uri,
                    "username": self.neo4j_user,
                    "password": self.neo4j_password
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-2024-08-06",
                    "api_key": self.openai_api_key,
                    "temperature": 0.2,
                    "max_tokens": 2000
                }
            },
            # 🎯 CUSTOM FACT EXTRACTION: Use Jean Memory V2 ontology-based prompt
            "custom_fact_extraction_prompt": CUSTOM_FACT_EXTRACTION_PROMPT,
            
            # 🎯 OPTIMIZATION: Enhanced deduplication settings
            "custom_prompt": {
                "fact_extraction": (
                    "Extract entities and relationships that are personally relevant "
                    "to the user. Focus on people, places, preferences, activities, "
                    "and meaningful connections. Ignore generic or common knowledge. "
                    "If this information is similar to existing memories, UPDATE the existing memory "
                    "rather than creating duplicates. Prioritize consolidation over creation."
                ),
                "update_memory": (
                    "Update the memory graph by merging new information with existing entries. "
                    "If new facts conflict with old ones, keep the most recent and informative version. "
                    "Always prefer updating existing memories over creating new ones when content overlaps."
                )
            },
            # Enhanced deduplication and consolidation
            "memory_config": {
                "enable_deduplication": True,
                "similarity_threshold": 0.8,  # Higher threshold for more aggressive deduplication
                "consolidate_memories": True,
                "update_existing": True,
                "max_memories_per_entity": 3  # Limit memories per entity to force consolidation
            },
            # Version specification for Mem0 v1.1 features
            "version": "v1.1"
        }
        
        logger.info("✅ CUSTOM FACT EXTRACTION PROMPT APPLIED TO MEM0 CONFIG")
        return config
    
    def to_graphiti_config(self) -> Dict[str, Any]:
        """Convert to Graphiti configuration format with ontology support"""
        logger.info("🕸️ APPLYING ONTOLOGY TO GRAPHITI CONFIG")
        
        base_config = {
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "neo4j_password": self.neo4j_password,
            "openai_api_key": self.openai_api_key
        } 
        
        # Add ontology configuration
        ontology_config = get_ontology_config()
        logger.info(f"   Entity types: {len(ontology_config['entity_types'])}")
        logger.info(f"   Edge types: {len(ontology_config['edge_types'])}")
        logger.info(f"   Edge mappings: {len(ontology_config['edge_type_map'])}")
        
        base_config.update(ontology_config)
        
        logger.info("✅ ONTOLOGY APPLIED TO GRAPHITI CONFIG")
        return base_config
    
    def get_ontology_config(self) -> Dict[str, Any]:
        """Get the ontology configuration for use with Graphiti"""
        return get_ontology_config() 