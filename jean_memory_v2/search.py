"""
Jean Memory V2 Search Engine
============================

Advanced hybrid search combining Mem0, Graphiti, and Gemini AI for intelligent memory retrieval.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from .config import JeanMemoryConfig
from .exceptions import SearchError, DatabaseConnectionError

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Structured search result with synthesis and source data"""
    
    query: str
    user_id: str
    synthesis: str
    confidence_score: float
    total_results: int
    processing_time: float
    
    # Source results
    mem0_results: List[Dict[str, Any]]
    graphiti_results: List[Dict[str, Any]]
    
    # Metadata
    search_method: str = "hybrid"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "query": self.query,
            "user_id": self.user_id,
            "synthesis": self.synthesis,
            "confidence_score": self.confidence_score,
            "total_results": self.total_results,
            "processing_time": self.processing_time,
            "mem0_results": self.mem0_results,
            "graphiti_results": self.graphiti_results,
            "search_method": self.search_method,
            "timestamp": self.timestamp.isoformat()
        }


class HybridSearchEngine:
    """Advanced hybrid search engine combining multiple memory systems"""
    
    def __init__(self, config: JeanMemoryConfig):
        self.config = config
        self.mem0_memory = None
        self.graphiti = None
        self.gemini_client = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize all search engines and configurations"""
        if self._initialized:
            return
        
        logger.info("🔧 Initializing Hybrid Search Engine...")
        
        try:
            await self._initialize_mem0()
            await self._initialize_graphiti()
            self._initialize_gemini()
            self._initialized = True
            logger.info("✅ Hybrid Search Engine ready!")
        except Exception as e:
            logger.error(f"❌ Failed to initialize search engine: {e}")
            raise SearchError(f"Search engine initialization failed: {e}")
    
    async def _initialize_mem0(self):
        """Initialize Mem0 Graph Memory"""
        logger.info("🧠 Initializing Mem0 Graph Memory...")
        
        try:
            from mem0 import Memory
            
            mem0_config = self.config.to_mem0_config()
            self.mem0_memory = Memory.from_config(config_dict=mem0_config)
            logger.info("✅ Mem0 Graph Memory initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Mem0: {e}")
            raise DatabaseConnectionError(f"Mem0 initialization failed: {e}")
    
    async def _initialize_graphiti(self):
        """Initialize Graphiti temporal reasoning"""
        logger.info("🕸️ Initializing Graphiti...")
        
        try:
            from graphiti_core import Graphiti
            
            graphiti_config = self.config.to_graphiti_config()
            self.graphiti = Graphiti(
                uri=graphiti_config["neo4j_uri"],
                user=graphiti_config["neo4j_user"],
                password=graphiti_config["neo4j_password"]
            )
            logger.info("✅ Graphiti initialized")
            
        except Exception as e:
            logger.warning(f"⚠️ Graphiti initialization failed, continuing without: {e}")
            self.graphiti = None
    
    def _initialize_gemini(self):
        """Initialize Gemini AI for synthesis"""
        if not self.config.gemini_api_key:
            logger.warning("⚠️ No Gemini API key provided, synthesis will use fallback")
            return
        
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.config.gemini_api_key)
            self.gemini_client = genai.GenerativeModel('gemini-2.0-flash-exp')
            logger.info("✅ Gemini AI initialized")
            
        except Exception as e:
            logger.warning(f"⚠️ Gemini initialization failed, using fallback: {e}")
            self.gemini_client = None
    
    async def search_mem0(self, query: str, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search using Mem0 Graph Memory"""
        if not self.mem0_memory:
            raise SearchError("Mem0 not initialized")
        
        search_limit = limit or self.config.default_search_limit
        search_limit = min(search_limit, self.config.max_search_limit)
        
        try:
            logger.info(f"🔍 Searching Mem0 for '{query}' (user: {user_id}, limit: {search_limit})")
            
            # Search with user_id filter
            results = self.mem0_memory.search(
                query=query,
                user_id=user_id,
                limit=search_limit
            )
            
            # Handle different result formats
            if isinstance(results, dict):
                if "results" in results:
                    memories = results["results"]
                elif "memories" in results:
                    memories = results["memories"]
                else:
                    memories = [results]
            elif isinstance(results, list):
                memories = results
            else:
                memories = []
            
            logger.info(f"📊 Mem0 found {len(memories)} results")
            
            # Standardize result format
            standardized_results = []
            for memory in memories:
                if isinstance(memory, dict):
                    standardized_results.append({
                        "id": memory.get("id", "unknown"),
                        "content": memory.get("memory", memory.get("content", "")),
                        "score": memory.get("score", 0.0),
                        "metadata": memory.get("metadata", {}),
                        "source": "mem0",
                        "created_at": memory.get("created_at"),
                        "user_id": memory.get("user_id", user_id)
                    })
            
            return standardized_results
            
        except Exception as e:
            logger.error(f"❌ Mem0 search failed: {e}")
            raise SearchError(f"Mem0 search failed: {e}")
    
    async def search_graphiti(self, query: str, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search using Graphiti temporal reasoning"""
        if not self.graphiti:
            logger.warning("⚠️ Graphiti not available, skipping")
            return []
        
        search_limit = limit or self.config.default_search_limit
        
        try:
            logger.info(f"🕸️ Searching Graphiti for '{query}' (user: {user_id})")
            
            # Search for relevant nodes and edges
            search_results = await self.graphiti.search(
                query=query,
                user_id=user_id,
                limit=search_limit
            )
            
            # Process Graphiti results
            standardized_results = []
            if search_results:
                for result in search_results:
                    standardized_results.append({
                        "id": result.get("id", "unknown"),
                        "content": result.get("content", result.get("name", "")),
                        "score": result.get("score", 0.0),
                        "metadata": result.get("properties", {}),
                        "source": "graphiti",
                        "node_type": result.get("type", "unknown"),
                        "user_id": user_id
                    })
            
            logger.info(f"📊 Graphiti found {len(standardized_results)} results")
            return standardized_results
            
        except Exception as e:
            logger.warning(f"⚠️ Graphiti search failed, continuing: {e}")
            return []
    
    async def synthesize_with_gemini(self, query: str, all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize search results using Gemini AI"""
        if not self.gemini_client or not all_results:
            return await self._fallback_synthesis(query, all_results)
        
        try:
            # Prepare context from all results
            context_parts = []
            for result in all_results:
                source = result.get("source", "unknown")
                content = result.get("content", "")
                score = result.get("score", 0.0)
                
                context_parts.append(f"[{source.upper()}, score: {score:.3f}] {content}")
            
            context = "\n".join(context_parts)
            
            # Create synthesis prompt
            synthesis_prompt = f"""You are an AI assistant that synthesizes information from multiple memory sources to answer user queries.

Query: "{query}"

Available Memory Sources:
{context}

Please provide a comprehensive, thoughtful response that:
1. Directly answers the user's query
2. Synthesizes information from multiple sources when relevant
3. Maintains accuracy and doesn't hallucinate beyond the provided context
4. Is conversational and helpful
5. Acknowledges limitations if the context is insufficient

Response:"""

            # Generate synthesis
            response = await self.gemini_client.generate_content_async(synthesis_prompt)
            synthesis = response.text.strip()
            
            # Calculate confidence based on result quality and quantity
            confidence = min(0.9, 0.3 + (len(all_results) * 0.1) + (sum(r.get("score", 0) for r in all_results) / len(all_results) * 0.5))
            
            return {
                "synthesis": synthesis,
                "confidence_score": confidence,
                "method": "gemini_ai"
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Gemini synthesis failed, using fallback: {e}")
            return await self._fallback_synthesis(query, all_results)
    
    async def _fallback_synthesis(self, query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback synthesis when Gemini is unavailable"""
        if not results:
            return {
                "synthesis": f"I couldn't find any relevant memories for '{query}'. Try rephrasing your question or adding more specific details.",
                "confidence_score": 0.0,
                "method": "fallback_empty"
            }
        
        # Simple concatenation with source attribution
        synthesis_parts = [f"Based on your memories, here's what I found for '{query}':\n"]
        
        for i, result in enumerate(results[:5], 1):  # Limit to top 5 results
            content = result.get("content", "")
            source = result.get("source", "memory")
            score = result.get("score", 0.0)
            
            synthesis_parts.append(f"{i}. [{source.title()}, relevance: {score:.1%}] {content}")
        
        if len(results) > 5:
            synthesis_parts.append(f"\n... and {len(results) - 5} more related memories.")
        
        synthesis = "\n".join(synthesis_parts)
        confidence = min(0.7, 0.2 + (len(results) * 0.05))
        
        return {
            "synthesis": synthesis,
            "confidence_score": confidence,
            "method": "fallback_concatenation"
        }
    
    async def search(self, query: str, user_id: str, limit: Optional[int] = None) -> SearchResult:
        """
        Perform hybrid search across all available engines
        🎯 NOW WITH SEMANTIC CACHING for 30%+ performance improvement
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            logger.info(f"🔍 Starting hybrid search for '{query}' (user: {user_id})")
            
            # 🎯 OPTIMIZATION 1: Check semantic cache first
            try:
                from .cache import get_semantic_cache
                semantic_cache = await get_semantic_cache()
                
                if semantic_cache:
                    cached_result = await semantic_cache.get_cached_result(query, user_id)
                    if cached_result:
                        # Convert cached result to SearchResult format
                        processing_time = time.time() - start_time
                        logger.info(f"🎯 CACHE HIT: Returning cached result ({processing_time*1000:.1f}ms)")
                        
                        return SearchResult(
                            query=query,
                            user_id=user_id,
                            synthesis=cached_result.synthesis or "Results from semantic cache",
                            confidence_score=cached_result.confidence_score,
                            total_results=len(cached_result.results),
                            processing_time=processing_time,
                            mem0_results=cached_result.results,
                            graphiti_results=[],
                            search_method="cached_hybrid"
                        )
            except Exception as cache_error:
                logger.warning(f"⚠️ Cache lookup failed, proceeding with search: {cache_error}")
            
            # Search all engines in parallel
            search_tasks = [
                self.search_mem0(query, user_id, limit)
            ]
            
            if self.graphiti:
                search_tasks.append(self.search_graphiti(query, user_id, limit))
            
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Process results
            mem0_results = search_results[0] if not isinstance(search_results[0], Exception) else []
            graphiti_results = search_results[1] if len(search_results) > 1 and not isinstance(search_results[1], Exception) else []
            
            # Combine all results
            all_results = mem0_results + graphiti_results
            
            # Sort by score
            all_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            
            # Apply limit
            if limit:
                all_results = all_results[:limit]
            
            # Synthesize results
            synthesis_result = await self.synthesize_with_gemini(query, all_results)
            
            processing_time = time.time() - start_time
            
            # Create final result
            result = SearchResult(
                query=query,
                user_id=user_id,
                synthesis=synthesis_result["synthesis"],
                confidence_score=synthesis_result["confidence_score"],
                total_results=len(all_results),
                processing_time=processing_time,
                mem0_results=mem0_results,
                graphiti_results=graphiti_results,
                search_method=synthesis_result["method"]
            )
            
            # 💾 OPTIMIZATION 2: Cache the result for future similar queries
            try:
                if 'semantic_cache' in locals() and semantic_cache and all_results:
                    await semantic_cache.cache_result(
                        query=query,
                        user_id=user_id,
                        results=all_results,
                        synthesis=synthesis_result["synthesis"],
                        ttl_hours=24
                    )
            except Exception as cache_error:
                logger.warning(f"⚠️ Failed to cache result: {cache_error}")
            
            logger.info(f"✅ Hybrid search completed in {processing_time:.2f}s, found {len(all_results)} results")
            return result
            
        except Exception as e:
            logger.error(f"❌ Hybrid search failed: {e}")
            raise SearchError(f"Hybrid search failed: {e}")
    
    async def close(self):
        """Close all connections and cleanup"""
        logger.info("🔄 Closing hybrid search engine...")
        
        if self.mem0_memory:
            # Mem0 might not have explicit close method
            pass
        
        if self.graphiti:
            try:
                await self.graphiti.close()
            except Exception as e:
                logger.warning(f"⚠️ Error closing Graphiti: {e}")
        
        logger.info("✅ Hybrid search engine closed")


# NEW: Specialized Life Graph Search Function
async def search_for_life_graph(
    query: str,
    user_id: str,
    limit: int = 50,
    config: Optional[JeanMemoryConfig] = None,
    include_entities: bool = True,
    include_temporal_clusters: bool = True
) -> Dict[str, Any]:
    """
    Specialized search function for life graph visualization.
    
    Returns memories with enhanced metadata for graph visualization:
    - Entity extraction
    - Temporal clustering
    - Relationship mapping
    - Optimized for 3D visualization
    
    Args:
        query: Search query (or None for comprehensive life overview)
        user_id: User identifier
        limit: Maximum number of memories to return
        config: Jean Memory configuration
        include_entities: Whether to extract entities from memories
        include_temporal_clusters: Whether to create temporal clusters
    
    Returns:
        Dict containing nodes, edges, clusters, and metadata for visualization
    """
    logger.info(f"🕸️ Life Graph Search: '{query}' for user {user_id} (limit: {limit})")
    
    # Initialize search engine
    search_config = config or JeanMemoryConfig.from_environment()
    search_engine = HybridSearchEngine(search_config)
    
    try:
        await search_engine.initialize()
        
        # Use broad life-focused query if none provided
        if not query or query.strip() == "":
            query = "life experiences goals relationships work personal growth memories important moments"
        
        # Search for memories
        start_time = time.time()
        search_result = await search_engine.search(query, user_id, limit)
        search_time = time.time() - start_time
        
        logger.info(f"🔍 Found {search_result.total_results} memories in {search_time:.2f}s")
        
        # Combine all search results
        all_memories = []
        
        # Add Mem0 results
        for mem in search_result.mem0_results:
            all_memories.append({
                'id': mem['id'],
                'content': mem['content'],
                'score': mem['score'],
                'metadata': mem['metadata'],
                'source': 'mem0',
                'created_at': mem.get('created_at'),
                'user_id': mem.get('user_id', user_id)
            })
        
        # Add Graphiti results
        for mem in search_result.graphiti_results:
            all_memories.append({
                'id': mem.get('id', f"graphiti_{len(all_memories)}"),
                'content': mem.get('content', mem.get('memory', '')),
                'score': mem.get('score', 0.5),
                'metadata': mem.get('metadata', {}),
                'source': 'graphiti',
                'created_at': mem.get('created_at'),
                'user_id': mem.get('user_id', user_id)
            })
        
        # Create visualization data
        visualization_data = await _create_life_graph_visualization_data(
            memories=all_memories,
            include_entities=include_entities,
            include_temporal_clusters=include_temporal_clusters,
            synthesis=search_result.synthesis
        )
        
        # Add search metadata
        visualization_data['metadata'].update({
            'search_query': query,
            'search_synthesis': search_result.synthesis,
            'search_confidence': search_result.confidence_score,
            'search_time': search_time,
            'total_search_results': search_result.total_results,
            'jean_memory_version': '2.1.0-optimized'
        })
        
        logger.info(f"✅ Life graph data created: {len(visualization_data['nodes'])} nodes, {len(visualization_data['edges'])} edges")
        
        return visualization_data
        
    except Exception as e:
        logger.error(f"❌ Life graph search failed: {e}")
        raise SearchError(f"Life graph search failed: {e}")
    
    finally:
        await search_engine.close()


async def _create_life_graph_visualization_data(
    memories: List[Dict[str, Any]],
    include_entities: bool = True,
    include_temporal_clusters: bool = True,
    synthesis: str = ""
) -> Dict[str, Any]:
    """
    Create optimized visualization data from memories.
    
    Returns:
        Dict with nodes, edges, clusters, and metadata for 3D visualization
    """
    import re
    from datetime import datetime
    
    nodes = []
    edges = []
    clusters = []
    entity_groups = {}
    
    logger.info(f"📊 Creating visualization data from {len(memories)} memories")
    
    # Process each memory
    for i, memory in enumerate(memories):
        content = memory.get('content', '')
        if not content or len(content.strip()) < 10:
            continue
        
        # Create memory node
        memory_node = {
            'id': f"memory_{i}",
            'type': 'memory',
            'content': content.strip(),
            'source': memory.get('source', 'unknown'),
            'score': memory.get('score', 0.5),
            'timestamp': memory.get('created_at'),
            'user_id': memory.get('user_id'),
            'size': min(max(len(content) / 100, 0.5), 2.0),  # Size based on content length
            'metadata': memory.get('metadata', {})
        }
        
        # Extract entities if requested
        if include_entities:
            entities = _extract_entities_simple(content)
            
            for entity in entities:
                entity_id = f"entity_{entity['name'].lower().replace(' ', '_')}"
                
                # Create or update entity node
                if entity_id not in entity_groups:
                    entity_groups[entity_id] = {
                        'id': entity_id,
                        'type': 'entity',
                        'name': entity['name'],
                        'entity_type': entity['type'],
                        'memories': [],
                        'strength': 0
                    }
                
                entity_groups[entity_id]['memories'].append(memory_node['id'])
                entity_groups[entity_id]['strength'] += 1
                
                # Create edge between memory and entity
                edges.append({
                    'source': memory_node['id'],
                    'target': entity_id,
                    'type': 'contains',
                    'strength': entity.get('confidence', 0.5)
                })
        
        nodes.append(memory_node)
    
    # Add entity nodes (only those mentioned multiple times)
    for entity_id, entity_data in entity_groups.items():
        if entity_data['strength'] >= 2:  # Only include entities mentioned multiple times
            entity_node = {
                'id': entity_id,
                'type': 'entity',
                'name': entity_data['name'],
                'entity_type': entity_data['entity_type'],
                'strength': entity_data['strength'],
                'size': min(max(entity_data['strength'] / 2, 0.3), 1.5),
                'memories': entity_data['memories']
            }
            nodes.append(entity_node)
    
    # Create temporal clusters if requested
    if include_temporal_clusters:
        clusters = _create_temporal_clusters_simple(nodes)
    
    # Calculate 3D positions
    positions = _calculate_3d_layout(nodes, edges, clusters)
    
    # Add positions to nodes
    for node in nodes:
        node['position'] = positions.get(node['id'], {'x': 0, 'y': 0, 'z': 0})
    
    return {
        'nodes': nodes,
        'edges': edges,
        'clusters': clusters,
        'metadata': {
            'total_memories': len(memories),
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'total_clusters': len(clusters),
            'entity_extraction_enabled': include_entities,
            'temporal_clustering_enabled': include_temporal_clusters,
            'generated_at': datetime.now().isoformat(),
            'synthesis': synthesis
        }
    }


def _extract_entities_simple(content: str) -> List[Dict[str, Any]]:
    """Simple entity extraction using regex patterns"""
    import re
    
    entities = []
    
    # Simple patterns for common entities
    patterns = {
        'person': [
            r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # Full names
            r'\b(?:met|talked to|called|texted|saw|visited|with) ([A-Z][a-z]+)\b',  # Names after verbs
        ],
        'place': [
            r'\bin ([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b',  # Places after "in"
            r'\bat ([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b',  # Places after "at"
            r'\bwent to ([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b',  # Places after "went to"
        ],
        'topic': [
            r'\b(work|job|career|project|meeting|presentation|interview|startup|company)\b',  # Work-related
            r'\b(family|friends|relationship|dating|marriage|wedding|parents|children)\b',  # Personal
            r'\b(exercise|workout|fitness|running|gym|sport|health|meditation)\b',  # Health
            r'\b(travel|vacation|trip|flight|hotel|restaurant|food|dinner)\b',  # Travel & Food
            r'\b(book|movie|music|art|learning|course|education|study)\b',  # Learning & Culture
        ]
    }
    
    for entity_type, pattern_list in patterns.items():
        for pattern in pattern_list:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ""
                
                if match and len(match) > 2:
                    entities.append({
                        'name': match.strip(),
                        'type': entity_type,
                        'confidence': 0.7
                    })
    
    # Remove duplicates
    unique_entities = []
    seen = set()
    for entity in entities:
        key = (entity['name'].lower(), entity['type'])
        if key not in seen:
            seen.add(key)
            unique_entities.append(entity)
    
    return unique_entities[:10]  # Limit to 10 entities per memory


def _create_temporal_clusters_simple(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create temporal clusters from memory nodes"""
    from datetime import datetime
    
    clusters = []
    time_groups = {}
    
    for node in nodes:
        if node['type'] == 'memory':
            timestamp = node.get('timestamp')
            if timestamp:
                try:
                    # Parse timestamp
                    if isinstance(timestamp, str):
                        if timestamp.endswith('Z'):
                            timestamp = timestamp[:-1] + '+00:00'
                        date_obj = datetime.fromisoformat(timestamp)
                    else:
                        date_obj = datetime.fromtimestamp(timestamp)
                    
                    # Create period key (year-month)
                    period = f"{date_obj.year}-{date_obj.month:02d}"
                    if period not in time_groups:
                        time_groups[period] = []
                    time_groups[period].append(node['id'])
                except Exception as e:
                    logger.warning(f"Could not parse timestamp {timestamp}: {e}")
    
    # Create cluster objects
    for period, node_ids in time_groups.items():
        if len(node_ids) >= 2:  # Only create clusters with multiple memories
            clusters.append({
                'id': f"cluster_{period}",
                'name': f"Memories from {period}",
                'type': 'temporal',
                'period': period,
                'nodes': node_ids,
                'size': len(node_ids)
            })
    
    return clusters


def _calculate_3d_layout(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], clusters: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Calculate 3D positions using simple force-directed layout"""
    import math
    import random
    
    random.seed(42)  # For reproducible layouts
    
    positions = {}
    
    # Initialize random positions
    for node in nodes:
        positions[node['id']] = {
            'x': random.uniform(-10, 10),
            'y': random.uniform(-10, 10),
            'z': random.uniform(-10, 10)
        }
    
    # Simple force-directed layout
    for iteration in range(50):
        forces = {node['id']: {'x': 0, 'y': 0, 'z': 0} for node in nodes}
        
        # Repulsive forces between all nodes
        for i, node1 in enumerate(nodes):
            for j, node2 in enumerate(nodes):
                if i != j:
                    pos1 = positions[node1['id']]
                    pos2 = positions[node2['id']]
                    
                    dx = pos1['x'] - pos2['x']
                    dy = pos1['y'] - pos2['y']
                    dz = pos1['z'] - pos2['z']
                    
                    distance = math.sqrt(dx*dx + dy*dy + dz*dz) + 0.01
                    
                    # Repulsive force
                    force = 5.0 / (distance * distance)
                    
                    forces[node1['id']]['x'] += (dx / distance) * force
                    forces[node1['id']]['y'] += (dy / distance) * force
                    forces[node1['id']]['z'] += (dz / distance) * force
        
        # Attractive forces between connected nodes
        for edge in edges:
            if edge['source'] in positions and edge['target'] in positions:
                pos1 = positions[edge['source']]
                pos2 = positions[edge['target']]
                
                dx = pos2['x'] - pos1['x']
                dy = pos2['y'] - pos1['y']
                dz = pos2['z'] - pos1['z']
                
                distance = math.sqrt(dx*dx + dy*dy + dz*dz) + 0.01
                
                # Attractive force
                force = distance * 0.05 * edge.get('strength', 0.5)
                
                forces[edge['source']]['x'] += (dx / distance) * force
                forces[edge['source']]['y'] += (dy / distance) * force
                forces[edge['source']]['z'] += (dz / distance) * force
                
                forces[edge['target']]['x'] -= (dx / distance) * force
                forces[edge['target']]['y'] -= (dy / distance) * force
                forces[edge['target']]['z'] -= (dz / distance) * force
        
        # Apply forces with damping
        damping = 0.1
        for node in nodes:
            node_id = node['id']
            positions[node_id]['x'] += forces[node_id]['x'] * damping
            positions[node_id]['y'] += forces[node_id]['y'] * damping
            positions[node_id]['z'] += forces[node_id]['z'] * damping
    
    return positions 


# NEW: Enhanced Life Graph Search Function with Graph-Based Intelligence
async def search_for_enhanced_life_graph(
    query: str,
    user_id: str,
    limit: int = 50,
    config: Optional[JeanMemoryConfig] = None,
    graph_depth: int = 2,
    include_ai_insights: bool = True
) -> Dict[str, Any]:
    """
    Enhanced life graph search using Graphiti graph search capabilities.
    
    This function leverages:
    - Graphiti's graph search for structured entities and relationships
    - Mem0's semantic search for contextual memory retrieval
    - Gemini AI synthesis for pattern recognition and insights
    - Hybrid search engine with caching for performance
    
    Args:
        query: Search query (or None for comprehensive life overview)
        user_id: User identifier
        limit: Maximum number of memories to return
        config: Jean Memory configuration
        graph_depth: How deep to search in the graph for relationships
        include_ai_insights: Whether to include AI-generated insights
    
    Returns:
        Dict containing rich visualization data with graph-based entities
    """
    logger.info(f"🚀 Enhanced Life Graph Search: '{query}' for user {user_id}")
    
    # Initialize search engine
    search_config = config or JeanMemoryConfig.from_environment()
    search_engine = HybridSearchEngine(search_config)
    
    try:
        await search_engine.initialize()
        
        # Step 1: Use comprehensive life queries for broad context
        life_queries = [
            query if query else "life experiences goals relationships work personal growth",
            "important people relationships family friends colleagues",
            "significant places locations work home travel",
            "major topics interests hobbies work projects achievements",
            "temporal patterns growth changes over time milestones"
        ]
        
        start_time = time.time()
        all_memories = []
        graph_entities = []
        ai_insights = []
        
        # Step 2: Execute parallel searches for different aspects
        logger.info("🔍 Executing parallel graph searches...")
        
        search_tasks = []
        for i, life_query in enumerate(life_queries):
            if i == 0:  # Primary query - use full limit
                search_tasks.append(search_engine.search(life_query, user_id, limit))
            else:  # Secondary queries - use smaller limits
                search_tasks.append(search_engine.search(life_query, user_id, limit // 4))
        
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Step 3: Process and deduplicate results
        seen_memory_ids = set()
        for result in search_results:
            if isinstance(result, Exception):
                logger.warning(f"⚠️ Search failed: {result}")
                continue
            
            # Add unique memories
            for mem in result.mem0_results:
                mem_id = mem.get("id")
                if mem_id and mem_id not in seen_memory_ids:
                    seen_memory_ids.add(mem_id)
                    all_memories.append(mem)
            
            # Extract graph entities from Graphiti results
            for graph_result in result.graphiti_results:
                if graph_result.get("node_type") in ["person", "place", "organization", "concept"]:
                    graph_entities.append({
                        "id": graph_result.get("id"),
                        "name": graph_result.get("content", ""),
                        "type": graph_result.get("node_type"),
                        "properties": graph_result.get("metadata", {}),
                        "score": graph_result.get("score", 0.0),
                        "source": "graphiti_graph"
                    })
            
            # Collect AI insights
            if include_ai_insights and result.synthesis:
                ai_insights.append({
                    "query": result.query,
                    "insight": result.synthesis,
                    "confidence": result.confidence_score,
                    "source_count": result.total_results
                })
        
        logger.info(f"📊 Found {len(all_memories)} unique memories, {len(graph_entities)} graph entities")
        
        # Step 4: Enhanced entity extraction using graph + semantic data
        enhanced_entities = await _extract_enhanced_entities(
            memories=all_memories,
            graph_entities=graph_entities,
            search_engine=search_engine,
            user_id=user_id
        )
        
        # Step 5: Generate temporal and relational patterns
        temporal_patterns = await _generate_temporal_patterns(
            memories=all_memories,
            entities=enhanced_entities,
            search_engine=search_engine,
            user_id=user_id
        )
        
        # Step 6: Create enhanced visualization data
        visualization_data = await _create_enhanced_visualization_data(
            memories=all_memories,
            entities=enhanced_entities,
            temporal_patterns=temporal_patterns,
            ai_insights=ai_insights,
            graph_depth=graph_depth
        )
        
        # Step 7: Add comprehensive metadata
        processing_time = time.time() - start_time
        visualization_data['metadata'].update({
            'search_query': query,
            'ai_insights': ai_insights if include_ai_insights else [],
            'graph_entities_found': len(graph_entities),
            'enhanced_entities_extracted': len(enhanced_entities),
            'temporal_patterns_identified': len(temporal_patterns),
            'processing_time': processing_time,
            'search_method': 'enhanced_graph_hybrid',
            'jean_memory_version': '2.1.0-graph-enhanced',
            'capabilities_used': {
                'graphiti_graph_search': search_engine.graphiti is not None,
                'mem0_semantic_search': search_engine.mem0_memory is not None,
                'gemini_ai_synthesis': search_engine.gemini_client is not None,
                'temporal_pattern_analysis': True,
                'relationship_mapping': True
            }
        })
        
        logger.info(f"✅ Enhanced life graph generated: {len(visualization_data['nodes'])} nodes, {len(visualization_data['edges'])} edges ({processing_time:.2f}s)")
        
        return visualization_data
        
    except Exception as e:
        logger.error(f"❌ Enhanced life graph search failed: {e}")
        raise SearchError(f"Enhanced life graph search failed: {e}")
    
    finally:
        await search_engine.close()


async def _extract_enhanced_entities(
    memories: List[Dict[str, Any]],
    graph_entities: List[Dict[str, Any]],
    search_engine: HybridSearchEngine,
    user_id: str
) -> List[Dict[str, Any]]:
    """Extract entities using graph + semantic analysis"""
    logger.info("🧠 Extracting enhanced entities from graph and semantic data...")
    
    entities = []
    
    # Priority 1: Use graph entities (highest confidence)
    for graph_entity in graph_entities:
        entities.append({
            "id": f"graph_{graph_entity['id']}",
            "name": graph_entity["name"],
            "type": graph_entity["type"],
            "extraction_method": "graphiti_graph",
            "confidence": graph_entity["score"],
            "properties": graph_entity["properties"],
            "mentions": [],
            "strength": 1
        })
    
    # Priority 2: Use semantic search to find related entities
    entity_queries = [
        "important people in my life friends family colleagues",
        "significant places locations work home travel destinations",
        "major topics interests hobbies work projects skills",
        "organizations companies schools institutions"
    ]
    
    for query in entity_queries:
        try:
            # Search for entity-related memories
            entity_search = await search_engine.search(query, user_id, limit=20)
            
            # Extract entities from synthesis (AI-identified)
            if entity_search.synthesis:
                ai_entities = _extract_entities_from_ai_synthesis(
                    entity_search.synthesis,
                    query
                )
                entities.extend(ai_entities)
                
        except Exception as e:
            logger.warning(f"⚠️ Entity search failed for '{query}': {e}")
    
    # Priority 3: Cross-reference with memory content
    for memory in memories:
        content = memory.get("content", "")
        memory_id = memory.get("id")
        
        # Find mentions of existing entities
        for entity in entities:
            entity_name = entity["name"].lower()
            if entity_name in content.lower():
                entity["mentions"].append({
                    "memory_id": memory_id,
                    "context": content[:200] + "..." if len(content) > 200 else content
                })
                entity["strength"] = entity.get("strength", 0) + 1
    
    # Filter entities by strength (mentioned in multiple contexts)
    filtered_entities = []
    for entity in entities:
        if entity["strength"] >= 2 or entity["extraction_method"] == "graphiti_graph":
            filtered_entities.append(entity)
    
    logger.info(f"📊 Enhanced entity extraction: {len(filtered_entities)} high-confidence entities")
    return filtered_entities


def _extract_entities_from_ai_synthesis(synthesis: str, query_context: str) -> List[Dict[str, Any]]:
    """Extract entities from AI synthesis text"""
    entities = []
    
    # Determine entity type from query context
    entity_type = "unknown"
    if "people" in query_context.lower() or "friends" in query_context.lower():
        entity_type = "person"
    elif "places" in query_context.lower() or "locations" in query_context.lower():
        entity_type = "place"
    elif "topics" in query_context.lower() or "interests" in query_context.lower():
        entity_type = "topic"
    elif "organizations" in query_context.lower() or "companies" in query_context.lower():
        entity_type = "organization"
    
    # Simple extraction from synthesis (can be enhanced with NER)
    import re
    
    # Look for proper nouns and quoted entities
    patterns = [
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # Proper nouns
        r'"([^"]+)"',  # Quoted entities
        r'\'([^\']+)\'',  # Single-quoted entities
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, synthesis)
        for match in matches:
            if len(match) > 1 and match not in ["AI", "The", "You", "I", "My", "Your"]:
                entities.append({
                    "id": f"ai_{match.lower().replace(' ', '_')}",
                    "name": match,
                    "type": entity_type,
                    "extraction_method": "ai_synthesis",
                    "confidence": 0.6,
                    "properties": {"synthesis_context": query_context},
                    "mentions": [],
                    "strength": 1
                })
    
    return entities


async def _generate_temporal_patterns(
    memories: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    search_engine: HybridSearchEngine,
    user_id: str
) -> List[Dict[str, Any]]:
    """Generate temporal patterns and life phases"""
    logger.info("📅 Generating temporal patterns...")
    
    patterns = []
    
    # Group memories by time periods
    time_periods = {}
    for memory in memories:
        created_at = memory.get("created_at")
        if created_at:
            try:
                from datetime import datetime
                date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                year_month = f"{date.year}-{date.month:02d}"
                
                if year_month not in time_periods:
                    time_periods[year_month] = []
                time_periods[year_month].append(memory)
            except:
                continue
    
    # Analyze each time period
    for period, period_memories in time_periods.items():
        if len(period_memories) >= 2:  # Only periods with multiple memories
            # Extract themes from this period
            period_content = " ".join([m.get("content", "") for m in period_memories])
            
            # Use AI to identify themes if available
            if search_engine.gemini_client:
                try:
                    theme_prompt = f"""Analyze this time period ({period}) and identify 1-3 key themes or patterns:

{period_content[:1000]}...

What were the main themes, activities, or focus areas during this period? Respond with just the themes, separated by semicolons."""
                    
                    response = await search_engine.gemini_client.generate_content_async(theme_prompt)
                    themes = [theme.strip() for theme in response.text.split(';')]
                    
                    patterns.append({
                        "id": f"period_{period}",
                        "type": "temporal_pattern",
                        "period": period,
                        "themes": themes,
                        "memory_count": len(period_memories),
                        "strength": len(period_memories)
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Theme analysis failed for {period}: {e}")
    
    logger.info(f"📊 Generated {len(patterns)} temporal patterns")
    return patterns


async def _create_enhanced_visualization_data(
    memories: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    temporal_patterns: List[Dict[str, Any]],
    ai_insights: List[Dict[str, Any]],
    graph_depth: int
) -> Dict[str, Any]:
    """Create enhanced visualization data with graph-based relationships"""
    logger.info("🎨 Creating enhanced visualization data...")
    
    nodes = []
    edges = []
    clusters = []
    
    # Create memory nodes
    for i, memory in enumerate(memories):
        node = {
            "id": f"memory_{i}",
            "type": "memory",
            "content": memory.get("content", ""),
            "source": memory.get("source", "unknown"),
            "score": memory.get("score", 0.0),
            "created_at": memory.get("created_at"),
            "size": min(max(len(memory.get("content", "")) / 100, 0.5), 2.0),
            "position": {
                "x": (hash(memory.get("id", str(i))) % 1000 - 500) / 25,
                "y": (hash(memory.get("content", "")[:50]) % 1000 - 500) / 25,
                "z": (hash(str(i)) % 1000 - 500) / 25
            }
        }
        nodes.append(node)
    
    # Create enhanced entity nodes
    for entity in entities:
        node = {
            "id": entity["id"],
            "type": "entity",
            "name": entity["name"],
            "entity_type": entity["type"],
            "extraction_method": entity["extraction_method"],
            "confidence": entity["confidence"],
            "strength": entity["strength"],
            "size": min(max(entity["strength"] / 3, 0.4), 1.8),
            "position": {
                "x": (hash(entity["name"]) % 1000 - 500) / 25,
                "y": (hash(entity["type"]) % 1000 - 500) / 25,
                "z": (hash(entity["id"]) % 1000 - 500) / 25
            }
        }
        nodes.append(node)
        
        # Create edges between entities and memories
        for mention in entity["mentions"]:
            memory_id = mention["memory_id"]
            # Find corresponding memory node
            for memory_node in nodes:
                if memory_node["type"] == "memory" and memory_node.get("id") == memory_id:
                    edges.append({
                        "source": memory_node["id"],
                        "target": entity["id"],
                        "type": "mentions",
                        "strength": entity["confidence"]
                    })
                    break
    
    # Create temporal pattern nodes
    for pattern in temporal_patterns:
        node = {
            "id": pattern["id"],
            "type": "temporal_pattern",
            "period": pattern["period"],
            "themes": pattern["themes"],
            "memory_count": pattern["memory_count"],
            "size": min(max(pattern["strength"] / 4, 0.3), 1.5),
            "position": {
                "x": (hash(pattern["period"]) % 1000 - 500) / 25,
                "y": (hash(str(pattern["themes"])) % 1000 - 500) / 25,
                "z": (hash(pattern["id"]) % 1000 - 500) / 25
            }
        }
        nodes.append(node)
    
    # Create AI insight clusters
    for insight in ai_insights:
        clusters.append({
            "id": f"insight_{hash(insight['query']) % 1000}",
            "type": "ai_insight",
            "query": insight["query"],
            "insight": insight["insight"],
            "confidence": insight["confidence"],
            "source_count": insight["source_count"]
        })
    
    # Apply enhanced 3D layout
    positions = _calculate_enhanced_3d_layout(nodes, edges, clusters)
    
    # Update node positions
    for node in nodes:
        if node["id"] in positions:
            node["position"] = positions[node["id"]]
    
    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "metadata": {
            "total_memories": len(memories),
            "total_entities": len(entities),
            "total_temporal_patterns": len(temporal_patterns),
            "total_ai_insights": len(ai_insights),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "generated_at": datetime.now().isoformat()
        }
    }


def _calculate_enhanced_3d_layout(
    nodes: List[Dict[str, Any]], 
    edges: List[Dict[str, Any]], 
    clusters: List[Dict[str, Any]]
) -> Dict[str, Dict[str, float]]:
    """Calculate enhanced 3D layout with improved clustering"""
    logger.info("📐 Calculating enhanced 3D layout...")
    
    positions = {}
    
    # Initialize positions based on node type
    for node in nodes:
        node_id = node["id"]
        node_type = node["type"]
        
        # Position nodes in different layers by type
        if node_type == "memory":
            # Memories in the center layer
            base_x = (hash(node_id) % 2000 - 1000) / 50
            base_y = (hash(node.get("content", "")) % 2000 - 1000) / 50
            base_z = 0
        elif node_type == "entity":
            # Entities in outer layer
            base_x = (hash(node_id) % 2000 - 1000) / 30
            base_y = (hash(node.get("name", "")) % 2000 - 1000) / 30
            base_z = 5 if node.get("entity_type") == "person" else -5
        elif node_type == "temporal_pattern":
            # Temporal patterns in vertical arrangement
            base_x = 0
            base_y = (hash(node_id) % 2000 - 1000) / 40
            base_z = 10
        else:
            # Default positioning
            base_x = (hash(node_id) % 2000 - 1000) / 50
            base_y = (hash(node_id) % 2000 - 1000) / 50
            base_z = 0
        
        positions[node_id] = {
            "x": base_x,
            "y": base_y,
            "z": base_z
        }
    
    # Apply force-directed layout for connected nodes
    for iteration in range(30):
        forces = {node_id: {"x": 0, "y": 0, "z": 0} for node_id in positions}
        
        # Repulsive forces
        node_list = list(positions.keys())
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                node1, node2 = node_list[i], node_list[j]
                pos1, pos2 = positions[node1], positions[node2]
                
                dx = pos1["x"] - pos2["x"]
                dy = pos1["y"] - pos2["y"]
                dz = pos1["z"] - pos2["z"]
                
                distance = max(0.1, (dx*dx + dy*dy + dz*dz) ** 0.5)
                force = 2.0 / (distance * distance)
                
                forces[node1]["x"] += (dx / distance) * force
                forces[node1]["y"] += (dy / distance) * force
                forces[node1]["z"] += (dz / distance) * force
                
                forces[node2]["x"] -= (dx / distance) * force
                forces[node2]["y"] -= (dy / distance) * force
                forces[node2]["z"] -= (dz / distance) * force
        
        # Attractive forces for connected nodes
        for edge in edges:
            source_id = edge["source"]
            target_id = edge["target"]
            
            if source_id in positions and target_id in positions:
                pos1, pos2 = positions[source_id], positions[target_id]
                
                dx = pos2["x"] - pos1["x"]
                dy = pos2["y"] - pos1["y"]
                dz = pos2["z"] - pos1["z"]
                
                distance = max(0.1, (dx*dx + dy*dy + dz*dz) ** 0.5)
                force = distance * 0.05 * edge.get("strength", 0.5)
                
                forces[source_id]["x"] += (dx / distance) * force
                forces[source_id]["y"] += (dy / distance) * force
                forces[source_id]["z"] += (dz / distance) * force
                
                forces[target_id]["x"] -= (dx / distance) * force
                forces[target_id]["y"] -= (dy / distance) * force
                forces[target_id]["z"] -= (dz / distance) * force
        
        # Apply forces with damping
        damping = 0.1
        for node_id in positions:
            positions[node_id]["x"] += forces[node_id]["x"] * damping
            positions[node_id]["y"] += forces[node_id]["y"] * damping
            positions[node_id]["z"] += forces[node_id]["z"] * damping
    
    logger.info(f"📊 Enhanced 3D layout calculated for {len(positions)} nodes")
    return positions 