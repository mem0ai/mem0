"""
Standardized error handling utilities for the application.
Provides consistent error handling patterns across all modules.
"""

import logging
import traceback
from typing import Any, Dict, Optional, Type, Union
from functools import wraps
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class StandardError(Exception):
    """Base class for application-specific errors."""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}


class MemoryError(StandardError):
    """Memory-related operation errors."""
    pass


class DatabaseError(StandardError):
    """Database operation errors."""
    pass


class ValidationError(StandardError):
    """Data validation errors."""
    pass


class AuthenticationError(StandardError):
    """Authentication-related errors."""
    pass


class APIError(StandardError):
    """External API-related errors."""
    pass


def log_error(error: Exception, context: str = None, user_id: str = None, 
              additional_info: Dict[str, Any] = None) -> None:
    """Log error with consistent format and context."""
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context,
        'user_id': user_id,
        'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
    }
    
    if additional_info:
        error_info.update(additional_info)
    
    logger.error(f"Error in {context or 'unknown context'}: {error_info}")


def handle_database_error(error: Exception, operation: str = None, 
                         user_id: str = None) -> DatabaseError:
    """Standardize database error handling."""
    context = f"database operation: {operation}" if operation else "database operation"
    log_error(error, context, user_id)
    
    return DatabaseError(
        message=f"Database operation failed: {operation or 'unknown operation'}",
        error_code="DB_ERROR",
        details={
            'original_error': str(error),
            'operation': operation,
            'user_id': user_id
        }
    )


def handle_memory_error(error: Exception, operation: str = None, 
                       user_id: str = None, memory_id: str = None) -> MemoryError:
    """Standardize memory operation error handling."""
    context = f"memory operation: {operation}" if operation else "memory operation"
    log_error(error, context, user_id, {'memory_id': memory_id})
    
    return MemoryError(
        message=f"Memory operation failed: {operation or 'unknown operation'}",
        error_code="MEMORY_ERROR",
        details={
            'original_error': str(error),
            'operation': operation,
            'user_id': user_id,
            'memory_id': memory_id
        }
    )


def handle_api_error(error: Exception, service: str = None, 
                    user_id: str = None) -> APIError:
    """Standardize external API error handling."""
    context = f"API call to {service}" if service else "API call"
    log_error(error, context, user_id)
    
    return APIError(
        message=f"External API call failed: {service or 'unknown service'}",
        error_code="API_ERROR",
        details={
            'original_error': str(error),
            'service': service,
            'user_id': user_id
        }
    )


def safe_execute(func, *args, error_handler=None, context: str = None, 
                user_id: str = None, **kwargs):
    """Safely execute a function with standardized error handling."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if error_handler:
            raise error_handler(e, context, user_id)
        else:
            log_error(e, context, user_id)
            raise


def with_error_handling(error_type: Type[StandardError] = StandardError,
                       context: str = None,
                       log_errors: bool = True):
    """Decorator for standardized error handling."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    log_error(e, context or f"function: {func.__name__}")
                raise error_type(
                    message=f"Error in {func.__name__}: {str(e)}",
                    error_code=f"{func.__name__.upper()}_ERROR",
                    details={'original_error': str(e)}
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    log_error(e, context or f"function: {func.__name__}")
                raise error_type(
                    message=f"Error in {func.__name__}: {str(e)}",
                    error_code=f"{func.__name__.upper()}_ERROR",
                    details={'original_error': str(e)}
                )
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def convert_to_http_exception(error: StandardError) -> HTTPException:
    """Convert application errors to HTTP exceptions."""
    status_code_map = {
        'ValidationError': 400,
        'AuthenticationError': 401,
        'MemoryError': 404,
        'DatabaseError': 500,
        'APIError': 502
    }
    
    status_code = status_code_map.get(error.__class__.__name__, 500)
    
    return HTTPException(
        status_code=status_code,
        detail={
            'message': error.message,
            'error_code': error.error_code,
            'details': error.details
        }
    )


def format_error_response(error: Exception, include_details: bool = False) -> Dict[str, Any]:
    """Format error for API response."""
    if isinstance(error, StandardError):
        response = {
            'error': error.error_code,
            'message': error.message
        }
        if include_details:
            response['details'] = error.details
        return response
    else:
        return {
            'error': 'UNKNOWN_ERROR',
            'message': str(error),
            'details': {'type': type(error).__name__} if include_details else {}
        }


# Import asyncio for decorator
import asyncio