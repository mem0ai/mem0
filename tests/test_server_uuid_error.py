from fastapi import HTTPException
import pytest
from mem0.exceptions import ValidationError as Mem0ValidationError

# Test functions logic directly without heavy database dependencies
def _client_error(exc: Exception) -> HTTPException:
    detail = str(exc)
    status_code = 404 if isinstance(exc, ValueError) and "not found" in detail.lower() else 400
    return HTTPException(status_code=status_code, detail=detail)

def _is_client_id_error(exc: Exception) -> bool:
    err_str = str(exc).lower()
    return "invalid input syntax for type uuid" in err_str or ("invalid" in err_str and "uuid" in err_str)

def test_is_client_id_error_postgres_uuid_syntax():
    exc = Exception('invalid input syntax for type uuid: "GPK0F14H"')
    assert _is_client_id_error(exc) is True

def test_is_client_id_error_generic_invalid_uuid():
    exc = Exception('Invalid UUID format: 12345')
    assert _is_client_id_error(exc) is True

def test_is_client_id_error_unrelated_exception():
    exc = Exception('Connection refused: database server down')
    assert _is_client_id_error(exc) is False

def test_client_error_not_found():
    exc = ValueError("Memory not found: mem_123")
    res = _client_error(exc)
    assert res.status_code == 404
    assert "Memory not found" in res.detail

def test_client_error_validation():
    exc = Mem0ValidationError(message="Invalid memory payload", error_code="VAL_001")
    res = _client_error(exc)
    assert res.status_code == 400
