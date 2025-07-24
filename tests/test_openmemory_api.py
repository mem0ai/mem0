import requests

BASE_URL = "http://24gatel.eu:8765"  # nebo http://localhost:8765

def test_docs_endpoint():
    resp = requests.get(f"{BASE_URL}/docs")
    assert resp.status_code == 200
    assert "Swagger UI" in resp.text

def test_openapi_json():
    resp = requests.get(f"{BASE_URL}/openapi.json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "paths" in resp.json() 