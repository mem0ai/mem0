import psutil
import os
import gc
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config.memory_limits import MEMORY_LIMITS

logger = logging.getLogger(__name__)

class MemoryMonitorMiddleware(BaseHTTPMiddleware):
    """Middleware to monitor memory usage and prevent OOM crashes"""
    
    async def dispatch(self, request: Request, call_next):
        # Check memory before processing request
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_usage_mb = memory_info.rss / 1024 / 1024  # Convert to MB
            
            # Log high memory usage
            if memory_usage_mb > MEMORY_LIMITS.gc_threshold_mb:
                logger.warning(f"High memory usage detected: {memory_usage_mb:.2f}MB")
                # Force garbage collection
                gc.collect()
                # Check memory again after GC
                memory_info = process.memory_info()
                memory_usage_mb_after_gc = memory_info.rss / 1024 / 1024
                logger.info(f"Memory after GC: {memory_usage_mb_after_gc:.2f}MB (freed {memory_usage_mb - memory_usage_mb_after_gc:.2f}MB)")
            
            # Critical memory check
            if memory_usage_mb > MEMORY_LIMITS.max_memory_usage_mb:
                logger.error(f"Critical memory usage: {memory_usage_mb:.2f}MB - refusing new requests")
                # Return 503 Service Unavailable to prevent crash
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Service temporarily unavailable due to high memory usage",
                        "message": "Please try again in a few moments"
                    }
                )
        except ImportError:
            # psutil not available, skip monitoring
            pass
        except Exception as e:
            logger.error(f"Error in memory monitoring: {e}")
        
        # Process request
        response = await call_next(request)
        
        # Check memory after request
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_usage_mb = memory_info.rss / 1024 / 1024
            
            # Add memory usage to response headers for monitoring
            response.headers["X-Memory-Usage-MB"] = f"{memory_usage_mb:.2f}"
            
        except Exception:
            pass
        
        return response 