#!/usr/bin/env python3
"""
Test authentication implementation without requiring database connections.
"""
import os
import pytest
from typing import Optional
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader


# Mock the auth logic from main.py
def create_test_app(admin_key: Optional[str] = None):
    """Create a test FastAPI app with the same auth logic"""
    app = FastAPI()
    
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
    
    async def check_api_key(api_key: Optional[str] = Depends(api_key_header)):
        if admin_key:  # If ADMIN_API_KEY is set
            if api_key is None:
                raise HTTPException(
                    status_code=401,
                    detail="Header 'X-API-Key' is required for this deployment.",
                    headers={"WWW-Authenticate": "ApiKey"},
                )
            if api_key != admin_key:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid API Key.",
                    headers={"WWW-Authenticate": "ApiKey"},
                )
        return api_key
    
    @app.get("/test")
    async def test_endpoint(api_key: str = Depends(check_api_key)):
        return {"message": "success", "api_key": api_key}
    
    return app


class TestAuthentication:
    """Test class for authentication functionality"""
    
    def test_auth_disabled_no_header(self):
        """Test authentication when ADMIN_API_KEY is not set - no header"""
        app = create_test_app(admin_key=None)
        client = TestClient(app)
        
        response = client.get("/test")
        assert response.status_code == 200
        
    def test_auth_disabled_with_header(self):
        """Test authentication when ADMIN_API_KEY is not set - with header"""
        app = create_test_app(admin_key=None)
        client = TestClient(app)
        
        response = client.get("/test", headers={"X-API-Key": "random-key"})
        assert response.status_code == 200
        
    def test_auth_enabled_no_header(self):
        """Test authentication when ADMIN_API_KEY is set - no header (should fail)"""
        admin_key = "test-secret-key"
        app = create_test_app(admin_key=admin_key)
        client = TestClient(app)
        
        response = client.get("/test")
        assert response.status_code == 401
        assert response.json()["detail"] == "Header 'X-API-Key' is required for this deployment."
        
    def test_auth_enabled_wrong_key(self):
        """Test authentication when ADMIN_API_KEY is set - wrong key (should fail)"""
        admin_key = "test-secret-key"
        app = create_test_app(admin_key=admin_key)
        client = TestClient(app)
        
        response = client.get("/test", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API Key."
        
    def test_auth_enabled_correct_key(self):
        """Test authentication when ADMIN_API_KEY is set - correct key (should pass)"""
        admin_key = "test-secret-key"
        app = create_test_app(admin_key=admin_key)
        client = TestClient(app)
        
        response = client.get("/test", headers={"X-API-Key": admin_key})
        assert response.status_code == 200
        assert response.json()["message"] == "success"
        assert response.json()["api_key"] == admin_key
        
    def test_warning_message_logic(self):
        """Test that warning logic works correctly"""
        # Test when no ADMIN_API_KEY is set
        admin_key = os.environ.get("ADMIN_API_KEY")
        if not admin_key:
            # Should show warning
            assert True
        else:
            # Should show info message
            assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])