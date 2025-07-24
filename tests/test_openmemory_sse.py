import requests

BASE_URL = "http://24gatel.eu:8765"
SSE_URL = f"{BASE_URL}/mcp/cursor/sse/testuser"

def test_sse_stream():
    with requests.get(SSE_URL, stream=True, timeout=10) as resp:
        assert resp.status_code == 200
        first_chunk = next(resp.iter_lines(), None)
        assert first_chunk is not None 