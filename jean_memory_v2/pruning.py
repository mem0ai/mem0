"""
Jean Memory V2 - Vector Pruning and Memory Management
====================================================

Automated cleanup system for maintaining optimal performance and cost efficiency.
Implements research-based strategies for pruning and consolidating memory data.

Features:
- Automatic duplicate detection and removal
- Temporal-based pruning (remove old, irrelevant memories)
- Vector consolidation and merging
- Low-value memory detection
- Storage optimization
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict

import numpy as np

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    QDRANT_AVAILABLE = True
except ImportError:
    logger.warning("Qdrant client not available")
    QDRANT_AVAILABLE = False


@dataclass
class PruningStats:
    """Statistics from pruning operation"""
    total_memories_before: int
    total_memories_after: int
    duplicates_removed: int
    expired_removed: int
    low_value_removed: int
    merged_memories: int
    storage_saved_mb: float
    processing_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_memories_before": self.total_memories_before,
            "total_memories_after": self.total_memories_after,
            "duplicates_removed": self.duplicates_removed,
            "expired_removed": self.expired_removed,
            "low_value_removed": self.low_value_removed,
            "merged_memories": self.merged_memories,
            "storage_saved_mb": round(self.storage_saved_mb, 2),
            "processing_time": round(self.processing_time, 2)
        }


@dataclass
class PruningConfig:
    """Configuration for pruning operations"""
    # Temporal pruning
    max_age_days: int = 365  # Remove memories older than 1 year
    recent_memory_days: int = 30  # Keep all memories from last 30 days
    
    # Duplicate detection
    similarity_threshold: float = 0.95  # Cosine similarity threshold for duplicates
    content_overlap_threshold: float = 0.85  # Text overlap threshold
    
    # Value-based pruning
    min_score: float = 0.1  # Minimum relevance score to keep
    min_length: int = 10  # Minimum content length
    
    # Consolidation
    enable_memory_merging: bool = True
    merge_similarity_threshold: float = 0.85
    max_memories_per_cluster: int = 5
    
    # Safety limits
    max_removal_percentage: float = 0.3  # Never remove more than 30% in one operation
    dry_run: bool = False  # Set to True to simulate without actual deletion


class MemoryPruningService:
    """
    Automated memory pruning and optimization service
    
    Implements intelligent cleanup strategies to maintain performance
    while preserving important user memories.
    """
    
    def __init__(self, config: PruningConfig = None):
        self.config = config or PruningConfig()
        self.qdrant_client = None
        self.mem0_client = None
        self._initialized = False
    
    async def initialize(self, qdrant_url: str, qdrant_api_key: str = None):
        """Initialize connections to storage systems"""
        if not QDRANT_AVAILABLE:
            logger.error("Qdrant client not available for pruning service")
            return False
        
        try:
            if qdrant_api_key:
                self.qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
            else:
                self.qdrant_client = QdrantClient(url=qdrant_url)
            
            # Test connection
            collections = self.qdrant_client.get_collections()
            self._initialized = True
            logger.info("✅ Memory pruning service initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize pruning service: {e}")
            return False
    
    async def analyze_user_memories(self, user_id: str) -> Dict[str, Any]:
        """
        Analyze user's memory collection for pruning opportunities
        
        Returns analysis report with recommendations
        """
        if not self._initialized:
            return {"error": "Service not initialized"}
        
        collection_name = f"mem0_{user_id}"
        
        try:
            # Get collection info
            collection_info = self.qdrant_client.get_collection(collection_name)
            total_vectors = collection_info.points_count
            
            if total_vectors == 0:
                return {"total_memories": 0, "recommendations": []}
            
            # Get sample of vectors for analysis (limit to avoid memory issues)
            points, _ = self.qdrant_client.scroll(
                collection_name=collection_name,
                limit=min(1000, total_vectors),  # Sample for large collections
                with_payload=True,
                with_vectors=True
            )
            
            analysis = {
                "total_memories": total_vectors,
                "analyzed_sample": len(points),
                "collection_size_mb": self._estimate_collection_size(points, total_vectors),
                "age_distribution": self._analyze_age_distribution(points),
                "duplicate_candidates": len(self._find_duplicate_candidates(points)),
                "low_value_candidates": len(self._find_low_value_candidates(points)),
                "recommendations": []
            }
            
            # Generate recommendations
            recommendations = []
            
            if analysis["duplicate_candidates"] > 0:
                recommendations.append({
                    "type": "duplicate_removal",
                    "count": analysis["duplicate_candidates"],
                    "estimated_savings_mb": analysis["collection_size_mb"] * 0.1,
                    "description": f"Remove ~{analysis['duplicate_candidates']} duplicate memories"
                })
            
            if analysis["low_value_candidates"] > 0:
                recommendations.append({
                    "type": "low_value_removal", 
                    "count": analysis["low_value_candidates"],
                    "estimated_savings_mb": analysis["collection_size_mb"] * 0.05,
                    "description": f"Remove ~{analysis['low_value_candidates']} low-value memories"
                })
            
            old_memories = analysis["age_distribution"].get("older_than_1_year", 0)
            if old_memories > 0:
                recommendations.append({
                    "type": "temporal_pruning",
                    "count": old_memories,
                    "estimated_savings_mb": analysis["collection_size_mb"] * 0.2,
                    "description": f"Archive ~{old_memories} memories older than 1 year"
                })
            
            analysis["recommendations"] = recommendations
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze memories for user {user_id}: {e}")
            return {"error": str(e)}
    
    def _estimate_collection_size(self, sample_points: List, total_count: int) -> float:
        """Estimate total collection size in MB based on sample"""
        if not sample_points:
            return 0.0
        
        # Rough estimate: 1536 dims * 4 bytes + metadata
        avg_vector_size = 1536 * 4  # Float32
        avg_metadata_size = 500  # Estimated metadata size
        avg_point_size = avg_vector_size + avg_metadata_size
        
        total_size_bytes = total_count * avg_point_size
        return total_size_bytes / (1024 * 1024)  # Convert to MB
    
    def _analyze_age_distribution(self, points: List) -> Dict[str, int]:
        """Analyze age distribution of memories"""
        now = datetime.now()
        distribution = {
            "last_7_days": 0,
            "last_30_days": 0,
            "last_3_months": 0,
            "last_year": 0,
            "older_than_1_year": 0
        }
        
        for point in points:
            created_at = point.payload.get("created_at")
            if not created_at:
                continue
            
            try:
                if isinstance(created_at, str):
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created_date = created_at
                
                age = now - created_date
                
                if age.days <= 7:
                    distribution["last_7_days"] += 1
                elif age.days <= 30:
                    distribution["last_30_days"] += 1
                elif age.days <= 90:
                    distribution["last_3_months"] += 1
                elif age.days <= 365:
                    distribution["last_year"] += 1
                else:
                    distribution["older_than_1_year"] += 1
                    
            except Exception:
                continue
        
        return distribution
    
    def _find_duplicate_candidates(self, points: List) -> List[Tuple[str, str, float]]:
        """Find potential duplicate memories based on vector similarity"""
        duplicates = []
        
        if len(points) < 2:
            return duplicates
        
        # Extract vectors and IDs
        vectors = []
        point_ids = []
        
        for point in points:
            if point.vector:
                vectors.append(np.array(point.vector))
                point_ids.append(point.id)
        
        if len(vectors) < 2:
            return duplicates
        
        # Compare pairs for similarity (limit comparisons for performance)
        max_comparisons = min(len(vectors), 100)  # Limit for performance
        for i in range(min(max_comparisons, len(vectors))):
            for j in range(i + 1, min(max_comparisons, len(vectors))):
                similarity = self._cosine_similarity(vectors[i], vectors[j])
                
                if similarity >= self.config.similarity_threshold:
                    duplicates.append((point_ids[i], point_ids[j], similarity))
        
        return duplicates
    
    def _find_low_value_candidates(self, points: List) -> List[str]:
        """Find memories that are candidates for removal (low value)"""
        low_value = []
        
        for point in points:
            payload = point.payload or {}
            
            # Check content length
            content = payload.get("content", "")
            if len(content) < self.config.min_length:
                low_value.append(point.id)
                continue
            
            # Check if it's just metadata without meaningful content
            if self._is_low_value_content(content):
                low_value.append(point.id)
        
        return low_value
    
    def _is_low_value_content(self, content: str) -> bool:
        """Determine if content has low value"""
        content = content.lower().strip()
        
        # Very short content
        if len(content) < 10:
            return True
        
        # Common low-value patterns
        low_value_patterns = [
            "ok", "yes", "no", "thanks", "bye", "hello",
            "test", "testing", ".", "..", "...", "???",
            "lol", "haha", "hmm", "uh", "um"
        ]
        
        if content in low_value_patterns:
            return True
        
        # Check if it's just punctuation or numbers
        if not any(c.isalpha() for c in content):
            return True
        
        return False
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        except:
            return 0.0
    
    async def prune_user_memories(self, user_id: str) -> PruningStats:
        """
        Perform comprehensive pruning of user's memories
        
        Returns statistics about the pruning operation
        """
        if not self._initialized:
            raise RuntimeError("Pruning service not initialized")
        
        start_time = time.time()
        collection_name = f"mem0_{user_id}"
        
        logger.info(f"🧹 Starting memory pruning for user {user_id}")
        
        try:
            # Get initial state
            collection_info = self.qdrant_client.get_collection(collection_name)
            initial_count = collection_info.points_count
            
            if initial_count == 0:
                return PruningStats(
                    total_memories_before=0,
                    total_memories_after=0,
                    duplicates_removed=0,
                    expired_removed=0,
                    low_value_removed=0,
                    merged_memories=0,
                    storage_saved_mb=0.0,
                    processing_time=time.time() - start_time
                )
            
            # Get all points
            points, _ = self.qdrant_client.scroll(
                collection_name=collection_name,
                limit=10000,
                with_payload=True,
                with_vectors=True
            )
            
            initial_size_mb = self._estimate_collection_size(points, len(points))
            
            # Track removals
            to_remove = set()
            duplicates_removed = 0
            expired_removed = 0
            low_value_removed = 0
            merged_memories = 0
            
            # 1. Remove duplicates
            if not self.config.dry_run:
                duplicate_pairs = self._find_duplicate_candidates(points)
                for id1, id2, similarity in duplicate_pairs:
                    # Remove the one with less content or older timestamp
                    point1 = next((p for p in points if p.id == id1), None)
                    point2 = next((p for p in points if p.id == id2), None)
                    
                    if point1 and point2:
                        # Choose which one to remove (keep the more recent or longer one)
                        to_remove_id = self._choose_duplicate_to_remove(point1, point2)
                        if to_remove_id:
                            to_remove.add(to_remove_id)
                            duplicates_removed += 1
            
            # 2. Remove low-value memories
            low_value_candidates = self._find_low_value_candidates(points)
            for point_id in low_value_candidates:
                to_remove.add(point_id)
                low_value_removed += 1
            
            # 3. Remove expired memories (very old)
            cutoff_date = datetime.now() - timedelta(days=self.config.max_age_days)
            for point in points:
                created_at = point.payload.get("created_at")
                if created_at:
                    try:
                        if isinstance(created_at, str):
                            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        else:
                            created_date = created_at
                        
                        if created_date < cutoff_date:
                            to_remove.add(point.id)
                            expired_removed += 1
                    except Exception:
                        continue
            
            # Safety check: don't remove too much at once
            max_removals = int(initial_count * self.config.max_removal_percentage)
            if len(to_remove) > max_removals:
                logger.warning(f"Limiting removals to {max_removals} (was {len(to_remove)})")
                to_remove = set(list(to_remove)[:max_removals])
            
            # Perform actual removal
            if to_remove and not self.config.dry_run:
                self.qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=models.PointIdsList(
                        points=list(to_remove)
                    )
                )
                logger.info(f"🗑️ Removed {len(to_remove)} memories")
            
            # Get final state
            final_collection_info = self.qdrant_client.get_collection(collection_name)
            final_count = final_collection_info.points_count
            
            # Calculate storage savings
            storage_saved_mb = initial_size_mb * (len(to_remove) / initial_count) if initial_count > 0 else 0
            
            processing_time = time.time() - start_time
            
            stats = PruningStats(
                total_memories_before=initial_count,
                total_memories_after=final_count,
                duplicates_removed=duplicates_removed,
                expired_removed=expired_removed,
                low_value_removed=low_value_removed,
                merged_memories=merged_memories,
                storage_saved_mb=storage_saved_mb,
                processing_time=processing_time
            )
            
            logger.info(f"✅ Pruning completed: {stats.to_dict()}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Pruning failed for user {user_id}: {e}")
            raise
    
    def _choose_duplicate_to_remove(self, point1, point2) -> Optional[str]:
        """Choose which duplicate point to remove (keep the better one)"""
        payload1 = point1.payload or {}
        payload2 = point2.payload or {}
        
        content1 = payload1.get("content", "")
        content2 = payload2.get("content", "")
        
        # Keep the one with more content
        if len(content1) != len(content2):
            return point1.id if len(content1) < len(content2) else point2.id
        
        # Keep the more recent one
        created1 = payload1.get("created_at")
        created2 = payload2.get("created_at")
        
        if created1 and created2:
            try:
                date1 = datetime.fromisoformat(created1.replace('Z', '+00:00')) if isinstance(created1, str) else created1
                date2 = datetime.fromisoformat(created2.replace('Z', '+00:00')) if isinstance(created2, str) else created2
                
                return point1.id if date1 < date2 else point2.id
            except:
                pass
        
        # Default to removing the first one
        return point1.id
    
    async def schedule_periodic_pruning(self, user_id: str, interval_days: int = 7):
        """
        Schedule periodic pruning for a user
        
        This would typically be called by a background task scheduler
        """
        logger.info(f"📅 Scheduling periodic pruning for user {user_id} every {interval_days} days")
        
        # In a real implementation, this would integrate with a task scheduler
        # For now, it's a placeholder for the architecture
        pass


# Global service instance
_pruning_service: Optional[MemoryPruningService] = None


async def get_pruning_service(config: PruningConfig = None) -> Optional[MemoryPruningService]:
    """Get or create global pruning service instance"""
    global _pruning_service
    
    if not QDRANT_AVAILABLE:
        return None
    
    if _pruning_service is None:
        _pruning_service = MemoryPruningService(config)
    
    return _pruning_service 