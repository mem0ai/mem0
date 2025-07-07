"""
Jean Memory V2 Exceptions
========================

Custom exception classes for better error handling and debugging.
"""


class JeanMemoryError(Exception):
    """Base exception for all Jean Memory V2 errors"""
    pass


class ConfigurationError(JeanMemoryError):
    """Raised when there are configuration issues"""
    pass


class IngestionError(JeanMemoryError):
    """Raised when memory ingestion fails"""
    pass


class SearchError(JeanMemoryError):
    """Raised when search operations fail"""
    pass


class DatabaseConnectionError(JeanMemoryError):
    """Raised when database connections fail"""
    pass


class AuthenticationError(JeanMemoryError):
    """Raised when API key authentication fails"""
    pass


class ValidationError(JeanMemoryError):
    """Raised when input validation fails"""
    pass 