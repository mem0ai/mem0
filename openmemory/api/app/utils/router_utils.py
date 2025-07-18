"""
Common utilities for FastAPI routers.
Standardizes error handling, authentication patterns, and response formatting.
"""

import logging
from typing import Any, Dict, Optional, Union
from functools import wraps

from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from gotrue.types import User as SupabaseUser

from app.auth import get_current_supa_user
from app.database import get_db
from app.utils.db import get_or_create_user, get_user_and_app
from app.utils.error_handlers import (
    StandardError, format_error_response, log_error,
    convert_to_http_exception
)

logger = logging.getLogger(__name__)


class RouterDependencies:
    """Common dependency injection for routers."""
    
    @staticmethod
    def get_authenticated_user_and_db():
        """Get authenticated user and database session."""
        def dependency(
            current_supa_user: SupabaseUser = Depends(get_current_supa_user),
            db: Session = Depends(get_db)
        ):
            return current_supa_user, db
        return dependency
    
    @staticmethod
    def get_user_context():
        """Get user context with database user object."""
        def dependency(
            current_supa_user: SupabaseUser = Depends(get_current_supa_user),
            db: Session = Depends(get_db)
        ):
            user = get_or_create_user(
                db, 
                str(current_supa_user.id), 
                current_supa_user.email
            )
            return user, db, current_supa_user
        return dependency


class StandardResponses:
    """Standard response formatters for common scenarios."""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success") -> Dict[str, Any]:
        """Format success response."""
        response = {"status": "success", "message": message}
        if data is not None:
            response["data"] = data
        return response
    
    @staticmethod
    def error(message: str, code: str = "ERROR", details: Dict = None) -> Dict[str, Any]:
        """Format error response."""
        response = {
            "status": "error",
            "error": {"code": code, "message": message}
        }
        if details:
            response["error"]["details"] = details
        return response
    
    @staticmethod
    def not_found(resource: str = "Resource") -> HTTPException:
        """Standard 404 response."""
        return HTTPException(
            status_code=404,
            detail=f"{resource} not found"
        )
    
    @staticmethod
    def unauthorized(message: str = "Unauthorized access") -> HTTPException:
        """Standard 401 response."""
        return HTTPException(
            status_code=401,
            detail=message
        )
    
    @staticmethod
    def forbidden(message: str = "Access forbidden") -> HTTPException:
        """Standard 403 response."""
        return HTTPException(
            status_code=403,
            detail=message
        )
    
    @staticmethod
    def internal_error(message: str = "Internal server error") -> HTTPException:
        """Standard 500 response."""
        return HTTPException(
            status_code=500,
            detail=message
        )


def handle_router_errors(func):
    """Decorator to standardize error handling in router functions."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except StandardError as e:
            # Convert application errors to HTTP exceptions
            raise convert_to_http_exception(e)
        except Exception as e:
            # Log unexpected errors and return generic error
            log_error(e, f"router function: {func.__name__}")
            raise StandardResponses.internal_error(f"An unexpected error occurred")
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPException:
            raise
        except StandardError as e:
            raise convert_to_http_exception(e)
        except Exception as e:
            log_error(e, f"router function: {func.__name__}")
            raise StandardResponses.internal_error(f"An unexpected error occurred")
    
    # Return appropriate wrapper based on function type
    import asyncio
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def validate_user_access(user_id: str, resource_user_id: str) -> bool:
    """Validate that user has access to resource."""
    return user_id == resource_user_id


def paginate_query(query, page: int = 1, size: int = 20, max_size: int = 100):
    """Standardize query pagination."""
    # Validate pagination parameters
    page = max(1, page)
    size = min(max(1, size), max_size)
    
    # Calculate offset
    offset = (page - 1) * size
    
    # Apply pagination
    paginated_query = query.offset(offset).limit(size)
    
    return paginated_query, page, size


def format_pagination_response(
    items: list,
    total: int,
    page: int,
    size: int,
    endpoint: str = None
) -> Dict[str, Any]:
    """Format paginated response."""
    total_pages = (total + size - 1) // size  # Ceiling division
    
    response = {
        "items": items,
        "pagination": {
            "current_page": page,
            "page_size": size,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
    }
    
    if endpoint:
        response["pagination"]["links"] = {
            "self": f"{endpoint}?page={page}&size={size}",
            "next": f"{endpoint}?page={page + 1}&size={size}" if page < total_pages else None,
            "previous": f"{endpoint}?page={page - 1}&size={size}" if page > 1 else None
        }
    
    return response


class QueryOptimizer:
    """Utilities for optimizing database queries."""
    
    @staticmethod
    def add_eager_loading(query, *relationships):
        """Add eager loading for relationships to prevent N+1 queries."""
        from sqlalchemy.orm import joinedload
        
        for relationship in relationships:
            query = query.options(joinedload(relationship))
        return query
    
    @staticmethod
    def add_select_related(query, *relationships):
        """Add select related for better query performance."""
        from sqlalchemy.orm import selectinload
        
        for relationship in relationships:
            query = query.options(selectinload(relationship))
        return query


# Common validation functions
def validate_uuid(value: str, field_name: str = "ID") -> str:
    """Validate UUID format."""
    import uuid
    try:
        uuid.UUID(value)
        return value
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} format"
        )


def validate_pagination_params(page: Optional[int] = None, size: Optional[int] = None) -> tuple[int, int]:
    """Validate and normalize pagination parameters."""
    page = page or 1
    size = size or 20
    
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be >= 1")
    if size < 1 or size > 100:
        raise HTTPException(status_code=400, detail="Size must be between 1 and 100")
    
    return page, size


def require_permissions(required_permissions: list):
    """Decorator to require specific permissions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implement permission checking logic
            # For now, just pass through
            return await func(*args, **kwargs)
        return wrapper
    return decorator