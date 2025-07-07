#!/usr/bin/env python3
"""
Jean Memory V2 - FastAPI Integration Example
============================================

This example shows how to integrate Jean Memory V2 with existing FastAPI routes
to enhance them with V2 capabilities while maintaining backward compatibility.
"""

import asyncio
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any

from jean_memory_v2.api_adapter import JeanMemoryV2ApiAdapter, create_v2_adapter_from_env
from jean_memory_v2.exceptions import JeanMemoryError, SearchError, IngestionError

# Initialize FastAPI app
app = FastAPI(title="Jean Memory V2 API Integration Example")

# Global V2 adapter instance
v2_adapter: Optional[JeanMemoryV2ApiAdapter] = None


# Request/Response models
class CreateMemoryRequest(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = None
    app_name: str = "jean_memory_v2"


class SearchMemoriesRequest(BaseModel):
    query: str
    limit: Optional[int] = 20
    include_synthesis: bool = True


class DeepQueryRequest(BaseModel):
    query: str
    context_limit: Optional[int] = 50


# Startup event to initialize V2 adapter
@app.on_event("startup")
async def startup_event():
    global v2_adapter
    try:
        # Initialize V2 adapter from environment file
        v2_adapter = create_v2_adapter_from_env("openmemory/api/.env.test")
        await v2_adapter.initialize()
        print("🚀 V2 API Adapter initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize V2 adapter: {e}")
        # You could fall back to V1 only here


# Shutdown event to clean up resources
@app.on_event("shutdown")
async def shutdown_event():
    global v2_adapter
    if v2_adapter:
        await v2_adapter.close()
        print("🧹 V2 API Adapter closed")


# Dependency to get V2 adapter
async def get_v2_adapter() -> JeanMemoryV2ApiAdapter:
    if not v2_adapter:
        raise HTTPException(status_code=503, detail="V2 adapter not available")
    return v2_adapter


# Enhanced V2 Routes
@app.post("/api/v2/memories/")
async def create_memory_v2(
    user_id: str,
    request: CreateMemoryRequest,
    adapter: JeanMemoryV2ApiAdapter = Depends(get_v2_adapter)
):
    """Enhanced memory creation with V2 capabilities"""
    try:
        result = await adapter.create_memory_v2(
            user_id=user_id,
            text=request.text,
            metadata=request.metadata,
            app_name=request.app_name
        )
        return result
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.post("/api/v2/memories/search/")
async def search_memories_v2(
    user_id: str,
    request: SearchMemoriesRequest,
    adapter: JeanMemoryV2ApiAdapter = Depends(get_v2_adapter)
):
    """Enhanced memory search with V2 hybrid capabilities"""
    try:
        result = await adapter.search_memories_v2(
            user_id=user_id,
            query=request.query,
            limit=request.limit,
            include_synthesis=request.include_synthesis
        )
        return result
    except SearchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.post("/api/v2/memories/deep-query/")
async def deep_life_query_v2(
    user_id: str,
    request: DeepQueryRequest,
    adapter: JeanMemoryV2ApiAdapter = Depends(get_v2_adapter)
):
    """Enhanced deep life query with V2 AI synthesis"""
    try:
        result = await adapter.deep_life_query_v2(
            user_id=user_id,
            query=request.query,
            context_limit=request.context_limit
        )
        return result
    except SearchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/api/v2/memories/narrative/")
async def get_life_narrative_v2(
    user_id: str,
    adapter: JeanMemoryV2ApiAdapter = Depends(get_v2_adapter)
):
    """Generate comprehensive life narrative using V2 capabilities"""
    try:
        result = await adapter.get_life_narrative_v2(user_id=user_id)
        return result
    except SearchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/api/v2/users/{user_id}/stats/")
async def get_user_stats_v2(
    user_id: str,
    adapter: JeanMemoryV2ApiAdapter = Depends(get_v2_adapter)
):
    """Get comprehensive user statistics with V2 enhancements"""
    try:
        result = await adapter.get_user_stats_v2(user_id=user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/api/v2/health/")
async def health_check_v2(
    adapter: JeanMemoryV2ApiAdapter = Depends(get_v2_adapter)
):
    """Comprehensive health check including V2 systems"""
    try:
        result = await adapter.health_check_v2()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")


# Backward Compatible V1 Routes (Enhanced with V2)
@app.post("/api/v1/memories/")
async def create_memory_v1_enhanced(
    user_id: str,
    request: CreateMemoryRequest,
    adapter: JeanMemoryV2ApiAdapter = Depends(get_v2_adapter)
):
    """V1 route enhanced with V2 capabilities (backward compatible)"""
    try:
        result = await adapter.create_memory_v2(
            user_id=user_id,
            text=request.text,
            metadata=request.metadata,
            app_name=request.app_name
        )
        
        # Return V1-compatible response (hide V2 details)
        return {
            "status": result["status"],
            "memory_id": result["memory_id"],
            "message": result["message"]
        }
        
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.post("/api/v1/memories/search/")
async def search_memories_v1_enhanced(
    user_id: str,
    request: SearchMemoriesRequest,
    adapter: JeanMemoryV2ApiAdapter = Depends(get_v2_adapter)
):
    """V1 search route enhanced with V2 capabilities (backward compatible)"""
    try:
        result = await adapter.search_memories_v2(
            user_id=user_id,
            query=request.query,
            limit=request.limit,
            include_synthesis=False  # V1 compatibility - no synthesis
        )
        
        # Return V1-compatible response
        return {
            "results": result["results"],
            "total": result["total"],
            "query": result["query"]
        }
        
    except SearchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# Example of gradual migration route
@app.post("/api/v1/memories/search/enhanced/")
async def search_memories_v1_with_v2_features(
    user_id: str,
    request: SearchMemoriesRequest,
    adapter: JeanMemoryV2ApiAdapter = Depends(get_v2_adapter)
):
    """V1 route with optional V2 features for gradual migration"""
    try:
        result = await adapter.search_memories_v2(
            user_id=user_id,
            query=request.query,
            limit=request.limit,
            include_synthesis=request.include_synthesis
        )
        
        # Return enhanced response with optional V2 features
        response = {
            "results": result["results"],
            "total": result["total"],
            "query": result["query"],
            "processing_time": result.get("processing_time")
        }
        
        # Include V2 enhancements if synthesis was requested
        if request.include_synthesis and "v2_enhancements" in result:
            response["ai_synthesis"] = result["v2_enhancements"].get("synthesis")
            response["confidence_score"] = result["v2_enhancements"].get("confidence_score")
        
        return response
        
    except SearchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# Example client code
async def example_client_usage():
    """Example of how to use the enhanced API endpoints"""
    import httpx
    
    base_url = "http://localhost:8000"
    user_id = "example_user_123"
    
    async with httpx.AsyncClient() as client:
        # Create a memory using V2 enhanced endpoint
        create_response = await client.post(
            f"{base_url}/api/v2/memories/",
            params={"user_id": user_id},
            json={
                "text": "I learned to play guitar last summer",
                "metadata": {"category": "hobby", "year": 2023}
            }
        )
        print(f"Memory created: {create_response.json()}")
        
        # Search with V2 AI synthesis
        search_response = await client.post(
            f"{base_url}/api/v2/memories/search/",
            params={"user_id": user_id},
            json={
                "query": "What musical instruments do I play?",
                "include_synthesis": True
            }
        )
        print(f"Search results: {search_response.json()}")
        
        # Deep life query
        deep_query_response = await client.post(
            f"{base_url}/api/v2/memories/deep-query/",
            params={"user_id": user_id},
            json={
                "query": "How have my hobbies evolved over time?"
            }
        )
        print(f"Deep analysis: {deep_query_response.json()}")


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Jean Memory V2 API Integration Example")
    print("📚 Available endpoints:")
    print("   POST /api/v2/memories/ - Enhanced memory creation")
    print("   POST /api/v2/memories/search/ - Hybrid search with AI synthesis")
    print("   POST /api/v2/memories/deep-query/ - Deep life query analysis")
    print("   GET  /api/v2/memories/narrative/ - Life narrative generation")
    print("   GET  /api/v2/health/ - Comprehensive health check")
    print("   POST /api/v1/memories/ - V1 compatible (V2 enhanced)")
    print("   POST /api/v1/memories/search/ - V1 compatible search")
    
    uvicorn.run(app, host="0.0.0.0", port=8000) 